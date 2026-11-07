FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY scripts ./scripts
COPY tests ./tests
EXPOSE 8000
CMD ["sh", "-c", "uvicorn profitpulse.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
