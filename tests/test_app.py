from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("VK_CASE_DEMO_STORE", str(tmp_path/"ui-demo.sqlite"))
    if not Path("outputs/current_run.json").exists():
        pytest.skip("Для UI-тестов нужен завершённый локальный прогон; ядро тестируется автономно.")
    return AppTest.from_file(Path("app/streamlit_app.py").resolve()).run(timeout=30)


def test_sections_empty_filter_and_unrelated_market(app):
    for section in ["Качество", "Бизнесы", "Маркет", "Экономика", "Концепция", "Обзор"]:
        app.radio[0].set_value(section).run(timeout=30)
        assert not app.exception, section
    app.radio[0].set_value("Бизнесы").run()
    next(x for x in app.multiselect if x.label == "Тип бизнеса").set_value([]).run()
    assert any("нет бизнесов" in x.value for x in app.info)
    app.radio[0].set_value("Маркет").run()
    assert next(x for x in app.metric if x.label == "Оформленные заказы").value == "413 740"


def test_live_scenario_update(app):
    app.radio[0].set_value("Экономика").run()
    before = next(x for x in app.metric if x.label == "Сохранённая стоимость").value
    next(x for x in app.slider if x.label == "Дополнительная активация, п.п.").set_value(8.).run()
    after = next(x for x in app.metric if x.label == "Сохранённая стоимость").value
    assert before != after
    assert not app.exception
    next(x for x in app.slider if x.label == "Дополнительная активация, п.п.").set_value(0.).run()
    assert next(x for x in app.metric if x.label == "Доп. заказы, ожидание").value == "0,00"


def test_demo_ui_confirmation_is_idempotent(app, tmp_path):
    from vk_case.demo import DemoStore
    app.radio[0].set_value("Концепция").run()
    next(x for x in app.checkbox if x.label == "Проверил состав, стоимость и получение").check().run()
    next(x for x in app.button if x.label == "Подтвердить демо-заказ").click().run()
    assert not app.exception
    next(x for x in app.button if x.label == "Подтвердить демо-заказ").click().run()
    assert not app.exception
    assert len(DemoStore(tmp_path/"ui-demo.sqlite").list_orders()) == 1
