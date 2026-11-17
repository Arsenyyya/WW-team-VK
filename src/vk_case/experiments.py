"""Power for independent business-level binary outcomes; no simulated A/B results."""

import math

from scipy.optimize import brentq
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize


def plan_sample(p0, p1, alpha=.05, power=.8, ratio=1.):
    if not all(math.isfinite(x) for x in [p0, p1, alpha, power, ratio]):
        raise ValueError("Параметры мощности должны быть конечными числами.")
    if not 0 < p0 < 1 or not 0 < p1 < 1 or p0 == p1:
        raise ValueError("Требуется 0 < p0,p1 < 1 и ненулевая разница.")
    if not 0 < alpha < 1 or not 0 < power < 1 or ratio <= 0:
        raise ValueError("Недопустимые alpha, power или соотношение групп.")
    effect = abs(proportion_effectsize(p1, p0))
    n_control = math.ceil(NormalIndPower().solve_power(effect_size=effect, alpha=alpha, power=power, ratio=ratio))
    n_treatment = math.ceil(n_control * ratio)
    return {"p0": p0, "p1": p1, "mde_pp": (p1-p0)*100, "alpha": alpha, "power": power,
            "ratio": ratio, "n_control": n_control, "n_treatment": n_treatment,
            "n_total": n_control+n_treatment, "method": "Cohen h; NormalIndPower; two-sided",
            "unit": "независимый business_id; связанные сообщества объединить по владельцу",
            "limitation": "иллюстративный p0; для будущих кандидатов неизвестен; кластеризация требует поправки"}


def available_power(n_total, p0, p1, alpha=.05, ratio=1.):
    plan_sample(p0, p1, alpha, .8, ratio)
    if n_total < 4:
        raise ValueError("Для планирования нужны хотя бы четыре независимых бизнеса.")
    n1 = math.floor(n_total / (1+ratio))
    return float(NormalIndPower().power(abs(proportion_effectsize(p1, p0)), n1, alpha, ratio=ratio))


def detectable_difference(n_total, p0, alpha=.05, power=.8):
    if n_total < 4 or not 0 < p0 < 1 or not 0 < alpha < 1 or not 0 < power < 1:
        raise ValueError("Недопустимые параметры MDE.")
    def objective(delta):
        return available_power(n_total, p0, p0+delta, alpha) - power
    if objective(1-p0-1e-8) < 0:
        return None
    return float(brentq(objective, 1e-8, 1-p0-1e-8))
