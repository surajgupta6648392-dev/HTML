"""
Library Management System
==========================
Flask + SQLite application with librarian and student panels.

Run:
    python seed.py        # create DB + sample data (first time)
    flask run             # or: python app.py
"""
import os
import sqlite3
from datetime import date, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
DATABASE = config.DATABASE_PATH


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    """Per-request SQLite connection with FK enforcement."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create all tables from schema.sql."""
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "schema.sql"), encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()
    db.close()


def today_str():
    return date.today().isoformat()


def refresh_overdue_status(db):
    """Mark issued books past their due date as 'overdue'."""
    db.execute(
        "UPDATE issued_books SET status = 'overdue' "
        "WHERE status = 'issued' AND due_date < ?",
        (today_str(),),
    )


def overdue_days(due_date):
    """Number of days past due (0 if not overdue)."""
    delta = (date.today() - date.fromisoformat(due_date)).days
    return max(delta, 0)


def fine_amount(due_date):
    """Fine for a book due on `due_date` if returned today."""
    return round(overdue_days(due_date) * config.DAILY_FINE_RATE, 2)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def current_user():
    if "user_id" not in session:
        return None
    return get_db().execute(
        "SELECT * FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()


def current_student():
    """students row for the logged-in student user (None for librarians)."""
    user = current_user()
    if not user or user["role"] != "student":
        return None
    return get_db().execute(
        "SELECT * FROM students WHERE user_id = ?", (user["id"],)
    ).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def librarian_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        if user["role"] != "librarian":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def student_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        if user["role"] != "student":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    user = current_user()
    return {
        "user": user,
        "today": today_str(),
        "fine_rate": config.DAILY_FINE_RATE,
        "loan_days": config.LOAN_PERIOD_DAYS,
    }


# ---------------------------------------------------------------------------
# Public / auth routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    user = current_user()
    if user is None:
        return redirect(url_for("login"))
    if user["role"] == "librarian":
        return redirect(url_for("dashboard"))
    return redirect(url_for("student_dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name']}!", "success")
            nxt = request.args.get("next")
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            return redirect(url_for("index"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()
        department = request.form.get("department", "").strip()

        # ---- server-side validation ----
        errors = []
        if len(name) < 2:
            errors.append("Please enter your full name.")
        if "@" not in email or "." not in email:
            errors.append("Please enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        db = get_db()
        if db.execute("SELECT id FROM users WHERE email = ?",
                      (email,)).fetchone():
            errors.append("An account with this email already exists.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html")

        db.execute(
            "INSERT INTO users (name, email, password_hash, role) "
            "VALUES (?, ?, ?, 'student')",
            (name, email, generate_password_hash(password)),
        )
        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO students (user_id, name, email, phone, department,"
            " registration_date) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, name, email, phone, department, today_str()),
        )
        db.commit()
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Librarian: dashboard
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@librarian_required
def dashboard():
    db = get_db()
    refresh_overdue_status(db)
    db.commit()
    stats = {
        "total_copies": db.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM books").fetchone()[0],
        "total_titles": db.execute(
            "SELECT COUNT(*) FROM books").fetchone()[0],
        "students": db.execute(
            "SELECT COUNT(*) FROM students").fetchone()[0],
        "issued": db.execute(
            "SELECT COUNT(*) FROM issued_books "
            "WHERE status IN ('issued','overdue')").fetchone()[0],
        "overdue": db.execute(
            "SELECT COUNT(*) FROM issued_books "
            "WHERE status = 'overdue'").fetchone()[0],
        "unpaid_fines": db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM fines "
            "WHERE payment_status = 'unpaid'").fetchone()[0],
    }
    recent = db.execute(
        "SELECT ib.*, b.title AS book_title, s.name AS student_name "
        "FROM issued_books ib "
        "JOIN books b ON b.id = ib.book_id "
        "JOIN students s ON s.id = ib.student_id "
        "ORDER BY ib.id DESC LIMIT 8"
    ).fetchall()
    return render_template("dashboard.html", stats=stats, recent=recent)


# ---------------------------------------------------------------------------
# Librarian: books CRUD + search
# ---------------------------------------------------------------------------

@app.route("/books")
@login_required
def books():
    db = get_db()
    q = request.args.get("q", "").strip()
    field = request.args.get("field", "all")
    allowed = {"title": "b.title", "author": "b.author",
               "isbn": "b.isbn", "category": "b.category"}
    sql = "SELECT b.* FROM books b"
    params = []
    if q:
        like = f"%{q}%"
        if field in allowed:
            sql += f" WHERE {allowed[field]} LIKE ?"
            params.append(like)
        else:
            sql += (" WHERE b.title LIKE ? OR b.author LIKE ? "
                    "OR b.isbn LIKE ? OR b.category LIKE ?")
            params.extend([like] * 4)
    sql += " ORDER BY b.title"
    book_list = db.execute(sql, params).fetchall()
    return render_template("books.html", books=book_list, q=q, field=field)


@app.route("/books/add", methods=["GET", "POST"])
@librarian_required
def add_book():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        isbn = request.form.get("isbn", "").strip()
        category = request.form.get("category", "").strip()
        publisher = request.form.get("publisher", "").strip()
        try:
            quantity = int(request.form.get("quantity", "1"))
        except ValueError:
            quantity = -1

        errors = []
        if not title:
            errors.append("Title is required.")
        if not author:
            errors.append("Author is required.")
        if not isbn:
            errors.append("ISBN is required.")
        if quantity < 1:
            errors.append("Quantity must be at least 1.")
        db = get_db()
        if isbn and db.execute("SELECT id FROM books WHERE isbn = ?",
                               (isbn,)).fetchone():
            errors.append("A book with this ISBN already exists.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("book_form.html", book=None)

        db.execute(
            "INSERT INTO books (title, author, isbn, category, publisher,"
            " quantity, available_quantity) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, author, isbn, category, publisher, quantity, quantity),
        )
        db.commit()
        flash(f'Book "{title}" added successfully.', "success")
        return redirect(url_for("books"))
    return render_template("book_form.html", book=None)


@app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@librarian_required
def edit_book(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id = ?",
                      (book_id,)).fetchone()
    if book is None:
        abort(404)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        isbn = request.form.get("isbn", "").strip()
        category = request.form.get("category", "").strip()
        publisher = request.form.get("publisher", "").strip()
        try:
            quantity = int(request.form.get("quantity", "1"))
        except ValueError:
            quantity = -1

        errors = []
        if not title:
            errors.append("Title is required.")
        if not author:
            errors.append("Author is required.")
        if not isbn:
            errors.append("ISBN is required.")
        if quantity < 1:
            errors.append("Quantity must be at least 1.")
        issued_out = book["quantity"] - book["available_quantity"]
        if quantity < issued_out:
            errors.append(
                f"Quantity cannot be less than the {issued_out} "
                "copy/copies currently issued.")
        if isbn != book["isbn"] and db.execute(
                "SELECT id FROM books WHERE isbn = ?", (isbn,)).fetchone():
            errors.append("A book with this ISBN already exists.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("book_form.html", book=book)

        available = quantity - issued_out
        db.execute(
            "UPDATE books SET title=?, author=?, isbn=?, category=?,"
            " publisher=?, quantity=?, available_quantity=? WHERE id=?",
            (title, author, isbn, category, publisher, quantity,
             available, book_id),
        )
        db.commit()
        flash(f'Book "{title}" updated successfully.', "success")
        return redirect(url_for("books"))
    return render_template("book_form.html", book=book)


@app.route("/books/<int:book_id>/delete", methods=["POST"])
@librarian_required
def delete_book(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id = ?",
                      (book_id,)).fetchone()
    if book is None:
        abort(404)
    refs = db.execute(
        "SELECT COUNT(*) FROM issued_books WHERE book_id = ?",
        (book_id,)).fetchone()[0]
    if refs:
        flash("Cannot delete: this book has issue/return history. "
              "Set its quantity to 0 instead.", "danger")
        return redirect(url_for("books"))
    db.execute("DELETE FROM books WHERE id = ?", (book_id,))
    db.commit()
    flash(f'Book "{book["title"]}" deleted.', "success")
    return redirect(url_for("books"))


# ---------------------------------------------------------------------------
# Librarian: student management
# ---------------------------------------------------------------------------

@app.route("/students")
@librarian_required
def students():
    db = get_db()
    q = request.args.get("q", "").strip()
    sql = ("SELECT s.*, (SELECT COUNT(*) FROM issued_books ib "
           "WHERE ib.student_id = s.id "
           "AND ib.status IN ('issued','overdue')) AS active_issues "
           "FROM students s")
    params = []
    if q:
        like = f"%{q}%"
        sql += " WHERE s.name LIKE ? OR s.email LIKE ? OR s.department LIKE ?"
        params.extend([like] * 3)
    sql += " ORDER BY s.name"
    student_list = db.execute(sql, params).fetchall()
    return render_template("students.html", students=student_list, q=q)


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@librarian_required
def edit_student(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?",
                         (student_id,)).fetchone()
    if student is None:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        department = request.form.get("department", "").strip()
        if len(name) < 2:
            flash("Please enter a valid name.", "danger")
            return render_template("student_form.html", student=student)
        db.execute("UPDATE students SET name=?, phone=?, department=? "
                   "WHERE id=?", (name, phone, department, student_id))
        db.execute("UPDATE users SET name=? WHERE id=?",
                   (name, student["user_id"]))
        db.commit()
        flash("Student record updated.", "success")
        return redirect(url_for("students"))
    return render_template("student_form.html", student=student)


@app.route("/students/<int:student_id>/delete", methods=["POST"])
@librarian_required
def delete_student(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?",
                         (student_id,)).fetchone()
    if student is None:
        abort(404)
    active = db.execute(
        "SELECT COUNT(*) FROM issued_books WHERE student_id = ? "
        "AND status IN ('issued','overdue')", (student_id,)).fetchone()[0]
    if active:
        flash("Cannot delete: student has books currently issued.", "danger")
        return redirect(url_for("students"))
    # issued_books history for this student blocks delete via FK; keep record
    hist = db.execute("SELECT COUNT(*) FROM issued_books WHERE student_id=?",
                      (student_id,)).fetchone()[0]
    if hist:
        flash("Cannot delete: student has borrowing history. "
              "Records must be retained.", "danger")
        return redirect(url_for("students"))
    db.execute("DELETE FROM users WHERE id = ?", (student["user_id"],))
    db.commit()
    flash(f'Student "{student["name"]}" deleted.', "success")
    return redirect(url_for("students"))


# ---------------------------------------------------------------------------
# Librarian: issue & return
# ---------------------------------------------------------------------------

@app.route("/issue", methods=["GET", "POST"])
@librarian_required
def issue_book():
    db = get_db()
    if request.method == "POST":
        try:
            book_id = int(request.form.get("book_id", "0"))
            student_id = int(request.form.get("student_id", "0"))
        except ValueError:
            flash("Invalid selection.", "danger")
            return redirect(url_for("issue_book"))

        book = db.execute("SELECT * FROM books WHERE id = ?",
                          (book_id,)).fetchone()
        student = db.execute("SELECT * FROM students WHERE id = ?",
                             (student_id,)).fetchone()

        # ---- business-rule validation ----
        if book is None:
            flash("Selected book does not exist.", "danger")
        elif student is None:
            flash("Selected student does not exist.", "danger")
        elif book["available_quantity"] <= 0:
            flash(f'No copies of "{book["title"]}" are currently '
                  "available.", "danger")
        elif db.execute(
                "SELECT id FROM issued_books WHERE book_id = ? "
                "AND student_id = ? AND status IN ('issued','overdue')",
                (book_id, student_id)).fetchone():
            flash("This student already has an active issue of this book.",
                  "danger")
        else:
            issue_date = date.today()
            due_date = issue_date + timedelta(days=config.LOAN_PERIOD_DAYS)
            db.execute(
                "INSERT INTO issued_books (book_id, student_id, issue_date,"
                " due_date, status) VALUES (?, ?, ?, ?, 'issued')",
                (book_id, student_id, issue_date.isoformat(),
                 due_date.isoformat()),
            )
            db.execute(
                "UPDATE books SET available_quantity = available_quantity - 1"
                " WHERE id = ?", (book_id,))
            db.commit()
            flash(f'Issued "{book["title"]}" to {student["name"]}. '
                  f"Due on {due_date.isoformat()}.", "success")
            return redirect(url_for("issue_book"))
        return redirect(url_for("issue_book"))

    books_avail = db.execute(
        "SELECT * FROM books WHERE available_quantity > 0 ORDER BY title"
    ).fetchall()
    student_list = db.execute(
        "SELECT * FROM students ORDER BY name").fetchall()
    active = db.execute(
        "SELECT ib.*, b.title AS book_title, s.name AS student_name "
        "FROM issued_books ib JOIN books b ON b.id = ib.book_id "
        "JOIN students s ON s.id = ib.student_id "
        "WHERE ib.status IN ('issued','overdue') ORDER BY ib.due_date"
    ).fetchall()
    return render_template("issue.html", books=books_avail,
                           students=student_list, active=active)


@app.route("/return/<int:issue_id>", methods=["POST"])
@librarian_required
def return_book(issue_id):
    db = get_db()
    refresh_overdue_status(db)
    issue = db.execute(
        "SELECT ib.*, b.title AS book_title, s.name AS student_name "
        "FROM issued_books ib JOIN books b ON b.id = ib.book_id "
        "JOIN students s ON s.id = ib.student_id WHERE ib.id = ?",
        (issue_id,)).fetchone()
    if issue is None:
        abort(404)
    if issue["status"] == "returned":
        flash("This book was already returned.", "warning")
        return redirect(url_for("issue_book"))

    ret = today_str()
    db.execute(
        "UPDATE issued_books SET return_date = ?, status = 'returned' "
        "WHERE id = ?", (ret, issue_id))
    db.execute(
        "UPDATE books SET available_quantity = available_quantity + 1 "
        "WHERE id = ?", (issue["book_id"],))

    # ---- automatic fine calculation ----
    amount = fine_amount(issue["due_date"])
    if amount > 0:
        db.execute(
            "INSERT INTO fines (student_id, issue_id, amount,"
            " payment_status, created_date) VALUES (?, ?, ?, 'unpaid', ?)",
            (issue["student_id"], issue_id, amount, ret))
        flash(f'Book returned {overdue_days(issue["due_date"])} day(s) late. '
              f"Fine of \u20b9{amount:.2f} recorded for "
              f'{issue["student_name"]}.', "warning")
    else:
        flash(f'"{issue["book_title"]}" returned on time. Thank you!',
              "success")
    db.commit()
    return redirect(url_for("issue_book"))


# ---------------------------------------------------------------------------
# Librarian: history, fines, reports
# ---------------------------------------------------------------------------

@app.route("/history")
@librarian_required
def history():
    db = get_db()
    refresh_overdue_status(db)
    db.commit()
    status = request.args.get("status", "all")
    q = request.args.get("q", "").strip()
    sql = ("SELECT ib.*, b.title AS book_title, s.name AS student_name "
           "FROM issued_books ib JOIN books b ON b.id = ib.book_id "
           "JOIN students s ON s.id = ib.student_id WHERE 1=1")
    params = []
    if status in ("issued", "overdue", "returned"):
        sql += " AND ib.status = ?"
        params.append(status)
    if q:
        like = f"%{q}%"
        sql += " AND (b.title LIKE ? OR s.name LIKE ?)"
        params.extend([like, like])
    sql += " ORDER BY ib.id DESC"
    rows = db.execute(sql, params).fetchall()
    return render_template("history.html", rows=rows, status=status, q=q)


@app.route("/fines")
@librarian_required
def fines():
    db = get_db()
    rows = db.execute(
        "SELECT f.*, s.name AS student_name, b.title AS book_title "
        "FROM fines f JOIN students s ON s.id = f.student_id "
        "JOIN issued_books ib ON ib.id = f.issue_id "
        "JOIN books b ON b.id = ib.book_id "
        "ORDER BY f.payment_status, f.id DESC"
    ).fetchall()
    totals = {
        "collected": db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM fines "
            "WHERE payment_status='paid'").fetchone()[0],
        "outstanding": db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM fines "
            "WHERE payment_status='unpaid'").fetchone()[0],
    }
    return render_template("fines.html", fines=rows, totals=totals)


@app.route("/fines/<int:fine_id>/pay", methods=["POST"])
@librarian_required
def pay_fine(fine_id):
    db = get_db()
    fine = db.execute("SELECT * FROM fines WHERE id = ?",
                      (fine_id,)).fetchone()
    if fine is None:
        abort(404)
    db.execute("UPDATE fines SET payment_status = 'paid' WHERE id = ?",
               (fine_id,))
    db.commit()
    flash(f"Fine of \u20b9{fine['amount']:.2f} marked as paid.", "success")
    return redirect(url_for("fines"))


@app.route("/reports")
@librarian_required
def reports():
    db = get_db()
    refresh_overdue_status(db)
    db.commit()
    popular = db.execute(
        "SELECT b.title, b.author, COUNT(ib.id) AS times_issued "
        "FROM books b LEFT JOIN issued_books ib ON ib.book_id = b.id "
        "GROUP BY b.id ORDER BY times_issued DESC LIMIT 10"
    ).fetchall()
    overdue_rows = db.execute(
        "SELECT ib.*, b.title AS book_title, s.name AS student_name "
        "FROM issued_books ib JOIN books b ON b.id = ib.book_id "
        "JOIN students s ON s.id = ib.student_id "
        "WHERE ib.status = 'overdue' ORDER BY ib.due_date"
    ).fetchall()
    overdue = [dict(r, est_fine=fine_amount(r["due_date"]))
               for r in overdue_rows]
    fine_stats = {
        "collected": db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM fines "
            "WHERE payment_status='paid'").fetchone()[0],
        "outstanding": db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM fines "
            "WHERE payment_status='unpaid'").fetchone()[0],
        "count": db.execute("SELECT COUNT(*) FROM fines").fetchone()[0],
    }
    category = db.execute(
        "SELECT category, COUNT(*) AS titles, "
        "COALESCE(SUM(quantity),0) AS copies FROM books "
        "GROUP BY category ORDER BY titles DESC"
    ).fetchall()
    return render_template("reports.html", popular=popular, overdue=overdue,
                           fine_stats=fine_stats, category=category)


# ---------------------------------------------------------------------------
# Student panel
# ---------------------------------------------------------------------------

@app.route("/student/dashboard")
@student_required
def student_dashboard():
    db = get_db()
    refresh_overdue_status(db)
    db.commit()
    st = current_student()
    active = db.execute(
        "SELECT ib.*, b.title AS book_title, b.author AS book_author "
        "FROM issued_books ib JOIN books b ON b.id = ib.book_id "
        "WHERE ib.student_id = ? AND ib.status IN ('issued','overdue') "
        "ORDER BY ib.due_date", (st["id"],)).fetchall()
    overdue_count = sum(1 for r in active if r["status"] == "overdue")
    unpaid = db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM fines WHERE student_id = ? "
        "AND payment_status = 'unpaid'", (st["id"],)).fetchone()[0]
    total_borrowed = db.execute(
        "SELECT COUNT(*) FROM issued_books WHERE student_id = ?",
        (st["id"],)).fetchone()[0]
    return render_template("student_dashboard.html", student=st,
                           active=active, overdue_count=overdue_count,
                           unpaid=unpaid, total_borrowed=total_borrowed)


@app.route("/student/books")
@student_required
def student_books():
    db = get_db()
    q = request.args.get("q", "").strip()
    field = request.args.get("field", "all")
    allowed = {"title": "title", "author": "author", "category": "category"}
    sql = "SELECT * FROM books"
    params = []
    if q:
        like = f"%{q}%"
        if field in allowed:
            sql += f" WHERE {allowed[field]} LIKE ?"
            params.append(like)
        else:
            sql += " WHERE title LIKE ? OR author LIKE ? OR category LIKE ?"
            params.extend([like] * 3)
    sql += " ORDER BY title"
    book_list = db.execute(sql, params).fetchall()
    return render_template("student_books.html", books=book_list,
                           q=q, field=field)


@app.route("/student/history")
@student_required
def student_history():
    db = get_db()
    refresh_overdue_status(db)
    db.commit()
    st = current_student()
    rows = db.execute(
        "SELECT ib.*, b.title AS book_title, b.author AS book_author "
        "FROM issued_books ib JOIN books b ON b.id = ib.book_id "
        "WHERE ib.student_id = ? ORDER BY ib.id DESC",
        (st["id"],)).fetchall()
    return render_template("student_history.html", rows=rows, student=st)


@app.route("/student/fines")
@student_required
def student_fines():
    db = get_db()
    refresh_overdue_status(db)
    db.commit()
    st = current_student()
    fine_rows = db.execute(
        "SELECT f.*, b.title AS book_title FROM fines f "
        "JOIN issued_books ib ON ib.id = f.issue_id "
        "JOIN books b ON b.id = ib.book_id "
        "WHERE f.student_id = ? ORDER BY f.id DESC",
        (st["id"],)).fetchall()
    # live estimate for currently overdue (not yet returned) books
    pending_rows = db.execute(
        "SELECT ib.*, b.title AS book_title FROM issued_books ib "
        "JOIN books b ON b.id = ib.book_id "
        "WHERE ib.student_id = ? AND ib.status = 'overdue'",
        (st["id"],)).fetchall()
    pending = [dict(r, est_fine=fine_amount(r["due_date"]))
               for r in pending_rows]
    return render_template("student_fines.html", fines=fine_rows,
                           pending=pending, student=st)


# ---------------------------------------------------------------------------

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403,
                           message="You don't have permission to view this "
                                   "page."), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404,
                           message="The page you requested was not found."
                           ), 404


if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        init_db()
        print("Database created. Run 'python seed.py' to add sample data.")
    app.run(debug=True)
