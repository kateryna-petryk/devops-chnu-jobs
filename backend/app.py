from flask import Flask, request, redirect, session, send_from_directory
from backend.db import get_connection
from backend.models import init_db
import bcrypt
import os

app = Flask(__name__, static_folder="../src", static_url_path="")
app.secret_key = os.getenv("SESSION_SECRET", "secret123")


# ---------- Helpers ----------
def is_logged_in():
    return "user" in session

def require_login():
    if not is_logged_in():
        return redirect("/login")

def require_role(role):
    if not is_logged_in() or session["user"]["role"] != role:
        return "403 Forbidden — insufficient permissions", 403


# ---------- Serve static index ----------
@app.route("/")
def landing_page():
    return send_from_directory("../src", "index.html")


# ---------- AUTH ----------
@app.route("/register", methods=["GET"])
def register_page():
    return """
    <h1>Реєстрація</h1>
    <form method="POST">
      Імʼя: <input name="full_name"><br>
      Email: <input name="email"><br>
      Пароль: <input type="password" name="password"><br>
      Роль:
      <select name="role">
        <option value="STUDENT">Student</option>
        <option value="FIRMA">Firma</option>
      </select>
      <button>Зареєструватися</button>
    </form>
    """


@app.route("/register", methods=["POST"])
def register_submit():
    full_name = request.form["full_name"]
    email = request.form["email"]
    password = request.form["password"]
    role = request.form["role"]

    pwd_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
            (full_name, email, pwd_hash, role)
        )
        conn.commit()
    except:
        return "Користувач вже існує"
    finally:
        conn.close()

    return redirect("/login")


@app.route("/login", methods=["GET"])
def login_page():
    return """
    <h1>Вхід</h1>
    <form method="POST">
      Email: <input name="email"><br>
      Пароль: <input type="password" name="password"><br>
      <button>Увійти</button>
    </form>
    """


@app.route("/login", methods=["POST"])
def login_submit():
    email = request.form["email"]
    password = request.form["password"]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, full_name, email, password_hash, role FROM users WHERE email=%s", (email,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return "Невірний email або пароль"

    user_id, full_name, email, pwd_hash, role = row

    if not bcrypt.checkpw(password.encode(), pwd_hash.encode()):
        return "Невірний email або пароль"

    session["user"] = {
        "id": user_id,
        "full_name": full_name,
        "email": email,
        "role": role
    }

    return redirect("/dashboard")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/")


# ---------- DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    if not is_logged_in():
        return redirect("/login")

    u = session["user"]

    if u["role"] == "STUDENT":
        return f"<h1>Кабінет студента</h1><a href='/jobs'>Переглянути вакансії</a>"

    if u["role"] == "FIRMA":
        return """
        <h1>Кабінет компанії</h1>
        <a href='/firma/jobs/new'>Створити вакансію</a><br>
        <a href='/firma/jobs/mine'>Мої вакансії</a><br>
        <a href='/firma/applications'>Заявки студентів</a>
        """

    if u["role"] == "ADMIN":
        return "<h1>Адмін панель</h1>"

    return "Unknown role"


# ---------- JOBS (public list) ----------
@app.route("/jobs")
def job_list():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT j.id, j.title, j.location, j.employment_type, u.full_name
        FROM jobs j
        JOIN users u ON u.id = j.company_id
        WHERE j.is_active = TRUE
        ORDER BY j.created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()

    html = "<h1>Вакансії</h1><table border='1'>"
    for r in rows:
        html += f"<tr><td><a href='/jobs/{r[0]}'>{r[1]}</a></td><td>{r[4]}</td><td>{r[2]}</td></tr>"
    html += "</table>"
    return html


# ---------- JOB DETAILS ----------
@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT j.title, j.description, j.location, j.employment_type, u.full_name
        FROM jobs j
        JOIN users u ON u.id = j.company_id
        WHERE j.id = %s
    """, (job_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return "Вакансію не знайдено"

    title, desc, loc, typ, company = row

    return f"""
    <h1>{title}</h1>
    <p><strong>Компанія:</strong> {company}</p>
    <p><strong>Опис:</strong> {desc}</p>
    <p><a href='/jobs/{job_id}/apply'>Відгукнутися</a></p>
    """


# ---------- APPLY ----------
@app.route("/jobs/<int:job_id>/apply", methods=["GET", "POST"])
def apply(job_id):
    if not is_logged_in() or session["user"]["role"] != "STUDENT":
        return redirect("/login")

    if request.method == "GET":
        return f"""
        <h1>Відгук на вакансію</h1>
        <form method="POST">
          Cover letter: <textarea name="cover_letter"></textarea>
          <button>Надіслати</button>
        </form>
        """

    cover = request.form.get("cover_letter", "")
    student_id = session["user"]["id"]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO applications (job_id, student_id, cover_letter)
        VALUES (%s, %s, %s)
    """, (job_id, student_id, cover))
    conn.commit()
    conn.close()

    return "Заявка надіслана"


# ---------- FIRMA CREATE JOB ----------
@app.route("/firma/jobs/new", methods=["GET"])
def job_form():
    require_role("FIRMA")
    return """
    <h1>Нова вакансія</h1>
    <form method="POST" action="/firma/jobs">
      Назва: <input name="title"><br>
      Місце: <input name="location"><br>
      Тип: <input name="employment_type"><br>
      Опис: <textarea name="description"></textarea><br>
      <button>Створити</button>
    </form>
    """


@app.route("/firma/jobs", methods=["POST"])
def job_submit():
    require_role("FIRMA")

    title = request.form["title"]
    location = request.form["location"]
    type_ = request.form["employment_type"]
    desc = request.form["description"]
    company_id = session["user"]["id"]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO jobs (company_id, title, description, employment_type, location)
        VALUES (%s, %s, %s, %s, %s)
    """, (company_id, title, desc, type_, location))
    conn.commit()
    conn.close()

    return redirect("/firma/jobs/mine")


# ---------- FIRMA LIST JOBS ----------
@app.route("/firma/jobs/mine")
def firma_jobs():
    require_role("FIRMA")

    cid = session["user"]["id"]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, location FROM jobs
        WHERE company_id = %s
    """, (cid,))
    jobs = cur.fetchall()
    conn.close()

    html = "<h1>Мої вакансії</h1><table border=1>"
    for j in jobs:
        html += f"<tr><td>{j[0]}</td><td>{j[1]}</td><td>{j[2]}</td></tr>"
    html += "</table>"
    return html


# ---------- FIRMA APPLICATIONS ----------
@app.route("/firma/applications")
def firma_applications():
    require_role("FIRMA")
    cid = session["user"]["id"]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, s.full_name, j.title, a.cover_letter, a.status
        FROM applications a
        JOIN users s ON s.id = a.student_id
        JOIN jobs j ON j.id = a.job_id
        WHERE j.company_id = %s
    """, (cid,))
    rows = cur.fetchall()
    conn.close()

    html = "<h1>Заявки студентів</h1><table border=1>"
    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[4]}</td></tr>"
    html += "</table>"
    return html


# ---------- START ----------
if __name__ == "__main__":
    # retry system like Node.js version
    import time

    for i in range(10):
        try:
            init_db()
            break
        except Exception as e:
            print("DB not ready, retrying...")
            time.sleep(3)

    app.run(host="0.0.0.0", port=int(os.getenv("APP_PORT", 3000)))
