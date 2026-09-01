# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy and install shared package
COPY services/shared /app/services/shared
RUN pip install --no-cache-dir /app/services/shared

# Copy and install consent-processor package
COPY services/consent-processor /app/services/consent-processor
RUN pip install --no-cache-dir /app/services/consent-processor

# Stage 2: Runtime
FROM python:3.12-slim

RUN groupadd -r cms && useradd -r -g cms -d /home/cms -s /sbin/nologin cms

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

USER cms

EXPOSE 8001

CMD ["uvicorn", "consent_processor.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
