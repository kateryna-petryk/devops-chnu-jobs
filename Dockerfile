FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY src ./src

EXPOSE 3000

CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:3000", "backend.wsgi:app"]
