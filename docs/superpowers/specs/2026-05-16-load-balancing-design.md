# Load Balancing & Multiple Replicas Design

**Date:** 2026-05-16  
**Status:** Approved

## Goal

Add health-aware load balancing and multiple service replicas to anomaly-wiki for the course defense. Demonstrate: running 3 replicas per service, automatic failover when a replica goes down, and real-time observability of backend health.

---

## Architecture

### Current Flow
```
Client → API Gateway :8000 → encyclopedia-service:8000
                            → researcher-auth-service:8000
                            → media-service:8000
                            → search-service:8000
```

### New Flow
```
Client → API Gateway :8000 → HAProxy :8001 → encyclopedia-service-1:8000
                                            → encyclopedia-service-2:8000
                                            → encyclopedia-service-3:8000

                           → HAProxy :8002 → researcher-auth-service-1:8000
                                            → researcher-auth-service-2:8000
                                            → researcher-auth-service-3:8000

                           → HAProxy :8003 → media-service-1:8000
                                            → media-service-2:8000
                                            → media-service-3:8000

                           → HAProxy :8004 → search-service-1:8000
                                            → search-service-2:8000
                                            → search-service-3:8000

RabbitMQ → search-indexer-1 (competing consumers)
         → search-indexer-2
         → search-indexer-3
```

HAProxy is a **single container** listening on 4 internal ports (one per service group). Ports 8001–8004 are not exposed to the host — only the api-gateway talks to HAProxy on the internal Docker network. The stats UI at port 8404 is exposed to the host for demo purposes.

---

## Components

### 1. HAProxy Container

- **Image:** `haproxy:2.9-alpine`
- **Config file:** `haproxy/haproxy.cfg` (mounted read-only)
- **Exposed port:** 8404 (stats page only)
- **Internal ports:** 8001–8004 (one per backend service group)
- **Algorithm:** Round-robin
- **Health check:** Active HTTP checks using each service's existing health endpoint
  - `/ready` — encyclopedia-service, media-service
  - `/health` — researcher-auth-service
  - `/readiness` — search-service
- **Stats page:** `http://localhost:8404/stats` — shows live backend status, request counts, up/down state per replica

### 2. Service Replicas (HTTP services)

Each of the 4 HTTP services gets 3 named replicas in docker-compose using YAML anchors to avoid config repetition:

| Service | Replicas | Health endpoint |
|---|---|---|
| encyclopedia-service | 3 | `/ready` |
| researcher-auth-service | 3 | `/health` |
| media-service | 3 | `/ready` |
| search-service | 3 | `/readiness` |

Named pattern: `<service-name>-1`, `<service-name>-2`, `<service-name>-3`

### 3. search-indexer Replicas

`search-indexer` is a RabbitMQ consumer, not an HTTP service. It uses the **competing consumers** pattern — 3 replicas connect to the same queue and RabbitMQ distributes messages between them (each message processed by exactly one consumer). No HAProxy needed. Uses `deploy.replicas: 3`.

### 4. API Gateway Changes

Update environment variables to point at HAProxy instead of direct service hostnames:

| Variable | Old value | New value |
|---|---|---|
| `ENCYCLOPEDIA_BASE_URL` | `http://encyclopedia-service:8000` | `http://haproxy:8001` |
| `RESEARCHER_AUTH_BASE_URL` | `http://researcher-auth-service:8000` | `http://haproxy:8002` |
| `MEDIA_SERVICE_BASE_URL` | `http://media-service:8000` | `http://haproxy:8003` |
| `SEARCH_SERVICE_BASE_URL` | `http://search-service:8000` | `http://haproxy:8004` |

No code changes to the API gateway — only config.

---

## Files to Create / Modify

| File | Action |
|---|---|
| `haproxy/haproxy.cfg` | **Create** — HAProxy config with 4 frontends/backends + stats |
| `docker-compose.yml` | **Modify** — add HAProxy service, replace single services with named replicas, update api-gateway env vars |

---

## HAProxy Config

```
global
    daemon

defaults
    mode http
    timeout connect 5s
    timeout client 10s
    timeout server 10s

frontend encyclopedia_front
    bind *:8001
    default_backend encyclopedia_back

backend encyclopedia_back
    balance roundrobin
    option httpchk GET /ready
    server enc1 encyclopedia-service-1:8000 check
    server enc2 encyclopedia-service-2:8000 check
    server enc3 encyclopedia-service-3:8000 check

frontend auth_front
    bind *:8002
    default_backend auth_back

backend auth_back
    balance roundrobin
    option httpchk GET /health
    server auth1 researcher-auth-service-1:8000 check
    server auth2 researcher-auth-service-2:8000 check
    server auth3 researcher-auth-service-3:8000 check

frontend media_front
    bind *:8003
    default_backend media_back

backend media_back
    balance roundrobin
    option httpchk GET /ready
    server media1 media-service-1:8000 check
    server media2 media-service-2:8000 check
    server media3 media-service-3:8000 check

frontend search_front
    bind *:8004
    default_backend search_back

backend search_back
    balance roundrobin
    option httpchk GET /readiness
    server search1 search-service-1:8000 check
    server search2 search-service-2:8000 check
    server search3 search-service-3:8000 check

listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 5s
```

---

## Docker Compose Structure

### YAML Anchor Pattern (encyclopedia example)

```yaml
x-encyclopedia: &encyclopedia-base
  build: ./services/encyclopedia
  environment:
    - DATABASE_URL=postgresql+asyncpg://admin:admin@db:5432/encyclopedia_db
    - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
  depends_on:
    db:
      condition: service_healthy
    rabbitmq:
      condition: service_healthy
  healthcheck:
    test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/ready').close()\""]
    interval: 5s
    timeout: 5s
    retries: 10
  restart: unless-stopped

encyclopedia-service-1:
  <<: *encyclopedia-base

encyclopedia-service-2:
  <<: *encyclopedia-base

encyclopedia-service-3:
  <<: *encyclopedia-base
```

Same anchor pattern applies to `researcher-auth-service`, `media-service`, `search-service`.

### search-indexer

```yaml
search-indexer:
  build: ./services/search-indexer
  deploy:
    replicas: 3
  restart: on-failure
```

### HAProxy

```yaml
haproxy:
  image: haproxy:2.9-alpine
  volumes:
    - ./haproxy/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
  ports:
    - "8404:8404"
  depends_on:
    - encyclopedia-service-1
    - encyclopedia-service-2
    - encyclopedia-service-3
    - researcher-auth-service-1
    - researcher-auth-service-2
    - researcher-auth-service-3
    - media-service-1
    - media-service-2
    - media-service-3
    - search-service-1
    - search-service-2
    - search-service-3
  restart: unless-stopped
```

---

## Total Container Count

| Group | Count |
|---|---|
| Infrastructure (db, rabbitmq, minio, opensearch) | 4 |
| api-gateway | 1 |
| encyclopedia-service replicas | 3 |
| researcher-auth-service replicas | 3 |
| media-service replicas | 3 |
| search-service replicas | 3 |
| search-indexer replicas | 3 |
| haproxy | 1 |
| frontend | 1 |
| **Total** | **22** |

---

## Defense Demo Script

1. Start all services: `docker compose up`
2. Open HAProxy stats: `http://localhost:8404/stats` — show all 12 replicas green
3. Stop one replica: `docker compose stop encyclopedia-service-2`
4. Watch stats page — `enc2` turns red within seconds
5. Make requests to the app — everything still works (traffic goes to enc1 and enc3)
6. Restart it: `docker compose start encyclopedia-service-2`
7. Watch `enc2` turn green and rejoin the pool

---

## What Is Not Changed

- No code changes to any service
- No code changes to the API gateway (env vars only)
- Infrastructure services (db, rabbitmq, minio, opensearch) remain single-instance
- Frontend remains single-instance
