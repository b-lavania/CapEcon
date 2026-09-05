"""Demand panel adapter and power gate."""

from analytics.agentic_profile import get_preset
from analytics.demand_panel import build_demand_panel, panel_power
from core.workspace import build_workspace
from data.ground_truth import get as get_ground_truth


def test_assistant_heavy_panel_underpowered():
    profile = get_preset("assistant_heavy")
    ws = build_workspace(profile, seed=42, n_sessions=500)
    panel = build_demand_panel(ws)
    power = panel_power(panel)
    assert not power["ok"]


def test_api_metered_panel_has_price_variation_and_shock():
    profile = get_preset("api_metered")
    ws = build_workspace(profile, seed=42, n_sessions=800)
    panel = build_demand_panel(ws)
    assert not panel.empty
    assert {"sku", "period", "price", "quantity"} <= set(panel.columns)

    gt = get_ground_truth(ws.seed)
    assert gt is not None
    treated = set(gt.planted_treated_skus or [])
    shock = gt.planted_shock_week
    assert treated and shock

    price_cv_skus = 0
    for sku, grp in panel.groupby("sku"):
        if len(grp) >= 2 and grp["price"].std() > 0:
            price_cv_skus += 1
    assert price_cv_skus >= 2

    pre_qty = post_qty = 0
    for sku in treated:
        sub = panel[panel["sku"] == sku]
        pre = sub[sub["period"] < shock]["quantity"].sum()
        post = sub[sub["period"] >= shock]["quantity"].sum()
        pre_qty += int(pre)
        post_qty += int(post)
    if pre_qty > 0 and post_qty > 0:
        assert post_qty < pre_qty

    power = panel_power(panel)
    assert power["n_skus"] >= 4
    assert power["n_periods"] >= 8
