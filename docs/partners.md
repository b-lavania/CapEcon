# Who this is useful to talk to

I need two or three teams that already have agents in production (or a real canary), not a pilot that lives in a deck.

Before I promise Version Gate statistics they should have:

- traces or logs that can fill `runs` / `spans`
- a named verified outcome, or a willingness to sit through Outcome Definition
- some cost signal — per-run, or at least a monthly bill we can allocate
- enough volume that five runs isn't the whole study

If they can't define an outcome, the work is instrumentation. If they don't have volume, don't fake a p-value.

Shapes that match the warehouse:

1. **Ops / quoting.** Something with a deterministic downstream step (rate engine, booking). Join is run → verified quote → subscription.
2. **CRM / workspace copilot.** Connectors, HITL, a bill that keeps going up. Join is trust + dismiss rate + cost per successful outcome.
3. **A router plus specialists.** The pain is "who owns this handoff." Join is the connector / capability graph → a subgraph record.

Questions I'd actually ask, instead of guessing: OTel GenAI attributes or framework-specific dumps? Cost per run or just the invoice? How many HITL reviews in a week? Do they need this on their network from day one? And who has to care — the person owning agents, platform, or finance — because that decides whether I open Version Gate or the Executive Summary first.
