# FleetSense

Multi-agent fleet operations for trucks and ambulances, powered by an open-weights LLM (DeepSeek).

- **Maintenance agent**: diagnoses the failing part from telemetry + driver report, decides repair vs replace, ranks suppliers on KPIs (price, delivery time, on-time rate, warranty, rating), sends the driver to the nearest depot with a replacement vehicle, computes SLA penalty risk.
- **Fuel agent**: detects overconsumption, fuel-card anomalies, idling, detours; finds the cheapest route (fuel + tolls + driver time).
- **Delay agent**: predicts late deliveries, re-sequences stops, reassigns loads, drafts client notifications.
- **Orchestrator**: routes events between agents (e.g. fuel overconsumption → mechanical cause → maintenance) and writes the audit timeline.

> Team README sections (problem, architecture diagram, demo video) land before submission.

## Run

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows; use .venv/bin/activate on mac/linux
pip install -r requirements.txt
cp ../.env.example ../.env    # add DEEPSEEK_API_KEY
python scripts/seed.py        # regenerates data/*.json
uvicorn app.main:app --reload --port 8000
```

Trigger a scenario: `curl -X POST localhost:8000/scenario/1`, watch `localhost:8000/events`.

## Team workflow

See `shared/contracts.md` (API + SSE) and `backend/app/schemas.py` (models). Branches: `feat/maintenance` (A), `feat/fuel-delay` (B), `feat/frontend` (C). Stay inside the files you own; small PRs into `main`.
