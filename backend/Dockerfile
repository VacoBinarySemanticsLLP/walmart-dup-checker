# ── Stage 1: Build ──
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r dupcheck && useradd -r -g dupcheck -d /app -s /sbin/nologin dupcheck

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Only copy the app code — no secrets, no node_modules, no git
COPY main.py .
COPY rule_compiler.py .
COPY rules.json .

# Give the non-root user write access so it can save the AI response cache
RUN chown -R dupcheck:dupcheck /app

# Runtime optimizations
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

USER dupcheck

CMD ["python", "main.py"]
