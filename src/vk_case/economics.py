"""Scenario estimates are assumptions, never observed experiment outcomes."""

import math
from dataclasses import dataclass, replace

import pandas as pd


@dataclass(frozen=True)
class Scenario:
    n: float
    delta_activation: float
    orders_per_seller: float
    aov: float
    realized_value_share: float
    net_service_rate: float = .02
    gross_margin: float | None = None
    acquisition_cost: float = 0
    fulfillment_and_return_costs: float = 0
    labor_cost: float = 0
    incremental_ad_revenue: float = 0
    net_partner_revenue: float = 0
    variable_costs: float = 0
    subsidies: float = 0
    support_costs: float = 0
    cannibalized_contribution: float = 0
    investment: float = 574000
    retention: float = .8
    horizon_months: int = 12
    p0: float | None = None
    p1: float | None = None

    def validate(self):
        for key, value in self.__dict__.items():
            if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError(f"{key}: требуется конечное число.")
        for name in ["realized_value_share", "net_service_rate", "gross_margin", "retention", "p0", "p1"]:
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name}: доля должна находиться в [0, 1].")
        if not -1 <= self.delta_activation <= 1:
            raise ValueError("Дополнительная активация должна находиться в [-1, 1].")
        if (self.p0 is None) != (self.p1 is None):
            raise ValueError("Задайте обе p0 и p1 либо только разницу.")
        if self.p0 is not None and not math.isclose(self.p1 - self.p0, self.delta_activation, abs_tol=1e-10):
            raise ValueError("p1 − p0 не совпадает с дополнительной активацией.")
        if self.horizon_months < 1 or int(self.horizon_months) != self.horizon_months:
            raise ValueError("Горизонт должен быть положительным целым числом месяцев.")
        for name in ["n", "orders_per_seller", "aov", "investment", "acquisition_cost",
                     "fulfillment_and_return_costs", "labor_cost", "incremental_ad_revenue", "net_partner_revenue",
                     "variable_costs", "subsidies", "support_costs", "cannibalized_contribution"]:
            if getattr(self, name) < 0:
                raise ValueError(f"{name}: требуется неотрицательное значение.")


def model(s: Scenario):
    s.validate()
    sellers = s.n * s.delta_activation
    orders = sellers * s.orders_per_seller
    created = orders * s.aov
    realized = created * s.realized_value_share
    fees = realized * s.net_service_rate
    profit = None if s.gross_margin is None else (
        realized * s.gross_margin - s.acquisition_cost - s.fulfillment_and_return_costs - fees - s.labor_cost)
    contribution = (s.incremental_ad_revenue + fees + s.net_partner_revenue - s.variable_costs
                    - s.subsidies - s.support_costs - s.cannibalized_contribution)
    cumulative, payback = 0., None
    periods = []
    for month in range(1, s.horizon_months + 1):
        # A single initial cohort, no unobserved inflow of new businesses in later months.
        retained = s.retention ** (month - 1)
        cash = contribution * retained
        cumulative += cash
        if payback is None and cumulative >= s.investment and contribution > 0:
            payback = month
        periods.append({"month": month, "retained_cohort_share": retained,
                        "incremental_orders": orders * retained, "contribution": cash,
                        "cumulative_contribution": cumulative, "net_of_investment": cumulative - s.investment})
    per_candidate = contribution / s.n if s.n else None
    horizon_factor = sum(s.retention ** i for i in range(s.horizon_months))
    # Scaling is only valid without fixed costs/revenues, otherwise an N threshold would be misleading.
    has_fixed = any([s.incremental_ad_revenue, s.net_partner_revenue, s.variable_costs, s.subsidies,
                     s.support_costs, s.cannibalized_contribution])
    breakeven = (s.investment / (per_candidate * horizon_factor)
                 if per_candidate is not None and per_candidate > 0 and not has_fixed else None)
    return {"delta_sellers": sellers, "delta_orders": orders, "gmv_created": created,
            "gmv_realized": realized, "seller_profit": profit, "net_service_revenue": fees,
            "vk_contribution": contribution, "payback_month": payback,
            "horizon_net": cumulative - s.investment, "breakeven_n": breakeven, "periods": periods}


def scenario_tables(metrics, config):
    if metrics["goods_aov"] is None:
        raise ValueError("Нет среднего чека: сценарный GMV недоступен при нуле заказов в исходной базе.")
    rows, periods = [], []
    for spec in config["scenarios"]:
        params = {k: v for k, v in spec.items() if k != "name"}
        s = Scenario(n=metrics["candidates"], aov=metrics["goods_aov"], **config["economics"], **params)
        result = model(s)
        rows.append({"name": spec["name"], **s.__dict__, **{k: v for k, v in result.items() if k != "periods"},
                     "type": "scenario", "profit_availability": "unknown_margin" if s.gross_margin is None else "assumed"})
        periods.extend({"name": spec["name"], **p} for p in result["periods"])
    base_spec = next((s for s in config["scenarios"] if s["name"] == "Базовый"), config["scenarios"][0])
    base = Scenario(n=metrics["candidates"], aov=metrics["goods_aov"], **config["economics"],
                    **{k: v for k, v in base_spec.items() if k != "name"})
    sensitivities = []
    for key in ["n", "delta_activation", "orders_per_seller", "aov", "realized_value_share", "net_service_rate"]:
        for factor in [.5, .75, 1., 1.25, 1.5]:
            value = getattr(base, key) * factor
            if key in {"realized_value_share", "net_service_rate"} and value > 1:
                continue
            result = model(replace(base, **{key: value}))
            sensitivities.append({"parameter": key, "factor": factor, "value": value,
                                  **{k: v for k, v in result.items() if k != "periods"}})
    return pd.DataFrame(rows), pd.DataFrame(sensitivities), pd.DataFrame(periods)


def reference_reproduction():
    return [dict(name=name, **{k: v for k, v in model(Scenario(966, d, q, 2853, r)).items() if k != "periods"})
            for name, d, q, r in [("Низкий", .02, 3, .7), ("Базовый", .04, 5, .8), ("Высокий", .07, 7, .85)]]
