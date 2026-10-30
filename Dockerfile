FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# psycopg2 builds against libpq; WeasyPrint (PDFs) needs Pango.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libffi-dev \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        fonts-dejavu-core \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Packages added after the base set go in requirements-extra.txt. Changing
# requirements.txt re-downloads all ~160 packages, which over the server's
# slow PyPI link took hours instead of the usual 2 minutes; extras install on
# top of the cached base layer, with a pip cache so only new ones download.
COPY requirements-extra.txt /app/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-extra.txt

COPY . /app/

# Static files are baked into the image and served by WhiteNoise. Settings
# read these at import time; none of them are used by collectstatic.
RUN DEBUG=False SECRET_KEY=build-only DB_NAME=x DB_USER=x DB_PASSWORD=x \
    EMAIL_HOST=x EMAIL_PORT=25 EMAIL_HOST_USER=x EMAIL_HOST_PASSWORD=x \
    CELERY_BROKER_URL=memory:// CELERY_RESULT_BACKEND=cache+memory:// \
    VAPID_PUBLIC_KEY=x VAPID_PRIVATE_KEY=x VAPID_ADMIN_EMAIL=x \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "hrms.asgi:application"]
