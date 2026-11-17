import pytest

from vk_case.demo import DemoStore, internal_sellers


def test_idempotency_and_payload_collision(tmp_path):
    store = DemoStore(tmp_path/"demo.sqlite")
    one = store.create("request", "demo-cup", 1, "on_receipt", "pickup")
    two = store.create("request", "demo-cup", 1, "on_receipt", "pickup")
    assert one["order_id"] == two["order_id"]
    assert len(store.list_orders()) == 1
    with pytest.raises(ValueError, match="другому составу"):
        store.create("request", "demo-cup", 2, "on_receipt", "pickup")


def test_payment_routes_and_late_payment(tmp_path):
    store = DemoStore(tmp_path/"demo.sqlite")
    cod = store.create("cod", "demo-cup", 1, "on_receipt", "pickup")["order_id"]
    store.transition(cod, "ready", "r1")
    assert store.transition(cod, "order_completed", "c1")["state"] == "completed"
    assert store.transition(cod, "payment_registered", "p1")["paid"]
    assert store.transition(cod, "payment_registered", "p1")["paid"]
    online = store.create("online", "demo-cup", 1, "online", "delivery")["order_id"]
    with pytest.raises(ValueError):
        store.transition(online, "ready", "r2")
    store.transition(online, "payment_registered", "p2")
    store.transition(online, "ready", "r2")
    assert store.transition(online, "order_completed", "c2")["state"] == "completed"


def test_custom_food_and_external(tmp_path):
    store = DemoStore(tmp_path/"demo.sqlite")
    with pytest.raises(ValueError, match="согласуйте"):
        store.create("custom", "demo-vase", 1, "online", "pickup")
    store.save_request("custom", "demo-vase", "Синяя ваза, высота 20 см")
    saved = store.create("custom", "demo-vase", 1, "online", "pickup", quote_accepted=True)
    assert "Синяя ваза" in saved["payload"]
    with pytest.raises(ValueError, match="зоне"):
        store.create("food", "demo-bread", 1, "on_receipt", "pickup", zone="Вне зоны")
    with pytest.raises(ValueError, match="Внешний"):
        store.create("external", "demo-external", 1, "online", "delivery")
    store.record_event("redirect", "partner_redirect")
    assert len(store.list_orders()) == 1


def test_kpi_excludes_demo_external_duplicates():
    event = {"event_id": "one", "event_name": "order_created", "order_contour": "internal",
             "is_demo": False, "is_eligible_goods": True, "business_id": 7}
    assert internal_sellers([event, event, {**event, "event_id": "demo", "business_id": 8, "is_demo": True},
                             {**event, "event_id": "external", "order_contour": "external", "business_id": 9}]) == 1
