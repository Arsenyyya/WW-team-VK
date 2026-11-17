"""Read the workbook by named headers; preserve raw cells and their availability."""

import re
import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import openpyxl
import pandas as pd
from openpyxl.utils import get_column_letter

BUSINESS_HEADERS = {
    "ID бизнеса": "business_id", "Тематика": "theme", "Тип бизнеса (товары / услуги)": "business_type",
    "Число подписчиков": "subscribers", "Посты за 30 дней": "posts", "Клипы за 30 дней": "clips",
    "Посты с товаром за 30 дней": "product_posts", "Клипы с товаром за 30 дней": "product_clips",
    "Просмотры обычного контента": "ordinary_views", "Лайки обычного контента": "ordinary_likes",
    "Репосты обычного контента": "ordinary_reposts", "Просмотры товарного контента": "product_views",
    "Лайки товарного контента": "product_likes", "Репосты товарного контента": "product_reposts",
    "Открытия карточки товара из контента": "content_opens", "Товары загружены": "uploaded_products",
    "Число активных товаров в каталоге": "active_products", "Подключён чекаут": "checkout",
    "Подключена доставка": "delivery", "Подключена оплата": "payment",
    "Автор оригинального контента (оценка модели)": "original_content",
    "Участие в реферальной программе": "referral", "Заказы через чекаут": "orders",
    "GMV через чекаут, ₽": "gmv", "Средний чек, ₽": "reported_aov",
    "Траты на рекламу всего, ₽": "ad_spend", "Число активных услуг": "active_services",
    "Медианная цена товара, ₽": "median_product_price",
}
SHEETS = {
    "businesses": "Бизнесы", "totals": "Маркет Вконтакте — итоги",
    "daily": "Маркет Вконтакте — по дням", "sources": "Маркет Вконтакте — источники",
    "categories": "Маркет Вконтакте — категории", "demography": "Покупатели",
    "regions": "Покупатели по регионам",
}
TOTAL_IDS = {
    "Показы товаров": "impressions", "Открытия карточки товара": "opens",
    "Нажатия на кнопку в карточке": "button_clicks",
    "Прямые переходы к Партнёру 1 (без открытия карточки)": "direct_redirects",
    "Оформленные заказы": "orders", "Оплаченные заказы": "paid_orders", "GMV, ₽": "gmv",
    "Средний чек, ₽": "reported_aov", "Уникальные покупатели за 30 дней": "buyers",
    "Заказов на покупателя": "orders_per_buyer", "Доля повторных покупателей (2+ заказа), %": "repeat_share",
    "Конверсия: показ → открытие карточки, %": "reported_open_ratio",
    "Конверсия: открытие карточки → заказ, %": "reported_order_open_ratio",
    "Конверсия: показ → заказ, %": "reported_order_impression_ratio",
    "Покупатели на листах «Покупатели» и «Покупатели по регионам» (без групп меньше 100)": "visible_buyers",
    "Заказы на листах «Покупатели» и «Покупатели по регионам» (без групп меньше 100)": "visible_orders",
    "DAU Маркета Вконтакте (среднее за день)": "dau",
    "MAU Маркета Вконтакте (уникальные за 30 дней)": "mau",
    "Пользователи, видевшие товары за 30 дней": "unique_viewers",
    "Пользователи, открывавшие карточку товара за 30 дней": "unique_openers",
    "Открытия карточки товара из постов и клипов": "content_opens",
    "в т.ч. из реферальных постов и клипов": "referral_opens",
    "Запросы в товарном поиске": "search_queries",
    "Доля поисковых запросов с открытием карточки, %": "search_open_share",
}
DAILY_IDS = {
    "DAU Маркета Вконтакте": ("dau", "common", "mean"),
    "Видели товары (уник.)": ("unique_viewers", "common", "non_additive"),
    "Открывали карточку (уник.)": ("unique_openers", "common", "non_additive"),
    "Поисковые запросы": ("search_queries", "common", "sum"),
    "Поисковые запросы с открытием карточки": ("search_queries_with_open", "common", "sum"),
}
EVENT_PREFIXES = {
    "Показы товаров": "impressions", "Открытия карточки": "opens", "Нажатия на кнопку": "button_clicks",
    "Заказы": "orders", "Оплаченные заказы": "paid_orders", "GMV, ₽": "gmv", "Покупатели": "buyers",
}
SCOPES = {"Маркет Вконтакте": "market", "Партнёр 1": "partner", "Всего": "common"}


class DataError(ValueError):
    """A user-readable input or integrity problem."""


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip().lower().replace("ё", "е")


def availability(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "missing"
    if isinstance(value, str) and value.strip() in {"—", "–", "-"}:
        return "dash_unavailable"
    return "available"


def validate_headers(headers, required):
    normalized = [normalize(h) for h in headers]
    if len(normalized) != len(set(normalized)):
        raise DataError("Неоднозначные заголовки: коллизия после нормализации пробелов/Unicode.")
    lookup = dict(zip(normalized, headers, strict=True))
    missing = [h for h in required if normalize(h) not in lookup]
    if missing:
        raise DataError(f"Отсутствуют обязательные столбцы: {', '.join(missing)}")
    return {lookup[normalize(h)]: name for h, name in required.items()}


@dataclass
class Bundle:
    path: Path
    source_hash: str
    period: str
    business: pd.DataFrame
    raw: dict[str, pd.DataFrame]
    totals: pd.DataFrame
    daily: pd.DataFrame
    sources: pd.DataFrame
    categories: pd.DataFrame
    demography: pd.DataFrame
    regions: pd.DataFrame
    cell_status: pd.DataFrame
    schema: list[dict]

    def total(self, metric, scope="market"):
        rows = self.totals[(self.totals.metric_id == metric) & (self.totals.scope == scope)]
        if len(rows) != 1 or rows.iloc[0].availability != "available":
            raise DataError(f"Недоступен или неоднозначен итог {scope}/{metric}.")
        return float(rows.iloc[0].value)


def locate(input_dir: Path, workbook: Path | None = None) -> Path:
    if workbook:
        if not workbook.is_file():
            raise DataError(f"XLSX не найден: {workbook}")
        return workbook.resolve()
    choices = sorted(input_dir.glob("*.xlsx"))
    if len(choices) != 1:
        raise DataError(f"Нужен один XLSX в {input_dir}; найдено {len(choices)}. Укажите --workbook.")
    return choices[0].resolve()


def load(path: Path) -> Bundle:
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    lookup = {normalize(name): name for name in book.sheetnames}
    if len(lookup) != len(book.sheetnames):
        raise DataError("Неоднозначные названия листов.")
    raw, schema, statuses = {}, [], []
    for key, expected in SHEETS.items():
        if normalize(expected) not in lookup:
            raise DataError(f"Отсутствует обязательный лист «{expected}».")
        sheet = book[lookup[normalize(expected)]]
        rows = list(sheet.values)
        headers = rows[0]
        validate_headers(headers, {})
        raw[key] = pd.DataFrame(rows[1:], columns=headers)
        schema.append({"sheet": sheet.title, "key": key, "rows": len(rows) - 1,
                       "columns": len(headers), "headers": list(headers)})
        for i, row in enumerate(rows[1:], start=2):
            for j, value in enumerate(row, start=1):
                status = availability(value)
                if status != "available":
                    statuses.append({"source_ref": f"{sheet.title}!{get_column_letter(j)}{i}",
                                     "availability": status, "original": value})
    book.close()
    b = raw["businesses"].rename(columns=validate_headers(raw["businesses"].columns, BUSINESS_HEADERS)).copy()
    for col in BUSINESS_HEADERS.values():
        if col not in {"theme", "business_type"}:
            original = b[col]
            b[col] = pd.to_numeric(original.where(original.map(availability) == "available"), errors="raise")
            if col not in {"reported_aov", "median_product_price"}:
                if (b[col].dropna() % 1 != 0).any():
                    raise DataError(f"Ожидался целочисленный счётчик: {col}")
                b[col] = b[col].astype("Int64")
    if b.empty:
        raise DataError("Лист бизнесов пуст; результат анализа не может быть успешным.")
    required_nonnull = set(BUSINESS_HEADERS.values()) - {"original_content", "reported_aov", "median_product_price"}
    if b[list(required_nonnull)].isna().any().any():
        raise DataError("Пропуск в обязательном поле бизнеса. Проверьте исходник; ноль не подставляется.")
    if b.business_id.duplicated().any():
        raise DataError("Повторяющиеся ID бизнеса: единица наблюдения неоднозначна.")
    unknown = set(b.business_type) - {"товарное", "товарное и услужное", "услужное", "без каталога"}
    if unknown:
        raise DataError(f"Неизвестный тип бизнеса: {unknown}")
    for col in ["checkout", "delivery", "payment", "referral", "original_content"]:
        if not b[col].dropna().isin([0, 1]).all():
            raise DataError(f"Флаг {col} должен принимать 0/1 или допустимый пропуск.")
    numeric = b.select_dtypes("number")
    if (numeric < 0).any().any():
        raise DataError("Отрицательный исходный счётчик или денежное поле.")

    total_raw = raw["totals"]
    validate_headers(total_raw.columns, {h: h for h in ["Метрика", *SCOPES]})
    period_rows = total_raw[total_raw["Метрика"].map(normalize) == normalize("Период")]
    if len(period_rows) != 1 or not isinstance(period_rows.iloc[0]["Всего"], str):
        raise DataError("Не найден однозначный период на листе итогов.")
    period = period_rows.iloc[0]["Всего"]
    totals = []
    metric_lookup = {normalize(k): v for k, v in TOTAL_IDS.items()}
    for i, row in total_raw.iterrows():
        metric_id = metric_lookup.get(normalize(row["Метрика"]))
        if metric_id is None:
            continue
        for label, scope in SCOPES.items():
            if scope == "common" and i < period_rows.index[0]:
                continue
            if scope != "common" and i >= period_rows.index[0]:
                continue
            value = row[label]
            totals.append({"metric_id": metric_id, "scope": scope, "label": row["Метрика"],
                           "value": float(value) if availability(value) == "available" else None,
                           "unit": "₽" if "₽" in row["Метрика"] else "%" if "%" in row["Метрика"] else "count",
                           "availability": availability(value), "period": period,
                           "source_ref": f"{SHEETS['totals']}!{get_column_letter(total_raw.columns.get_loc(label)+1)}{i+2}"})
    totals = pd.DataFrame(totals)
    if totals.duplicated(["metric_id", "scope"]).any():
        raise DataError("Повторяющиеся метрики на листе итогов.")

    def scope_column(header):
        if ": " not in header:
            raise DataError(f"Неизвестный формат столбца: {header}")
        prefix, scope_name = header.rsplit(": ", 1)
        scopes = {normalize(k): v for k, v in SCOPES.items()}
        if prefix not in EVENT_PREFIXES or normalize(scope_name) not in scopes:
            raise DataError(f"Неизвестная метрика или контур: {header}")
        return EVENT_PREFIXES[prefix], scopes[normalize(scope_name)]

    validate_headers(raw["daily"].columns, {"Дата": "date", **{k: k for k in DAILY_IDS}})
    daily = []
    for i, row in raw["daily"].iterrows():
        for col in raw["daily"].columns:
            if col == "Дата":
                continue
            if col in DAILY_IDS:
                metric_id, scope, aggregation = DAILY_IDS[col]
            else:
                metric_id, scope = scope_column(col)
                aggregation = "non_additive" if metric_id == "buyers" else "sum"
            daily.append({"date": pd.Timestamp(row["Дата"]), "metric_id": metric_id, "scope": scope,
                          "value": row[col] if availability(row[col]) == "available" else None,
                          "aggregation": aggregation,
                          "source_ref": f"{SHEETS['daily']}!{get_column_letter(raw['daily'].columns.get_loc(col)+1)}{i+2}"})
    daily = pd.DataFrame(daily)
    if daily.duplicated(["date", "metric_id", "scope"]).any():
        raise DataError("Дубли дат в дневном ряду.")
    bounds = re.findall(r"\d{4}-\d{2}-\d{2}", period)
    if len(bounds) != 2 or daily.date.min() != pd.Timestamp(bounds[0]) or daily.date.max() != pd.Timestamp(bounds[1]):
        raise DataError("Даты дневного ряда не совпадают с периодом итогов.")
    if len(daily.date.unique()) != (pd.Timestamp(bounds[1]) - pd.Timestamp(bounds[0])).days + 1:
        raise DataError("В дневном ряду отсутствуют даты.")
    sources = []
    validate_headers(raw["sources"].columns, {"Источник": "source", "Маркет Вконтакте": "market", "Партнёр 1": "partner"})
    for i, row in raw["sources"].iterrows():
        for label, scope in list(SCOPES.items())[:2]:
            value = row[label]
            sources.append({"source": row["Источник"], "scope": scope,
                            "opens": value if availability(value) == "available" else None,
                            "reported_share_pct": row[f"Доля, %: {label}"],
                            "is_nested": normalize(row["Источник"]).startswith("в т.ч."),
                            "availability": availability(value),
                            "source_ref": f"{SHEETS['sources']}!{get_column_letter(raw['sources'].columns.get_loc(label)+1)}{i+2}"})

    def dimensions(key, dims):
        validate_headers(raw[key].columns, dims)
        records = []
        for i, row in raw[key].iterrows():
            for col in raw[key].columns:
                if col in dims:
                    continue
                metric_id, scope = scope_column(col)
                value = row[col]
                records.append({**{v: row[k] for k, v in dims.items()}, "metric_id": metric_id, "scope": scope,
                                "value": value if availability(value) == "available" else None,
                                "availability": availability(value),
                                "source_ref": f"{SHEETS[key]}!{get_column_letter(raw[key].columns.get_loc(col)+1)}{i+2}"})
        return pd.DataFrame(records)

    return Bundle(path, digest(path), period, b, raw, totals, daily, pd.DataFrame(sources),
                  dimensions("categories", {"Категория": "category"}),
                  dimensions("demography", {"Пол": "sex", "Возраст": "age"}),
                  dimensions("regions", {"Регион": "region"}), pd.DataFrame(statuses), schema)
