# --- stage 1: install python packages ---
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- stage 2: small final image ---
FROM python:3.12-slim
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# non-root user, so a hacked app cannot do much on the container
RUN useradd --create-home --uid 10001 appuser
WORKDIR /srv
COPY --from=builder /install /usr/local
COPY app ./app

USER appuser
EXPOSE 8000

# python is used for the check because slim image has no curl
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready')" || exit 1

# create tables / seed once, then start the server
CMD ["sh", "-c", "python -m app.db && exec gunicorn --bind 0.0.0.0:8000 --workers 2 --access-logfile - 'app.main:app_factory()'"]
