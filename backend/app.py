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
    
def require_student():
    if "user" not in session or session["user"]["role"] != "STUDENT":
        return redirect("/login")


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
    <h1>Кабінет студента</h1>
    <p>Ви увійшли як студент ЧНУ.</p>
    <a class="btn-primary" href="/jobs">Переглянути вакансії</a>
    <br><br>
    <a class="btn-secondary" href="/applications/mine">Мої відгуки</a>
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
            {rows_html or "<tr><td colspan='4'>Поки що немає активних вакансій.</td></tr>"}
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

@app.route("/applications/mine")
def my_applications():
    if "user" not in session or session["user"]["role"] != "STUDENT":
        return redirect("/login")

    student_id = session["user"]["id"]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            a.id,
            j.title,
            j.location,
            a.status,
            a.applied_at
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE a.student_id = %s
        ORDER BY a.applied_at DESC
    """, (student_id,))
    rows = cur.fetchall()
    conn.close()

    rows_html = ""
    for r in rows:
        app_id = r[0]
        job_title = r[1]
        location = r[2]
        status = r[3]
        applied_at = r[4]

        rows_html += f"""
        <tr>
            <td>{app_id}</td>
            <td>{job_title}</td>
            <td>{location}</td>
            <td>{status}</td>
            <td>{applied_at}</td>
        </tr>
        """

    return f"""
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <title>Мої відгуки – ЧНУ Jobs</title>
        <link rel="stylesheet" href="/css/style.css">
    </head>
    <body>
        <div class="page">

            <h1>Мої відгуки на вакансії</h1>

            <table>
                <tr>
                    <th>ID заявки</th>
                    <th>Вакансія</th>
                    <th>Локація</th>
                    <th>Статус</th>
                    <th>Дата подачі</th>
                </tr>
                {rows_html or "<tr><td colspan='5'>Ви ще не відгукувались на вакансії.</td></tr>"}
            </table>

            <p style="margin-top:20px;">
                <a href="/dashboard">← Повернутися в кабінет</a>
            </p>

        </div>
    </body>
    </html>
    """



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
        SELECT id, title, location, is_active 
        FROM jobs
        WHERE company_id = %s
        ORDER BY created_at DESC
    """, (cid,))
    jobs = cur.fetchall()
    conn.close()

    rows_html = ""
    for j in jobs:
        job_id = j[0]
        title = j[1]
        location = j[2]
        is_active = j[3]

        status_label = "Активна" if is_active else "Закрита"

        # кнопка "Закрити" тільки для активних
        close_button = ""
        if is_active:
            close_button = f"""
            <form method="POST" action="/firma/jobs/{job_id}/close" style="display:inline;">
                <button class="btn-secondary" style="margin-top:4px;">Закрити вакансію</button>
            </form>
            """

        rows_html += f"""
        <tr>
            <td>{job_id}</td>
            <td>{title}</td>
            <td>{location}</td>
            <td>{status_label}</td>
            <td>{close_button}</td>
        </tr>
        """

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
                    <th>Статус</th>
                    <th>Дії</th>
                </tr>
                {rows_html or "<tr><td colspan='5'>Поки що немає вакансій.</td></tr>"}
            </table>

            <p style="margin-top:20px;">
                <a href="/dashboard">← Назад в кабінет</a>
            </p>
        </div>
    </body>
    </html>
    """

# ---------- CLOSE THE JOB ----------
@app.route("/firma/jobs/<int:job_id>/close", methods=["POST"])
def close_job(job_id):
    require_role("FIRMA")
    cid = session["user"]["id"]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE jobs
            SET is_active = FALSE
            WHERE id = %s AND company_id = %s
        """, (job_id, cid))
        conn.commit()
    finally:
        conn.close()

    return redirect("/firma/jobs/mine")


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

    status_options = ["NEW", "REVIEW", "APPROVED", "REJECTED"]

    # будуємо рядки таблиці
    rows_html = ""
    for r in rows:
        app_id = r[0]
        student_name = r[1]
        student_email = r[2]
        job_title = r[3]
        cover_letter = r[4] or "—"
        status = r[5]
        applied_at = r[6]

        # select зі статусами
        options_html = ""
        for opt in status_options:
            selected = "selected" if opt == status else ""
            label = {
                "NEW": "NEW (новий)",
                "REVIEW": "REVIEW (в роботі)",
                "APPROVED": "APPROVED (схвалено)",
                "REJECTED": "REJECTED (відхилено)"
            }[opt]
            options_html += f'<option value="{opt}" {selected}>{label}</option>'

        rows_html += f"""
        <tr>
            <td>{app_id}</td>
            <td>{student_name}</td>
            <td><a href="mailto:{student_email}">{student_email}</a></td>
            <td>{job_title}</td>
            <td>{cover_letter}</td>
            <td>
                <form method="POST" action="/firma/applications/{app_id}/status">
                    <select name="status">
                        {options_html}
                    </select>
                    <button class="btn-secondary" style="margin-top:6px;">Оновити</button>
                </form>
            </td>
            <td>{applied_at}</td>
        </tr>
        """

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
                {rows_html or "<tr><td colspan='7'>Поки що немає заявок.</td></tr>"}
            </table>

            <p style="margin-top:20px;">
                <a href="/dashboard">← Повернутися в кабінет</a>
            </p>

        </div>
    </body>
    </html>
    """

@app.route("/firma/applications/<int:app_id>/status", methods=["POST"])
def update_application_status(app_id):
    require_role("FIRMA")
    cid = session["user"]["id"]
    new_status = request.form.get("status")

    # дозволяємо тільки певні статуси
    allowed_statuses = {"NEW", "REVIEW", "APPROVED", "REJECTED"}
    if new_status not in allowed_statuses:
        return "Некоректний статус", 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        # оновлюємо тільки ті заявки, що належать вакансіям цієї компанії
        cur.execute("""
            UPDATE applications
            SET status = %s
            WHERE id = %s
              AND job_id IN (
                  SELECT id FROM jobs WHERE company_id = %s
              )
        """, (new_status, app_id, cid))
        conn.commit()
    finally:
        conn.close()

    return redirect("/firma/applications")




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