# Production Deploy Readiness Plan

Date: 2026-04-13
Status: Completed

## Goal

Prepare AI DevStudio for deployment on a shared Ubuntu 24 server without conflicts with existing Docker projects and with Cloudflare Tunnel connected by token.

## Live plan

- [x] Audit the current deployment configuration and identify blockers.
- [x] Redesign the stack to avoid host-port conflicts on the shared server.
- [x] Introduce unique internal service URLs for this project: `http://devstudio-web` and `http://devstudio-app:8000`.
- [x] Add Cloudflare Tunnel service support through `CLOUDFLARE_TUNNEL_TOKEN`.
- [x] Fix build and runtime blockers and validate the final stack configuration.
- [x] Publish the final deployment notes and completion summary.

## Validation summary

- `docker compose --env-file .env.example config` resolves successfully.
- Backend Python modules compile successfully with `py -3 -m compileall backend`.
- Frontend dependencies install successfully with `npm.cmd --prefix frontend ci`.
- Frontend production build succeeds with `npm.cmd --prefix frontend run build`.
- Frontend audit is clean after upgrading to `next@15.5.15`.

## Remaining operator inputs

- Fill the real `.env` values before deployment.
- Provide a valid `CLOUDFLARE_TUNNEL_TOKEN`.
- Run the final Docker image build on the target machine, because Docker daemon validation was not available in this local workspace.
