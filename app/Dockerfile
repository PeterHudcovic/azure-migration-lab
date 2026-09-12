FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

# Pull current Debian security patches at build time so newly-disclosed OS
# package CVEs (gzip, perl, sqlite, etc.) don't fail the Trivy gate just
# because the base image tag itself hasn't been rebuilt recently.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py db.py k8s_ops.py main.py ./
COPY static ./static

RUN useradd -u 10001 -m appuser
USER 10001

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
