import bcrypt

from backend.db import get_connection


DEMO_USERS = [
    {
        "full_name": "Olena Koval",
        "email": "olena.student@example.com",
        "password": "student123",
        "role": "STUDENT",
    },
    {
        "full_name": "Andrii Melnyk",
        "email": "andrii.student@example.com",
        "password": "student123",
        "role": "STUDENT",
    },
    {
        "full_name": "Sofia Hrytsenko",
        "email": "sofia.student@example.com",
        "password": "student123",
        "role": "STUDENT",
    },
    {
        "full_name": "SoftServe Chernivtsi",
        "email": "softserve@example.com",
        "password": "firma123",
        "role": "FIRMA",
    },
    {
        "full_name": "BukTech Labs",
        "email": "buktech@example.com",
        "password": "firma123",
        "role": "FIRMA",
    },
    {
        "full_name": "CHNU Career Center",
        "email": "admin@example.com",
        "password": "admin123",
        "role": "ADMIN",
    },
]

DEMO_JOBS = [
    {
        "company_email": "softserve@example.com",
        "title": "Python Flask Intern",
        "description": "Help build internal Flask services, write tests, and work with PostgreSQL queries.",
        "employment_type": "Internship",
        "location": "Chernivtsi / Hybrid",
        "is_active": True,
    },
    {
        "company_email": "softserve@example.com",
        "title": "Junior QA Engineer",
        "description": "Create manual test cases, report bugs, and support release checks for web projects.",
        "employment_type": "Part-time",
        "location": "Remote",
        "is_active": True,
    },
    {
        "company_email": "buktech@example.com",
        "title": "Frontend Trainee",
        "description": "Build HTML, CSS, and JavaScript interfaces for student-focused web products.",
        "employment_type": "Internship",
        "location": "Chernivtsi",
        "is_active": True,
    },
    {
        "company_email": "buktech@example.com",
        "title": "Data Analyst Assistant",
        "description": "Prepare reports, clean CSV data, and create simple dashboards for business teams.",
        "employment_type": "Part-time",
        "location": "Remote",
        "is_active": False,
    },
]

DEMO_APPLICATIONS = [
    {
        "student_email": "olena.student@example.com",
        "job_title": "Python Flask Intern",
        "cover_letter": "I have completed Python coursework and want to practice Flask on a real team.",
        "status": "REVIEW",
    },
    {
        "student_email": "andrii.student@example.com",
        "job_title": "Junior QA Engineer",
        "cover_letter": "I am attentive to details and have experience writing test scenarios for lab projects.",
        "status": "NEW",
    },
    {
        "student_email": "sofia.student@example.com",
        "job_title": "Frontend Trainee",
        "cover_letter": "I enjoy building responsive pages and already know HTML, CSS, and basic JavaScript.",
        "status": "APPROVED",
    },
]


def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('ADMIN', 'STUDENT', 'FIRMA')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                company_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                employment_type TEXT NOT NULL,
                location TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id SERIAL PRIMARY KEY,
                job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                cover_letter TEXT,
                status TEXT NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW', 'REVIEW', 'APPROVED', 'REJECTED')),
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        seed_demo_data(cur)
        conn.commit()
    finally:
        conn.close()


def seed_demo_data(cur):
    user_ids = {}
    for user in DEMO_USERS:
        password_hash = bcrypt.hashpw(
            user["password"].encode(), bcrypt.gensalt()
        ).decode()
        cur.execute(
            """
            INSERT INTO users (full_name, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE
            SET full_name = EXCLUDED.full_name,
                password_hash = EXCLUDED.password_hash,
                role = EXCLUDED.role
            RETURNING id
            """,
            (user["full_name"], user["email"], password_hash, user["role"]),
        )
        user_ids[user["email"]] = cur.fetchone()[0]

    job_ids = {}
    for job in DEMO_JOBS:
        company_id = user_ids[job["company_email"]]
        cur.execute(
            """
            SELECT id
            FROM jobs
            WHERE company_id = %s AND title = %s
            """,
            (company_id, job["title"]),
        )
        row = cur.fetchone()
        if row:
            job_id = row[0]
            cur.execute(
                """
                UPDATE jobs
                SET description = %s,
                    employment_type = %s,
                    location = %s,
                    is_active = %s
                WHERE id = %s
                """,
                (
                    job["description"],
                    job["employment_type"],
                    job["location"],
                    job["is_active"],
                    job_id,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO jobs (
                    company_id, title, description, employment_type, location, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    company_id,
                    job["title"],
                    job["description"],
                    job["employment_type"],
                    job["location"],
                    job["is_active"],
                ),
            )
            job_id = cur.fetchone()[0]
        job_ids[job["title"]] = job_id

    for application in DEMO_APPLICATIONS:
        student_id = user_ids[application["student_email"]]
        job_id = job_ids[application["job_title"]]
        cur.execute(
            """
            SELECT id
            FROM applications
            WHERE job_id = %s AND student_id = %s
            """,
            (job_id, student_id),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                """
                UPDATE applications
                SET cover_letter = %s,
                    status = %s
                WHERE id = %s
                """,
                (application["cover_letter"], application["status"], row[0]),
            )
        else:
            cur.execute(
                """
                INSERT INTO applications (job_id, student_id, cover_letter, status)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    job_id,
                    student_id,
                    application["cover_letter"],
                    application["status"],
                ),
            )
