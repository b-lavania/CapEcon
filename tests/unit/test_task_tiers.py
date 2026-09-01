"""Task tier commercial signal."""

from analytics.commercial import resolve_price_signal
from analytics.agentic_profile import get_preset


def test_below_tier_list_when_floor_exceeds_tier_list():
    economics = {
        "floor_usd": 1.50,
        "tier_list_usd": 0.99,
        "cap_usd": 5.0,
        "charged_usd": 1.20,
        "pricing_mode": "product_sku",
    }
    signal = resolve_price_signal(economics, profile=get_preset("api_metered"))
    assert signal["price_signal"] == "below_tier_list"
