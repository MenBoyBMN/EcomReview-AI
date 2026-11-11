FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    DEMO_CACHE_MODE=true

COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY src/ ./src/
COPY knowledge/ ./knowledge/
COPY prompts/ ./prompts/
COPY data/ ./data/
COPY scripts/ ./scripts/

EXPOSE 8000

CMD ["uvicorn", "ecomreview.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
# CreBy: MenBoyBMN

