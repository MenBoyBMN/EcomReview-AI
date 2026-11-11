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

EXPOSE 8501

CMD ["streamlit", "run", "src/ecomreview/ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
# CreBy: MenBoyBMN

