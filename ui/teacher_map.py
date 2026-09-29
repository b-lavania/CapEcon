"""Cluster orientation + atlas diagrams. Orientation lives on every page; atlas is Reference-only."""

from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from core.workspace import get_workspace_from_session

GROUP_LABELS = {
    "setup": "Setup",
    "call": "The call",
    "price": "Price",
    "lab": "Lab",
    "after": "After",
    "config": "Config",
}

# Slim strip on every page: one question, one insight, next hops
CLUSTERS: dict[str, dict[str, Any]] = {
    "setup": {
        "question": "What product is this?",
        "insight": "Name a verified outcome before you trust Version Gate.",
        "next": [
            ("pages/00_Agentic_Product_Profile.py", "Product Profile"),
            ("pages/02_Outcome_Definition.py", "Outcome Definition"),
            ("pages/01_Data_Connect.py", "Data Connect"),
        ],
    },
    "call": {
        "question": "Ship, hold, or kill?",
        "insight": "Ops action on the GDR — not a dashboard tile.",
        "next": [
            ("pages/24_Version_Gate.py", "Version Gate"),
            ("pages/19_Decision_Inbox.py", "Inbox"),
            ("pages/17_Run_Economics.py", "Run Economics"),
        ],
    },
    "price": {
        "question": "Can we charge this?",
        "insight": "Floor and CPSO first; Packaging Lab is the demand curve.",
        "next": [
            ("pages/17_Run_Economics.py", "Run Economics"),
            ("pages/38_Math_Lab_Packaging.py", "Lab · Packaging"),
            ("pages/24_Version_Gate.py", "Version Gate"),
        ],
    },
    "lab": {
        "question": "Do I believe the estimator?",
        "insight": "Math Labs teach the method — claim_type still rules the card.",
        "next": [
            ("pages/38_Math_Lab_Packaging.py", "Lab · Packaging"),
            ("pages/17_Run_Economics.py", "Run Economics"),
            ("pages/20_Outcome_Flywheel.py", "Flywheel"),
        ],
    },
    "after": {
        "question": "What happened after the call?",
        "insight": "Write outcomes back onto the same GDR — close the loop.",
        "next": [
            ("pages/20_Outcome_Flywheel.py", "Flywheel"),
            ("pages/37_Executive_Summary.py", "Executive Summary"),
            ("pages/19_Decision_Inbox.py", "Inbox"),
        ],
    },
    "config": {
        "question": "How do hooks fire?",
        "insight": "Slack and review — CapEcon does not write flag weights.",
        "next": [
            ("pages/40_Integrations.py", "Integrations"),
            ("pages/19_Decision_Inbox.py", "Inbox"),
        ],
    },
}

JOIN_ASCII = """\
  builder owns                          CapEcon join
  ┌──────────────┐                    ┌──────────────────┐
  │ LangGraph /  │  traces            │ warehouse        │
  │ Langfuse     │ ─────────────────► │ outcomes × cost  │
  │ Stripe       │  invoices          │ × trust          │
  └──────────────┘                    └────────┬─────────┘
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │ GDR              │
                                      │ floor / claim /  │
                                      │ ship or hold     │
                                      └──────────────────┘"""

SIDEBAR_ASCII = """\
  TODAY DECIDE                         AFTER
  Version Gate                         THE CALL
  Inbox                                  Version Gate
  Radar                                  Inbox
  Subgraph                               Radar
  Activation                             · Activation
  Trust                                  · Trust
  Run Economics                          · Connectors
  Connectors                             · Subgraph
  Marketplace Radar                      · Version Compare
  Clinical Radar                       PRICE
  Version Compare                        Run Economics
                                       Lab · Packaging"""

PRICE_ASCII = """\
  Outcome Definition ── priors / verified success
  Run Economics      ── floor, CPSO, WTP, Fit demand  ← land here
  Lab · Packaging    ── authored ε or fitted log-log
  GDR caption        ── surplus-opt / list_below_demand_opt"""

TEACHER_MERMAID = """\
flowchart TB
  Setup["Setup: what product is this?"]
  Call["The call: ship, hold, or kill?"]
  Price["Price: can we charge this?"]
  Lab["Lab: do I believe the estimator?"]
  After["After: what happened after the call?"]
  Setup --> Call
  Call --> Price
  Price --> Lab
  Call --> After"""

ENGINE_MERMAID = """\
flowchart LR
  subgraph engine [Engine_loop]
    P[Profile]
    W[Warehouse]
    C[Classify]
    Y[YAML_rules]
    G[GDR]
    R[Radar]
    F[Flywheel]
    P --> W --> C --> Y --> G --> R --> F
  end
  subgraph teacher [Teacher_clusters]
    S[Setup]
    Call[The_call]
    Pr[Price]
    L[Lab]
    A[After]
    S --> Call --> Pr --> L
    Call --> A
  end"""

NAV_TABLE = [
    ("Setup", "What product is this?", "Profile, Data Connect, Outcome Definition"),
    ("The call", "Ship, hold, or kill?", "Version Gate, Inbox, Radar · receipts: Activation, Trust, Connectors, Subgraph, Version Compare"),
    ("Price", "Can we charge this?", "Run Economics (home); Lab · Packaging under Learn"),
    ("Learn", "Do I believe the estimator / what after?", "Exec, Experiments, Flags, Flywheel, then seven Lab · X"),
    ("Config", "How do hooks fire?", "Integrations; Reference / Legacy collapsed"),
]


def render_orientation_strip(cluster: str) -> None:
    """Slim question + insight + next links — on every agentic page, not a destination."""
    from ui.magazine import load_magazine_css

    load_magazine_css()
    spec = CLUSTERS.get(cluster)
    if not spec:
        return
    st.session_state["teacher_map_group"] = cluster
    label = GROUP_LABELS.get(cluster, cluster)
    st.markdown(
        f"""
        <aside class="mag-orient" aria-label="Cluster orientation">
          <p class="mag-orient-q"><span class="mag-orient-cluster">{escape(label)}</span>
            {escape(spec["question"])}</p>
          <p class="mag-orient-insight">{escape(spec["insight"])}</p>
        </aside>
        """,
        unsafe_allow_html=True,
    )
    links = spec.get("next") or []
    if links:
        cols = st.columns(len(links))
        for col, (path, title) in zip(cols, links):
            with col:
                st.page_link(path, label=title)


def render_ascii_diagram(text: str) -> None:
    st.markdown(
        f'<pre class="mag-diagram">{escape(text)}</pre>',
        unsafe_allow_html=True,
    )


def render_mermaid(diagram: str, *, height: int = 420) -> None:
    """Embed mermaid.js from CDN; themed to Blavania tokens."""
    safe = diagram.replace("</", "<\\/")
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{
      startOnLoad: true,
      theme: 'base',
      themeVariables: {{
        primaryColor: '#f1f8f6',
        primaryTextColor: '#0f1112',
        primaryBorderColor: '#0a5a46',
        lineColor: '#5c6370',
        secondaryColor: '#faf9f7',
        tertiaryColor: '#ffffff',
        fontFamily: 'DM Sans, system-ui, sans-serif',
      }}
    }});
  </script>
</head>
<body style="margin:0;background:#faf9f7;color:#0f1112;">
  <pre class="mermaid">{safe}</pre>
  <p style="font-family:monospace;font-size:11px;color:#8b92a0;margin:8px 0 0;">
    If the diagram is blank, JS is blocked — use the ASCII tabs.
  </p>
</body>
</html>
"""
    components.html(html, height=height, scrolling=False)


def _section_header(question: str, insight: str) -> None:
    st.markdown(f'<p class="mag-section-kicker">{escape(question)}</p>', unsafe_allow_html=True)
    st.caption(insight)


def render_atlas() -> None:
    """Full diagram atlas — Reference / Architecture only."""
    tabs = st.tabs(
        [
            "Join",
            "Clusters",
            "Sidebar before / after",
            "Engine vs map",
            "Price cluster",
        ]
    )

    with tabs[0]:
        _section_header(
            "What is CapEcon?",
            "Key insight: Radar does not run the agent. It prices leaving it live.",
        )
        render_ascii_diagram(JOIN_ASCII)
        st.caption(
            "Magentic Marketplace, HARK, Econojax, and similar repos simulate. "
            "CapEcon prices the export after Data Connect overlay — it does not run those engines."
        )

    with tabs[1]:
        _section_header(
            "How should a teacher walk the product?",
            "One question per nav group — orientation strips repeat this on every page.",
        )
        render_mermaid(TEACHER_MERMAID, height=440)
        st.dataframe(
            [{"Group": g, "Question": q, "Pages": p} for g, q, p in NAV_TABLE],
            use_container_width=True,
            hide_index=True,
        )

    with tabs[2]:
        _section_header(
            "Why did DECIDE feel like a blob?",
            "Eleven equal peers → three primaries, then receipts; Price is its own group.",
        )
        render_ascii_diagram(SIDEBAR_ASCII)
        st.caption(
            "Marketplace / Clinical Radar appear only when the workspace preset is "
            "`marketplace_agentic` or `openmed_v22`."
        )

    with tabs[3]:
        _section_header(
            "Engine loop vs teacher clusters",
            "YAML and classify stay in the engine diagram — never as sidebar peers. "
            "The stepper copies Setup → Call → Price → Lab → After.",
        )
        render_mermaid(ENGINE_MERMAID, height=380)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Engine**")
            st.caption("Profile → Warehouse → Classify → YAML → GDR → Radar → Flywheel")
        with c2:
            st.markdown("**Teacher**")
            st.caption("Setup → Call → Price → Lab → After")

    with tabs[4]:
        _section_header(
            "Can we charge this?",
            "Four surfaces, one question. Land on Run Economics after you generate a warehouse.",
        )
        render_ascii_diagram(PRICE_ASCII)


render_teacher_map_page = render_atlas


def docs_architecture_markdown() -> str:
    return f"""# Architecture (join, not a runtime)

CapEcon sits on the join: traces × verified outcomes × trust × cost-to-serve.
It does not replace LangGraph, Langfuse, or Stripe.

## What CapEcon is (not a runtime)

```
{JOIN_ASCII}
```

**Key insight:** Radar does not run the agent. It prices leaving it live.

## Engine loop vs teacher clusters

```mermaid
{ENGINE_MERMAID}
```

- **Engine:** Profile → Warehouse → Classify → YAML → GDR → Radar → Flywheel.
- **Teacher clusters (sidebar + page strips + stepper):** Setup → Call → Price → Lab → After.

Orientation is a **strip on every page**, not a destination. Full atlas: Reference → Architecture.
"""


def docs_information_architecture_markdown() -> str:
    rows = "\n".join(f"| **{g}** | {q} | {p} |" for g, q, p in NAV_TABLE)
    return f"""# Information architecture

One question per nav group. Each page repeats that question in a slim orientation strip.

```mermaid
{TEACHER_MERMAID}
```

| Group | Question | Pages |
| --- | --- | --- |
{rows}

## Sidebar before / after

```
{SIDEBAR_ASCII}
```

## Price cluster

```
{PRICE_ASCII}
```

Full atlas diagrams: in-app **Reference → Architecture**.
"""
