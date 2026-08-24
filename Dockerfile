FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY web/ web/
COPY samples/ samples/

RUN mkdir -p data

EXPOSE 8321

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8321"]
