"""In-app explainers — how churnOS works and what numbers mean."""

from __future__ import annotations

import streamlit as st

from ui.magazine import load_magazine_css, section_kicker

# Surface-specific one-liners for DECISIONS pages
SURFACE_EXPLAINERS: dict[str, dict[str, str]] = {
    "radar": {
        "title": "What this screen is",
        "body": (
            "The weekly meeting, rendered. Each card is a **GrowthDecisionRecord** for one "
            "capability (skill, automation, agent tool): what’s wrong, what it may cost to "
            "leave live, and what to do. Radar ranks cost of leaving live and margin risk — "
            "Numbers come from the synthetic workspace — not "
            "production agents — until you connect real event data. "
            "not willingness to pay. Value/surplus captions appear when the value ledger has data."
        ),
    },
    "profile": {
        "title": "What this screen is",
        "body": (
            "Pick a product shape — personal assistant, CRM workspace, ops missions, "
            "metered agent API, or marketplace (agent-assisted GMV). That choice switches "
            "ontology semantics and the **fake** rates used to generate seats, runs, "
            "approvals, and churn. Press **Generate workspace** before any other screen has data. "
            "In production this warehouse would be LangSmith-class traces + ChartMogul-class billing. "
            "Today it is authored priors."
        ),
    },
    "activation": {
        "title": "What this measures",
        "body": (
            "**Activation** = share of seats that got a first trusted successful run. "
            "**Weekly delegation habit** (your OEC) = among activated seats, share that "
            "keep running successfully each week. Cards here filter for activation leaks "
            "and habit collapse only."
        ),
    },
    "trust": {
        "title": "What this measures",
        "body": (
            "**Trust incidents** = runs flagged as scary/wrong (`trust_flag`). "
            "**Dismiss rate** = humans rejecting agent proposals — high dismiss often means "
            "approval fatigue or low trust. Cards filter for `trust_break` and `approval_fatigue`."
        ),
    },
    "run_economics": {
        "title": "What this measures",
        "body": (
            "**$/successful run** vs **seat ARPU** — if run cost eats willingness to pay, "
            "the capability is uneconomic even if users like it. Cards filter for "
            "`run_cost_blowout` and CAC/LTV-style contradictions. Rigorous mode adds "
            "token VaR/CVaR tail risk."
        ),
    },
    "marketplace_radar": {
        "title": "What this measures",
        "body": (
            "Agent-assisted marketplace transactions: GMV, platform take, inference cost, "
            "and net margin per workflow/seller. Cards use `platform_margin_at_risk_usd` "
            "and throttle uneconomic agent assists."
        ),
    },
    "clinical_radar": {
        "title": "What this measures",
        "body": (
            "Clinical SDK capabilities (OpenMed v2.2 case study): residual risk priced as "
            "inference + review labor + expected harm. Cards use `residual_clinical_risk_usd`. "
            "Separate from main Radar — same capability may appear on both surfaces."
        ),
    },
    "math_drift": {
        "title": "What this measures",
        "body": (
            "Distributional drift (KL/JS) between outcome mix windows and a CUSUM "
            "change-point on weekly success rate. Complements slope-based `quality_drift` on Radar."
        ),
    },
    "math_packaging": {
        "title": "What this measures",
        "body": (
            "Teaching sensitivity: margin per outcome and a **synthetic** conversion curve vs list price. "
            "Not conjoint or Van Westendorp — use external research for demand discovery. "
            "Floor comes from the price block; list/take from your contract or sliders."
        ),
    },
    "connector": {
        "title": "What this measures",
        "body": (
            "Tool/integration failures (Gmail, HubSpot, MCP, etc.) that block jobs-to-be-done. "
            "Blast radius = how many capabilities depend on a fragile connector. "
            "Cards filter for `connector_fragility`."
        ),
    },
    "flywheel": {
        "title": "What this measures",
        "body": (
            "After you decide (ship / hold / throttle…), write back **retention Δ** and "
            "**churn happened** onto the record. Today this is a **simulated** 14-day "
            "write-back on synthetic seats — it demos the closed loop, not real causality."
        ),
    },
    "semantics": {
        "title": "What this is",
        "body": (
            "Agent-readable glossary **and** governing rules (`semantics.yaml`): "
            "verdict rules, action maps, and classification thresholds. "
            "Edit sample values in YAML → regenerate workspace → Radar decisions change. "
            "Not a dashboard — the policy layer agents and humans share."
        ),
    },
    "taxonomy": {
        "title": "What this is",
        "body": (
            "Exception categories (activation leak, trust break, …), owners, and playbook "
            "hints. Taxonomy first, then semantics, then schema — the ontology recipe."
        ),
    },
    "inspector": {
        "title": "What this is",
        "body": (
            "Raw `GrowthDecisionRecord` inspection: validate against schema, override "
            "actions, see SQLite + JSONL persistence. Audit surface for the decision object."
        ),
    },
    "data_connect": {
        "title": "What this screen is",
        "body": (
            "Upload an OTel JSONL or Langfuse dump (prompt bodies get stripped), a Vision "
            "bakeoff `run.json` plus historic jobs JSONL, and optional CSVs for accounts / "
            "outcomes / subscriptions. Vision Agent is two records: bakeoff API $ is the "
            "agent floor (`estimated`); historic `price_dollars` is the move invoice. "
            "If subscriptions are missing, CM-NRR just isn't available — that's fine. "
            "There's a synthetic demo button if you don't have files yet."
        ),
    },
    "outcome_kit": {
        "title": "What this screen is",
        "body": (
            "What does success mean, in a way you can verify? If you can't name that, "
            "don't pretend Version Gate is doing retention. `verified_by` is "
            "`deterministic_stage`, `human_confirmation`, `llm_judge`, or `webhook`."
        ),
    },
    "version_gate": {
        "title": "What this screen is",
        "body": (
            "Should this version **ship, hold, or roll back**? Eval delta, canary SPRT, "
            "then a GDR you can drop in the Inbox. CI can hit the same function at "
            "`POST /version-gate`."
        ),
    },
    "inbox": {
        "title": "What this screen is",
        "body": (
            "Same GrowthDecisionRecords as Radar, with a status (pending / in review / resolved). "
            "Filter by owner. The knapsack line is 'you only have N HITL slots this week.'"
        ),
    },
    "subgraph": {
        "title": "What this measures",
        "body": (
            "When one agent hands to another: success rate on that edge, extra cost of "
            "coordination, retries, tasks that never finish, connector blast radius. "
            "A subgraph GDR can recommend kill, but it still `requires_review`."
        ),
    },
    "executive": {
        "title": "What this screen is",
        "body": (
            "The 3–5 decisions with the highest cost of leaving live, plus a handful of "
            "pinned metrics. Every number keeps its claim type. Download markdown, or copy "
            "the Slack JSON — print-to-PDF if you need a file."
        ),
    },
    "integrations": {
        "title": "What this screen is",
        "body": (
            "Slack first, then require_review, then PagerDuty, then a CI check. "
            "I will not write your feature flags. This page stores URLs and logs that you asked."
        ),
    },
    "concepts": {
        "title": "What this is",
        "body": (
            "Human-facing playbook compiled from ontology semantics + the governed metric "
            "lexicon. Same meanings as agents get — not a separate encyclopedia."
        ),
    },
}

VERDICT_GLOSS = {
    "healthy": "No ranked exceptions above threshold — safe to keep shipping.",
    "leaking": "Activation or habit problems — value unfinished for many seats.",
    "destructive": "Usage correlates with churn / trust damage — throttle or rollback.",
    "uneconomic": "Run cost or growth economics break policy even if UX looks fine.",
    "underpowered": "Signal exists but not decision-grade yet — hold and gather evidence.",
    "needs_review": "Low confidence — a human should confirm before acting.",
}

ACTION_GLOSS = {
    "ship": "Promote / raise traffic.",
    "hold": "Freeze rollout; gather evidence.",
    "throttle": "Cap % traffic, rate, or tool budget.",
    "shadow": "Run offline / no user-visible side effects.",
    "rollback": "Revert to last known-good version.",
    "kill": "Remove from the product surface.",
    "experiment": "Force a governed test before further ship.",
    "revise": "Change prompt/tool/policy; re-enter eval.",
    # Commercial — change the price or the packaging, not the runtime. Always reviewed.
    "hold_sku": "Freeze this outcome SKU; stop selling more of it on this version.",
    "raise_list": "List sits below the floor — open a price-book change.",
    "split_tier": "Fence the expensive cohort; all-inclusive is subsidising it.",
    "cut_credits": "The included bucket or credit grant is the leak.",
    "kill_all_inclusive": "A flat bucket cannot cover this capability.",
    "reallocate": "Routing / retry tax is the leak — change routing before price.",
}

PAIN_MAP_ROWS: list[tuple[str, str, str, str]] = [
    (
        "Cost / margin",
        "Cost per span / user; no ARPU join",
        "MRR looks fine while serving cost explodes",
        "CPSO vs seat ARPU; power-user margin leakage; ship/throttle uneconomic capabilities",
    ),
    (
        "Visibility",
        "“What did this trace cost?”",
        "“What is NRR?”",
        "Unattributed spend; static routing age; cost heatmap by step × cohort",
    ),
    (
        "Activation",
        "Run success ≠ first win",
        "Paying customer still in “trial”",
        "TTFV payment→verified; paying-but-dormant; tourist / activation_failure GDRs",
    ),
    (
        "Switching costs",
        "Tool-call graph, not rip-out risk",
        "Churn reason = “unknown” / competitor",
        "Integration depth; rebuild/competitor share; connector blast radius",
    ),
    (
        "Trust / reliability",
        "Evals and user scores on traces",
        "Health score drops after the fact",
        "Catastrophic event rate; HITL trend; trust_break → rollback",
    ),
    (
        "Opaque success",
        "Completed trace ≠ trusted SOP",
        "Login/usage health",
        "Verified outcome rate; coordination overhead; flywheel write-back",
    ),
]

OUTPUT_CONTRAST_ROWS: list[tuple[str, str, str]] = [
    (
        "LangSmith",
        "Trace URL, span tree, eval score",
        "Should we kill this capability? What’s the $ of leaving it live?",
    ),
    (
        "Langfuse",
        "Cost per user/session, latency",
        "Did this account churn because of agent quality or price?",
    ),
    (
        "ChartMogul",
        "MRR, NRR, cohort charts",
        "CPSO, retry amplification, verified activation",
    ),
    (
        "ChurnZero",
        "Health score, playbooks",
        "Which agent capability caused the health drop?",
    ),
    (
        "churnOS",
        "`GrowthDecisionRecord`: verdict, action, `$` impact, exceptions",
        "(Demo: synthetic; production: needs your exports)",
    ),
]

TOOL_SPLIT_CAPTIONS: dict[str, str] = {
    "activation": "Paying in ChartMogul ≠ verified win in traces.",
    "trust": "Eval score ≠ post-failure churn.",
    "run_economics": "ChartMogul will not show CPSO; LangSmith will not show ARPU.",
    "connector": "LangSmith shows connector errors; ChurnZero will not show rebuild / competitor rip-out risk.",
    "flywheel": "Neither tool writes the decision back to retention Δ.",
    "experiments": "Quality flags live in LangSmith / Braintrust; these flags measure CPSO / TTFV on synthetic cohorts.",
}

COMPETITIVE_FAQ: list[tuple[str, str]] = [
    (
        "Can’t I join this in Looker/dbt?",
        "You can SQL the join; churnOS’s IP is the **exception taxonomy**, **YAML policy**, "
        "and **auditable decision record**, not the warehouse.",
    ),
    (
        "Is this observability?",
        "No. Use LangSmith for traces. churnOS consumes trace-shaped *facts* (runs, outcomes, cost) "
        "and emits *decisions*.",
    ),
    (
        "Is this a BI churn tool?",
        "No. ChartMogul tells you churn happened; churnOS ranks **interventions** on capabilities "
        "and accounts with playbook hints.",
    ),
    (
        "Do you replace my stack?",
        "No — ingest later; decide now on a teaching model. Keep LangSmith for debugging; "
        "keep ChartMogul for board NRR.",
    ),
]

FIELD_GLOSS = [
    ("Verdict", "Engine’s state call on this capability (see glossary below)."),
    ("Capability ID", "The shippable unit: skill, automation, agent, or tool policy."),
    ("Cost of leaving live", "Teaching estimate of $ at risk if you do nothing this window."),
    ("Platform margin at risk", "Marketplace $ at risk when inference eats platform take."),
    ("Verified GMV", "GMV with deterministic/webhook confirmation — not agent-claimed alone."),
    ("Exceptions", "Ranked reasons — activation leak, trust break, cost blowout, etc."),
    ("Recommended / Final", "What the engine suggests vs what you chose (override)."),
    ("Outcome", "Later write-back: retention Δ and whether churn happened (simulated today)."),
    ("Value", "Demand-side task value rollup (observed, estimated, or prior)."),
    ("Surplus", "value_usd minus floor per verified outcome when both exist."),
    ("Task tier", "S/M/L scoped footprint + list price from Outcome Definition."),
    ("Data-derived WTP cap", "Rigorous mode cap from subscriptions/outcomes — associational unless experiment."),
]


def synthetic_notice() -> None:
    """Persistent honesty banner: demo warehouse, not production."""
    load_magazine_css()
    st.markdown(
        """
        <div class="mag-notice">
            <span class="mag-notice-kicker">Synthetic demo</span>
            <span class="mag-notice-body">
                Numbers come from an authored warehouse (profile priors), not live product
                telemetry. Use this to learn the decision loop — not to certify production forecasts.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def surface_explainer(surface_key: str, *, expanded: bool = False) -> None:
    """Short ‘what this screen is / measures’ expander."""
    spec = SURFACE_EXPLAINERS.get(surface_key)
    if not spec:
        return
    with st.expander(spec["title"], expanded=expanded):
        st.markdown(spec["body"])


def how_it_works(*, expanded: bool = True) -> None:
    """Full product loop — primarily on Radar home."""
    with st.expander("How churnOS works (read this first)", expanded=expanded):
        st.markdown(
            """
**One loop**

1. **Product Profile** — pick product shape → sets ontology + fake rates (or **Data Connect** real traces)
2. **Generate / ingest warehouse** — seats, capabilities, runs, approvals, connectors, outcomes
3. **Version Gate** — ship / hold / rollback this version (SPRT + eval)
4. **Decision Inbox / Radar** — ranked GrowthDecisionRecords → override
5. **Outcome Flywheel** — write retention Δ / churn back onto the record (simulated unless real outcomes)

In production the warehouse is LangSmith-class traces + ChartMogul-class billing; today it is authored so you can learn the decision object.

**What is real vs demo**

| Real (the IP) | Demo today |
| --- | --- |
| Decision object, taxonomy, semantics | Synthetic seats & runs |
| Exception categories & playbooks | Authored correlation structure |
| Override → outcome flywheel pattern | Fake 14d retention / churn labels |

**Sidebar map**

- **Setup** — Product Profile, Data Connect, Outcome Definition
- **The call** — Version Gate, Inbox, Radar, then receipts (Activation, Trust, Connectors, Subgraph, Version Compare)
- **Price** — Run Economics (home); Lab · Packaging under Learn
- **Learn** — Executive Summary, Experiments, Flags, Flywheel, seven Lab · X
- **Config** — Integrations (hooks)
- **Reference** (collapsed) — Concepts, Architecture (atlas), Map atlas, Semantics, Taxonomy, Record Inspector
- **Legacy** (collapsed) — Pre-agentic ecomm / marketplace modules

Every agentic page shows a slim **orientation strip** (cluster question + next links). Full diagrams live under Reference → Architecture.
            """
        )


def decision_card_glossary(*, expanded: bool = False) -> None:
    """Plain-English meanings for card fields, verdicts, actions."""
    with st.expander("How to read a Decision Card", expanded=expanded):
        section_kicker("Card fields")
        for name, meaning in FIELD_GLOSS:
            st.markdown(f"**{name}** — {meaning}")
        section_kicker("Verdicts")
        for k, v in VERDICT_GLOSS.items():
            st.markdown(f"**`{k}`** — {v}")
        section_kicker("Actions")
        for k, v in ACTION_GLOSS.items():
            st.markdown(f"**`{k}`** — {v}")
        st.caption(
            "`capability_harm` is associational unless an experiment is attached — "
            "not automatic causal proof. **`p_churn_30d`** is calibrated 30-day churn "
            "probability (rigorous math_mode). **`uplift_pp`** is treatment effect when experiment_id present."
        )


def measurement_honesty() -> None:
    """Compact table: helps think vs measures production."""
    with st.expander("Does this measure what’s really going on?"):
        st.markdown(
            """
**Yes, as a model of what agentic products should measure**

- First trusted successful run (activation)  
- Weekly delegation habit (north-star / OEC)  
- Approval fatigue & trust incidents  
- $/successful run vs seat ARPU  
- Connector failures blocking jobs  

**No, as live instrumentation (yet)**

- No Lindy / Dench / Invice / your-product ingest  
- Harm scores are teaching correlations, not causal proof  
- Seat Retention / Unit Economics pages are still partly the old purchase story  
- Outcome write-back is simulated for the portfolio demo  
- GDR dollar impact is priced from synthetic **runs + seat ARPU** today; spans, outcomes, and subscriptions exist in the warehouse for metrics and a future ingest path — not yet the core of `classify()`

The durable idea: ranked, dollar-weighted judgments with human override and outcome feedback — not another vanity dashboard.

**Where this sits vs LangSmith / ChartMogul**

| Layer | What you already have | What this Radar adds |
| --- | --- | --- |
| Traces | LangSmith / Langfuse: runs, spans, evals | Warehouse models the join; GDRs use synthetic runs + accounts today |
| Revenue / CS | ChartMogul NRR; ChurnZero health (usage proxies) | Agent-native exceptions + $ cost of leaving live |
| This screen | — | `GrowthDecisionRecord`: ship / throttle / kill |
| Honesty | — | Synthetic until you plug extracts; no live connectors |
            """
        )


def _pain_map_markdown() -> str:
    header = "| Challenge | Traces (LangSmith / Langfuse) | Revenue (ChartMogul / ChurnZero) | churnOS alternative |\n"
    header += "| --- | --- | --- | --- |\n"
    rows = "\n".join(
        f"| {a} | {b} | {c} | {d} |"
        for a, b, c, d in PAIN_MAP_ROWS
    )
    return header + rows


def _output_contrast_markdown() -> str:
    header = "| Tool | Typical output | What you still can’t answer |\n"
    header += "| --- | --- | --- |\n"
    rows = "\n".join(f"| {a} | {b} | {c} |" for a, b, c in OUTPUT_CONTRAST_ROWS)
    return header + rows


def tool_stack_explainer(*, expanded: bool = False) -> None:
    """Six-row pain map + output contrast — LangSmith/ChartMogul complement positioning."""
    with st.expander("Where churnOS sits vs LangSmith / ChartMogul", expanded=expanded):
        st.markdown(
            "**Traces** (LangSmith, Langfuse, Braintrust) tell you what the agent did. "
            "**Revenue / CS** (ChartMogul NRR, ChurnZero health scores) tell you that money moved. "
            "churnOS is the weekly join: Account → Run → Outcome → Subscription → "
            "`GrowthDecisionRecord` (ship / throttle / kill)."
        )
        section_kicker("Pain map")
        st.markdown(_pain_map_markdown())
        section_kicker("What each tool returns")
        st.markdown(_output_contrast_markdown())
        st.caption(
            "Product analytics (PostHog / Amplitude) sit in the same gap: sessions and funnels, "
            "no agent internals. Eval tools improve quality; they do not run your weekly business review. "
            "Demo today: the warehouse scaffolds Account→Run→Outcome→Subscription; "
            "Radar economics come from synthetic runs and seat priors until you plug exports."
        )


def competitive_faq(*, expanded: bool = False) -> None:
    """Objection handling for traces-vs-revenue positioning."""
    with st.expander("Common questions (not LangSmith, not ChartMogul)", expanded=expanded):
        for question, answer in COMPETITIVE_FAQ:
            st.markdown(f"**{question}**")
            st.markdown(answer)


def render_tool_split_caption(surface_key: str) -> None:
    """One-line kicker: what LangSmith / ChartMogul still cannot answer on this surface."""
    caption = TOOL_SPLIT_CAPTIONS.get(surface_key)
    if caption:
        st.caption(caption)


def page_help(surface_key: str, *, show_notice: bool = True, show_card_glossary: bool = False) -> None:
    """Standard chrome: notice + surface explainer (+ optional card glossary)."""
    if show_notice:
        synthetic_notice()
    surface_explainer(surface_key, expanded=False)
    if show_card_glossary:
        decision_card_glossary(expanded=False)
