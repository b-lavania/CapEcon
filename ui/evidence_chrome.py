"""Evidence presentation chrome — stats → operator copy on The call surfaces."""

from __future__ import annotations

from typing import Any

import streamlit as st

CLAIM_GLOSS = {
    "associational": "Correlation-style signal — not a causal claim.",
    "causal": "Randomized experiment present — causal estimand allowed.",
    "simulated": "Synthetic demo — teaching estimate from planted DGP.",
}


def claim_badge(claim_type: str) -> str:
    gloss = CLAIM_GLOSS.get(claim_type, "")
    return (
        f'<span class="mag-meta-chip" title="{gloss}" '
        f'style="font-size:0.75rem; text-transform:uppercase;">{claim_type}</span>'
    )


def render_claim_badge(claim_type: str) -> None:
    st.markdown(claim_badge(claim_type), unsafe_allow_html=True)


def posterior_ribbon(
    mean: float,
    ci95: tuple[float, float] | list[float],
    *,
    unit: str = "%",
    decimals: int = 1,
) -> str:
    lo, hi = float(ci95[0]), float(ci95[1])
    if unit == "%":
        return f"**{mean * 100:.{decimals}f}%** ({lo * 100:.{decimals}f}–{hi * 100:.{decimals}f}%)"
    if unit == "$":
        return f"**${mean:,.0f}** (${lo:,.0f}–${hi:,.0f})"
    return f"**{mean:.{decimals}f}** ({lo:.{decimals}f}–{hi:.{decimals}f})"


def render_posterior_ribbon(
    mean: float,
    ci95: tuple[float, float] | list[float],
    *,
    label: str = "Estimate",
    unit: str = "%",
) -> None:
    st.caption(f"{label}: {posterior_ribbon(mean, ci95, unit=unit)}")


def so_what_line(
    action: str,
    stakes: str,
    uncertainty: str,
    *,
    headline: str | None = None,
) -> str:
    head = headline or "Action"
    return f"**{head}:** {action} · {stakes} · {uncertainty}"


def render_so_what(
    action: str,
    stakes: str,
    uncertainty: str,
    *,
    headline: str | None = None,
) -> None:
    st.markdown(so_what_line(action, stakes, uncertainty, headline=headline))


def underpowered_callout(n: int, n_required: int) -> str:
    return (
        f"**Hold — not enough data.** You have **{n}** units; "
        f"~**{n_required}** needed at this MDE. Ship only if you accept high false-negative risk."
    )


def render_underpowered_callout(n: int, n_required: int) -> None:
    st.warning(underpowered_callout(n, n_required))


def render_evidence_block(evidence: dict[str, Any] | None) -> None:
    """Render evidence from GDR exception or root."""
    if not evidence:
        return
    ct = evidence.get("claim_type", "simulated")
    render_claim_badge(ct)
    post = evidence.get("posterior") or {}
    if "mean" in post and "ci95" in post:
        estimand = evidence.get("estimand", "rate")
        unit = "$" if "cost" in estimand or "usd" in estimand else "%"
        render_posterior_ribbon(
            post["mean"],
            post["ci95"],
            label=estimand.replace("_", " ").title(),
            unit=unit,
        )
    if evidence.get("experiment_id"):
        st.caption(f"Experiment: `{evidence['experiment_id']}`")
    elif ct == "associational":
        st.caption("Why not causal: no `experiment_id` on this record.")


def account_risk_so_what(
    account_id: str,
    p_churn: float,
    ci95: list[float],
    cost_mean: float,
    cost_ci: list[float],
    primary_signal: str,
    recommended: str,
) -> str:
    return (
        f"**Call this week.** {account_id} has **{p_churn * 100:.0f}%** 30-day churn risk "
        f"({ci95[0] * 100:.0f}–{ci95[1] * 100:.0f}%). Primary signal: {primary_signal}. "
        f"Cost of leaving live **~${cost_mean:,.0f}** (${cost_ci[0]:,.0f}–${cost_ci[1]:,.0f}). "
        f"Recommended: **{recommended}**."
    )
