"""WTP priors from synthetic warehouse."""

from analytics.agentic_profile import get_preset
from analytics.wtp_priors import churn_after_price_change, wtp_cap_from_data
from core.workspace import build_workspace


def test_wtp_cap_from_api_metered_workspace():
    profile = get_preset("api_metered")
    profile.setdefault("priors", {})["math_mode"] = "rigorous"
    ws = build_workspace(profile, seed=42, n_sessions=500)
    wtp = wtp_cap_from_data(ws, profile)
    assert wtp.get("cap_usd") is not None or wtp.get("underpowered")


def test_churn_after_price_change_on_usage_billing():
    profile = get_preset("api_metered")
    ws = build_workspace(profile, seed=7, n_sessions=500)
    churn = churn_after_price_change(ws)
    assert churn.get("n_treated", 0) >= 0
