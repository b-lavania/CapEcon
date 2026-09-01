"""Magazine-style Decision Card component."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from analytics.price_block import display_metric_label, format_usd, price_sentence
from analytics.value_ledger import value_sentence
from ontology.exception_taxonomy import ACTIONS, CATEGORIES
from ui.evidence_chrome import render_evidence_block, account_risk_so_what, render_claim_badge
from ui.explain import ACTION_GLOSS, VERDICT_GLOSS
from ui.magazine import load_magazine_css


def _cost_label(economics: dict[str, Any], entity_type: str) -> str:
    label = display_metric_label(economics)
    if economics.get("primary_metric_label"):
        return label
    if entity_type in ("seller", "workflow"):
        return "Platform margin at risk"
    return "Cost of leaving live"


def _evidence_line(record: dict[str, Any]) -> str:
    """Human-readable evidence hint from exception impacts / counts."""
    excs = record.get("exceptions", [])
    n = len(excs)
    cats = ", ".join(sorted({e.get("category", "") for e in excs if e.get("category")})[:3])
    verdict = record.get("decision", {}).get("verdict", "")
    gloss = VERDICT_GLOSS.get(verdict, "")
    parts = [f"{n} exception(s)"]
    if cats:
        parts.append(cats)
    if gloss:
        return f"{' · '.join(parts)} — {gloss}"
    return " · ".join(parts)


def _headline_amount(economics: dict[str, Any]) -> tuple[str, str]:
    """Whole dollars for Radar-scale ranking; unit floor when ranking rounds to $0."""
    ranking = economics.get("primary_metric_usd")
    floor = economics.get("floor_usd")
    ranking_note = "— ranking total" if floor is not None else "— teaching estimate if you do nothing"
    if ranking is not None and abs(float(ranking)) >= 1:
        return f"${float(ranking):,.0f}", ranking_note
    if floor is not None:
        return format_usd(floor), "— unit floor"
    if ranking is not None:
        return format_usd(ranking), ranking_note
    return "$0", ranking_note


def render_decision_card(
    record: dict[str, Any],
    *,
    key_prefix: str = "card",
    on_override: Callable[[dict, str, str], None] | None = None,
    show_override: bool = True,
    expanded: bool = False,
    workspace: Any | None = None,
) -> None:
    """Render one GDR as a single expandable row — not a stack of section headers."""
    load_magazine_css()
    decision = record.get("decision", {})
    economics = record.get("economics", {})
    subject = record.get("subject", {})
    verdict = decision.get("verdict", "unknown")
    cost = economics.get("primary_metric_usd", 0)
    cost_txt, cost_note = _headline_amount(economics)
    entity_type = subject.get("entity_type", "capability")
    cap_id = subject.get("capability_id", "—")
    acc_id = subject.get("account_id", "—")
    cap_ver = subject.get("capability_version", "—")
    rec_action = decision.get("recommended_action", "hold")
    excs = record.get("exceptions", [])

    if entity_type == "account":
        title = acc_id
        p_churn = record.get("p_churn_30d")
        if p_churn is not None:
            ci = record.get("p_churn_ci95") or [p_churn, p_churn]
            risk_part = f" · {p_churn * 100:.0f}% churn risk ({ci[0] * 100:.0f}–{ci[1] * 100:.0f}%)"
        else:
            risk = record.get("risk_score")
            risk_part = f" · risk {risk:.2f}" if risk is not None else ""
        meta_line = f"Account · {record.get('vertical', '')}{risk_part}"
        cost_label = _cost_label(economics, entity_type)
    elif entity_type == "seller":
        title = subject.get("seller_id", "—")
        meta_line = f"Seller · {record.get('vertical', 'marketplace_commerce')}"
        cost_label = _cost_label(economics, entity_type)
    elif entity_type == "workflow":
        title = subject.get("capability_id", cap_id)
        assist = subject.get("assist_type", "agent_assist")
        meta_line = f"Workflow · {assist}"
        cost_label = _cost_label(economics, entity_type)
    else:
        title = cap_id
        meta_line = f"Version {cap_ver} · Capability · {record.get('vertical', '')}"
        cost_label = _cost_label(economics, entity_type)

    summary = (
        f"{title}  ·  {verdict}  ·  {cost_txt}  ·  "
        f"{rec_action}  ·  {len(excs)} exceptions"
    )
    claim = (record.get("evidence") or {}).get("claim_type")
    if claim:
        summary += f"  ·  {claim}"
    if entity_type == "account" and record.get("primary_signal"):
        summary = f"{title}  ·  {record.get('primary_signal')}  ·  " + summary.split("  ·  ", 1)[-1] if "  ·  " in summary else summary
    with st.expander(summary, expanded=expanded):
        st.markdown(
            f"""
            <article class="mag-decision-card mag-decision-card--compact">
                <p class="mag-kicker">{entity_type.upper()} · {verdict.upper()}</p>
                <h2 class="mag-card-title">{title}</h2>
                <p class="mag-card-meta">{meta_line}</p>
                <p class="mag-evidence">{_evidence_line(record)}</p>
                <p class="mag-card-deck">{decision.get('rationale', '')}</p>
                <p class="mag-card-cost">{cost_txt}</p>
                <p class="mag-card-cost-label">{cost_label}
                  <span style="font-weight:400; text-transform:none; letter-spacing:0;">
                  {cost_note}</span>
                </p>
            </article>
            """,
            unsafe_allow_html=True,
        )

        sentence = price_sentence(economics, record.get("evidence"))
        if economics.get("pricing_mode") or economics.get("floor_usd") is not None:
            st.caption(sentence)

        value_line = value_sentence(economics, record.get("evidence"))
        if value_line:
            st.caption(value_line)
            breakdown = economics.get("value_breakdown") or []
            if breakdown:
                with st.expander("Value breakdown", expanded=False):
                    st.dataframe(breakdown, use_container_width=True, hide_index=True)

        cost_ci = economics.get("primary_metric_ci95_usd")
        if cost_ci:
            st.caption(f"95% band: ${cost_ci[0]:,.0f}–${cost_ci[1]:,.0f}")

        if record.get("evidence"):
            render_claim_badge(record["evidence"].get("claim_type") or "associational")
            with st.expander("Evidence", expanded=False):
                render_evidence_block(record["evidence"])
        elif excs and any(e.get("evidence") for e in excs):
            with st.expander("Evidence", expanded=False):
                for exc in excs[:3]:
                    if exc.get("evidence"):
                        st.caption(exc.get("category", ""))
                        render_evidence_block(exc["evidence"])

        attrs = record.get("attributions") or []
        if entity_type == "account" and attrs:
            top = ", ".join(f"{a['feature']} ({a['importance']:.3f})" for a in attrs[:3])
            st.caption(f"Top hazard drivers (permutation): {top}")

        if entity_type == "account" and record.get("p_churn_30d") is not None:
            ci = record.get("p_churn_ci95") or [0, 1]
            cost_ci = record.get("cost_ci95_usd") or [cost, cost]
            st.info(
                account_risk_so_what(
                    acc_id,
                    record["p_churn_30d"],
                    ci,
                    cost,
                    cost_ci,
                    record.get("primary_signal", "—"),
                    rec_action,
                )
            )

        if decision.get("requires_review") and record.get("evsi", {}).get("evsi_usd"):
            st.caption(
                f"EVSI ${record['evsi']['evsi_usd']:,.0f} — uncertainty worth a human review."
            )

        if decision.get("commercial_action"):
            owner = decision.get("commercial_owner_role", "packaging")
            st.warning(
                f"Commercial ask · **{decision['commercial_action']}** → `{owner}`  \n"
                f"{decision.get('commercial_rationale', '')}"
            )

        trace = decision.get("rule_trace")
        if trace:
            rule = trace.get("matched_verdict_rule") or {}
            rule_txt = rule.get("when_any_category") or rule.get("when_exception_count_lt") or rule.get("default", "")
            st.markdown(
                f'<p class="mag-rule-trace">Policy: <code>{trace.get("action_map_key")}</code> → '
                f'<strong>{trace.get("action_spec", {}).get("recommended_action")}</strong> · '
                f"rule {rule_txt}</p>",
                unsafe_allow_html=True,
            )

        if excs:
            chips = []
            total_impact = sum(e.get("impact", {}).get("cost_usd", 0) for e in excs) or 1
            for exc in excs[:6]:
                cat = exc.get("category", "")
                impact = exc.get("impact", {}).get("cost_usd", 0)
                pct = min(100, int(impact / total_impact * 100))
                chips.append(f"`{cat}` {pct}%")
            st.caption("Evidence · " + (" · ".join(chips) if chips else "none"))

            viz = record.get("viz")
            if viz:
                with st.expander("Visual receipt", expanded=False):
                    from ui.viz.viz_receipts import render_viz_receipt

                    if workspace is not None:
                        render_viz_receipt(viz, workspace)
                    else:
                        st.caption(f"Chart: `{viz.get('chart')}` · category `{viz.get('category')}`")
                        if viz.get("headline"):
                            st.json(viz["headline"])

            st.markdown("**Exceptions** (highest $ impact first)")
            harm_sort = sorted(
                excs[:5],
                key=lambda e: (
                    -(e.get("impact", {}).get("cost_usd", 0))
                    * (1 + (e.get("evidence") or {}).get("posterior", {}).get("mean", 0))
                    if e.get("category") == "capability_harm"
                    else -e.get("impact", {}).get("cost_usd", 0)
                ),
            )
            for exc in harm_sort:
                impact = exc.get("impact", {}).get("cost_usd", 0)
                cat = exc.get("category", "")
                hint = CATEGORIES.get(cat, {}).get("playbook_hint", "")
                st.markdown(
                    f"- **`{cat}`** — {exc.get('title', '')} "
                    f"(${impact:,.0f})"
                    + (f"  \n  _{hint}_" if hint else "")
                )

        if show_override and on_override:
            st.caption(
                f"Recommended: **{rec_action}** — "
                f"{ACTION_GLOSS.get(rec_action, 'Engine suggestion')}"
            )
            final = st.selectbox(
                "Final action",
                ACTIONS,
                index=ACTIONS.index(decision.get("final_action", rec_action))
                if decision.get("final_action") in ACTIONS
                else (ACTIONS.index(rec_action) if rec_action in ACTIONS else 0),
                format_func=lambda a: f"{a} — {ACTION_GLOSS.get(a, '')}",
                key=f"{key_prefix}_action_{record['record_id']}",
            )
            reason = ""
            if final != rec_action:
                reason = st.text_input(
                    "Override reason (required when you disagree)",
                    key=f"{key_prefix}_reason_{record['record_id']}",
                    help="Logged on the record without re-running classification.",
                )
            if st.button("Apply decision", key=f"{key_prefix}_apply_{record['record_id']}"):
                if final != rec_action and not reason.strip():
                    st.error("Override reason required when final ≠ recommended.")
                else:
                    on_override(record, final, reason or "")
                    st.success("Decision recorded (session + SQLite store).")

        st.page_link("pages/19_Decision_Inbox.py", label="View in Inbox")

        outcome = record.get("outcome")
        if outcome:
            st.caption(
                f"Outcome — Retention Δ (14d): {outcome.get('retention_delta_14d')} · "
                f"Churn happened: {outcome.get('churn_happened')}"
            )
