# How to run the pieces

The analytics live in `analytics/`, `ontology/`, `data/adapters/`, `core/`. Streamlit is a client. The FastAPI app in `service/` is the same functions over HTTP. I am not shipping a multi-tenant SaaS from this repo.

```bash
streamlit run app.py                 # operator UI
uvicorn service.app:app --port 8088  # optional; CI and hooks
```

Retention math does not need to be real-time. Daily/weekly is fine. The only low-latency path I care about is Version Gate as a CI check (`POST /version-gate`).

Records, inbox triage, and hook audit go to SQLite (`ontology/store.py`) plus JSONL. There's no login. Inbox "assignees" are a hardcoded map from `owner_role` → a display name in `analytics/inbox.py`. That's enough to demo routing. SSO is a later problem.

I don't want prompt bodies leaving the machine, which is why ingest is local and the adapters scrub. If someone needs VPC, they run this themselves.

How you charge for it is a conversation, not a page on this repo. I'm not going to put "percent of churn saved" on a slide — we couldn't verify it, and it fights [honesty.md](honesty.md).
