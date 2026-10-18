# Library Management System

A complete, fully functional Library Management System built with **Python Flask**,
**SQLite**, and **Bootstrap 5**. It includes a librarian admin panel and a student
portal with real database-backed issue/return transactions and automatic fine
calculation.

## Features

**Librarian panel**
- Secure login/logout (hashed passwords)
- Dashboard: total copies/titles, registered students, books issued, overdue count, unpaid fines, recent activity
- Full book CRUD (add / edit / delete) with validation (unique ISBN, quantity guards)
- Student record management (view / search / edit / delete)
- Issue books to students (validates availability, blocks duplicate active issues)
- Record returns with **automatic overdue fine calculation** (₹5/day, configurable)
- Search books by title, author, ISBN or category
- Complete issue & return history with filters
- Fine management (view, mark as paid) and reports page (most issued books, fines collected/outstanding, overdue list, collection by category)

**Student panel**
- Self-registration + login
- Browse & search available books
- Dashboard with currently issued books, due dates, overdue count, unpaid fines
- Borrowing history and fine details (students see **only their own** records)

**Business rules enforced**
- Cannot issue a book with 0 available copies
- Issuing decrements `available_quantity`; returning increments it
- Overdue fine = days late × `DAILY_FINE_RATE`
- No duplicate active issue of the same book to the same student
- Role-based access: only librarians manage books/transactions

## Project structure

```
library-management-system/
├── app.py                 # Flask app: routes, auth, business logic
├── config.py              # SECRET_KEY, DATABASE_PATH, DAILY_FINE_RATE, LOAN_PERIOD_DAYS
├── schema.sql             # SQLite schema (users, books, students, issued_books, fines)
├── seed.py                # Sample data: librarian, 12 books, 3 students, demo transactions
├── requirements.txt
├── README.md
├── .gitignore
├── templates/             # Jinja2 pages (base layout, auth, dashboards, CRUD, reports…)
└── static/
    ├── css/style.css
    └── js/main.js
```

## Setup & run

```bash
cd library-management-system

# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create the database and load sample data (first run only)
python seed.py                  # use --reset to wipe and reseed

# 4. Run the app
flask run                       # or: python app.py
```

Open http://127.0.0.1:5000 in your browser.

## Default credentials

| Role      | Email              | Password   |
|-----------|--------------------|------------|
| Librarian | admin@library.com  | admin123   |
| Student   | aarav@library.com  | student123 |
| Student   | diya@library.com   | student123 |
| Student   | kabir@library.com  | student123 |

The seed data includes one **overdue** issue (Diya's *Sapiens*) and one
**late return with a recorded fine** (Kabir's *The Great Gatsby*) so you can
see the fines flow immediately.

## Configuration

Edit `config.py`:
- `DAILY_FINE_RATE` – fine charged per overdue day (default ₹5.0)
- `LOAN_PERIOD_DAYS` – standard loan period (default 14 days)

## Notes

- Passwords are hashed with Werkzeug's `generate_password_hash`.
- SQLite foreign keys are enforced (`PRAGMA foreign_keys = ON`).
- The database file `library.db` is created in the project root on first run
  and is git-ignored.
