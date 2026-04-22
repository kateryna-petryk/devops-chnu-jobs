import logging
import os
import time
from functools import wraps

import bcrypt
from flask import Flask, jsonify, redirect, request, send_from_directory, session
from markupsafe import escape

from backend.db import get_connection
from backend.models import init_db

ALLOWED_ROLES = {"STUDENT", "FIRMA", "ADMIN"}
ALLOWED_APPLICATION_STATUSES = ("NEW", "REVIEW", "APPROVED", "REJECTED")


def configure_logging() -> None:
    if logging.getLogger().handlers:
        return

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def create_app(test_config=None) -> Flask:
    configure_logging()

    app = Flask(__name__, static_folder="../src", static_url_path="")
    app.config.update(
        SECRET_KEY=os.getenv("SESSION_SECRET", "chnu-jobs-dev-secret"),
        TESTING=False,
        SKIP_DB_INIT=os.getenv("SKIP_DB_INIT", "0") == "1",
        DB_INIT_RETRIES=int(os.getenv("DB_INIT_RETRIES", "15")),
        DB_INIT_DELAY=float(os.getenv("DB_INIT_DELAY", "2")),
    )

    if test_config:
        app.config.update(test_config)

    register_routes(app)

    if not app.config["TESTING"] and not app.config["SKIP_DB_INIT"]:
        initialize_database_with_retry(app)

    return app


def initialize_database_with_retry(app: Flask) -> None:
    retries = app.config["DB_INIT_RETRIES"]
    delay = app.config["DB_INIT_DELAY"]
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            init_db()
            app.logger.info("Database schema is ready.")
            return
        except Exception as exc:  # pragma: no cover - exercised in container startup
            last_error = exc
            app.logger.warning(
                "Database initialization attempt %s/%s failed: %s",
                attempt,
                retries,
                exc,
            )
            if attempt < retries:
                time.sleep(delay)

    raise RuntimeError("Could not initialize database.") from last_error


def register_routes(app: Flask) -> None:
    def current_user():
        return session.get("user")

    def render_page(title: str, body: str) -> str:
        safe_title = escape(title)
        return f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_title} – CHNU Jobs</title>
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <div class="page">
        {body}
    </div>
</body>
</html>
"""

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user():
                return redirect("/login")
            return view(*args, **kwargs)

        return wrapped

    def role_required(role):
        def decorator(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                user = current_user()
                if not user:
                    return redirect("/login")
                if user["role"] != role:
                    return "403 Forbidden", 403
                return view(*args, **kwargs)

            return wrapped

        return decorator

    def fetch_one(query, params=()):
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            return cur.fetchone()
        finally:
            conn.close()

    def fetch_all(query, params=()):
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            return cur.fetchall()
        finally:
            conn.close()

    def execute_write(query, params=()):
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
        except Exception:
            if hasattr(conn, "rollback"):
                conn.rollback()
            raise
        finally:
            conn.close()

    @app.route("/")
    def landing_page():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/health")
    def health():
        try:
            row = fetch_one("SELECT 1")
            if row and row[0] == 1:
                return jsonify({"status": "ok", "database": "up"}), 200
        except Exception as exc:
            app.logger.warning("Health check failed: %s", exc)
        return jsonify({"status": "error", "database": "down"}), 503

    @app.route("/register", methods=["GET"])
    def register_page():
        error = request.args.get("error", "")
        error_html = (
            f"<div class='error-msg'>{escape(error)}</div>" if error else ""
        )
        body = f"""
        <h1>Реєстрація</h1>
        {error_html}
        <form method="POST" action="/register">
            <label>Повне ім'я</label>
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

            <button class="btn-primary" type="submit">Зареєструватися</button>
        </form>
        <p>Вже маєте акаунт? <a href="/login">Увійти</a></p>
        """
        return render_page("Реєстрація", body)

    @app.route("/register", methods=["POST"])
    def register_submit():
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "")

        if not full_name or not email or not password or role not in {"STUDENT", "FIRMA"}:
            return redirect("/register?error=Перевірте+заповнення+форми")

        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        try:
            execute_write(
                """
                INSERT INTO users (full_name, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
                """,
                (full_name, email, password_hash, role),
            )
        except Exception as exc:
            app.logger.warning("Registration failed for %s: %s", email, exc)
            return redirect("/register?error=Користувач+з+таким+email+вже+існує")

        return redirect("/login")

    @app.route("/login", methods=["GET"])
    def login_page():
        error = request.args.get("error", "")
        error_html = (
            f"<div class='error-msg'>{escape(error)}</div>" if error else ""
        )
        body = f"""
        <h1>Вхід</h1>
        {error_html}
        <form method="POST" action="/login">
            <label>Email</label>
            <input type="email" name="email" required>

            <label>Пароль</label>
            <input type="password" name="password" required>

            <button class="btn-primary" type="submit">Увійти</button>
        </form>
        <p>Ще не маєте акаунта? <a href="/register">Зареєструватися</a></p>
        """
        return render_page("Вхід", body)

    @app.route("/login", methods=["POST"])
    def login_submit():
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        row = fetch_one(
            """
            SELECT id, full_name, email, password_hash, role
            FROM users
            WHERE email = %s
            """,
            (email,),
        )

        if not row:
            return redirect("/login?error=Невірний+email+або+пароль")

        user_id, full_name, user_email, password_hash, role = row
        if not bcrypt.checkpw(password.encode(), password_hash.encode()):
            return redirect("/login?error=Невірний+email+або+пароль")

        session["user"] = {
            "id": user_id,
            "full_name": full_name,
            "email": user_email,
            "role": role,
        }
        return redirect("/dashboard")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect("/")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        user = current_user()
        full_name = escape(user["full_name"])

        if user["role"] == "STUDENT":
            body = f"""
            <h1>Кабінет студента</h1>
            <p>Вітаємо, <strong>{full_name}</strong>.</p>
            <a class="btn-primary" href="/jobs">Переглянути вакансії</a>
            <br><br>
            <a class="btn-secondary" href="/applications/mine">Мої відгуки</a>
            <form method="POST" action="/logout">
                <button class="btn-secondary" type="submit">Вийти</button>
            </form>
            """
            return render_page("Кабінет студента", body)

        if user["role"] == "FIRMA":
            body = f"""
            <h1>Кабінет компанії</h1>
            <p>Вітаємо, <strong>{full_name}</strong>.</p>
            <a class="btn-primary" href="/firma/jobs/new">Створити вакансію</a><br><br>
            <a class="btn-secondary" href="/firma/jobs/mine">Мої вакансії</a><br><br>
            <a class="btn-secondary" href="/firma/applications">Заявки студентів</a>
            <form method="POST" action="/logout">
                <button class="btn-secondary" type="submit">Вийти</button>
            </form>
            """
            return render_page("Кабінет компанії", body)

        body = f"""
        <h1>Адмін панель</h1>
        <p>Вітаємо, <strong>{full_name}</strong>.</p>
        <form method="POST" action="/logout">
            <button class="btn-secondary" type="submit">Вийти</button>
        </form>
        """
        return render_page("Адмін панель", body)

    @app.route("/jobs")
    def job_list():
        rows = fetch_all(
            """
            SELECT j.id, j.title, j.location, j.employment_type, u.full_name
            FROM jobs j
            JOIN users u ON u.id = j.company_id
            WHERE j.is_active = TRUE
            ORDER BY j.created_at DESC
            """
        )

        if rows:
            rows_html = "".join(
                f"""
                <tr>
                    <td><a href="/jobs/{job_id}">{escape(title)}</a></td>
                    <td>{escape(company)}</td>
                    <td>{escape(location)}</td>
                    <td>{escape(job_type)}</td>
                </tr>
                """
                for job_id, title, location, job_type, company in rows
            )
        else:
            rows_html = "<tr><td colspan='4'>Поки що немає активних вакансій.</td></tr>"

        back_link = "/dashboard" if current_user() else "/"
        body = f"""
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
        <p style="margin-top:20px;"><a href="{back_link}">← Назад</a></p>
        """
        return render_page("Вакансії", body)

    @app.route("/jobs/<int:job_id>")
    def job_detail(job_id):
        row = fetch_one(
            """
            SELECT j.title, j.description, j.location, j.employment_type, u.full_name
            FROM jobs j
            JOIN users u ON u.id = j.company_id
            WHERE j.id = %s
            """,
            (job_id,),
        )

        if not row:
            return render_page(
                "Вакансію не знайдено",
                "<h1>Вакансію не знайдено</h1><p><a href='/jobs'>← До списку вакансій</a></p>",
            ), 404

        title, description, location, job_type, company = row
        success = request.args.get("success", "")
        success_html = (
            f"<div class='success-msg'>{escape(success)}</div>" if success else ""
        )
        apply_link = (
            f"<a class='btn-primary' href='/jobs/{job_id}/apply'>Відгукнутися</a>"
            if current_user() and current_user()["role"] == "STUDENT"
            else "<a class='btn-primary' href='/login'>Увійти, щоб відгукнутися</a>"
        )
        body = f"""
        {success_html}
        <h1>{escape(title)}</h1>
        <p><strong>Компанія:</strong> {escape(company)}</p>
        <p><strong>Тип:</strong> {escape(job_type)}</p>
        <p><strong>Локація:</strong> {escape(location)}</p>
        <p><strong>Опис:</strong></p>
        <p>{escape(description)}</p>
        <p style="margin-top:20px;">{apply_link}</p>
        <p style="margin-top:10px;"><a href="/jobs">← До списку вакансій</a></p>
        """
        return render_page(str(title), body)

    @app.route("/jobs/<int:job_id>/apply", methods=["GET", "POST"])
    @role_required("STUDENT")
    def apply(job_id):
        if request.method == "GET":
            body = f"""
            <h1>Відгук на вакансію</h1>
            <form method="POST" action="/jobs/{job_id}/apply">
                <label>Супровідний лист</label>
                <textarea name="cover_letter"></textarea>
                <button class="btn-primary" type="submit">Надіслати</button>
            </form>
            <p style="margin-top:10px;"><a href="/jobs/{job_id}">← Назад до вакансії</a></p>
            """
            return render_page("Відгук на вакансію", body)

        cover_letter = request.form.get("cover_letter", "").strip()
        execute_write(
            """
            INSERT INTO applications (job_id, student_id, cover_letter)
            VALUES (%s, %s, %s)
            """,
            (job_id, current_user()["id"], cover_letter),
        )
        return redirect(f"/jobs/{job_id}?success=Ваш+відгук+успішно+надіслано")

    @app.route("/applications/mine")
    @role_required("STUDENT")
    def my_applications():
        rows = fetch_all(
            """
            SELECT a.id, j.title, j.location, a.status, a.applied_at
            FROM applications a
            JOIN jobs j ON j.id = a.job_id
            WHERE a.student_id = %s
            ORDER BY a.applied_at DESC
            """,
            (current_user()["id"],),
        )

        if rows:
            rows_html = "".join(
                f"""
                <tr>
                    <td>{app_id}</td>
                    <td>{escape(job_title)}</td>
                    <td>{escape(location)}</td>
                    <td>{escape(status)}</td>
                    <td>{escape(applied_at)}</td>
                </tr>
                """
                for app_id, job_title, location, status, applied_at in rows
            )
        else:
            rows_html = "<tr><td colspan='5'>Ви ще не відгукувались на вакансії.</td></tr>"

        body = f"""
        <h1>Мої відгуки на вакансії</h1>
        <table>
            <tr>
                <th>ID заявки</th>
                <th>Вакансія</th>
                <th>Локація</th>
                <th>Статус</th>
                <th>Дата подачі</th>
            </tr>
            {rows_html}
        </table>
        <p style="margin-top:20px;"><a href="/dashboard">← Повернутися в кабінет</a></p>
        """
        return render_page("Мої відгуки", body)

    @app.route("/firma/jobs/new", methods=["GET"])
    @role_required("FIRMA")
    def job_form():
        body = """
        <h1>Нова вакансія</h1>
        <form method="POST" action="/firma/jobs">
            <label>Назва</label>
            <input name="title" required>

            <label>Місце</label>
            <input name="location" required>

            <label>Тип</label>
            <input name="employment_type" required>

            <label>Опис</label>
            <textarea name="description" required></textarea>

            <button class="btn-primary" type="submit">Створити</button>
        </form>
        <p style="margin-top:20px;"><a href="/dashboard">← Повернутися в кабінет</a></p>
        """
        return render_page("Нова вакансія", body)

    @app.route("/firma/jobs", methods=["POST"])
    @role_required("FIRMA")
    def job_submit():
        execute_write(
            """
            INSERT INTO jobs (company_id, title, description, employment_type, location)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                current_user()["id"],
                request.form.get("title", "").strip(),
                request.form.get("description", "").strip(),
                request.form.get("employment_type", "").strip(),
                request.form.get("location", "").strip(),
            ),
        )
        return redirect("/firma/jobs/mine")

    @app.route("/firma/jobs/mine")
    @role_required("FIRMA")
    def firma_jobs():
        rows = fetch_all(
            """
            SELECT id, title, location, is_active
            FROM jobs
            WHERE company_id = %s
            ORDER BY created_at DESC
            """,
            (current_user()["id"],),
        )

        if rows:
            rows_html = ""
            for job_id, title, location, is_active in rows:
                status_label = "Активна" if is_active else "Закрита"
                close_button = ""
                if is_active:
                    close_button = f"""
                    <form method="POST" action="/firma/jobs/{job_id}/close" style="display:inline;">
                        <button class="btn-secondary" type="submit">Закрити вакансію</button>
                    </form>
                    """
                rows_html += f"""
                <tr>
                    <td>{job_id}</td>
                    <td>{escape(title)}</td>
                    <td>{escape(location)}</td>
                    <td>{status_label}</td>
                    <td>{close_button}</td>
                </tr>
                """
        else:
            rows_html = "<tr><td colspan='5'>Поки що немає вакансій.</td></tr>"

        body = f"""
        <h1>Мої вакансії</h1>
        <table>
            <tr>
                <th>ID</th>
                <th>Назва вакансії</th>
                <th>Локація</th>
                <th>Статус</th>
                <th>Дії</th>
            </tr>
            {rows_html}
        </table>
        <p style="margin-top:20px;"><a href="/dashboard">← Назад в кабінет</a></p>
        """
        return render_page("Мої вакансії", body)

    @app.route("/firma/jobs/<int:job_id>/close", methods=["POST"])
    @role_required("FIRMA")
    def close_job(job_id):
        execute_write(
            """
            UPDATE jobs
            SET is_active = FALSE
            WHERE id = %s AND company_id = %s
            """,
            (job_id, current_user()["id"]),
        )
        return redirect("/firma/jobs/mine")

    @app.route("/firma/applications")
    @role_required("FIRMA")
    def firma_applications():
        page = max(request.args.get("page", 1, type=int), 1)
        per_page = 20
        offset = (page - 1) * per_page

        rows = fetch_all(
            """
            SELECT a.id, s.full_name, s.email, j.title, a.cover_letter, a.status, a.applied_at
            FROM applications a
            JOIN users s ON s.id = a.student_id
            JOIN jobs j ON j.id = a.job_id
            WHERE j.company_id = %s
            ORDER BY a.applied_at DESC
            LIMIT %s OFFSET %s
            """,
            (current_user()["id"], per_page, offset),
        )

        if rows:
            rows_html = ""
            for app_id, student_name, student_email, job_title, cover_letter, status, applied_at in rows:
                options_html = "".join(
                    f"<option value='{option}' {'selected' if option == status else ''}>{option}</option>"
                    for option in ALLOWED_APPLICATION_STATUSES
                )
                rows_html += f"""
                <tr>
                    <td>{app_id}</td>
                    <td>{escape(student_name)}</td>
                    <td><a href="mailto:{escape(student_email)}">{escape(student_email)}</a></td>
                    <td>{escape(job_title)}</td>
                    <td>{escape(cover_letter or '—')}</td>
                    <td>
                        <form method="POST" action="/firma/applications/{app_id}/status">
                            <select name="status">{options_html}</select>
                            <button class="btn-secondary" type="submit">Оновити</button>
                        </form>
                    </td>
                    <td>{escape(applied_at)}</td>
                </tr>
                """
        else:
            rows_html = "<tr><td colspan='7'>Поки що немає заявок.</td></tr>"

        prev_link = (
            f"<a href='/firma/applications?page={page - 1}'>← Попередня</a>"
            if page > 1
            else ""
        )
        next_link = (
            f"<a href='/firma/applications?page={page + 1}'>Наступна →</a>"
            if len(rows) == per_page
            else ""
        )
        pagination_html = ""
        if prev_link or next_link:
            pagination_html = f"<div style='margin-top:20px; display:flex; gap:16px;'>{prev_link}{next_link}</div>"

        body = f"""
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
        {pagination_html}
        <p style="margin-top:20px;"><a href="/dashboard">← Повернутися в кабінет</a></p>
        """
        return render_page("Заявки студентів", body)

    @app.route("/firma/applications/<int:app_id>/status", methods=["POST"])
    @role_required("FIRMA")
    def update_application_status(app_id):
        new_status = request.form.get("status")
        if new_status not in ALLOWED_APPLICATION_STATUSES:
            return "Некоректний статус", 400

        execute_write(
            """
            UPDATE applications
            SET status = %s
            WHERE id = %s
              AND job_id IN (
                  SELECT id FROM jobs WHERE company_id = %s
              )
            """,
            (new_status, app_id, current_user()["id"]),
        )
        return redirect("/firma/applications")


def main() -> None:
    app = create_app()
    port = int(os.getenv("PORT", "3000"))
    app.logger.info("Starting CHNU Jobs on port %s", port)
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
