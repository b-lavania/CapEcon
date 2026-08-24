# Hooks (so this isn't only a dashboard)

I will not auto-act. Order of operations, on purpose:

1. Slack / a ticket with the GDR and the `rule_trace`
2. `requires_review` on the Decision Inbox (knapsack picks the slots)
3. Open a rollback or "please turn the flag down" request in *their* system
4. Only later, with policy and a human, write traffic weights or disable a capability

| They have | What churnOS does |
| --- | --- |
| GitHub Actions / GitLab / Jenkins | `POST /version-gate` → pass / warn / fail |
| LaunchDarkly / Split / Statsig | Recommend weights. They still own the flag. |
| PagerDuty / Opsgenie | Destructive + `requires_review` can open an incident |
| Langfuse / LangSmith / OTel | We ingest. We don't replace. |

Wire URLs on **CONFIG → Integrations**. Invocations get a row in the SQLite audit table. Delivery to a real Slack webhook is on you — the page logs the intent.

```bash
uvicorn service.app:app --port 8088

curl -sS -X POST http://127.0.0.1:8088/version-gate \
  -H 'content-type: application/json' \
  -d '{"n_prev":100,"s_prev":82,"n_curr":100,"s_curr":61,"eval_delta":-0.12}'
```
