# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

# Install dependencies before application sources so this layer is reused when
# only the backend or frontend code changes.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend

# The web process has no reason to run as root. Database migrations use the
# same image and only connect to PostgreSQL, so this user is sufficient there.
RUN addgroup --system humary \
    && adduser --system --ingroup humary --home /app humary \
    && chown -R humary:humary /app

USER humary

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
