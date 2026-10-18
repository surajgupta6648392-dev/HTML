"""
Seed the database with sample data.

Usage:
    python seed.py            # create tables (if needed) + insert sample data
    python seed.py --reset    # drop everything and reseed from scratch

Default credentials created:
    Librarian: admin@library.com / admin123
    Students:  aarav@library.com / student123
               diya@library.com  / student123
               kabir@library.com / student123
"""
import os
import sqlite3
import sys
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

import config
from app import init_db

DB = config.DATABASE_PATH

BOOKS = [
    ("The Great Gatsby", "F. Scott Fitzgerald", "9780743273565", "Fiction",
     "Scribner", 5),
    ("To Kill a Mockingbird", "Harper Lee", "9780061120084", "Fiction",
     "Harper Perennial", 4),
    ("1984", "George Orwell", "9780451524935", "Fiction",
     "Signet Classic", 6),
    ("A Brief History of Time", "Stephen Hawking", "9780553380163",
     "Science", "Bantam", 3),
    ("The Selfish Gene", "Richard Dawkins", "9780199291151", "Science",
     "Oxford University Press", 2),
    ("Clean Code", "Robert C. Martin", "9780132350884", "Technology",
     "Prentice Hall", 4),
    ("Introduction to Algorithms", "Thomas H. Cormen", "9780262033848",
     "Technology", "MIT Press", 3),
    ("Sapiens", "Yuval Noah Harari", "9780062316097", "History",
     "Harper", 5),
    ("The Discovery of India", "Jawaharlal Nehru", "9780143449245",
     "History", "Penguin", 2),
    ("Linear Algebra Done Right", "Sheldon Axler", "9783319110790",
     "Mathematics", "Springer", 3),
    ("Pride and Prejudice", "Jane Austen", "9780141439518", "Literature",
     "Penguin Classics", 4),
    ("Oxford English Dictionary", "Oxford University Press",
     "9780198611868", "Reference", "Oxford University Press", 2),
]

STUDENTS = [
    ("Aarav Sharma", "aarav@library.com", "9876543210", "Computer Science"),
    ("Diya Patel", "diya@library.com", "9876543211", "Physics"),
    ("Kabir Singh", "kabir@library.com", "9876543212", "Literature"),
]


def seed():
    init_db()
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    # --- librarian ---
    db.execute(
        "INSERT OR IGNORE INTO users (name, email, password_hash, role)"
        " VALUES (?, ?, ?, 'librarian')",
        ("Library Admin", "admin@library.com",
         generate_password_hash("admin123")),
    )

    # --- books ---
    for title, author, isbn, category, publisher, qty in BOOKS:
        db.execute(
            "INSERT OR IGNORE INTO books (title, author, isbn, category,"
            " publisher, quantity, available_quantity)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, author, isbn, category, publisher, qty, qty),
        )

    # --- students (+ user accounts) ---
    student_ids = []
    for name, email, phone, dept in STUDENTS:
        db.execute(
            "INSERT OR IGNORE INTO users (name, email, password_hash, role)"
            " VALUES (?, ?, ?, 'student')",
            (name, email, generate_password_hash("student123")),
        )
        user = db.execute("SELECT id FROM users WHERE email = ?",
                          (email,)).fetchone()
        db.execute(
            "INSERT OR IGNORE INTO students (user_id, name, email, phone,"
            " department, registration_date) VALUES (?, ?, ?, ?, ?, ?)",
            (user["id"], name, email, phone, dept, date.today().isoformat()),
        )
        st = db.execute("SELECT id FROM students WHERE user_id = ?",
                        (user["id"],)).fetchone()
        student_ids.append(st["id"])

    db.commit()

    # --- sample transactions ---
    # Need book ids for a few titles
    def book_id(isbn):
        return db.execute("SELECT id FROM books WHERE isbn = ?",
                          (isbn,)).fetchone()["id"]

    gatsby = book_id("9780743273565")
    clean = book_id("9780132350884")
    sapiens = book_id("9780062316097")

    def issue(book, student, issued_days_ago, loan_days=14,
              returned_days_ago=None):
        """Create an issue record and keep available_quantity in sync."""
        issue_d = date.today() - timedelta(days=issued_days_ago)
        due_d = issue_d + timedelta(days=loan_days)
        status = "issued"
        ret = None
        if returned_days_ago is not None:
            ret = (date.today() - timedelta(days=returned_days_ago)).isoformat()
            status = "returned"
            if date.fromisoformat(ret) > due_d:
                status = "returned"  # fine recorded below
        elif due_d < date.today():
            status = "overdue"
        db.execute(
            "INSERT INTO issued_books (book_id, student_id, issue_date,"
            " due_date, return_date, status) VALUES (?, ?, ?, ?, ?, ?)",
            (book, student, issue_d.isoformat(), due_d.isoformat(),
             ret, status),
        )
        issue_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        if status != "returned":
            # book is still out: one fewer copy available
            db.execute(
                "UPDATE books SET available_quantity = available_quantity - 1"
                " WHERE id = ?", (book,))
        # (returned books were never decremented, so nothing to restore)
        # fine for late returns
        if ret and date.fromisoformat(ret) > due_d:
            days_late = (date.fromisoformat(ret) - due_d).days
            amount = round(days_late * config.DAILY_FINE_RATE, 2)
            db.execute(
                "INSERT INTO fines (student_id, issue_id, amount,"
                " payment_status, created_date)"
                " VALUES (?, ?, ?, 'unpaid', ?)",
                (student, issue_id, amount, ret),
            )
        return issue_id

    # Aarav: currently has "Clean Code" (issued 5 days ago, not overdue)
    issue(clean, student_ids[0], issued_days_ago=5)
    # Diya: "Sapiens" issued 20 days ago -> overdue (due 6 days ago)
    issue(sapiens, student_ids[1], issued_days_ago=20)
    # Kabir: "The Great Gatsby" issued 30 days ago, returned 5 days ago
    # (11 days late -> fine recorded) — demos the fines flow
    issue(gatsby, student_ids[2], issued_days_ago=30, returned_days_ago=5)

    db.commit()
    db.close()
    print("Database seeded successfully.")
    print("  Librarian: admin@library.com / admin123")
    print("  Students:  aarav@library.com, diya@library.com,")
    print("             kabir@library.com (all / student123)")


if __name__ == "__main__":
    if "--reset" in sys.argv and os.path.exists(DB):
        os.remove(DB)
        print("Existing database removed.")
    seed()
