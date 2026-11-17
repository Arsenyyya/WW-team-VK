from dataclasses import replace

import pytest

from vk_case.economics import Scenario, model, reference_reproduction
from vk_case.experiments import available_power, plan_sample


def base():
    return Scenario(966, .04, 5, 2852.8244650086754, .8)


def test_zero_negative_fractional_and_one_return_deduction():
    assert model(replace(base(), delta_activation=0))["gmv_created"] == 0
    assert model(replace(base(), delta_activation=-.01))["delta_orders"] < 0
    r = model(base())
    assert r["delta_sellers"] == pytest.approx(38.64)
    assert r["gmv_realized"] == pytest.approx(r["gmv_created"]*.8)
    assert r["seller_profit"] is None
    p = model(replace(base(), gross_margin=.3, fulfillment_and_return_costs=500))
    assert p["seller_profit"] == pytest.approx(p["gmv_realized"]*.3 - 500-p["net_service_revenue"])


def test_investment_and_retention():
    s = replace(base(), investment=10000)
    lo, hi = model(s), model(replace(s, investment=20000))
    assert hi["payback_month"] >= lo["payback_month"]
    assert hi["horizon_net"] == pytest.approx(lo["horizon_net"]-10000)
    assert model(replace(s, retention=0))["periods"][1]["contribution"] == 0


@pytest.mark.parametrize("change", [{"realized_value_share": 1.1}, {"p0": .1, "p1": 1.2},
                                   {"p0": .1}, {"p0": .2, "p1": .25}, {"n": -1}, {"aov": float('nan')}])
def test_invalid_scenarios(change):
    with pytest.raises(ValueError):
        model(replace(base(), **change))


def test_reference_is_separate():
    old = reference_reproduction()[1]
    current = model(base())
    assert old["gmv_created"] == pytest.approx(966*.04*5*2853)
    assert old["gmv_created"] != current["gmv_created"]


def test_experiment_unit_mde_and_ratio():
    small = plan_sample(.0685, .0985)
    large = plan_sample(.0685, .1285)
    assert small["n_control"] > large["n_control"]
    assert 1200 < small["n_control"] < 1500
    assert "business_id" in small["unit"]
    assert available_power(966, .0685, .0985) < .8
    unequal = plan_sample(.1, .15, ratio=2)
    assert unequal["n_treatment"] == unequal["n_control"]*2
    for p0, p1 in [(-.1, .1), (.5, 1.1), (.1, .1)]:
        with pytest.raises(ValueError):
            plan_sample(p0, p1)
