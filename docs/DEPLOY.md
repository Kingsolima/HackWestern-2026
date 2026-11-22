# Deploying to Vultr

One Ubuntu VM runs the stack with Docker Compose. **Caddy** (`web`) is the only public service:
it serves the built website and forwards `/api/*` + `/health` to the backend and `/cad/*` to the
CAD worker, the same routes the Vite dev proxy uses. Backend and CAD have no public ports.

Files: [deploy/Caddyfile](../deploy/Caddyfile), [deploy/web.Dockerfile](../deploy/web.Dockerfile),
[docker-compose.prod.yml](../docker-compose.prod.yml).

## Try the production stack locally first

```bash
make prod-up      # http://localhost:8080 (separate project, doesn't touch your dev containers)
make prod-down
```

## One-time setup

1. **VM**: Vultr Cloud Compute, Toronto, Ubuntu 24.04, 2 vCPU / 4 GB (the CAD image is ~2 GB and
   builds on the server). Add the deploy SSH key (`~/.ssh/vultr_hackwestern.pub`).
2. **SSH alias** on your laptop (`~/.ssh/config`):
   ```
   Host vultr-hw
     HostName <VM IP>
     User root
     IdentityFile ~/.ssh/vultr_hackwestern
   ```
3. **Server packages, firewall, code**:
   ```bash
   ssh vultr-hw 'curl -fsSL https://get.docker.com | sh && ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw --force enable && git clone https://github.com/Kingsolima/HackWestern-2026.git /opt/hackwestern'
   ```
4. **Secrets** (from your laptop; never paste them into a chat or commit them):
   ```bash
   scp .env vultr-hw:/opt/hackwestern/.env
   ssh vultr-hw 'echo LIVE_JOBS_TOKEN=$(openssl rand -hex 16) >> /opt/hackwestern/.env && chmod 600 /opt/hackwestern/.env'
   ssh vultr-hw 'grep LIVE_JOBS_TOKEN /opt/hackwestern/.env'   # keep this for the demo
   ```
5. **Start it**:
   ```bash
   make deploy
   ```
   The site is now on `http://<VM IP>`.

## Domain + HTTPS (GoDaddy)

1. In GoDaddy → DNS: **A** record `@` → VM IP, and **A** record `www` → VM IP.
2. On the server, add the domain to `.env` and restart Caddy:
   ```bash
   ssh vultr-hw "echo 'SITE_ADDRESS=example.com, www.example.com' >> /opt/hackwestern/.env"
   make deploy
   ```
   Caddy gets a Let's Encrypt certificate by itself once DNS resolves to the VM.

## Live jobs

Replay jobs are open to everyone. Live jobs spend TinyFish credit, so the server requires the
`X-Live-Token` header (`REQUIRE_LIVE_TOKEN=true` in the prod compose). Open the site with
`?live=1`, click **Run live** and enter the token once. Live runs are recorded to
`data/recordings` on the server so they can be replayed later.

## Updating

Merge to `main`, then `make deploy` (git pull + rebuild). Logs:
`ssh vultr-hw 'cd /opt/hackwestern && docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail 50'`.

## Tiger Data (Postgres)

The backend reads `DATABASE_URL` from the server's `.env` (the production compose file passes it
through; without it the backend falls back to the local `db` service, which production does not
start). Two settings, both in `.env`:

- `DATABASE_URL`: the Tiger Cloud connection string.
- `TIGER_ENABLED=true`: keep the board and `agent_runs` in Tiger Data. The backend applies
  `db/schema.sql` at startup and will not start if the database is unreachable. Left out or
  `false`, facts stay in memory and the database is only health-checked.

`GET /health/db` answers 200 when the backend can reach the database and 503 when it cannot.
`/health` does not depend on the database.

## Check a deploy

```bash
make smoke HOST=http://<VM IP>     # or HOST=http://localhost:8080 after make prod-up
```

It checks the backend, the database, the website and the three starter 3D models, then runs one
replay job per demo path (wheeled demo, AR4 club, Stretch, an onboarded company) and fails unless
each ends `DONE`. Replay jobs spend nothing. Recordings reach the server only through git, so a
replay that passes locally and fails on the server usually means a recording was not committed.

## Not deployed yet

Vultr Object Storage: no code uses it yet (CAD files are on the VM's disk). Add `S3_*` to the
server's `.env` when that lands.
