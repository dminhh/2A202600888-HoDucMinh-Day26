import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "lab.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT    NOT NULL,
    cohort TEXT    NOT NULL,
    score  REAL    DEFAULT 0.0,
    email  TEXT
);

CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS enrollments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id  INTEGER NOT NULL,
    grade      REAL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (course_id)  REFERENCES courses(id)
);
"""

SEED_SQL = """
INSERT OR IGNORE INTO students (id, name, cohort, score, email) VALUES
    (1, 'Alice Nguyen', 'A1', 95.5, 'alice@example.com'),
    (2, 'Bob Tran',     'A1', 82.0, 'bob@example.com'),
    (3, 'Carol Le',     'B1', 90.0, 'carol@example.com'),
    (4, 'David Pham',   'B1', 78.5, 'david@example.com'),
    (5, 'Eve Hoang',    'A2', 88.0, 'eve@example.com'),
    (6, 'Frank Do',     'A2', 73.0, 'frank@example.com');

INSERT OR IGNORE INTO courses (id, name, description) VALUES
    (1, 'Python Basics',    'Introduction to Python programming'),
    (2, 'Data Structures',  'Algorithms and data structures'),
    (3, 'Machine Learning', 'ML fundamentals with scikit-learn');

INSERT OR IGNORE INTO enrollments (id, student_id, course_id, grade) VALUES
    (1, 1, 1, 98.0),
    (2, 1, 2, 92.0),
    (3, 2, 1, 85.0),
    (4, 3, 2, 88.0),
    (5, 3, 3, 93.0),
    (6, 4, 1, 79.0),
    (7, 5, 2, 87.0),
    (8, 5, 3, 89.0),
    (9, 6, 1, 74.0);
"""


def create_database(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.executescript(SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


if __name__ == "__main__":
    path = create_database()
    print(f"Database created at: {path}")
