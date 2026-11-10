from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, Response, session
)
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import csv
import io
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
app.secret_key = "student-feedback-project"

DB_PATH = Path(__file__).resolve().parent / "feedback.db"

RATING_FIELDS = [
    "teaching", "clarity", "interaction", "punctuality", "facilities"
]

RATING_LABELS = {
    "teaching": "Teaching Quality",
    "clarity": "Subject Clarity",
    "interaction": "Faculty Interaction",
    "punctuality": "Punctuality",
    "facilities": "Learning Facilities"
}

DEPARTMENT_DATA = {
    "CSE": {
        "Data Structures and Algorithms": [
            "Dr. Ananya Rao",
            "Mr. Kiran Kumar",
            "Ms. Divya"
        ],
        "Java Programming": [
            "Mr. Rahul Reddy",
            "Ms. Priya Sharma"
        ],
        "Python Programming": [
            "Mr. Arjun Kumar",
            "Ms. Swathi",
            "Mr. Naveen"
        ],
        "Database Management Systems": [
            "Ms. Kavitha",
            "Mr. Suresh",
            "Dr. Meena"
        ],
        "Operating Systems": [
            "Mr. Vamsi",
            "Ms. Lakshmi"
        ],
        "Computer Networks": [
            "Mr. Karthik",
            "Ms. Sneha"
        ]
    },

    "ECE": {
        "Digital Electronics": [
            "Mr. Suresh Kumar",
            "Ms. Kavitha"
        ],
        "Signals and Systems": [
            "Dr. Meena Rao",
            "Mr. Naveen"
        ],
        "Analog Electronic Circuits": [
            "Ms. Swathi",
            "Mr. Ramesh"
        ],
        "Communication Systems": [
            "Mr. Arjun",
            "Ms. Divya"
        ],
        "Electronic Devices": [
            "Dr. Prasad",
            "Ms. Priya"
        ]
    },

    "EEE": {
        "Electrical Circuit Analysis": [
            "Mr. Ramesh",
            "Ms. Lakshmi"
        ],
        "Electrical Machines": [
            "Dr. Prasad",
            "Mr. Vamsi"
        ],
        "Power Systems": [
            "Ms. Harika",
            "Mr. Kiran"
        ],
        "Control Systems": [
            "Mr. Naveen",
            "Ms. Kavitha"
        ],
        "Power Electronics": [
            "Dr. Meena",
            "Mr. Suresh"
        ]
    },

    "IT": {
        "Web Technologies": [
            "Mr. Abhishek",
            "Ms. Sneha"
        ],
        "Computer Networks": [
            "Mr. Karthik",
            "Mr. Rahul"
        ],
        "Software Engineering": [
            "Dr. Sanjay",
            "Ms. Pooja"
        ],
        "Cloud Computing": [
            "Mr. Arjun",
            "Ms. Swathi"
        ],
        "Data Analytics": [
            "Ms. Priya",
            "Mr. Naveen"
        ]
    }
}

POSITIVE_WORDS = {
    "good", "great", "excellent", "helpful", "clear", "wonderful",
    "friendly", "amazing", "best", "nice", "supportive", "interesting"
}

NEGATIVE_WORDS = {
    "bad", "poor", "boring", "unclear", "confusing", "worst",
    "terrible", "slow", "problem", "difficult", "late", "weak"
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                roll_number TEXT NOT NULL,
                department TEXT NOT NULL,
                year TEXT NOT NULL,
                subject TEXT NOT NULL,
                faculty TEXT NOT NULL,
                teaching INTEGER NOT NULL,
                clarity INTEGER NOT NULL,
                interaction INTEGER NOT NULL,
                punctuality INTEGER NOT NULL,
                facilities INTEGER NOT NULL,
                comments TEXT,
                sentiment TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                roll_number TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def login_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return route_function(*args, **kwargs)
    return wrapper


def analyze_sentiment(comment):
    words = set(
        "".join(c.lower() if c.isalnum() else " " for c in comment).split()
    )

    positive = len(words & POSITIVE_WORDS)
    negative = len(words & NEGATIVE_WORDS)

    if positive > negative:
        return "Positive"
    if negative > positive:
        return "Negative"
    return "Neutral"


def get_filters():
    return {
        "department": request.args.get("department", "").strip(),
        "year": request.args.get("year", "").strip(),
        "subject": request.args.get("subject", "").strip(),
        "sentiment": request.args.get("sentiment", "").strip(),
        "search": request.args.get("search", "").strip()
    }


def fetch_feedback(filters=None):
    sql = "SELECT * FROM feedback WHERE 1=1"
    params = []

    if filters:
        for key in ["department", "year", "subject", "sentiment"]:
            if filters.get(key):
                sql += f" AND {key} = ?"
                params.append(filters[key])

        if filters.get("search"):
            sql += """ AND (
                student_name LIKE ? OR roll_number LIKE ?
                OR faculty LIKE ? OR comments LIKE ?
            )"""

            pattern = "%" + filters["search"] + "%"
            params.extend([pattern] * 4)

    sql += " ORDER BY id DESC"

    with get_db() as conn:
        return conn.execute(sql, params).fetchall()


def build_insights(total, average, rating_values, sentiments):
    if total == 0:
        return ["Submit feedback to unlock your first insights."]

    insights = []

    if average >= 4.2:
        insights.append(
            "Overall satisfaction is strong. Continue the practices students value."
        )
    elif average >= 3.3:
        insights.append(
            "Overall satisfaction is moderate. Review the lowest-rated category."
        )
    else:
        insights.append(
            "Overall satisfaction needs attention. Plan targeted improvements."
        )

    if rating_values:
        lowest = min(rating_values, key=lambda item: item["score"])
        highest = max(rating_values, key=lambda item: item["score"])

        insights.append(
            f"Improvement opportunity: {lowest['label']} averages "
            f"{lowest['score']:.2f}/5."
        )

        insights.append(
            f"Strongest category: {highest['label']} averages "
            f"{highest['score']:.2f}/5."
        )

    if sentiments["Negative"]:
        insights.append(
            f"Review the {sentiments['Negative']} comment(s) classified as "
            "negative to identify recurring concerns."
        )

    return insights[:4]


# ---------------- LANDING PAGE ----------------

@app.route("/")
def landing():
    if "user_id" in session:
        return redirect(url_for("index"))

    return render_template("landing.html")


# ---------------- REGISTRATION ----------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        student_name = request.form.get("student_name", "").strip()
        roll_number = request.form.get("roll_number", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([
            student_name, roll_number, email,
            password, confirm_password
        ]):
            flash("Please fill in all the fields.", "error")
            return redirect(url_for("register"))

        if not email.endswith("@mbu.asia"):
            flash("Please use your MBU student email address.", "error")
            return redirect(url_for("register"))

        email_roll_number = email.split("@")[0]

        if email_roll_number.lower() != roll_number.lower():
            flash("Your email ID must match your roll number.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        try:
            with get_db() as conn:
                conn.execute("""
                    INSERT INTO users (
                        student_name, roll_number, email,
                        password, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    student_name,
                    roll_number,
                    email,
                    hashed_password,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash(
                "This roll number or email is already registered.",
                "error"
            )
            return redirect(url_for("register"))

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["student_name"] = user["student_name"]
            session["roll_number"] = user["roll_number"]
            session["email"] = user["email"]

            flash("Welcome! You are logged in.", "success")
            return redirect(url_for("index"))

        flash("Invalid email address or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("landing"))


# ---------------- FEEDBACK FORM ----------------

@app.route("/feedback")
@login_required
def index():
    return render_template(
        "index.html",
        department_data=DEPARTMENT_DATA
    )


# ---------------- SUBMIT FEEDBACK ----------------

@app.route("/submit", methods=["POST"])
@login_required
def submit():
    fields = ["department", "year", "subject", "faculty"]

    data = {
        field: request.form.get(field, "").strip()
        for field in fields
    }

    # Get student details from the login session
    student_name = session["student_name"]
    roll_number = session["roll_number"]

    comments = request.form.get("comments", "").strip()

    # Check whether all required details are provided
    if any(not value for value in data.values()):
        flash("Please complete all feedback details.", "error")
        return redirect(url_for("index"))

    # Validate department, subject and faculty selection
    subjects = DEPARTMENT_DATA.get(data["department"], {})
    faculty_list = subjects.get(data["subject"], [])

    if data["faculty"] not in faculty_list:
        flash(
            "Please select a valid subject and its faculty.",
            "error"
        )
        return redirect(url_for("index"))

    if len(comments) > 2000:
        flash("Comments cannot exceed 2,000 characters.", "error")
        return redirect(url_for("index"))

    # Validate ratings
    ratings = {}

    try:
        for field in RATING_FIELDS:
            value = int(request.form.get(field, ""))

            if value not in range(1, 6):
                raise ValueError

            ratings[field] = value

    except ValueError:
        flash("Please rate every category from 1 to 5.", "error")
        return redirect(url_for("index"))

    # Save feedback in the database
    with get_db() as conn:
        conn.execute("""
            INSERT INTO feedback (
                student_name, roll_number, department, year,
                subject, faculty, teaching, clarity, interaction,
                punctuality, facilities, comments, sentiment, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            student_name,
            roll_number,
            data["department"],
            data["year"],
            data["subject"],
            data["faculty"],
            ratings["teaching"],
            ratings["clarity"],
            ratings["interaction"],
            ratings["punctuality"],
            ratings["facilities"],
            comments,
            analyze_sentiment(comments),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    flash("Feedback submitted successfully!", "success")
    return redirect(url_for("index"))


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
@login_required
def dashboard():
    filters = get_filters()
    rows = fetch_feedback(filters)
    total = len(rows)

    average = round(
        sum(
            sum(row[field] for field in RATING_FIELDS)
            / len(RATING_FIELDS)
            for row in rows
        ) / total, 2
    ) if total else 0

    sentiments = {
        "Positive": 0,
        "Neutral": 0,
        "Negative": 0
    }

    for row in rows:
        sentiments[row["sentiment"]] += 1

    rating_values = []

    for field in RATING_FIELDS:
        score = round(
            sum(row[field] for row in rows) / total, 2
        ) if total else 0

        rating_values.append({
            "label": RATING_LABELS[field],
            "score": score
        })

    department_counts = {}
    daily_counts = {}

    for row in rows:
        department = row["department"]
        day = row["created_at"][:10]

        department_counts[department] = (
            department_counts.get(department, 0) + 1
        )

        daily_counts[day] = daily_counts.get(day, 0) + 1

    all_rows = fetch_feedback()

    departments = sorted({
        row["department"] for row in all_rows
    })

    years = sorted({
        row["year"] for row in all_rows
    })

    subjects = sorted({
        row["subject"] for row in all_rows
    })

    return render_template(
        "dashboard.html",
        filters=filters,
        total=total,
        average=average,
        sentiment_counts=sentiments,
        rating_values=rating_values,
        rating_labels=[
            item["label"] for item in rating_values
        ],
        rating_scores=[
            item["score"] for item in rating_values
        ],
        insights=build_insights(
            total, average, rating_values, sentiments
        ),
        dept_labels=list(department_counts.keys()),
        dept_values=list(department_counts.values()),
        trend_labels=sorted(daily_counts.keys()),
        trend_values=[
            daily_counts[key]
            for key in sorted(daily_counts)
        ],
        departments=departments,
        years=years,
        subjects=subjects,
        recent=rows[:5]
    )


# ---------------- FEEDBACK HISTORY ----------------

@app.route("/history")
@login_required
def history():
    filters = get_filters()
    rows = fetch_feedback(filters)

    all_rows = fetch_feedback()

    departments = sorted({
        row["department"] for row in all_rows
    })

    years = sorted({
        row["year"] for row in all_rows
    })

    subjects = sorted({
        row["subject"] for row in all_rows
    })

    return render_template(
        "history.html",
        feedback=rows,
        filters=filters,
        departments=departments,
        years=years,
        subjects=subjects
    )


# ---------------- CSV EXPORT ----------------

@app.route("/export.csv")
@login_required
def export_csv():
    rows = fetch_feedback(get_filters())

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Date", "Student", "Roll Number", "Department", "Year",
        "Subject", "Faculty", "Teaching", "Clarity", "Interaction",
        "Punctuality", "Facilities", "Comments", "Sentiment"
    ])

    for row in rows:
        writer.writerow([
            row["created_at"],
            row["student_name"],
            row["roll_number"],
            row["department"],
            row["year"],
            row["subject"],
            row["faculty"],
            row["teaching"],
            row["clarity"],
            row["interaction"],
            row["punctuality"],
            row["facilities"],
            row["comments"],
            row["sentiment"]
        ])

    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=student_feedback_export.csv"
        }
    )


# ---------------- START APPLICATION ----------------

init_db()

if __name__ == "__main__":
    app.run(debug=True)