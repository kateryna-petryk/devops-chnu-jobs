// backend/server.js
const path = require("path");
const express = require("express");
const session = require("express-session");
const bcrypt = require("bcryptjs");
const { initDb, query } = require("./db");
require("dotenv").config();

const app = express();
const PORT = process.env.APP_PORT || 3000;

// ---------- Middleware ----------

// для форм
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// сесії
app.use(
  session({
    secret: process.env.SESSION_SECRET || "chnu-jobs-secret",
    resave: false,
    saveUninitialized: false
  })
);

// статика (landing page)
app.use(express.static(path.join(__dirname, "..", "src")));

// ---------- Helpers ----------

function requireAuth(req, res, next) {
  if (!req.session.user) {
    return res.redirect("/login");
  }
  next();
}

function requireRole(role) {
  return function (req, res, next) {
    if (!req.session.user || req.session.user.role !== role) {
      return res
        .status(403)
        .send("<h1>403 Forbidden</h1><p>Недостатньо прав доступу.</p>");
    }
    next();
  };
}

// ---------- Auth routes ----------

app.get("/register", (req, res) => {
  res.send(`
    <html lang="uk">
      <head>
        <meta charset="UTF-8" />
        <title>Реєстрація – ЧНУ Jobs</title>
      </head>
      <body style="font-family: system-ui; margin: 2rem;">
        <h1>Реєстрація користувача</h1>
        <p>Оберіть ваш тип: студент ЧНУ або компанія (Firma).</p>
        <form method="POST" action="/register">
          <div>
            <label>Повне ім'я:</label><br />
            <input type="text" name="full_name" required />
          </div>
          <div>
            <label>Email:</label><br />
            <input type="email" name="email" required />
          </div>
          <div>
            <label>Пароль:</label><br />
            <input type="password" name="password" required />
          </div>
          <div>
            <label>Тип користувача:</label><br />
            <select name="role" required>
              <option value="STUDENT">Student (студент ЧНУ)</option>
              <option value="FIRMA">Firma (компанія)</option>
            </select>
          </div>
          <button type="submit" style="margin-top:1rem;">Зареєструватися</button>
        </form>
        <p>Вже маєте акаунт? <a href="/login">Увійти</a></p>
      </body>
    </html>
  `);
});

app.post("/register", async (req, res) => {
  const { full_name, email, password, role } = req.body;

  if (!["STUDENT", "FIRMA"].includes(role)) {
    return res.status(400).send("Некоректна роль користувача.");
  }

  try {
    const passwordHash = await bcrypt.hash(password, 10);

    await query(
      `INSERT INTO users (full_name, email, password_hash, role)
       VALUES ($1, $2, $3, $4)`,
      [full_name, email, passwordHash, role]
    );

    // Отримаємо щойно створеного користувача
    const result = await query(
      `SELECT id, full_name, email, role FROM users WHERE email = $1`,
      [email]
    );
    const user = result.rows[0];

    req.session.user = user;
    res.redirect("/dashboard");
  } catch (err) {
    console.error(err);
    if (err.message.includes("duplicate key value")) {
      return res.send(
        'Користувач з таким email уже існує. <a href="/register">Спробувати ще раз</a>'
      );
    }
    res.status(500).send("Помилка сервера.");
  }
});

app.get("/login", (req, res) => {
  res.send(`
    <html lang="uk">
      <head>
        <meta charset="UTF-8" />
        <title>Вхід – ЧНУ Jobs</title>
      </head>
      <body style="font-family: system-ui; margin: 2rem;">
        <h1>Вхід до системи</h1>
        <form method="POST" action="/login">
          <div>
            <label>Email:</label><br />
            <input type="email" name="email" required />
          </div>
          <div>
            <label>Пароль:</label><br />
            <input type="password" name="password" required />
          </div>
          <button type="submit" style="margin-top:1rem;">Увійти</button>
        </form>
        <p>Ще не зареєстровані? <a href="/register">Створити акаунт</a></p>
      </body>
    </html>
  `);
});

app.post("/login", async (req, res) => {
  const { email, password } = req.body;

  try {
    const result = await query(
      `SELECT * FROM users WHERE email = $1`,
      [email]
    );
    const user = result.rows[0];

    if (!user) {
      return res.send(
        'Невірний email або пароль. <a href="/login">Спробувати ще раз</a>'
      );
    }

    const isMatch = await bcrypt.compare(password, user.password_hash);
    if (!isMatch) {
      return res.send(
        'Невірний email або пароль. <a href="/login">Спробувати ще раз</a>'
      );
    }

    req.session.user = {
      id: user.id,
      full_name: user.full_name,
      email: user.email,
      role: user.role
    };

    res.redirect("/dashboard");
  } catch (err) {
    console.error(err);
    res.status(500).send("Помилка сервера.");
  }
});

app.post("/logout", (req, res) => {
  req.session.destroy(() => {
    res.redirect("/");
  });
});

// ---------- Домашні сторінки-заглушки ----------

app.get("/dashboard", requireAuth, (req, res) => {
  const user = req.session.user;

  let content = "";
  if (user.role === "ADMIN") {
    content = `
      <h2>Адмін-панель ЧНУ Jobs</h2>
      <p>Ви увійшли як адміністратор: <strong>${user.full_name}</strong></p>
      <ul>
        <li>У майбутньому: керування користувачами</li>
        <li>Модерація вакансій</li>
        <li>Налаштування системи</li>
      </ul>
    `;
  } else if (user.role === "STUDENT") {
    content = `
      <h2>Кабінет студента ЧНУ</h2>
      <p>Вітаємо, <strong>${user.full_name}</strong>!</p>
      <p>У майбутньому тут будуть:</p>
      <ul>
        <li>Список вакансій, практик та стажувань;</li>
        <li>Ваші заявки та їх статус;</li>
        <li>Налаштування профілю.</li>
      </ul>
    `;
  } else if (user.role === "FIRMA") {
    content = `
      <h2>Кабінет компанії (Firma)</h2>
      <p>Ви залогінені як представник компанії: <strong>${user.full_name}</strong></p>
      <p>У майбутньому тут будуть:</p>
      <ul>
        <li>Створення вакансій та програм практики;</li>
        <li>Перегляд заявок студентів ЧНУ;</li>
        <li>Оновлення статусу заявок.</li>
      </ul>
    `;
  }

  res.send(`
    <html lang="uk">
      <head>
        <meta charset="UTF-8" />
        <title>Особистий кабінет – ЧНУ Jobs</title>
      </head>
      <body style="font-family: system-ui; margin: 2rem;">
        <h1>ЧНУ Jobs – особистий кабінет</h1>
        <p><strong>Роль:</strong> ${user.role}</p>
        ${content}
        <form method="POST" action="/logout" style="margin-top: 1.5rem;">
          <button type="submit">Вийти</button>
        </form>
        <p style="margin-top:1rem;"><a href="/">Повернутися на головну</a></p>
      </body>
    </html>
  `);
});

// ---------- Адмін-сторінка користувачів (тільки ADMIN) ----------

app.get("/admin/users", requireRole("ADMIN"), async (req, res) => {
  try {
    const result = await query(
      `SELECT id, full_name, email, role, created_at FROM users ORDER BY id`
    );

    const rowsHtml = result.rows
      .map(
        (u) => `
        <tr>
          <td>${u.id}</td>
          <td>${u.full_name}</td>
          <td>${u.email}</td>
          <td>${u.role}</td>
          <td>${u.created_at}</td>
        </tr>`
      )
      .join("");

    res.send(`
      <html lang="uk">
        <head>
          <meta charset="UTF-8" />
          <title>Користувачі – Адмін ЧНУ Jobs</title>
        </head>
        <body style="font-family: system-ui; margin: 2rem;">
          <h1>Список користувачів (ADMIN)</h1>
          <table border="1" cellpadding="6" cellspacing="0">
            <thead>
              <tr>
                <th>ID</th>
                <th>Ім'я</th>
                <th>Email</th>
                <th>Роль</th>
                <th>Створено</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml}
            </tbody>
          </table>
          <p style="margin-top:1rem;"><a href="/dashboard">← Повернутися в кабінет</a></p>
        </body>
      </html>
    `);
  } catch (err) {
    console.error(err);
    res.status(500).send("Помилка сервера.");
  }
});

// ---------- Старт сервера ----------

async function startServer() {
  const maxRetries = 10;      // максимум 10 спроб
  const delayMs = 3000;       // пауза між спробами 3 секунди

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`Спроба підключення до БД №${attempt}...`);
      await initDb();
      console.log("✔ Підключення до БД успішне, таблиця users готова.");
      
      app.listen(PORT, () => {
        console.log(`ЧНУ Jobs працює на http://localhost:${PORT}`);
      });
      return; // виходимо з функції, все добре
    } catch (err) {
      console.error("Помилка ініціалізації БД:", err.message);

      if (attempt === maxRetries) {
        console.error("❌ Не вдалося підключитися до БД після кількох спроб. Вихід.");
        process.exit(1);
      }

      console.log(`Очікування ${delayMs / 1000} сек перед наступною спробою...`);
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
}

startServer();
