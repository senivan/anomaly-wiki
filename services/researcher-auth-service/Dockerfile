FROM python:3.11-slim-bullseye

WORKDIR /app

# Install system dependencies if needed (e.g., for cryptography/psycopg2)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     && rm -rf /var/lib/apt/lists/*

COPY services/researcher-auth-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the shared package and auth service into the image.
COPY shared ./shared
COPY services/researcher-auth-service/ ./

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
