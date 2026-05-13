# Running Anomaly Wiki

## Prerequisites

- Docker + Docker Compose
- Node.js 20+ and npm (for local frontend dev only)
- `openssl` CLI (for key generation)

---

## 1. Generate the RSA signing key

The auth service signs JWTs with an RSA private key that must exist on disk before
any container starts. Generate it once:

```bash
mkdir -p services/researcher-auth-service/secrets
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out services/researcher-auth-service/secrets/rsa_private.pem
```

The docker-compose mounts this directory read-only at `/etc/secrets/auth/` inside
the container (see the `volumes` entry for `researcher-auth-service`).

---

## 2. Create the environment file

```bash
cp .env.example .env
```

Edit `.env` if you want non-default credentials. The defaults work out of the box
for local development.

---

## 3. Start the backend stack

```bash
docker compose up --build
```

This starts:

| Service | Exposed port |
|---|---|
| PostgreSQL | 5432 |
| RabbitMQ (AMQP) | 5672 |
| RabbitMQ Management UI | 15672 |
| MinIO API | 9000 |
| MinIO Console | 9001 |
| OpenSearch | 9200 |
| API Gateway | **8000** |

All services depend on their upstream dependencies being healthy before they start.
First boot is slower (~2 min) because OpenSearch initialises its index.

Health check:

```bash
curl http://localhost:8000/health
```

---

## 4. Start the frontend

### Option A — dev server (recommended for development)

```bash
cd frontend
npm install        # first time only
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The frontend reads `NEXT_PUBLIC_GATEWAY_URL` from `frontend/.env.local`
(already set to `http://localhost:8000`). No changes needed.

### Option B — production build (Docker)

Add the following service to `docker-compose.yml` (or run standalone):

```bash
docker build \
  --build-arg NEXT_PUBLIC_GATEWAY_URL=http://localhost:8000 \
  -t anomaly-wiki-frontend \
  frontend/

docker run -p 3000:3000 anomaly-wiki-frontend
```

---

## 5. Create the first account

1. Open [http://localhost:3000/register](http://localhost:3000/register).
2. Register with any email + password (≥ 8 chars).
3. All new accounts receive the **Researcher** role.
4. To promote a user to **Editor** or **Admin**, update the `role` column directly
   in the `auth_db.user` table via psql or any Postgres client:

```sql
-- connect: psql -h localhost -U admin -d auth_db
UPDATE "user" SET role = 'editor' WHERE email = 'your@email.com';
```

---

## Stopping the stack

```bash
docker compose down          # stop containers, keep volumes
docker compose down -v       # stop and delete all data volumes
```

---

## Service URLs at a glance

| URL | What it is |
|---|---|
| http://localhost:3000 | Frontend |
| http://localhost:8000/docs | API Gateway interactive docs (Swagger) |
| http://localhost:9001 | MinIO console (admin / admin123) |
| http://localhost:15672 | RabbitMQ management (guest / guest) |
| http://localhost:9200 | OpenSearch REST API |
