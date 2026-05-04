FROM python:3.12-slim
WORKDIR /app
COPY services/search-indexer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/search-indexer/ .
CMD ["python", "main.py"]
