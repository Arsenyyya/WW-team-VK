"""One calculation layer shared by CLI, charts, reports, and the application."""

import numpy as np
import pandas as pd
from statsmodels.stats.proportion import proportion_confint

from .ingest import Bundle, DataError

GOODS = {"товарное", "товарное и услужное"}


def ratio(numerator, denominator):
    if denominator is None or pd.isna(denominator) or denominator == 0:
        return None
    return float(numerator / denominator)


def features(b):
    b = b.copy()
    b["is_goods"] = b.business_type.isin(GOODS)
    b["has_catalog"] = b.uploaded_products > 0
    b["has_active_catalog"] = b.active_products > 0
    b["selling"] = b.orders > 0
    b["candidate"] = b.is_goods & b.has_active_catalog & (b.product_views > 0) & (b.orders == 0)
    b["audience_band"] = pd.cut(b.subscribers, [-1, 1000, 10000, 1e15],
                                labels=["до 1 тыс.", "1–10 тыс.", "свыше 10 тыс."], right=False).astype(str)
    b["ad_active"] = b.ad_spend > 0
    b["aov"] = b.gmv.div(b.orders.where(b.orders != 0))
    b["stage"] = np.select(
        [b.selling, ~b.has_active_catalog, b.product_views == 0, b.checkout == 0],
        ["Есть заказы", "Нет активного каталога", "Нет просмотров товарного контента", "Настроить путь заказа"],
        default="Проверить путь до заказа")
    b["seller_job"] = b.theme.map({"Творчество и хендмейд": "Мастерская / бренд — гипотеза",
                                    "Развлечения и хобби": "Мастерская / бренд — гипотеза",
                                    "Кулинария и еда": "Локальные товары еды — гипотеза",
                                    "Мода и стиль": "Одежда — следующий этап"}).fillna("Требуется классификация")
    b["source_row"] = np.arange(2, len(b) + 2)
    return b


def profile(b, groups):
    records = []
    for keys, group in b.groupby(groups, dropna=False, observed=True, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        n, sellers = len(group), int(group.selling.sum())
        low, high = proportion_confint(sellers, n, method="wilson")
        records.append({**dict(zip(groups, keys, strict=True)), "n": n, "sellers": sellers,
                        "seller_share": sellers / n, "ci_low": low, "ci_high": high,
                        "orders": int(group.orders.sum()), "gmv": int(group.gmv.sum()),
                        "aov": ratio(group.gmv.sum(), group.orders.sum()),
                        "catalog": int(group.has_active_catalog.sum()), "checkout": int(group.checkout.sum()),
                        "delivery": int(group.delivery.sum()), "payment": int(group.payment.sum()),
                        "candidates": int(group.candidate.sum()),
                        "median_subscribers": float(group.subscribers.median()),
                        "median_ad_spend": float(group.ad_spend.median()),
                        "share_denominator": "n: все бизнесы данной группы; единица — business_id"})
    return pd.DataFrame(records)


def calculate(bundle: Bundle):
    b = features(bundle.business)
    g = b[b.is_goods]
    if g.empty:
        raise DataError("Нет товарных или смешанных бизнесов; основная база кейса пуста.")
    c = b[b.candidate].sort_values(["content_opens", "product_views", "business_id"], ascending=[False, False, True]).copy()
    c["reason"] = "товарный/смешанный; активный каталог; просмотры товарного контента > 0; заказы = 0"
    c["unknown_conditions"] = "ассортимент; владелец; согласие; маржа; исполнение; другие каналы продаж"
    m = {
        "businesses": len(b), "goods_businesses": len(g), "selling_goods": int(g.selling.sum()),
        "goods_orders": int(g.orders.sum()), "goods_gmv": int(g.gmv.sum()),
        "goods_aov": ratio(g.gmv.sum(), g.orders.sum()), "seller_share": float(g.selling.mean()),
        "all_orders": int(b.orders.sum()), "all_sellers": int(b.selling.sum()),
        "original_missing": int(b.original_content.isna().sum()),
        "missing_aov_sellers": int((b.selling & b.reported_aov.isna()).sum()),
        "orders_without_current_checkout": int((b.selling & (b.checkout == 0)).sum()),
        "candidates": len(c), "market_orders": bundle.total("orders"), "partner_orders": bundle.total("orders", "partner"),
        "market_paid_orders": bundle.total("paid_orders"),
        "market_category_orders": float(bundle.categories.query("scope == 'market' and metric_id == 'orders'").value.sum()),
        "partner_category_orders": float(bundle.categories.query("scope == 'partner' and metric_id == 'orders'").value.sum()),
        "partner_demography_orders": float(bundle.demography.query("scope == 'partner' and metric_id == 'orders'").value.sum()),
        "homepage_opens": float(bundle.sources[(bundle.sources.scope == "market") &
                                              bundle.sources.source.str.startswith("Главная")].opens.sum()),
        "market_opens": bundle.total("opens"),
        "market_aov": ratio(bundle.total("gmv"), bundle.total("orders")),
        "partner_aov": ratio(bundle.total("gmv", "partner"), bundle.total("orders", "partner")),
    }
    m["homepage_share"] = ratio(m["homepage_opens"], m["market_opens"])
    for scope in ["market", "partner"]:
        m[f"{scope}_open_impression_ratio"] = ratio(bundle.total("opens", scope), bundle.total("impressions", scope))
        m[f"{scope}_order_open_ratio"] = ratio(bundle.total("orders", scope), bundle.total("opens", scope))
    m["dau_mau_ratio"] = ratio(bundle.total("dau", "common"), bundle.total("mau", "common"))
    for theme, key in [("Творчество и хендмейд", "handmade"), ("Развлечения и хобби", "hobby"),
                       ("Кулинария и еда", "food"), ("Мода и стиль", "fashion")]:
        m[f"candidates_{key}"] = int((c.theme == theme).sum())
    m["gmv_top_10_share"] = ratio(g.nlargest(10, "gmv").gmv.sum(), g.gmv.sum())
    tables = {"business_features": b, "pilot_candidates": c,
              "business_types": profile(b, ["business_type"]), "themes": profile(g, ["theme"]),
              "audience": profile(g, ["audience_band"]), "segments": profile(g, ["seller_job", "stage"]),
              "tool_combinations": profile(g, ["checkout", "delivery", "payment"]),
              "comparable_groups": profile(g, ["theme", "audience_band", "ad_active", "checkout"]),
              "originality": profile(g.assign(originality_group=g.original_content.astype("string").fillna("неизвестно")),
                                     ["originality_group"])}
    return m, tables


def content_comparisons(b, seed=2026, repetitions=1000):
    b = b[b.is_goods].copy()
    product_pubs = b.product_posts + b.product_clips
    ordinary_pubs = b.posts + b.clips - product_pubs
    valid = (product_pubs > 0) & (ordinary_pubs > 0) & (b.product_views > 0) & (b.ordinary_views > 0)
    p = b.loc[valid].copy()
    p["product_views_per_pub"] = p.product_views / product_pubs[valid]
    p["ordinary_views_per_pub"] = p.ordinary_views / ordinary_pubs[valid]
    p["product_engagement"] = (p.product_likes + p.product_reposts) / p.product_views
    p["ordinary_engagement"] = (p.ordinary_likes + p.ordinary_reposts) / p.ordinary_views
    p["log_view_ratio"] = np.log(p.product_views_per_pub.astype(float) / p.ordinary_views_per_pub.astype(float))
    rng = np.random.default_rng(seed)
    rows = []
    for name, a, d in [("log_views_per_publication", "log_view_ratio", None),
                        ("engagement_difference", "product_engagement", "ordinary_engagement")]:
        values = (p[a] if d is None else p[a] - p[d]).to_numpy(dtype=float)
        if len(values) == 0:
            rows.append({"comparison": name, "n": 0, "median": None, "ci_low": None, "ci_high": None})
            continue
        boot = [np.median(rng.choice(values, size=len(values), replace=True)) for _ in range(repetitions)]
        rows.append({"comparison": name, "n": len(values), "median": float(np.median(values)),
                     "ci_low": float(np.quantile(boot, .025)), "ci_high": float(np.quantile(boot, .975)),
                     "interpretation": "парное описательное сравнение внутри business_id; не причинный эффект"})
    strata = p.groupby(["theme", "audience_band", "ad_active"], observed=True, dropna=False).agg(
        n=("business_id", "count"), median_log_ratio=("log_view_ratio", "median"),
        product_engagement=("product_engagement", "median"), ordinary_engagement=("ordinary_engagement", "median")).reset_index()
    return pd.DataFrame(rows), strata


def robustness(b):
    g = b[b.is_goods]
    variants = {
        "Все товарные/смешанные": g,
        "Без крупнейшего по заказам": g.drop(g.orders.idxmax()),
        "Без верхнего 1% по GMV": g[g.gmv <= g.gmv.quantile(.99)],
        "Без заказов при текущем чекауте 0": g[~(g.selling & (g.checkout == 0))],
        "Без товарных постов сверх всех постов": g[g.product_posts <= g.posts],
    }
    rows = []
    for name, group in variants.items():
        rows.append({"variant": name, "n": len(group), "sellers": int(group.selling.sum()),
                     "seller_share": ratio(group.selling.sum(), len(group)), "orders": int(group.orders.sum()),
                     "gmv": int(group.gmv.sum()), "aov": ratio(group.gmv.sum(), group.orders.sum()),
                     "candidates": int(group.candidate.sum())})
    return pd.DataFrame(rows)


def metric_catalog(metrics, bundle):
    defs = {
        "seller_share": ("selling_goods", "goods_businesses", "число с orders>0 / число товарных и смешанных"),
        "goods_aov": ("goods_gmv", "goods_orders", "ΣGMV / Σorders"),
        "homepage_share": ("homepage_opens", "market_opens", "открытия с главной / все открытия товаров Маркета"),
        "gmv_top_10_share": ("GMV 10 крупнейших бизнесов", "goods_gmv", "ΣGMV top10 / ΣGMV"),
        "dau_mau_ratio": ("общий средний DAU", "общий MAU", "средний DAU / MAU; охваты других метрик отличаются"),
    }
    rows = []
    for name, value in metrics.items():
        scope = "businesses" if name.startswith(("goods", "selling", "all_", "candidates", "original", "missing", "orders_without", "seller", "gmv_top")) or name == "businesses" else "market"
        if name.startswith("partner"):
            scope = "partner"
        numerator, denominator, formula = defs.get(name, (None, None, "прямой счёт / сумма отфильтрованных исходных полей"))
        if name.endswith("_ratio") and name.startswith(("market_", "partner_")):
            s = name.split("_")[0]
            numerator, denominator = (f"{s}.orders", f"{s}.opens") if "order_open" in name else (f"{s}.opens", f"{s}.impressions")
            formula = f"{numerator} / {denominator}; описательное отношение событий"
        if name in {"market_aov", "partner_aov"}:
            numerator, denominator, formula = f"{scope}.gmv", f"{scope}.orders", "ΣGMV / Σorders"
        rows.append({"metric_id": name, "value": value, "unit": "ratio" if denominator and "aov" not in name else "₽" if "aov" in name or "gmv" in name and "share" not in name else "count",
                     "period": bundle.period, "scope": scope,
                     "population_filter": "type∈{товарное, товарное и услужное}" if scope == "businesses" and name not in {"businesses", "all_orders", "all_sellers", "original_missing", "missing_aov_sellers", "orders_without_current_checkout"} else "весь соответствующий контур",
                     "numerator_ref": numerator, "denominator_ref": denominator, "formula": formula,
                     "source_refs": [SHEETS_REF[scope]], "source_sha256": bundle.source_hash,
                     "availability": "available" if value is not None else "unavailable_zero_denominator",
                     "interpretation_notes": "Синтетическая выборка чемпионата; без экстраполяции на платформу"})
    return rows


SHEETS_REF = {"businesses": "Бизнесы!A1:AB", "market": "Маркет Вконтакте — итоги; источники; категории",
              "partner": "Маркет Вконтакте — итоги; категории; Покупатели"}
