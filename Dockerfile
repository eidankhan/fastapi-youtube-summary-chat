# ========================
# 1️⃣ Builder Stage
# ========================
FROM python:3.11-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ========================
# 2️⃣ Final Stage
# ========================
FROM python:3.11-slim
WORKDIR /app

COPY --from=builder /install /usr/local
COPY app ./app

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]