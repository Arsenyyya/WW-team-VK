"""Record inconsistencies without repairing source totals."""

import pandas as pd

from .metrics import ratio


def run_audit(bundle, b):
    issues = []

    def record(check, scope, actual, reference, interpretation, policy, severity="warning", count=1):
        delta = actual - reference if actual is not None and reference is not None else None
        issues.append({"issue_id": f"DQ{len(issues)+1:03}", "check_id": check, "severity": severity,
                       "status": "observed", "scope": scope, "affected_count": int(count),
                       "actual": actual, "reference": reference, "absolute_delta": delta,
                       "relative_delta": ratio(delta, reference) if delta is not None else None,
                       "source_refs": scope, "interpretation": interpretation, "analysis_policy": policy})

    for col in bundle.business.columns:
        n = b[col].isna().sum()
        if n:
            record("missing_values", f"Бизнесы.{col}", int(n), 0, "Значение неизвестно, не равно нулю.",
                   "Сохранять пропуск; показывать размер известной базы.", count=n)
    for check, mask in {
        "active_over_uploaded": b.active_products > b.uploaded_products,
        "product_posts_over_posts": b.product_posts > b.posts,
        "product_clips_over_clips": b.product_clips > b.clips,
        "orders_without_checkout": (b.orders > 0) & (b.checkout == 0),
        "orders_over_content_opens": b.orders > b.content_opens,
        "gmv_without_orders": (b.orders == 0) & (b.gmv > 0),
    }.items():
        n = mask.sum()
        if n:
            record(check, "Бизнесы", int(n), 0,
                   "Охваты/моменты измерения могут различаться; причина не установлена.",
                   "Сохранить строки; чувствительность отдельно. Отношение не считать причинной конверсией.",
                   severity="info" if check in {"orders_over_content_opens", "orders_without_checkout"} else "warning", count=n)
    known = b[(b.orders > 0) & b.reported_aov.notna()].copy()
    calc = known.gmv / known.orders
    mismatch = ((calc > 0) & ((known.reported_aov - calc).abs() / calc > .05)) | ((calc == 0) & (known.reported_aov != 0))
    if mismatch.any():
        record("reported_aov_over_5pct", "Бизнесы: заполненный чек и orders>0", int(mismatch.sum()), 0,
               "Исходный чек отличается от GMV/orders более чем на 5%; причина неизвестна.",
               "Взвешенный чек вычислять отношением сумм; исходный сохранить.", count=mismatch.sum())

    for (metric, scope, aggregation), group in bundle.daily.groupby(["metric_id", "scope", "aggregation"]):
        if aggregation == "non_additive":
            continue
        totals = bundle.totals.query("metric_id == @metric and scope == @scope")
        if len(totals) != 1:
            continue
        actual = group.value.mean() if aggregation == "mean" else group.value.sum(min_count=len(group))
        reference = bundle.total(metric, scope)
        tolerance = .5 if aggregation == "mean" else 0
        if pd.isna(actual) or abs(actual - reference) > tolerance:
            record(f"daily_{aggregation}_{metric}", f"По дням / Итоги: {scope}", float(actual), reference,
                   "Дневной агрегат отличается от итога; причина не установлена.", "Показывать обе величины с их охватом.")

    for scope in ["market", "partner"]:
        s = bundle.sources[(bundle.sources.scope == scope) & ~bundle.sources.is_nested]
        if s.opens.sum() != bundle.total("opens", scope):
            record("source_total", f"Источники / Итоги: {scope}", s.opens.sum(), bundle.total("opens", scope),
                   "Несогласованность открытий.", "Не нормировать разрез под итог.")
        for key in ["categories", "demography", "regions"]:
            table = getattr(bundle, key)
            for metric in ["orders", "buyers", "opens"]:
                rows = table.query("scope == @scope and metric_id == @metric")
                if rows.empty:
                    continue
                total_metric = f"visible_{metric}" if key in {"demography", "regions"} else metric
                reference = bundle.total(total_metric, scope)
                actual = rows.value.sum(min_count=1)
                if actual != reference:
                    record(f"{key}_{metric}", f"{key} / Итоги: {scope}", float(actual), reference,
                           "Расхождение с соответствующим итогом; скрытые группы не восстанавливаем.",
                           "Для распределения использовать сумму своего разреза; для масштаба — итог.")
        if scope in {"market", "partner"}:
            hidden = bundle.total("orders", scope) - bundle.total("visible_orders", scope)
            if hidden:
                record("visible_vs_all_orders", f"Покупатели / Итоги: {scope}", bundle.total("visible_orders", scope),
                       bundle.total("orders", scope), "В итогах заявлено исключение групп меньше 100; полная причина разницы неизвестна.",
                       "Не использовать разрез как полное число заказов.", severity="info")
    content = bundle.sources[bundle.sources.source.isin(["Лента", "Клипы"])].opens.sum()
    common = bundle.total("content_opens", "common")
    if content != common:
        record("content_scopes", "Источники / Общие итоги", float(content), common,
               "Сумма Лента+Клипы двух контуров не равна общей строке; причина неизвестна.",
               "Разные определения/охваты не объединять.")
    record("unique_nonadditivity", "По дням / Итоги", None, None,
           "Дневные уникальные и покупатели не складываются в месячных.", "Для месяца использовать месячный источник.", severity="info")
    record("payment_coverage", "Итоги: market", bundle.total("paid_orders"), bundle.total("orders"),
           "Зарегистрированная онлайн-оплата не охватывает обязательно все способы оплаты/исполнения.",
           "Не считать разницу потерянными продажами или отменами.", severity="info")
    return pd.DataFrame(issues)
