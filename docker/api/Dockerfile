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
COPY docker/ ./docker/

RUN useradd -u 1000 -m app && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"

CMD ["uvicorn", "ecomreview.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
# CreBy: MenBoyBMN

