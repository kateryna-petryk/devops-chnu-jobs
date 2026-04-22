# CHNU Jobs

CHNU Jobs is a student DevOps lab project: a small web application where CHNU students can register, log in, view vacancies, and apply for jobs or internships, while companies can publish vacancies and review applications.

## Chosen stack

This repository now uses **one backend only: Python Flask + PostgreSQL**.

Why this stack was kept:

- the Flask version already had the main business logic
- it supports registration and login
- it supports user roles (`STUDENT`, `FIRMA`, `ADMIN`)
- it has job listing and job application routes
- it already integrates with PostgreSQL
- the Node.js path was incomplete and conflicted with Docker startup

The Node runtime files were removed so the project has one clear startup flow.

## Technologies

- Python 3.11
- Flask
- PostgreSQL 16
- Gunicorn
- Docker
- Docker Compose
- pytest

## Features

- user registration
- user login/logout
- role-based dashboard
- public jobs list
- job details page
- student job applications
- company vacancy creation and application status updates
- `/health` endpoint for app health checking

## Project structure

```text
.
├── backend/
│   ├── app.py
│   ├── db.py
│   ├── models.py
│   └── wsgi.py
├── src/
│   ├── index.html
│   └── css/style.css
├── tests/
│   ├── conftest.py
│   └── test_app.py
├── .dockerignore
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pytest.ini
└── requirements.txt
```

## Local run

1. Create and activate a virtual environment.
2. Install dependencies.
3. Start PostgreSQL.
4. Create `.env` from `.env.example`.
5. Run the app.

Example commands:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m backend.app
```

The app will be available at:

- `http://localhost:3000`

## Environment variables

Example `.env`:

```env
POSTGRES_DB=chnu_jobs
POSTGRES_USER=chnu_jobs
POSTGRES_PASSWORD=chnu_jobs_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
SESSION_SECRET=change-this-secret
PORT=3000
DB_INIT_RETRIES=15
DB_INIT_DELAY=2
```

## Run with Docker Compose

The easiest way to run the lab project:

```bash
docker compose up --build
```

What Compose does:

- starts PostgreSQL in a separate container
- waits until the database is healthy
- starts the Flask app
- automatically creates the database schema during app startup

After startup:

- app: `http://localhost:3000`
- health endpoint: `http://localhost:3000/health`
- postgres: `localhost:5432`

To stop the project:

```bash
docker compose down
```

To stop and remove the database volume:

```bash
docker compose down -v
```

## Tests

Run tests locally:

```bash
pytest
```

The test suite checks:

- homepage route
- health endpoint
- registration + login flow
- jobs page route

The tests use a lightweight fake database connection, so they run without a real PostgreSQL instance.

## Why this fits Lab 1 requirements

- working web application: yes
- connected to database: yes, PostgreSQL
- tests: yes, `pytest`
- containerized with Docker: yes
- fully launched with Docker Compose: yes
- ready to push to GitHub: yes, with cleaned runtime structure and ignore files

## Notes

- Database tables are created automatically when the app starts.
- Docker uses Gunicorn instead of the Flask development server.
- Generated files like `node_modules`, `.venv`, `.DS_Store`, and Python caches should not be committed.
