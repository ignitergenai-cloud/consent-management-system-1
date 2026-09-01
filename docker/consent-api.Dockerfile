# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy and install shared package
COPY services/shared /app/services/shared
RUN pip install --no-cache-dir /app/services/shared

# Copy and install consent-api package
COPY services/consent-api /app/services/consent-api
RUN pip install --no-cache-dir /app/services/consent-api

# Stage 2: Runtime
FROM python:3.12-slim

RUN groupadd -r cms && useradd -r -g cms -d /home/cms -s /sbin/nologin cms

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

USER cms

EXPOSE 8000

CMD ["uvicorn", "consent_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
