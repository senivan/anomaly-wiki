FROM python:3.11-slim-bullseye

WORKDIR /app

COPY services/api-gateway/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/api-gateway/ ./

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
