FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal — no GPU, no large model downloads
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./
COPY queuestorm ./queuestorm
COPY reasoning ./reasoning

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

# Bind to 0.0.0.0 so judges can reach the service from outside the container.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
