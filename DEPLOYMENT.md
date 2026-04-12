# Production Deployment

This stack is prepared for deployment on a shared Ubuntu 24 server that already runs other Dockerized projects.

## Key decisions

- No host ports are published by this project.
- Cloudflare Tunnel runs inside the stack via `CLOUDFLARE_TUNNEL_TOKEN`.
- The internal service URLs for this project are unique:
  - `http://devstudio-web`
  - `http://devstudio-app:8000`

This avoids collisions with neighboring projects already using `http://web` and `http://app:8000`.

## Required environment setup

1. Copy `.env.example` to `.env`.
2. Fill in all real credentials and secrets.
3. Set `CLOUDFLARE_TUNNEL_TOKEN`.
4. When pasting a bcrypt hash into `ADMIN_PASSWORD_HASH`, escape every `$` as `$$`.

## Deploy

```bash
docker compose pull
docker compose build
docker compose up -d
docker compose exec devstudio-app python seed.py
```

## Verify

```bash
docker compose ps
docker compose logs devstudio-app --tail=100
docker compose logs devstudio-web --tail=100
docker compose logs cloudflared --tail=100
```

## Notes

- `devstudio-web` is the only HTTP entrypoint for the tunnel.
- `devstudio-app` is kept internal and is reachable only inside the project network.
- `frontend`, `postgres`, `redis`, and `minio` are also internal-only services.
