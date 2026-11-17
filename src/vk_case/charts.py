"""Publication exports with explicit units, populations, and scenario labels."""

import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "vk-case-matplotlib"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

INK, BLUE, MUTED, PALE = "#15263E", "#1768F2", "#6B7A90", "#DCE8FA"


def fmt(value):
    return f"{value:,.0f}".replace(",", " ")


def build_figures(out, bundle, tables, metrics, scenarios, sensitivity):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                         "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": INK,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
                         "axes.edgecolor": PALE, "figure.facecolor": "white", "axes.facecolor": "white"})
    exports = []

    def save(fig, name, note):
        fig.text(.02, .012, note, fontsize=8, color=MUTED, va="bottom")
        fig.tight_layout(rect=(0, .06, 1, .98))
        for suffix in ["png", "svg"]:
            fig.savefig(out/f"{name}.{suffix}", dpi=180, bbox_inches="tight")
        plt.close(fig)
        exports.append({"figure_id": name, "source": "DATA", "note": note})

    b = tables["business_features"]
    g = b[b.is_goods]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    labels = ["Вся товарная база", "Активный каталог", "Чекаут подключён", "Есть заказы", "Кандидаты для пилота"]
    vals = [len(g), g.has_active_catalog.sum(), g.checkout.sum(), g.selling.sum(), g.candidate.sum()]
    bars = ax.barh(labels[::-1], vals[::-1], color=[BLUE, INK, PALE, PALE, PALE])
    ax.bar_label(bars, labels=[fmt(x) for x in vals[::-1]], padding=6, color=INK)
    ax.set_xlim(0, max(vals)*1.13)
    ax.set_xlabel("Бизнесы, шт.")
    ax.set_title("Готовность и заказы — самостоятельные признаки", loc="left", weight="bold", pad=20)
    save(fig, "readiness", f"Бизнесы · товарные и смешанные · n={fmt(len(g))}. Группы пересекаются; это не последовательная воронка.")

    t = tables["themes"].sort_values("candidates")
    fig, ax = plt.subplots(figsize=(10, 11))
    bars = ax.barh(t.theme, t.candidates, color=[BLUE if x in {"Кулинария и еда", "Творчество и хендмейд", "Развлечения и хобби"} else PALE for x in t.theme])
    ax.bar_label(bars, padding=3, fontsize=8)
    ax.set_xlabel("Кандидаты, бизнесы")
    ax.set_xlim(0, max(1, t.candidates.max())*1.15)
    ax.set_title("Кандидаты по всем тематикам", loc="left", weight="bold", pad=20)
    save(fig, "candidate_themes", "Бизнесы · фильтр кандидата из методики. Тематика требует ручной проверки; нулевые группы сохранены.")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, scope, title in zip(axes, ["market", "partner"], ["Товары Маркета", "Партнёр 1"], strict=True):
        s = bundle.sources[(bundle.sources.scope == scope) & ~bundle.sources.is_nested].copy()
        s["share"] = s.opens / bundle.total("opens", scope) * 100
        s = s.sort_values("source")
        ax.barh(s.source, s.share, color=BLUE if scope == "market" else INK)
        ax.set_title(title, loc="left", weight="bold")
        ax.set_xlabel("% всех открытий карточек своего контура")
        ax.set_xlim(0, 100)
    save(fig, "traffic_sources", "Источники + Итоги · вложенная реферальная строка исключена. Знаменатель — все открытия соответствующего контура.")

    fig, axes = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
    for ax, scope, title in zip(axes, ["market", "partner"], ["Маркет", "Партнёр 1"], strict=True):
        d = bundle.daily.query("metric_id == 'orders' and scope == @scope").sort_values("date")
        ax.plot(d.date, d.value, color=BLUE, lw=1.5, alpha=.5, label="По дням")
        ax.plot(d.date, d.value.rolling(7, min_periods=7).mean(), color=INK, lw=2, label="Среднее за 7 дней")
        ax.set_ylabel(f"{title}\nзаказы, шт.")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: fmt(x)))
        ax.grid(axis="y", color=PALE)
    axes[0].legend(frameon=False, loc="upper right")
    axes[0].set_title("Динамика заказов без причинной интерпретации", loc="left", weight="bold")
    save(fig, "daily_orders", f"По дням · {bundle.period}. Панели имеют отдельные подписанные шкалы; недельный ряд — среднее событий.")

    fig, ax = plt.subplots(figsize=(10, 5))
    values = scenarios.gmv_realized / 1000
    bars = ax.bar(scenarios.name, values, color=[PALE, BLUE, INK, "#C36B65"][:len(scenarios)])
    ax.bar_label(bars, labels=[f"{x:,.1f}".replace(",", " ") for x in values], padding=6)
    ax.axhline(0, color=MUTED, lw=.7)
    ax.set_ylabel("Дополнительная сохранённая стоимость, тыс. ₽")
    ax.set_title("Сценарии пакета: эффект ещё предстоит измерить", loc="left", weight="bold", pad=20)
    ax.margins(y=.2)
    save(fig, "scenarios", f"Сценарий · N={fmt(metrics['candidates'])}; AOV=ΣGMV/Σзаказов товарной базы. Uplift, частота и выполнение — допущения.")

    fig, axes = plt.subplots(2, 3, figsize=(12, 6))
    names = {"n": "Число кандидатов", "delta_activation": "Дополнительная активация", "orders_per_seller": "Частота заказов",
             "aov": "Средний чек", "realized_value_share": "Сохранённая стоимость", "net_service_rate": "Чистая сервисная ставка"}
    for ax, (key, label) in zip(axes.ravel(), names.items(), strict=True):
        s = sensitivity[sensitivity.parameter == key]
        ax.plot(s.factor, s.vk_contribution/1000, color=BLUE, marker="o", ms=4)
        ax.set_title(label, loc="left", fontsize=10)
        ax.set_xlabel("Множитель допущения")
        ax.set_ylabel("Вклад VK, тыс. ₽")
        ax.grid(axis="y", color=PALE)
    save(fig, "sensitivity", "Сценарий · один параметр меняется, остальные фиксированы. Неизвестные расходы условно равны нулю; 2% — не тариф VK.")

    fig, ax = plt.subplots(figsize=(10, 6))
    t = bundle.categories.query("scope == 'market' and metric_id == 'orders'").sort_values("value")
    bars = ax.barh(t.category, t.value, color=PALE)
    ax.bar_label(bars, padding=3, fontsize=8, labels=[fmt(x) for x in t.value])
    ax.set_xlabel("Заказы по разрезу, шт.")
    ax.set_xlim(0, max(1, t.value.max())*1.2)
    ax.set_title("Все категории сохранены в исходном охвате", loc="left", weight="bold", pad=20)
    save(fig, "categories", f"Категории · сумма {fmt(metrics['market_category_orders'])} ≠ итог {fmt(metrics['market_orders'])}. Подгонка не выполнялась.")

    fig, ax = plt.subplots(figsize=(10, 4.5))
    shares = np.sort(g.gmv.astype(float).to_numpy())[::-1]
    if shares.sum() > 0:
        x = np.arange(1, len(shares)+1)/len(shares)*100
        ax.plot(x, np.cumsum(shares)/shares.sum()*100, color=BLUE, lw=2)
    ax.set(xlim=(0, 100), ylim=(0, 100), xlabel="Доля бизнесов по убыванию GMV, %", ylabel="Накопленная доля GMV, %")
    ax.set_title("Концентрация требует проверки устойчивости", loc="left", weight="bold", pad=20)
    ax.grid(color=PALE)
    save(fig, "concentration", f"Бизнесы · товарная база n={fmt(len(g))}; GMV={fmt(metrics['goods_gmv'])} ₽. Нулевые бизнесы включены.")
    return exports
