# Why the repo is shaped this way

I don't want churnOS to be an agent runtime. LangGraph, CrewAI, and a dozen others already run the loop. Langfuse / LangSmith already store traces. Stripe already invoices.

What's missing is the join: traces × verified outcomes × trust × what it cost to serve. From that join you should be able to answer, for a capability or a version, **ship, hold, throttle, roll back, or make a human look**. I will not let a correlation dress up as a cause. That's what `claim_type` is for.

The screen I care about first is **Version Gate**. "Did this change make things better or worse?" If that sentence isn't true on someone's data, the rest of the pages are decoration.

## What actually goes wrong

A prompt or model swap ships. Traces still look green. Outcome success on one customer segment falls off and nobody notices for weeks. People stop delegating before they cancel. Traditional analytics sees logins drop and has no idea why.

Power users hammer the agent. Each successful outcome costs more than you charge. NRR in Stripe looks heroic. Contribution-margin NRR is negative.

Two hundred runs in the review queue. Twenty of them matter. FIFO burns the team.

Evals passed. Canary looked fine on average. Two weeks later it breaks on one account's data shape.

Agent A called Agent B called a connector. Something failed. Nobody owns it, and you can't see the blast radius.

## Who this is even for

Someone already running internal agents, not a slide deck. Usually the person who got stuck owning "agent ops" plus whoever owns flags and traces.

If they can't name a verified outcome, the useful thing to do is the Outcome Definition page and an instrumentation checklist — not a fake Version Gate on five runs.

## What this is not

Not a chat UI. Not a scheduler. Not a Langfuse replacement. Not an auto-rollback bot. I will log a Slack message and put `requires_review` on a record before I ever write a flag weight.

The join and the claim types are in [contracts.md](contracts.md) and [honesty.md](honesty.md). Outcomes are in [outcome_contract.md](outcome_contract.md). The longer argument is [methodology.md](methodology.md).
