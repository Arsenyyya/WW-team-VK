"""Local research studio. The workbook, scenario, and demo are separate contexts."""

import json
import os
import sys
from dataclasses import replace
from html import escape
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

from vk_case.demo import CATALOG, DemoStore
from vk_case.economics import Scenario, model
from vk_case.pipeline import latest
from vk_case.reporting import number

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="WW team · От интереса к заказу", page_icon="◒", layout="wide")
st.markdown("""<style>
 .block-container{max-width:1280px;padding-top:4.7rem;padding-bottom:4rem}
 h1{font-size:2.55rem!important;letter-spacing:-.045em;font-weight:700!important}
 h2{font-size:1.7rem!important;letter-spacing:-.035em}
 h3{font-size:1.15rem!important;letter-spacing:-.015em}
 [data-testid="stSidebar"]{border-right:1px solid #E2E8F1;background:#fff}
 [data-testid="stSidebar"] .stRadio label{padding:.32rem 0}
 [data-testid="stMetric"]{background:#fff;border:1px solid #E3E9F2;border-radius:16px;padding:19px 22px;min-height:128px}
 [data-testid="stMetricValue"]{font-weight:650;letter-spacing:-.04em;font-size:1.9rem}
 .hero{background:#15263E;color:white;padding:36px 38px;border-radius:20px;margin:1rem 0 1.7rem}
 .hero h2{color:white;font-size:2rem!important;margin:0 0 12px}
 .hero p{color:#C3D1E5;font-size:1.05rem;line-height:1.65;max-width:820px;margin:0}
 .eyebrow{font-size:11px;letter-spacing:.13em;font-weight:700;color:#61718A;margin-bottom:12px}
 .tag{display:inline-block;background:#E5EDFA;color:#1768F2;font-size:11px;font-weight:650;padding:5px 10px;border-radius:6px;margin-bottom:10px}
 .product-art{height:180px;border-radius:16px;display:flex;align-items:center;justify-content:center;margin:12px 0 22px;overflow:hidden}
 .cup{width:90px;height:85px;border-radius:9px 9px 38px 38px;background:#FBFCFF;box-shadow:10px 18px 0 #15263E12;position:relative}
 .cup:after{content:'';position:absolute;right:-25px;top:12px;width:35px;height:42px;border:9px solid #FBFCFF;border-radius:50%}
 .small-note{font-size:12px;line-height:1.6;color:#61718A}
 div[data-testid="stAlert"]{border-radius:12px}
 .stButton button,.stDownloadButton button{border-radius:10px!important}
 footer{visibility:hidden}
 </style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def read_run(path, manifest_hash):
    path = Path(path)
    return {"dir": str(path), "metrics": json.loads((path/"metrics.json").read_text()),
            "manifest": json.loads((path/"manifest.json").read_text()),
            "config": json.loads((path/"configuration.json").read_text()),
            "businesses": pd.read_parquet(path/"tables/business_features.parquet"),
            "tables": {name: pd.read_csv(path/f"tables/{name}.csv") for name in ["totals", "daily", "sources", "categories", "demography", "regions", "scenarios", "robustness"]},
            "audit": pd.read_csv(path/"audit/issues.csv")}


def download(label, path, key, file_name=None):
    path = Path(path)
    st.download_button(label, path.read_bytes(), file_name=file_name or path.name, key=key, width="stretch")


def csv_download(label, df, key):
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"), file_name=f"{key}.csv", mime="text/csv", key=key)


def metric_row(items):
    for column, (label, value, help_text) in zip(st.columns(len(items)), items, strict=True):
        column.metric(label, value, help=help_text)


def header(kicker, title, description):
    st.markdown(f"<div class='eyebrow'>{escape(kicker.upper())}</div>", unsafe_allow_html=True)
    st.title(title)
    st.caption(description)


def overview(data):
    m = data["metrics"]
    header("WW team / исследовательская студия", "От интереса к заказу", "Стратегия социальной коммерции · VK Case Champ 2026 · Санкт-Петербург")
    st.markdown("<div class='hero'><div class='tag'>ПРОДУКТОВАЯ ГИПОТЕЗА</div><h2>Покупка начинается с доверия.<br>Продажа — с понятного следующего шага.</h2><p>Помочь готовому товарному бизнесу связать контент, условия и оформление заказа. Маркет — общие торговые компоненты. Роль отдельной главной проверяем экспериментом.</p></div>", unsafe_allow_html=True)
    metric_row([("Товарная база", number(m["goods_businesses"]), "Товарные и смешанные business_id"),
                ("С заказами", number(m["selling_goods"]), f"{number(m['selling_goods'])} / {number(m['goods_businesses'])} = {number(m['seller_share']*100,2)}%"),
                ("Кандидаты", number(m["candidates"]), "Активный каталог, просмотры товарного контента и ноль заказов"),
                ("Взвешенный чек", number(m["goods_aov"], 2)+" ₽", "ΣGMV / Σзаказов товарной базы")])
    st.write("")
    left, right = st.columns([1.4, 1], gap="large")
    with left:
        st.subheader("Три решения из анализа")
        st.markdown(f"**01 · Начать с готовности.** {number(m['candidates'])} кандидатов дают базу для ручной квалификации и аудита пути; не все станут новыми продавцами.")
        st.markdown(f"**02 · Проверить компоненты, затем главную.** Доля главной — {number(m['homepage_share']*100,3)}% открытий её товаров. Заказы и затраты этого входа неизвестны.")
        st.markdown("**03 · Измерять выполненный результат.** Подключение инструмента — промежуточный шаг. Считаем уникальных продающих бизнесов и отдельно качество исполнения.")
    with right:
        st.subheader("Материалы для команды")
        d = Path(data["dir"])
        download("Презентация · 8 слайдов PDF", d/"slides/strategy_draft.pdf", "deck_pdf", "WW_team_strategy_spb.pdf")
        download("Редактируемая презентация · PPTX", d/"slides/strategy_draft.pptx", "deck_pptx", "WW_team_strategy_spb.pptx")
        download("Исследование и экономика · PDF", d/"reports/report.pdf", "report_pdf")
        st.caption("WW team · Савватеев Глеб, Бочковский Андрей, Веселкин Арсений, Павлов Арсений. Состав и вузы включены в материалы.")
    with st.expander("Происхождение и границы данных"):
        st.write(f"Все 7 листов XLSX · {data['manifest']['period']} · синтетические данные чемпионата, не реальные показатели VK.")
        st.caption(f"Версия расчёта: {data['manifest']['run_id']} · SHA-256: {data['manifest']['workbook_sha256']}")
        st.info("Выборка бизнесов, агрегаты Маркета и Партнёр 1 — независимые контуры. Их аудитории и заказы не объединяются по выдуманным ключам.")


def quality(data):
    header("Проверяемость", "Данные с видимыми ограничениями", "Расхождения сохранены. Для каждого указано правило применения; исходные значения не исправлялись.")
    m = data["metrics"]
    metric_row([("Категории сверх итога", "+"+number(m["market_category_orders"]-m["market_orders"]), "Заказы Маркета по категориям минус итог"),
                ("Оригинальность неизвестна", number(m["original_missing"]), f"Из {number(m['businesses'])} бизнесов"),
                ("Заказы при чекауте 0", number(m["orders_without_current_checkout"]), "Настройка и заказы могут относиться к разным моментам")])
    st.write("")
    issues = data["audit"]
    level = st.segmented_control("Показать", ["Все", "Ограничения", "Особенности"], default="Все")
    if level != "Все":
        issues = issues[issues.severity == ("warning" if level == "Ограничения" else "info")]
    view = issues[["scope", "actual", "reference", "interpretation", "analysis_policy"]].rename(columns={
        "scope": "Источник", "actual": "Наблюдение", "reference": "Сравнение", "interpretation": "Что известно", "analysis_policy": "Как используем"})
    st.dataframe(view, hide_index=True, width="stretch", height=490)
    st.caption("Пропуски и тире имеют разные статусы; заполненные нули остаются нулями. Неизвестная причина не заменяется предположением.")
    csv_download("Выгрузить реестр проверок", issues, "audit")
    with st.expander("Методика и независимая сверка"):
        checks = pd.read_csv(Path(data["dir"])/"audit/independent_checks.csv")
        st.write(f"{len(checks)} ключевых чисел независимо пересчитаны через чтение исходных ячеек и скалярные операции Python.")
        st.dataframe(checks.rename(columns={"metric_id": "Показатель", "independent": "Независимо", "pipeline": "Основной расчёт", "matches": "Совпадает"}), hide_index=True)


def businesses(data):
    header("Анализ выборки", "Бизнесы и готовность к заказу", "Фильтры применяются только к сообществам. Агрегаты Маркета и Партнёра остаются в своих охватах.")
    b = data["businesses"]
    a, c, d, e = st.columns(4)
    types = a.multiselect("Тип бизнеса", sorted(b.business_type.unique()), default=["товарное", "товарное и услужное"])
    themes = c.multiselect("Тематика", sorted(b.theme.unique()), placeholder="Все тематики")
    scales = d.multiselect("Аудитория", sorted(b.audience_band.unique()), placeholder="Все размеры")
    stages = e.multiselect("Стадия", sorted(b.stage.unique()), placeholder="Все стадии")
    selected = b[b.business_type.isin(types)]
    for values, col in [(themes, "theme"), (scales, "audience_band"), (stages, "stage")]:
        if values:
            selected = selected[selected[col].isin(values)]
    only = st.toggle("Только кандидаты для пилота", value=False)
    if only:
        selected = selected[selected.candidate]
    if selected.empty:
        st.info("В выбранном сочетании нет бизнесов. Измените один из фильтров.")
        return
    n, sellers, orders, gmv = len(selected), int(selected.selling.sum()), int(selected.orders.sum()), int(selected.gmv.sum())
    metric_row([("Выбрано бизнесов", number(n), "Уникальные business_id"),
                ("С заказами / выбранные", number(sellers/n*100,2)+"%", f"{sellers} / {n}"),
                ("Заказы", number(orders), "Внутренний чекаут за исходный месяц"),
                ("GMV до возвратов", number(gmv)+" ₽", "Не прибыль и не выручка VK")])
    st.write("")
    tab1, tab2, tab3 = st.tabs(["Бизнесы", "Стадии и настройки", "Устойчивость и контент"])
    with tab1:
        view = selected.sort_values(["content_opens", "product_views", "business_id"], ascending=[False, False, True])
        cols = ["business_id", "theme", "business_type", "subscribers", "stage", "active_products", "content_opens", "orders", "gmv", "candidate"]
        display = view[cols].rename(columns={"business_id": "ID", "theme": "Тематика", "business_type": "Тип", "subscribers": "Подписчики", "stage": "Стадия", "active_products": "Активные товары", "content_opens": "Открытия из контента", "orders": "Заказы", "gmv": "GMV, ₽", "candidate": "Кандидат"})
        st.dataframe(display, hide_index=True, width="stretch", height=430)
        csv_download("Скачать выбранные бизнесы", display, "selected_businesses")
        st.caption("Сортировка по открытиям, просмотрам и ID — порядок ручного аудита. Имена, ссылки и согласие обезличенных продавцов неизвестны.")
    with tab2:
        st.bar_chart(selected.groupby("stage", dropna=False).size().rename("Бизнесы"), horizontal=True, color="#1768F2")
        ready = pd.Series({"Активный каталог": selected.has_active_catalog.sum(), "Чекаут": selected.checkout.sum(), "Доставка": selected.delivery.sum(), "Оплата": selected.payment.sum()})
        st.dataframe(ready.rename("Бизнесы").to_frame(), width="stretch")
        st.caption(f"Знаменатель каждой настройки — {n} выбранных бизнесов. Флаги самостоятельны; самовывоз и оплата при получении допустимы.")
    with tab3:
        st.caption("Этот раздел относится ко всей товарной базе и не меняется фильтрами выше.")
        st.dataframe(data["tables"]["robustness"], hide_index=True, width="stretch")
        compare = pd.read_csv(Path(data["dir"])/"tables/content_comparisons.csv")
        st.dataframe(compare[["comparison", "n", "median", "ci_low", "ci_high"]], hide_index=True, width="stretch")
        st.info("Парное сравнение — описательное, единица bootstrap — бизнес. Группа доступности мала; словарь числа публикаций требует проверки. Оно не доказывает причинный эффект контента.")


def market(data):
    header("Независимые товарные контуры", "Маркет и Партнёр 1", "Источник трафика, место оформления и место оплаты — разные признаки. Последовательную воронку эти агрегаты не задают.")
    label = st.segmented_control("Контур", ["Товары Маркета", "Партнёр 1"], default="Товары Маркета")
    scope = "market" if label == "Товары Маркета" else "partner"
    totals = data["tables"]["totals"]
    scoped = totals[totals.scope == scope].set_index("metric_id")
    def value(name):
        return float(scoped.loc[name, "value"])
    metric_row([("Показы", number(value("impressions")), "События за месяц"),
                ("Открытия карточек", number(value("opens")), "Не уникальные пользователи"),
                ("Оформленные заказы", number(value("orders")), "Контур Маркета внутренний; Партнёра — внешний"),
                ("Средний чек", number(value("gmv")/value("orders"), 2)+" ₽", "ΣGMV / Σзаказов своего контура")])
    if scope == "partner":
        st.info(f"Есть {number(value('direct_redirects'))} прямых переходов мимо карточки. Все заказы / открытия карточки — описательное отношение, не конверсия этого пути.")
    t1, t2, t3 = st.tabs(["Источники и дни", "Категории", "Покупатели и регионы"])
    with t1:
        s = data["tables"]["sources"]
        s = s[(s.scope == scope) & ~s.is_nested].copy()
        s["Доля открытий, %"] = s.opens/value("opens")*100
        st.bar_chart(s.set_index("source")[["Доля открытий, %"]], horizontal=True, color="#1768F2")
        st.caption("Знаменатель — все открытия карточек выбранного контура. Вложенная реферальная строка не прибавляется к источникам.")
        days = data["tables"]["daily"]
        days = days[(days.scope == scope) & (days.metric_id == "orders")].copy()
        days.date = pd.to_datetime(days.date)
        chosen = st.date_input("Период дневного ряда", (days.date.min().date(), days.date.max().date()), min_value=days.date.min().date(), max_value=days.date.max().date())
        if len(chosen) == 2:
            days = days[days.date.between(pd.Timestamp(chosen[0]), pd.Timestamp(chosen[1]))]
        st.line_chart(days.set_index("date").value.rename("Заказы за день"), color="#1768F2")
        st.caption("Фильтр дат меняет только дневной ряд. Месячные уникальные и метрики карточек выше берутся из итогов за полный месяц.")
    with t2:
        t = data["tables"]["categories"]
        t = t[(t.scope == scope) & (t.metric_id == "orders")].sort_values("value", ascending=False).copy()
        t["Доля разреза, %"] = t.value/t.value.sum()*100
        st.warning(f"Сумма категорий {number(t.value.sum())} отличается от итога {number(value('orders'))}. Доли ниже — от суммы категорий; источник не подгонялся.")
        st.dataframe(t[["category", "value", "Доля разреза, %"]].rename(columns={"category": "Категория", "value": "Заказы"}), hide_index=True, width="stretch")
    with t3:
        st.caption("Малые группы в источнике скрыты. Возраст и регион не соединяются с бизнесами по тематике.")
        for key, label, columns in [("demography", "Пол и возраст", ["sex", "age"]), ("regions", "Регионы", ["region"])]:
            t = data["tables"][key]
            t = t[(t.scope == scope) & (t.metric_id == "orders")].copy()
            st.subheader(label)
            st.caption(f"Сумма видимых заказов: {number(t.value.sum())}. Пропуск не равен нулю; оригинальные названия регионов сохранены.")
            st.dataframe(t[columns+["value", "availability"]].rename(columns={"sex": "Пол", "age": "Возраст", "region": "Регион", "value": "Заказы", "availability": "Доступность"}), hide_index=True, width="stretch")


def economics(data):
    header("Сценарный калькулятор", "Что должно измениться в экономике", "N и чек взяты из анализа. Остальные вводные — редактируемые допущения; это не прогноз и не результат эксперимента.")
    m, cfg = data["metrics"], data["config"]["economics"]
    a, b, c = st.columns(3)
    n = a.number_input("Подходящие бизнесы, N", min_value=0, value=int(m["candidates"]), step=10)
    uplift = b.slider("Дополнительная активация, п.п.", -10., 20., 4., .5)
    frequency = c.number_input("Заказов на дополнительного продавца", min_value=0., value=5., step=.5)
    a, b, c = st.columns(3)
    aov = a.number_input("Средний чек, ₽", min_value=0., value=float(m["goods_aov"]), step=100., format="%.2f")
    realized = b.slider("Сохранённая стоимость, %", 0, 100, 80)
    rate = c.slider("Условная чистая ставка сервиса, %", 0., 15., 2., .5)
    known_margin = st.toggle("Маржа продавца известна", value=False)
    margin = st.slider("Валовая маржа после себестоимости, %", 0, 100, 35) if known_margin else None
    with st.expander("Расходы, удержание и горизонт"):
        st.caption("Маржа уже учитывает себестоимость. Возвраты уменьшают стоимость один раз; возвратная логистика может быть расходом. Нули ниже — допущения, не установленные затраты.")
        a, b, c = st.columns(3)
        investment = a.number_input("Разовые инвестиции, ₽", min_value=0., value=float(cfg["investment"]), step=10000.)
        retention = b.slider("Месячное удержание когорты, %", 0, 100, int(cfg["retention"]*100))
        horizon = c.number_input("Горизонт, месяцев", min_value=1, max_value=60, value=cfg["horizon_months"])
        seller_costs = {}
        for column, key, label in zip(st.columns(3), ["acquisition_cost", "fulfillment_and_return_costs", "labor_cost"], ["Привлечение продавца, ₽", "Исполнение и возвратная логистика, ₽", "Дополнительный труд, ₽"], strict=True):
            seller_costs[key] = column.number_input(label, min_value=0., value=float(cfg[key]), step=1000.)
        vk_costs = {}
        columns = st.columns(3)
        for i, (key, label) in enumerate([("incremental_ad_revenue", "Дополнительная реклама VK, ₽"), ("net_partner_revenue", "Чистый партнёрский доход, ₽"), ("variable_costs", "Переменные расходы VK, ₽"), ("subsidies", "Субсидии VK, ₽"), ("support_costs", "Поддержка VK, ₽"), ("cannibalized_contribution", "Потерянный существующий вклад, ₽")]):
            vk_costs[key] = columns[i%3].number_input(label, min_value=0., value=float(cfg[key]), step=1000.)
    s = Scenario(n=n, delta_activation=uplift/100, orders_per_seller=frequency, aov=aov,
                 realized_value_share=realized/100, net_service_rate=rate/100,
                 gross_margin=None if margin is None else margin/100, investment=investment,
                 retention=retention/100, horizon_months=horizon, **seller_costs, **vk_costs)
    result = model(s)
    st.write("")
    metric_row([("Доп. продавцы, ожидание", number(result["delta_sellers"],2), "N × разница долей"),
                ("Доп. заказы, ожидание", number(result["delta_orders"],2), "Доп. продавцы × частота"),
                ("Сохранённая стоимость", number(result["gmv_realized"])+" ₽", "После невыполнения и возвратов"),
                ("Прибыль продавца", number(result["seller_profit"])+(" ₽" if margin is not None else ""), "Без маржи значение недоступно")])
    left, right = st.columns([1.5, 1], gap="large")
    with left:
        st.subheader("Вклад одной первоначальной когорты")
        curve = pd.DataFrame(result["periods"]).set_index("month")
        st.line_chart(curve[["cumulative_contribution", "net_of_investment"]].rename(columns={"cumulative_contribution": "Накопленный вклад, ₽", "net_of_investment": "После инвестиций, ₽"}))
    with right:
        st.subheader("Что получает VK")
        st.write(f"Дополнительный месячный вклад до инвестиций: **{number(result['vk_contribution'])} ₽**.")
        st.write(f"Окупаемость: **{str(result['payback_month'])+' мес.' if result['payback_month'] else 'не достигается на заданном горизонте'}**.")
        st.caption("Новые когорты не добавляются; вклад уменьшается с удержанием. Дополнительные расходы и доходы заданы для всей первоначальной когорты и масштабируются с ней. Это упрощение.")
    variants = []
    for factor in [.5, .75, 1., 1.25, 1.5]:
        r = model(replace(s, delta_activation=s.delta_activation*factor))
        variants.append({"Дополнительная активация, п.п.": s.delta_activation*factor*100, "Сохранённая стоимость, ₽": r["gmv_realized"]})
    st.subheader("Чувствительность к дополнительной активации")
    st.bar_chart(pd.DataFrame(variants).set_index("Дополнительная активация, п.п."), color="#1768F2")
    csv_download("Скачать текущий расчёт", pd.DataFrame([{**s.__dict__, **{k: v for k,v in result.items() if k != "periods"}}]), "scenario")
    with st.expander("Четыре исходных сценария текущего запуска"):
        st.dataframe(data["tables"]["scenarios"][["name", "delta_sellers", "delta_orders", "gmv_realized", "vk_contribution", "seller_profit"]], hide_index=True)


def demo():
    st.markdown("<span class='tag'>ЛОКАЛЬНОЕ ДЕМО · В АНАЛИЗ НЕ ПОПАДАЕТ</span>", unsafe_allow_html=True)
    store = DemoStore(Path(os.environ.get("VK_CASE_DEMO_STORE", str(ROOT/"data/demo/runtime.sqlite"))))
    if "request_key" not in st.session_state:
        st.session_state.request_key = str(uuid4())
    seller = st.selectbox("Сценарий продавца", ["Готовый товар", "Товар под заказ", "Локальная еда", "Внешний магазин"])
    product = CATALOG[["Готовый товар", "Товар под заказ", "Локальная еда", "Внешний магазин"].index(seller)]
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        st.subheader("Готовность продавца")
        ready1 = st.checkbox("Наличие и цена актуальны", value=True)
        ready2 = st.checkbox("Условия получения определены", value=True)
        ready3 = st.checkbox("Есть ответственный за исполнение", value=True)
        next_action = "Проверьте наличие и цену" if not ready1 else "Укажите получение" if not ready2 else "Назначьте ответственного" if not ready3 else "Пройдите тестовый путь покупателя"
        st.info("Следующее действие: "+next_action)
        st.caption("Это целевой дизайн диагностики; названия и товары вымышлены, данные не восстановлены из XLSX.")
    with right:
        st.markdown(f"<div class='product-art' style='background:{product['color']}'><div class='cup'></div></div>", unsafe_allow_html=True)
        st.caption(product["seller"])
        st.subheader(product["name"])
        st.write(product["description"])
        st.write(f"**{number(product['price_minor']/100)} ₽** · в наличии {product['stock']}")
        if product["route"] == "external":
            if st.button("Зафиксировать внешний переход", type="primary", width="stretch"):
                store.record_event(st.session_state.request_key+"-external", "partner_redirect")
                st.success("Переход сохранён. Покупка и внутренний заказ не подтверждены.")
            return
        quote = False
        if product["route"] == "custom":
            brief = st.text_area("Пожелания к товару", placeholder="Цвет, размер, особенности")
            if st.button("Сохранить запрос"):
                if len(brief.strip()) < 5:
                    st.warning("Опишите пожелания хотя бы несколькими словами.")
                else:
                    try:
                        store.save_request(st.session_state.request_key, product["id"], brief)
                        st.session_state.quote_ready = True
                        st.success("Пожелания сохранены локально.")
                    except ValueError as exc:
                        st.warning(str(exc))
            if not st.session_state.get("quote_ready"):
                st.caption("После запроса появится демонстрационное предложение.")
                return
            st.info(f"Демо-предложение: {number(product['price_minor']/100)} ₽, срок 14 дней. Реальному продавцу запрос не отправлялся.")
            quote = st.checkbox("Согласен с предложением и сроком")
        qty = st.number_input("Количество", min_value=1, max_value=product["stock"], value=1, step=1)
        fulfillment_label = st.selectbox("Получение", ["Самовывоз"] if product["route"] == "food" else ["Самовывоз", "Доставка"])
        zone = st.selectbox("Зона получения", ["Центр", "За пределами зоны"]) if product["route"] == "food" else "Центр"
        payment_label = st.selectbox("Оплата", ["При получении", "Онлайн — демонстрация"])
        consent = st.checkbox("Проверил состав, стоимость и получение")
        st.write(f"Итого: **{number(qty*product['price_minor']/100)} ₽**")
        if st.button("Подтвердить демо-заказ", type="primary", width="stretch"):
            if not (ready1 and ready2 and ready3 and consent):
                st.warning("Завершите готовность продавца и подтвердите условия.")
            else:
                try:
                    if quote:
                        store.record_event(st.session_state.request_key+"-quote", "quote_accepted")
                    order = store.create(st.session_state.request_key, product["id"], qty,
                                         "on_receipt" if payment_label == "При получении" else "online",
                                         "pickup" if fulfillment_label == "Самовывоз" else "delivery", zone, quote)
                    st.session_state.active_order = order["order_id"]
                    st.success("Заказ сохранён: "+order["order_id"]+". Повторное подтверждение не создаст второй.")
                except ValueError as exc:
                    st.warning(str(exc))
    orders = store.list_orders()
    if orders:
        st.divider()
        st.subheader("Демонстрационные заказы")
        chosen = st.selectbox("Заказ", [o["order_id"] for o in orders])
        row = next(o for o in orders if o["order_id"] == chosen)
        states = {"created": "Создан", "ready": "Готов к получению", "completed": "Выполнен", "cancelled": "Отменён", "refunded": "Возврат зарегистрирован"}
        st.write(f"Статус: **{states[row['state']]}** · оплата {'зарегистрирована' if row['paid'] else 'не зарегистрирована'}")
        action = st.selectbox("Изменить состояние", ["Зарегистрировать демо-оплату", "Подготовить к получению", "Подтвердить выполнение", "Отменить", "Зарегистрировать возврат"])
        events = ["payment_registered", "ready", "order_completed", "order_cancelled", "refund_registered"]
        if st.button("Применить изменение"):
            try:
                store.transition(chosen, events[["Зарегистрировать демо-оплату", "Подготовить к получению", "Подтвердить выполнение", "Отменить", "Зарегистрировать возврат"].index(action)], str(uuid4()))
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))
        st.caption("При онлайн-оплате подготовка доступна после регистрации оплаты. При оплате при получении выполнение может предшествовать платёжному событию.")
    col1, col2 = st.columns(2)
    if col1.button("Начать новый демо-заказ"):
        st.session_state.request_key = str(uuid4())
        st.session_state.quote_ready = False
        st.rerun()
    with col2.expander("Сброс демонстрации"):
        confirm = st.checkbox("Удалить все локальные демо-заказы")
        if st.button("Очистить демо", disabled=not confirm):
            store.reset()
            st.session_state.request_key = str(uuid4())
            st.session_state.quote_ready = False
            st.rerun()


def concept(data):
    header("Стратегия и прототип", "Общие компоненты. Разные пути.", "Решение отвечает задаче самостоятельного товарного бизнеса. Эксперимент и исследования ещё предстоят.")
    tab1, tab2, tab3 = st.tabs(["Концепция и альтернативы", "Пилот и метрики", "Работающий прототип"])
    with tab1:
        st.markdown((Path(data["dir"])/"reports/strategy.md").read_text())
    with tab2:
        experiment = json.loads((Path(data["dir"])/"experiment.json").read_text())
        metric_row([("Контроль", number(experiment["n_control"]), "Независимые бизнесы"),
                    ("Тест", number(experiment["n_treatment"]), "Иллюстрация +3 п.п., p0=6,85%"),
                    ("Кандидаты", number(data["metrics"]["candidates"]), "Для показанного размера эффекта недостаточно")])
        st.markdown((Path(data["dir"])/"reports/experiment_plan.md").read_text())
    with tab3:
        demo()


with st.sidebar:
    st.markdown("## WW team")
    st.caption("VK Case Champ 2026\n\nСанкт-Петербург")
    st.divider()
    page = st.radio("Раздел", ["Обзор", "Качество", "Бизнесы", "Маркет", "Экономика", "Концепция"], label_visibility="collapsed")
    st.divider()
    st.markdown("<div class='small-note'>Исследовательская концепция.<br>Синтетические данные кейса.<br>Версия материалов · 18.11.2026</div>", unsafe_allow_html=True)

if "--demo" in sys.argv:
    header("Отдельный режим", "Прототип заказа", "Работает без исходного XLSX. Демо не создаёт аналитический отчёт.")
    demo()
else:
    try:
        path = latest(ROOT/"outputs")
        import hashlib
        data = read_run(str(path), hashlib.sha256((path/"manifest.json").read_bytes()).hexdigest())
    except (ValueError, OSError, KeyError):
        st.info("Сначала выполните полный расчёт из README. Для просмотра только прототипа запустите приложение с параметром --demo.")
        st.stop()
    {"Обзор": overview, "Качество": quality, "Бизнесы": businesses, "Маркет": market,
     "Экономика": economics, "Концепция": concept}[page](data)
