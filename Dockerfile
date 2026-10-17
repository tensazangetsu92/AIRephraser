# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

# Install dependencies before application sources so this layer is reused when
# only the backend or frontend code changes.
# GigaChat API certificates use the Russian Ministry of Digital Development
# trust chain. The root CA is installed for both the OS and Python/httpx.
COPY backend/requirements.txt ./requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && curl --fail --silent --show-error --location \
        "https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt" \
        --output /usr/local/share/ca-certificates/russian_trusted_root_ca_pem.crt \
    && update-ca-certificates \
    && python -c "from pathlib import Path; import certifi; certificate = Path('/usr/local/share/ca-certificates/russian_trusted_root_ca_pem.crt').read_bytes(); bundle = Path(certifi.where()); bundle.write_bytes(bundle.read_bytes().rstrip(b'\\n') + b'\\n' + certificate.rstrip(b'\\n') + b'\\n')"

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
