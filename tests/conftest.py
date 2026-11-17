from datetime import datetime, timedelta

import openpyxl
import pytest
import yaml

from vk_case.ingest import BUSINESS_HEADERS, SHEETS
from vk_case.pipeline import ROOT


@pytest.fixture
def small_workbook(tmp_path):
    """An independently constructed seven-sheet fixture, no real workbook dependency."""
    w = openpyxl.Workbook()
    w.remove(w.active)
    s = w.create_sheet(SHEETS["businesses"])
    s.append(list(BUSINESS_HEADERS))
    for i in range(8):
        row = dict.fromkeys(BUSINESS_HEADERS.values(), 0)
        row.update(business_id=i+1, theme=["Творчество и хендмейд", "Кулинария и еда"][i%2],
                   business_type="товарное" if i < 6 else "услужное", subscribers=500+1000*i,
                   posts=20, clips=5, product_posts=4, product_clips=1, product_views=500,
                   ordinary_views=2000, ordinary_likes=50, product_likes=10,
                   uploaded_products=10, active_products=5 if i < 6 else 0,
                   checkout=1, original_content=None if i == 0 else 0, content_opens=100,
                   orders=2 if i < 2 else 0, gmv=1000 if i == 0 else 2000 if i == 1 else 0,
                   reported_aov=500 if i == 0 else 1000 if i == 1 else None,
                   median_product_price=200 if i < 6 else None)
        s.append([row[BUSINESS_HEADERS[h]] for h in BUSINESS_HEADERS])
    s = w.create_sheet(SHEETS["totals"])
    s.append(["Метрика", "Маркет Вконтакте", "Партнёр 1", "Всего"])
    totals = [("Показы товаров", 30000, 60000), ("Открытия карточки товара", 3000, 6000),
              ("Нажатия на кнопку в карточке", 900, 1800),
              ("Прямые переходы к Партнёру 1 (без открытия карточки)", "—", 1000),
              ("Оформленные заказы", 300, 600), ("Оплаченные заказы", 30, "—"),
              ("GMV, ₽", 30000, 60000), ("Средний чек, ₽", 100, 100),
              ("Уникальные покупатели за 30 дней", 150, 300),
              ("Покупатели на листах «Покупатели» и «Покупатели по регионам» (без групп меньше 100)", 150, 300),
              ("Заказы на листах «Покупатели» и «Покупатели по регионам» (без групп меньше 100)", 300, 600)]
    for row in totals:
        s.append([*row, None])
    s.append(["Общие метрики Маркета Вконтакте (без деления на сегменты)", None, None, None])
    for name, value in [("Период", "2026-09-01 — 2026-09-30"),
                        ("DAU Маркета Вконтакте (среднее за день)", 10),
                        ("MAU Маркета Вконтакте (уникальные за 30 дней)", 200),
                        ("Открытия карточки товара из постов и клипов", 1200),
                        ("Запросы в товарном поиске", 300)]:
        s.append([name, None, None, value])
    s = w.create_sheet(SHEETS["daily"])
    s.append(["Дата", "DAU Маркета Вконтакте", "Видели товары (уник.)", "Открывали карточку (уник.)",
              "Поисковые запросы", "Поисковые запросы с открытием карточки",
              "Заказы: Маркет Вконтакте", "Заказы: Партнёр 1", "GMV, ₽: Маркет Вконтакте", "GMV, ₽: Партнёр 1"])
    for i in range(30):
        s.append([datetime(2026, 9, 1)+timedelta(days=i), 10, 100, 50, 10, 2, 10, 20, 1000, 2000])
    s = w.create_sheet(SHEETS["sources"])
    s.append(["Источник", "Маркет Вконтакте", "Доля, %: Маркет Вконтакте", "Партнёр 1", "Доля, %: Партнёр 1"])
    for row in [("Другое", 2000, 66.67, 4000, 66.67), ("Лента", 500, 16.67, 500, 8.33),
                ("Клипы", 300, 10., 1000, 16.67), ("Главная Маркета Вконтакте", 200, 6.67, 500, 8.33),
                ("в т.ч. из реферальных постов и клипов", None, None, 1400, 23.33)]:
        s.append(row)
    for key, dims in [("categories", ["Категория"]), ("demography", ["Пол", "Возраст"]), ("regions", ["Регион"])]:
        s = w.create_sheet(SHEETS[key])
        metrics = ["Открытия карточки", "Заказы"] if key == "categories" else ["Покупатели", "Заказы"]
        s.append(dims + [f"{metric}: {scope}" for scope in ["Маркет Вконтакте", "Партнёр 1"] for metric in metrics])
        if key == "categories":
            s.append(["Хобби и развлечения", 1500, 180, 3000, 350])
            s.append(["Другое", 1500, 120, 3000, 250])
        else:
            first = ["Ж", "25–34"] if key == "demography" else ["Регион 1"]
            second = ["М", "35–44"] if key == "demography" else ["Регион 2"]
            s.append(first + [100, 200, 200, 400])
            s.append(second + [50, 100, 100, 200])
    path = tmp_path/"small.xlsx"
    w.save(path)
    return path


@pytest.fixture
def fast_config(tmp_path):
    c = yaml.safe_load((ROOT/"config/project.yaml").read_text())
    c["bootstrap_repetitions"] = 30
    p = tmp_path/"config.yaml"
    p.write_text(yaml.safe_dump(c, allow_unicode=True))
    return p
