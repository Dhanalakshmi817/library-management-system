from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
from datetime import date


app = Flask(__name__)
app.secret_key = "library_secret_key_123"

DATABASE = "library.db"
MAX_EXPLORE_STOCK = 10


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # ========================================================
    # USERS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # ========================================================
    # BOOKS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT,
            isbn TEXT,
            quantity INTEGER DEFAULT 1
        )
    """)

    # ========================================================
    # STUDENTS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            course TEXT
        )
    """)

    # Add missing student columns
    cursor.execute("PRAGMA table_info(students)")
    columns = [row[1] for row in cursor.fetchall()]

    if "enrollment" not in columns:
        cursor.execute("""
            ALTER TABLE students
            ADD COLUMN enrollment TEXT
        """)

    if "department" not in columns:
        cursor.execute("""
            ALTER TABLE students
            ADD COLUMN department TEXT
        """)

    if "semester" not in columns:
        cursor.execute("""
            ALTER TABLE students
            ADD COLUMN semester TEXT
        """)

    # ========================================================
    # ISSUES
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER,
            student_id INTEGER,
            issue_date TEXT,
            return_date TEXT,
            status TEXT DEFAULT 'Issued'
        )
    """)

    # ========================================================
    # DEFAULT ADMIN
    # ========================================================

    admin = cursor.execute(
        "SELECT * FROM users WHERE username = ?",
        ("admin",)
    ).fetchone()

    if admin is None:
        cursor.execute("""
            INSERT INTO users
            (username, email, password)
            VALUES (?, ?, ?)
        """, (
            "admin",
            "admin@gmail.com",
            "admin123"
        ))

    conn.commit()
    conn.close()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return render_template("home.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE username = ?
              AND password = ?
        """, (
            username,
            password
        )).fetchone()

        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect("/dashboard")

        flash(
            "Invalid username or password!",
            "error"
        )

        return redirect("/login")

    return render_template("login.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        terms = request.form.get("terms")

        if not username or not email or not password:

            flash(
                "Please fill all the fields!",
                "error"
            )

            return redirect("/register")

        if not terms:

            flash(
                "Please accept the terms and conditions!",
                "error"
            )

            return redirect("/register")

        if password != confirm_password:

            flash(
                "Passwords do not match!",
                "error"
            )

            return redirect("/register")

        conn = get_db()

        existing_user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing_user:

            conn.close()

            flash(
                "Username already exists!",
                "error"
            )

            return redirect("/register")

        existing_email = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_email:

            conn.close()

            flash(
                "Email already registered!",
                "error"
            )

            return redirect("/register")

        conn.execute("""
            INSERT INTO users
            (username, email, password)
            VALUES (?, ?, ?)
        """, (
            username,
            email,
            password
        ))

        conn.commit()
        conn.close()

        flash(
            "Account created successfully!",
            "success"
        )

        return redirect("/login")

    return render_template("register.html")


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    enrollment = request.args.get(
        "enrollment",
        ""
    ).strip()

    conn = get_db()

    total_books = conn.execute(
        "SELECT COUNT(*) FROM books"
    ).fetchone()[0]

    total_students = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    issued_books = conn.execute(
        "SELECT COUNT(*) FROM issues WHERE status = 'Issued'"
    ).fetchone()[0]

    returned_books = conn.execute(
        "SELECT COUNT(*) FROM issues WHERE status = 'Returned'"
    ).fetchone()[0]

    student = None
    student_books = []

    if enrollment:

        student = conn.execute("""
            SELECT *
            FROM students
            WHERE enrollment = ?
        """, (
            enrollment,
        )).fetchone()

        if student:

            student_books = conn.execute("""
                SELECT
                    issues.id AS issue_id,
                    issues.issue_date,
                    books.title,
                    books.author,
                    books.category
                FROM issues
                JOIN books
                    ON issues.book_id = books.id
                WHERE issues.student_id = ?
                  AND issues.status = 'Issued'
                ORDER BY issues.id DESC
            """, (
                student["id"],
            )).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        total_books=total_books,
        total_students=total_students,
        issued_books=issued_books,
        returned_books=returned_books,
        enrollment=enrollment,
        student=student,
        student_books=student_books
    )


# ============================================================
# BOOKS - VIEW + SEARCH
# ============================================================

@app.route("/books")
def books():

    if "user_id" not in session:
        return redirect("/login")

    search = request.args.get(
        "search",
        ""
    ).strip()

    conn = get_db()

    if search:

        books = conn.execute("""
            SELECT *
            FROM books
            WHERE title LIKE ?
               OR author LIKE ?
               OR category LIKE ?
            ORDER BY id DESC
        """, (
            "%" + search + "%",
            "%" + search + "%",
            "%" + search + "%"
        )).fetchall()

    else:

        books = conn.execute("""
            SELECT *
            FROM books
            ORDER BY id DESC
        """).fetchall()

    conn.close()

    return render_template(
        "books.html",
        books=books,
        search=search
    )


# ============================================================
# ADD BOOK
# ============================================================

@app.route("/addbook", methods=["GET", "POST"])
def add_book():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        author = request.form.get(
            "author",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        quantity = request.form.get(
            "quantity",
            "1"
        ).strip()

        if not title or not author:

            flash(
                "Book title and author are required!",
                "error"
            )

            return redirect("/addbook")

        try:
            quantity = int(quantity)

            if quantity < 1:
                quantity = 1

        except ValueError:
            quantity = 1

        conn = get_db()

        conn.execute("""
            INSERT INTO books
            (title, author, category, quantity)
            VALUES (?, ?, ?, ?)
        """, (
            title,
            author,
            category,
            quantity
        ))

        conn.commit()
        conn.close()

        flash(
            "Book added successfully!",
            "success"
        )

        return redirect("/books")

    return render_template("addbook.html")


# ============================================================
# EDIT BOOK
# ============================================================

@app.route("/editbook/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    book = conn.execute("""
        SELECT *
        FROM books
        WHERE id = ?
    """, (
        book_id,
    )).fetchone()

    if book is None:

        conn.close()

        flash(
            "Book not found!",
            "error"
        )

        return redirect("/books")

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        author = request.form.get(
            "author",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        quantity = request.form.get(
            "quantity",
            "1"
        ).strip()

        if not title or not author:

            conn.close()

            flash(
                "Book title and author are required!",
                "error"
            )

            return redirect(
                "/editbook/" + str(book_id)
            )

        try:

            quantity = int(quantity)

            if quantity < 1:
                quantity = 1

        except ValueError:

            quantity = 1

        conn.execute("""
            UPDATE books
            SET title = ?,
                author = ?,
                category = ?,
                quantity = ?
            WHERE id = ?
        """, (
            title,
            author,
            category,
            quantity,
            book_id
        ))

        conn.commit()
        conn.close()

        flash(
            "Book updated successfully!",
            "success"
        )

        return redirect("/books")

    conn.close()

    return render_template(
        "editbook.html",
        book=book
    )


# ============================================================
# DELETE BOOK
# ============================================================

@app.route("/deletebook/<int:book_id>")
@app.route("/delete-book/<int:book_id>")
def delete_book(book_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    conn.execute("""
        DELETE FROM issues
        WHERE book_id = ?
    """, (
        book_id,
    ))

    conn.execute("""
        DELETE FROM books
        WHERE id = ?
    """, (
        book_id,
    ))

    conn.commit()
    conn.close()

    flash(
        "Book deleted successfully!",
        "success"
    )

    return redirect("/books")


# ============================================================
# ISSUE BOOKS
# ============================================================

@app.route("/issuebook", methods=["GET", "POST"])
@app.route("/issue-book", methods=["GET", "POST"])
def issue_book():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    if request.method == "POST":

        book_id = request.form.get("book_id")
        student_id = request.form.get("student_id")

        issue_date = request.form.get(
            "issue_date"
        ) or str(date.today())

        if not book_id or not student_id:

            conn.close()

            flash(
                "Please select book and student!",
                "error"
            )

            return redirect("/issuebook")

        # Get book
        book = conn.execute(
            "SELECT * FROM books WHERE id = ?",
            (book_id,)
        ).fetchone()

        # Get student
        student = conn.execute(
            "SELECT * FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()

        # Check book
        if book is None:

            conn.close()

            flash(
                "Book not found!",
                "error"
            )

            return redirect("/issuebook")

        # Check student
        if student is None:

            conn.close()

            flash(
                "Student not found!",
                "error"
            )

            return redirect("/issuebook")

        # ====================================================
        # CHECK STUDENT MAXIMUM 3 BOOKS
        # ====================================================

        active_count = conn.execute("""
            SELECT COUNT(*)
            FROM issues
            WHERE student_id = ?
              AND status = 'Issued'
        """, (
            student_id,
        )).fetchone()[0]

        if active_count >= 3:

            conn.close()

            flash(
                "Student already has 3 books. "
                "Cannot take another book until one book is returned.",
                "error"
            )

            return redirect("/issuebook")

        # ====================================================
        # CHECK BOOK AVAILABILITY
        # ====================================================

        if book["quantity"] <= 0:

            conn.close()

            flash(
                "Book is not available!",
                "error"
            )

            return redirect("/issuebook")

        # ====================================================
        # INSERT ISSUE
        # ====================================================

        conn.execute("""
            INSERT INTO issues
            (book_id, student_id, issue_date, status)
            VALUES (?, ?, ?, 'Issued')
        """, (
            book_id,
            student_id,
            issue_date
        ))

        # ====================================================
        # DECREASE QUANTITY
        # ====================================================

        conn.execute("""
            UPDATE books
            SET quantity = quantity - 1
            WHERE id = ?
              AND quantity > 0
        """, (
            book_id,
        ))

        conn.commit()
        conn.close()

        flash(
            "Book issued successfully!",
            "success"
        )

        return redirect("/dashboard")

    # ========================================================
    # AVAILABLE BOOKS
    # ========================================================

    books = conn.execute("""
        SELECT *
        FROM books
        WHERE quantity > 0
        ORDER BY title
    """).fetchall()

    # ========================================================
    # ALL STUDENTS
    # ========================================================

    students = conn.execute("""
        SELECT *
        FROM students
        ORDER BY name
    """).fetchall()

    student_data = [
        dict(student)
        for student in students
    ]

    today = str(date.today())

    conn.close()

    return render_template(
        "issuebook.html",
        books=books,
        students=student_data,
        today=today
    )


# ============================================================
# ADD STUDENT
# ============================================================

@app.route("/addstudent", methods=["GET", "POST"])
def add_student():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        enrollment = request.form.get(
            "enrollment",
            ""
        ).strip()

        department = request.form.get(
            "department",
            ""
        ).strip()

        semester = request.form.get(
            "semester",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        if not name:

            conn.close()

            flash(
                "Student name is required!",
                "error"
            )

            return redirect("/addstudent")

        conn.execute("""
            INSERT INTO students
            (
                name,
                enrollment,
                department,
                semester,
                phone,
                email
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            name,
            enrollment,
            department,
            semester,
            phone,
            email
        ))

        conn.commit()
        conn.close()

        flash(
            "Student added successfully!",
            "success"
        )

        return redirect("/students")

    conn.close()

    return render_template("addstudent.html")


# ============================================================
# STUDENTS - VIEW + SEARCH
# ============================================================

@app.route("/students")
def students():

    if "user_id" not in session:
        return redirect("/login")

    search = request.args.get(
        "search",
        ""
    ).strip()

    conn = get_db()

    if search:

        students = conn.execute("""
            SELECT *
            FROM students
            WHERE name LIKE ?
               OR enrollment LIKE ?
               OR department LIKE ?
               OR semester LIKE ?
               OR phone LIKE ?
               OR email LIKE ?
            ORDER BY id DESC
        """, (
            "%" + search + "%",
            "%" + search + "%",
            "%" + search + "%",
            "%" + search + "%",
            "%" + search + "%",
            "%" + search + "%"
        )).fetchall()

    else:

        students = conn.execute("""
            SELECT *
            FROM students
            ORDER BY id DESC
        """).fetchall()

    conn.close()

    return render_template(
        "students.html",
        students=students,
        search=search
    )


# ============================================================
# EDIT STUDENT
# ============================================================

@app.route("/editstudent/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (
        student_id,
    )).fetchone()

    if student is None:

        conn.close()

        flash(
            "Student not found!",
            "error"
        )

        return redirect("/students")

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        enrollment = request.form.get(
            "enrollment",
            ""
        ).strip()

        department = request.form.get(
            "department",
            ""
        ).strip()

        semester = request.form.get(
            "semester",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        if not name:

            conn.close()

            flash(
                "Student name is required!",
                "error"
            )

            return redirect(
                "/editstudent/" + str(student_id)
            )

        conn.execute("""
            UPDATE students
            SET name = ?,
                enrollment = ?,
                department = ?,
                semester = ?,
                phone = ?,
                email = ?
            WHERE id = ?
        """, (
            name,
            enrollment,
            department,
            semester,
            phone,
            email,
            student_id
        ))

        conn.commit()
        conn.close()

        flash(
            "Student updated successfully!",
            "success"
        )

        return redirect("/students")

    conn.close()

    return render_template(
        "editstudent.html",
        student=student
    )


# ============================================================
# DELETE STUDENT
# ============================================================

@app.route("/deletestudent/<int:student_id>")
def delete_student(student_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    conn.execute("""
        DELETE FROM issues
        WHERE student_id = ?
    """, (
        student_id,
    ))

    conn.execute("""
        DELETE FROM students
        WHERE id = ?
    """, (
        student_id,
    ))

    conn.commit()
    conn.close()

    flash(
        "Student deleted successfully!",
        "success"
    )

    return redirect("/students")


# ============================================================
# RETURN BOOK
# ============================================================

@app.route("/returnbook", methods=["GET", "POST"])
@app.route("/return-book", methods=["GET", "POST"])
def return_book():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    if request.method == "POST":

        issue_id = request.form.get(
            "issue_id"
        )

        issue = conn.execute("""
            SELECT *
            FROM issues
            WHERE id = ?
              AND status = 'Issued'
        """, (
            issue_id,
        )).fetchone()

        if issue is None:

            conn.close()

            flash(
                "Issue record not found!",
                "error"
            )

            return redirect("/returnbook")

        conn.execute("""
            UPDATE issues
            SET return_date = date('now'),
                status = 'Returned'
            WHERE id = ?
        """, (
            issue_id,
        ))

        # Increase stock but maximum 10
        conn.execute("""
            UPDATE books
            SET quantity = MIN(quantity + 1, ?)
            WHERE id = ?
        """, (
            MAX_EXPLORE_STOCK,
            issue["book_id"]
        ))

        conn.commit()
        conn.close()

        flash(
            "Book returned successfully!",
            "success"
        )

        return redirect("/dashboard")

    # ========================================================
    # ACTIVE ISSUES
    # ========================================================

    issues = conn.execute("""
        SELECT
            issues.id,
            issues.issue_date,
            books.title,
            students.name AS student_name
        FROM issues
        JOIN books
            ON issues.book_id = books.id
        LEFT JOIN students
            ON issues.student_id = students.id
        WHERE issues.status = 'Issued'
        ORDER BY issues.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "returnbook.html",
        issues=issues
    )


# ============================================================
# BOOK COLLECTION
# ============================================================

@app.route("/bookcollection")
def bookcollection():

    if "user_id" not in session:
        return redirect("/login")

    return render_template(
        "bookcollection.html"
    )


# ============================================================
# EXPLORE BOOKS
# ============================================================

@app.route("/explorebooks")
def explore_books():

    if "user_id" not in session:
        return redirect("/login")

    books_data = [

        # ================= STORY =================

        {
            "name": "Charlotte's Web",
            "author": "E. B. White",
            "date": "1952",
            "category": "Story",
            "image": "https://covers.openlibrary.org/b/isbn/9780064400558-L.jpg"
        },

        {
            "name": "The Little Prince",
            "author": "Antoine de Saint-Exupéry",
            "date": "1943",
            "category": "Story",
            "image": "https://covers.openlibrary.org/b/isbn/9780156012195-L.jpg"
        },

        {
            "name": "Alice in Wonderland",
            "author": "Lewis Carroll",
            "date": "1865",
            "category": "Story",
            "image": "https://covers.openlibrary.org/b/isbn/9781503222687-L.jpg"
        },

        {
            "name": "The Jungle Book",
            "author": "Rudyard Kipling",
            "date": "1894",
            "category": "Story",
            "image": "https://covers.openlibrary.org/b/isbn/9780141325293-L.jpg"
        },

        # ================= MOTIVATIONAL =================

        {
            "name": "The Alchemist",
            "author": "Paulo Coelho",
            "date": "2006",
            "category": "Motivational",
            "image": "https://covers.openlibrary.org/b/isbn/9780061122415-L.jpg"
        },

        {
            "name": "Rich Dad Poor Dad",
            "author": "Robert T. Kiyosaki",
            "date": "1997",
            "category": "Motivational",
            "image": "https://covers.openlibrary.org/b/isbn/9781612681139-L.jpg"
        },

        {
            "name": "The Psychology of Money",
            "author": "Morgan Housel",
            "date": "2020",
            "category": "Motivational",
            "image": "https://covers.openlibrary.org/b/isbn/9780857197689-L.jpg"
        },

        {
            "name": "The Power of Now",
            "author": "Eckhart Tolle",
            "date": "1997",
            "category": "Motivational",
            "image": "https://covers.openlibrary.org/b/isbn/9781577314806-L.jpg"
        },

        {
            "name": "Deep Work",
            "author": "Cal Newport",
            "date": "2016",
            "category": "Motivational",
            "image": "https://covers.openlibrary.org/b/isbn/9781455586691-L.jpg"
        },

        {
            "name": "Think and Grow Rich",
            "author": "Napoleon Hill",
            "date": "1937",
            "category": "Motivational",
            "image": "https://covers.openlibrary.org/b/isbn/9781585424337-L.jpg"
        },

        {
            "name": "The 7 Habits of Highly Effective People",
            "author": "Stephen R. Covey",
            "date": "1989",
            "category": "Motivational",
            "image": "https://covers.openlibrary.org/b/isbn/9781982137274-L.jpg"
        },

        {
            "name": "Atomic Habits",
            "author": "James Clear",
            "date": "2018",
            "category": "Motivational",
            "image": "https://covers.openlibrary.org/b/isbn/9780735211292-L.jpg"
        },

        # ================= EDUCATIONAL =================

        {
            "name": "The Immortal Life of Henrietta Lacks",
            "author": "Rebecca Skloot",
            "date": "2010",
            "category": "Educational",
            "image": "https://covers.openlibrary.org/b/isbn/9781400052189-L.jpg"
        },

        {
            "name": "The Elements of Style",
            "author": "William Strunk Jr.",
            "date": "1918",
            "category": "Educational",
            "image": "https://covers.openlibrary.org/b/isbn/9780205309023-L.jpg"
        },

        {
            "name": "Sapiens",
            "author": "Yuval Noah Harari",
            "date": "2011",
            "category": "Educational",
            "image": "https://covers.openlibrary.org/b/isbn/9780062316097-L.jpg"
        },

        {
            "name": "A Brief History of Time",
            "author": "Stephen Hawking",
            "date": "1988",
            "category": "Educational",
            "image": "https://covers.openlibrary.org/b/isbn/9780553380163-L.jpg"
        },

        {
            "name": "The Selfish Gene",
            "author": "Richard Dawkins",
            "date": "1976",
            "category": "Educational",
            "image": "https://covers.openlibrary.org/b/isbn/9780198788607-L.jpg"
        },

        {
            "name": "How to Read a Book",
            "author": "Mortimer Adler",
            "date": "1940",
            "category": "Educational",
            "image": "https://covers.openlibrary.org/b/isbn/9780671212094-L.jpg"
        },

        {
            "name": "Guns, Germs, and Steel",
            "author": "Jared Diamond",
            "date": "1997",
            "category": "Educational",
            "image": "https://covers.openlibrary.org/b/isbn/9780393317558-L.jpg"
        },

        {
            "name": "The Story of Art",
            "author": "E. H. Gombrich",
            "date": "1950",
            "category": "Educational",
            "image": "https://covers.openlibrary.org/b/isbn/9780714832470-L.jpg"
        },

        # ================= SCIENCE =================

        {
            "name": "On the Origin of Species",
            "author": "Charles Darwin",
            "date": "1859",
            "category": "Science",
            "image": "https://covers.openlibrary.org/b/isbn/9780451529060-L.jpg"
        },

        {
            "name": "Astrophysics for People in a Hurry",
            "author": "Neil deGrasse Tyson",
            "date": "2017",
            "category": "Science",
            "image": "https://covers.openlibrary.org/b/isbn/9780393609394-L.jpg"
        },

        {
            "name": "Cosmos",
            "author": "Carl Sagan",
            "date": "1980",
            "category": "Science",
            "image": "https://covers.openlibrary.org/b/isbn/9780345539434-L.jpg"
        },

        {
            "name": "The Gene",
            "author": "Siddhartha Mukherjee",
            "date": "2016",
            "category": "Science",
            "image": "https://covers.openlibrary.org/b/isbn/9781476733500-L.jpg"
        },

        {
            "name": "Silent Spring",
            "author": "Rachel Carson",
            "date": "1962",
            "category": "Science",
            "image": "https://covers.openlibrary.org/b/isbn/9780618249060-L.jpg"
        },

        {
            "name": "The Elegant Universe",
            "author": "Brian Greene",
            "date": "1999",
            "category": "Science",
            "image": "https://covers.openlibrary.org/b/isbn/9780393338102-L.jpg"
        },

        {
            "name": "A Short History of Nearly Everything",
            "author": "Bill Bryson",
            "date": "2003",
            "category": "Science",
            "image": "https://covers.openlibrary.org/b/isbn/9780767908184-L.jpg"
        },

        # ================= NOVELS =================

        {
            "name": "The Hobbit",
            "author": "J. R. R. Tolkien",
            "date": "1937",
            "category": "Novels",
            "image": "https://covers.openlibrary.org/b/isbn/9780547928227-L.jpg"
        },

        {
            "name": "Pride and Prejudice",
            "author": "Jane Austen",
            "date": "1813",
            "category": "Novels",
            "image": "https://covers.openlibrary.org/b/isbn/9780141439518-L.jpg"
        },

        {
            "name": "The Kite Runner",
            "author": "Khaled Hosseini",
            "date": "2003",
            "category": "Novels",
            "image": "https://covers.openlibrary.org/b/isbn/9781594631931-L.jpg"
        },

        {
            "name": "The Book Thief",
            "author": "Markus Zusak",
            "date": "2005",
            "category": "Novels",
            "image": "https://covers.openlibrary.org/b/isbn/9780375842207-L.jpg"
        },

        {
            "name": "Harry Potter",
            "author": "J. K. Rowling",
            "date": "1997",
            "category": "Novels",
            "image": "https://covers.openlibrary.org/b/isbn/9780590353427-L.jpg"
        },

        {
            "name": "1984",
            "author": "George Orwell",
            "date": "1949",
            "category": "Novels",
            "image": "https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg"
        },

        {
            "name": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "date": "1925",
            "category": "Novels",
            "image": "https://covers.openlibrary.org/b/isbn/9780743273565-L.jpg"
        },

        {
            "name": "To Kill a Mockingbird",
            "author": "Harper Lee",
            "date": "1960",
            "category": "Novels",
            "image": "https://covers.openlibrary.org/b/isbn/9780061120084-L.jpg"
        }
    ]

    conn = get_db()

    # ========================================================
    # ADD / UPDATE EXPLORE BOOKS
    # ========================================================

    for book in books_data:

        existing = conn.execute("""
            SELECT id, quantity
            FROM books
            WHERE title = ?
              AND author = ?
        """, (
            book["name"],
            book["author"]
        )).fetchone()

        if existing is None:

            cursor = conn.execute("""
                INSERT INTO books
                (title, author, category, isbn, quantity)
                VALUES (?, ?, ?, ?, ?)
            """, (
                book["name"],
                book["author"],
                book["category"],
                "",
                MAX_EXPLORE_STOCK
            ))

            book["id"] = cursor.lastrowid
            book["quantity"] = MAX_EXPLORE_STOCK

        else:

            book["id"] = existing["id"]

            issue_count = conn.execute("""
                SELECT COUNT(*)
                FROM issues
                WHERE book_id = ?
            """, (
                existing["id"],
            )).fetchone()[0]

            if (
                issue_count == 0
                and existing["quantity"] < MAX_EXPLORE_STOCK
            ):

                conn.execute("""
                    UPDATE books
                    SET quantity = ?
                    WHERE id = ?
                """, (
                    MAX_EXPLORE_STOCK,
                    existing["id"]
                ))

                book["quantity"] = MAX_EXPLORE_STOCK

            else:

                book["quantity"] = existing["quantity"]

    # ========================================================
    # GET CURRENT BORROWERS
    # ========================================================

    for book in books_data:

        borrowers = conn.execute("""
            SELECT
                students.name,
                students.enrollment
            FROM issues
            JOIN students
                ON issues.student_id = students.id
            WHERE issues.book_id = ?
              AND issues.status = 'Issued'
            ORDER BY issues.id DESC
        """, (
            book["id"],
        )).fetchall()

        book["borrowers"] = [
            dict(row)
            for row in borrowers
        ]

    conn.commit()
    conn.close()

    return render_template(
        "explorebooks.html",
        books=books_data
    )


# ============================================================
# TAKE BOOK FROM EXPLORE
# ============================================================

@app.route("/takebook/<int:book_id>", methods=["GET", "POST"])
def take_book(book_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    # ========================================================
    # GET SELECTED BOOK
    # ========================================================

    book = conn.execute("""
        SELECT *
        FROM books
        WHERE id = ?
    """, (
        book_id,
    )).fetchone()

    if book is None:

        conn.close()

        flash(
            "Book not found!",
            "error"
        )

        return redirect("/explorebooks")

    # ========================================================
    # CHECK BOOK AVAILABILITY
    # ========================================================

    if book["quantity"] <= 0:

        conn.close()

        flash(
            "This book is NOT AVAILABLE!",
            "error"
        )

        return redirect("/explorebooks")

    # ========================================================
    # POST - TAKE BOOK
    # ========================================================

    if request.method == "POST":

        enrollment = request.form.get(
            "enrollment",
            ""
        ).strip()

        # ====================================================
        # CHECK ENROLLMENT
        # ====================================================

        if not enrollment:

            conn.close()

            flash(
                "Please enter student enrollment number!",
                "error"
            )

            return redirect(
                "/takebook/" + str(book_id)
            )

        # ====================================================
        # FIND STUDENT
        # ====================================================

        student = conn.execute("""
            SELECT *
            FROM students
            WHERE enrollment = ?
        """, (
            enrollment,
        )).fetchone()

        if student is None:

            conn.close()

            flash(
                "Student not found! "
                "Please register the student first.",
                "error"
            )

            return redirect(
                "/takebook/" + str(book_id)
            )

        # ====================================================
        # CHECK MAXIMUM 3 BOOKS
        # ====================================================

        active_count = conn.execute("""
            SELECT COUNT(*)
            FROM issues
            WHERE student_id = ?
              AND status = 'Issued'
        """, (
            student["id"],
        )).fetchone()[0]

        if active_count >= 3:

            conn.close()

            flash(
                "Student already has 3 books. "
                "This student cannot take another book "
                "until one book is returned.",
                "error"
            )

            return redirect(
                "/takebook/" + str(book_id)
            )

        # ====================================================
        # CHECK STOCK AGAIN
        # ====================================================

        current_book = conn.execute("""
            SELECT quantity
            FROM books
            WHERE id = ?
        """, (
            book_id,
        )).fetchone()

        if (
            current_book is None
            or current_book["quantity"] <= 0
        ):

            conn.close()

            flash(
                "Book is NOT AVAILABLE!",
                "error"
            )

            return redirect("/explorebooks")

        # ====================================================
        # ADD ISSUE RECORD
        # ====================================================

        conn.execute("""
            INSERT INTO issues
            (
                book_id,
                student_id,
                issue_date,
                return_date,
                status
            )
            VALUES
            (
                ?,
                ?,
                date('now'),
                NULL,
                'Issued'
            )
        """, (
            book_id,
            student["id"]
        ))

        # ====================================================
        # DECREASE BOOK QUANTITY
        # ====================================================

        conn.execute("""
            UPDATE books
            SET quantity = quantity - 1
            WHERE id = ?
              AND quantity > 0
        """, (
            book_id,
        ))

        conn.commit()
        conn.close()

        # ====================================================
        # SUCCESS MESSAGE
        # ====================================================

        flash(
            "Book taken successfully by "
            + student["name"]
            + "!",
            "success"
        )

        return redirect(
            "/details?enrollment=" + enrollment
        )

    # ========================================================
    # GET REQUEST
    # ========================================================

    conn.close()

    return render_template(
        "takebook.html",
        book=book
    )


# ============================================================
# COMPLETE BOOK DETAILS
# ============================================================

@app.route("/details")
def details():

    if "user_id" not in session:
        return redirect("/login")

    enrollment = request.args.get(
        "enrollment",
        ""
    ).strip()

    conn = get_db()

    total_books = conn.execute(
        "SELECT COUNT(*) FROM books"
    ).fetchone()[0]

    total_students = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    issued_books = conn.execute(
        "SELECT COUNT(*) FROM issues WHERE status = 'Issued'"
    ).fetchone()[0]

    returned_books = conn.execute(
        "SELECT COUNT(*) FROM issues WHERE status = 'Returned'"
    ).fetchone()[0]

    student = None
    student_books = []

    if enrollment:

        student = conn.execute("""
            SELECT *
            FROM students
            WHERE enrollment = ?
        """, (
            enrollment,
        )).fetchone()

        if student:

            student_books = conn.execute("""
                SELECT
                    issues.id AS issue_id,
                    issues.issue_date,
                    books.title,
                    books.author,
                    books.category
                FROM issues
                JOIN books
                    ON issues.book_id = books.id
                WHERE issues.student_id = ?
                  AND issues.status = 'Issued'
                ORDER BY issues.id DESC
            """, (
                student["id"],
            )).fetchall()

    conn.close()

    return render_template(
        "details.html",
        total_books=total_books,
        total_students=total_students,
        issued_books=issued_books,
        returned_books=returned_books,
        enrollment=enrollment,
        student=student,
        student_books=student_books
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ============================================================
# START APPLICATION
# ============================================================

# Initialize database when the application starts
init_db()


if __name__ == "__main__":

    print("====================================")
    print("Library Management System Started")
    print("Username : admin")
    print("Password : admin123")
    print("====================================")

    app.run(debug=True)