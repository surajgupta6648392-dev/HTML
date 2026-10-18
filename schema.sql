PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('librarian', 'student'))
);

CREATE TABLE IF NOT EXISTS books (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    title              TEXT NOT NULL,
    author             TEXT NOT NULL,
    isbn               TEXT NOT NULL UNIQUE,
    category           TEXT,
    publisher          TEXT,
    quantity           INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 0),
    available_quantity INTEGER NOT NULL DEFAULT 1 CHECK (available_quantity >= 0)
);

CREATE TABLE IF NOT EXISTS students (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    email             TEXT NOT NULL,
    phone             TEXT,
    department        TEXT,
    registration_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS issued_books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id     INTEGER NOT NULL REFERENCES books(id),
    student_id  INTEGER NOT NULL REFERENCES students(id),
    issue_date  TEXT NOT NULL,
    due_date    TEXT NOT NULL,
    return_date TEXT,
    status      TEXT NOT NULL DEFAULT 'issued'
                CHECK (status IN ('issued', 'returned', 'overdue'))
);

CREATE TABLE IF NOT EXISTS fines (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     INTEGER NOT NULL REFERENCES students(id),
    issue_id       INTEGER NOT NULL UNIQUE REFERENCES issued_books(id),
    amount         REAL NOT NULL CHECK (amount >= 0),
    payment_status TEXT NOT NULL DEFAULT 'unpaid'
                   CHECK (payment_status IN ('unpaid', 'paid')),
    created_date   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issued_book    ON issued_books(book_id);
CREATE INDEX IF NOT EXISTS idx_issued_student ON issued_books(student_id);
CREATE INDEX IF NOT EXISTS idx_issued_status  ON issued_books(status);
CREATE INDEX IF NOT EXISTS idx_fines_student  ON fines(student_id);
