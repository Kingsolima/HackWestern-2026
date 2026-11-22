# AI Robot Redesign Engine (Hack Western 13)

Tell it a robot's drive motor has to be replaced to meet US sourcing rules. TinyFish agents find real NEMA replacement motors and verify them on the vendors' sites. Code checks the engineering, and CadQuery regenerates the motor bracket to fit the new motor.

- Plan, demo script and team split: [docs/HANDOFF-v2.md](docs/HANDOFF-v2.md)
- Architecture, schemas and repo layout: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Entire workflow (branch + Trail per feature): [docs/ENTIRE.md](docs/ENTIRE.md)
- Agent rules: [AGENTS.md](AGENTS.md)

## Prerequisites

Node 22, [uv](https://docs.astral.sh/uv/), Docker. You don't need CadQuery or OCCT locally because they only run in Docker.

## Quickstart

```bash
cp .env.example .env              # fill in keys; never commit .env or paste keys into prompts
make install                      # backend (uv) + frontend (npm) deps
make db                           # local TimescaleDB with db/schema.sql applied
docker compose up -d --build cad  # CAD worker on :8001
make dev-backend                  # FastAPI on :8000  (docs at /docs)
make dev-frontend                 # Vite on :5173, proxies /api to :8000 and /cad to :8001
```

Make a sample model for the viewer:

```bash
curl -X POST localhost:8001/build -H 'content-type: application/json' -d '{"design_id":"test_23"}'
```

`make test` runs the backend tests. `make lint` runs ruff and oxlint. `make up` runs the full stack in Docker.

If ROS (or anything else) sets `PYTHONPATH` in your shell, use the `make` targets, which unset it. Otherwise pytest loads foreign plugins.

## Deploying (Vultr)

See [docs/DEPLOY.md](docs/DEPLOY.md). Short version: `make prod-up` to try the production stack
locally on :8080, `make deploy` to update the VM.

## Working on a feature

```bash
git switch main && git pull
git switch -c <feature-branch>
entire trail create --title "<feature>" --type feature
```

Commits must not credit any AI as an author (see [AGENTS.md](AGENTS.md)).
