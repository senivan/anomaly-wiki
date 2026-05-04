FROM python:3.12-slim
WORKDIR /app
COPY services/search-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/search-service/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
