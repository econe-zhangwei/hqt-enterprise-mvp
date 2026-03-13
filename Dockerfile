FROM node:20-alpine AS frontend-builder

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json /app/frontend/
RUN cd frontend && npm ci

COPY frontend /app/frontend
COPY app /app/app
RUN cd frontend && npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY app /app/app
COPY .env.example /app/.env.example
COPY --from=frontend-builder /app/app/static/react /app/app/static/react
RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["sh", "-c", "mkdir -p data && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
