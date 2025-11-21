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
    error = request.args.get("error", "")

    error_html = f"<div class='error-msg'>{error}</div>" if error else ""

    return f"""
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <title>Реєстрація – ЧНУ Jobs</title>
        <link rel="stylesheet" href="/css/style.css">
    </head>
    <body>
    <div class="page">

        <h1>Реєстрація</h1>

        {error_html}

        <form method="POST">
            <label>Повне імʼя</label>
            <input name="full_name" required>

            <label>Email</label>
            <input name="email" type="email" required>

            <label>Пароль</label>
            <input name="password" type="password" required>

            <label>Роль</label>
            <select name="role">
                <option value="STUDENT">Студент ЧНУ</option>
                <option value="FIRMA">Компанія / Фірма</option>
            </select>

            <button class="btn-primary">Зареєструватися</button>
        </form>

        <p>Вже маєте акаунт? <a href="/login">Увійти</a></p>

    </div>
    </body>
    </html>
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
        conn.close()
        return redirect("/register?error=Користувач+з+таким+email+вже+існує")
    finally:
        conn.close()

    return redirect("/login")



@app.route("/login", methods=["GET"])
def login_page():
    error = request.args.get("error", "")

    error_html = f"<div class='error-msg'>{error}</div>" if error else ""

    return f"""
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <title>Вхід – ЧНУ Jobs</title>
        <link rel="stylesheet" href="/css/style.css">
    </head>
    <body>
    <div class="page">

        <h1>Вхід</h1>

        {error_html}

        <form method="POST">
            <label>Email</label>
            <input type="email" name="email" required>

            <label>Пароль</label>
            <input type="password" name="password" required>

            <button class="btn-primary">Увійти</button>
        </form>

        <p>Ще не маєте акаунта? <a href="/register">Зареєструватися</a></p>

    </div>
    </body>
    </html>
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
        return redirect("/login?error=Невірний+email+або+пароль")

    user_id, full_name, email, pwd_hash, role = row

    if not bcrypt.checkpw(password.encode(), pwd_hash.encode()):
        return redirect("/login?error=Невірний+email+або+пароль")

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
        return f"""
        <html lang="uk">
<head>
    <meta charset="UTF-8" />
    <title>...</title>
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <div class="page">
    <h1>Кабінет студента</h1><a href='/jobs'>Переглянути вакансії</a>
    </div>
</body>
</html>"""

    if u["role"] == "FIRMA":
        return """
        <html lang="uk">
<head>
    <meta charset="UTF-8" />
    <title>...</title>
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <div class="page">
        <h1>Кабінет компанії</h1>
        <a href='/firma/jobs/new'>Створити вакансію</a><br>
        <a href='/firma/jobs/mine'>Мої вакансії</a><br>
        <a href='/firma/applications'>Заявки студентів</a>
        </div>
</body>
</html>
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

    # Build table rows dynamically
    rows_html = "".join(
        f"<tr>"
        f"<td><a href='/jobs/{r[0]}'>{r[1]}</a></td>"
        f"<td>{r[4]}</td>"
        f"<td>{r[2]}</td>"
        f"<td>{r[3]}</td>"
        f"</tr>"
        for r in rows
    )

    return f"""
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <title>Вакансії – ЧНУ Jobs</title>
        <link rel="stylesheet" href="/css/style.css">
    </head>
    <body>
        <div class="page">
            <h1>Вакансії та стажування</h1>

            <table>
                <tr>
                    <th>Назва</th>
                    <th>Компанія</th>
                    <th>Локація</th>
                    <th>Тип</th>
                </tr>
                {rows_html}
            </table>

            <p style="margin-top:20px;">
                <a href="/">← На головну</a>
            </p>
        </div>
    </body>
    </html>
    """





# ---------- JOB DETAILS ----------
@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    from flask import request  # якщо вище ще не імпортовано

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

    # читаємо успішне повідомлення
    success = request.args.get("success", "")
    success_html = f"<div class='success-msg'>{success}</div>" if success else ""

    return f"""
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <title>{title} – ЧНУ Jobs</title>
        <link rel="stylesheet" href="/css/style.css">
    </head>
    <body>
      <div class="page">
        {success_html}

        <h1>{title}</h1>
        <p><strong>Компанія:</strong> {company}</p>
        <p><strong>Тип:</strong> {typ}</p>
        <p><strong>Локація:</strong> {loc}</p>
        <p><strong>Опис:</strong></p>
        <p>{desc}</p>

        <p style="margin-top:20px;">
          <a class="btn-primary" href="/jobs/{job_id}/apply">Відгукнутися</a>
        </p>

        <p style="margin-top:10px;">
          <a href="/jobs">← До списку вакансій</a>
        </p>
      </div>
    </body>
    </html>
    """



# ---------- APPLY ----------
@app.route("/jobs/<int:job_id>/apply", methods=["GET", "POST"])
def apply(job_id):
    if not is_logged_in() or session["user"]["role"] != "STUDENT":
        return redirect("/login")

    if request.method == "GET":
        return f"""
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <title>Відгук на вакансію – ЧНУ Jobs</title>
            <link rel="stylesheet" href="/css/style.css">
        </head>
        <body>
          <div class="page">
            <h1>Відгук на вакансію</h1>
            <form method="POST">
              <label>Супровідний лист</label>
              <textarea name="cover_letter"></textarea>
              <button class="btn-primary">Надіслати</button>
            </form>
            <p style="margin-top:10px;">
              <a href="/jobs/{job_id}">← Назад до вакансії</a>
            </p>
          </div>
        </body>
        </html>
        """

    # POST
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

    # Повертаємося до сторінки вакансії з зеленим повідомленням
    return redirect(f"/jobs/{job_id}?success=Ваш+відгук+успішно+надіслано")



# ---------- FIRMA CREATE JOB ----------
@app.route("/firma/jobs/new", methods=["GET"])
def job_form():
    require_role("FIRMA")
    return """
     <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <title>Вакансії – ЧНУ Jobs</title>
        <link rel="stylesheet" href="/css/style.css">
    </head>
    <body>
        <div class="page">
    <h1>Нова вакансія</h1>
    <form method="POST" action="/firma/jobs">
      Назва: <input name="title"><br>
      Місце: <input name="location"><br>
      Тип: <input name="employment_type"><br>
      Опис: <textarea name="description"></textarea><br>
      <button>Створити</button>
    </form>
    </div>
    </body>
    </html>
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

    rows_html = "".join(
        f"<tr>"
        f"<td>{j[0]}</td>"
        f"<td>{j[1]}</td>"
        f"<td>{j[2]}</td>"
        f"</tr>"
        for j in jobs
    )

    return f"""
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <title>Мої вакансії – ЧНУ Jobs</title>
        <link rel="stylesheet" href="/css/style.css">
    </head>
    <body>
        <div class="page">
            <h1>Мої вакансії</h1>

            <table>
                <tr>
                    <th>ID</th>
                    <th>Назва вакансії</th>
                    <th>Локація</th>
                </tr>
                {rows_html}
            </table>

            <p style="margin-top:20px;">
                <a href="/dashboard">← Назад в кабінет</a>
            </p>
        </div>
    </body>
    </html>
    """


# ---------- FIRMA APPLICATIONS ----------
@app.route("/firma/applications")
def firma_applications():
    require_role("FIRMA")
    cid = session["user"]["id"]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            a.id, 
            s.full_name, 
            s.email,
            j.title, 
            a.cover_letter, 
            a.status,
            a.applied_at
        FROM applications a
        JOIN users s ON s.id = a.student_id
        JOIN jobs j ON j.id = a.job_id
        WHERE j.company_id = %s
        ORDER BY a.applied_at DESC
    """, (cid,))
    rows = cur.fetchall()
    conn.close()

    # Будуємо рядки таблиці
    rows_html = "".join(
        f"""
        <tr>
            <td>{r[0]}</td>
            <td>{r[1]}</td>
            <td><a href="mailto:{r[2]}">{r[2]}</a></td>
            <td>{r[3]}</td>
            <td>{(r[4] or "—")}</td>
            <td>{r[5]}</td>
            <td>{r[6]}</td>
        </tr>
        """
        for r in rows
    )

    return f"""
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <title>Заявки студентів – ЧНУ Jobs</title>
        <link rel="stylesheet" href="/css/style.css">
    </head>
    <body>
        <div class="page">

            <h1>Заявки студентів</h1>

            <table>
                <tr>
                    <th>ID</th>
                    <th>Студент</th>
                    <th>Email студента</th>
                    <th>Вакансія</th>
                    <th>Супровідний лист</th>
                    <th>Статус</th>
                    <th>Дата</th>
                </tr>
                {rows_html}
            </table>

            <p style="margin-top:20px;">
                <a href="/dashboard">← Повернутися в кабінет</a>
            </p>

        </div>
    </body>
    </html>
    """


# ---------- START ----------
if __name__ == "__main__":
    import os

    # Одноразова спроба ініціалізації БД.
    # Якщо не вийшло – просто лог, але сервер все одно стартує.
    try:
        init_db()
        print("DB init OK")
    except Exception as e:
        print("DB init failed, continuing without blocking:", e)

    # Render задає змінну PORT (типу 10000).
    # Локально можна не задавати – тоді буде 3000.
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)