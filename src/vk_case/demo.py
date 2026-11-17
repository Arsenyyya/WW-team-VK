"""Persistent, idempotent local demo orders, isolated from research data."""

import json
import sqlite3
from hashlib import sha256
from pathlib import Path

CATALOG = [
    {"id": "demo-cup", "name": "Кружка «Тихое утро»", "seller": "Демо · мастерская",
     "price_minor": 180000, "stock": 6, "route": "standard", "description": "Керамика ручной работы · 300 мл",
     "color": "#DAE4EF", "symbol": "☕"},
    {"id": "demo-vase", "name": "Ваза по вашему эскизу", "seller": "Демо · мастерская",
     "price_minor": 420000, "stock": 1, "route": "custom", "description": "Изготовление после согласования · 14 дней",
     "color": "#E9E1F0", "symbol": "◒"},
    {"id": "demo-bread", "name": "Набор свежего хлеба", "seller": "Демо · локальная пекарня",
     "price_minor": 65000, "stock": 12, "route": "food", "description": "Самовывоз сегодня · зона «Центр»",
     "color": "#F4E4D0", "symbol": "◓"},
    {"id": "demo-external", "name": "Товар внешнего магазина", "seller": "Демо · внешний маршрут",
     "price_minor": 250000, "stock": 1, "route": "external", "description": "Фиксируется только переход, покупка неизвестна",
     "color": "#DCEBE6", "symbol": "↗"},
]


class DemoStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS orders (
                  order_id TEXT PRIMARY KEY, request_key TEXT UNIQUE, payload TEXT NOT NULL,
                  state TEXT NOT NULL, paid INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS events (
                  event_id TEXT PRIMARY KEY, event_name TEXT NOT NULL, order_id TEXT,
                  is_demo INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS requests (
                  request_key TEXT PRIMARY KEY, product_id TEXT NOT NULL, brief TEXT NOT NULL);
            """)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def create(self, request_key, product_id, quantity, payment, fulfillment, zone="Центр", quote_accepted=False):
        product = next((p for p in CATALOG if p["id"] == product_id), None)
        if not product or not isinstance(quantity, int) or not 1 <= quantity <= product["stock"]:
            raise ValueError("Проверьте товар, количество и наличие.")
        if product["route"] == "external":
            raise ValueError("Внешний переход не является внутренним заказом.")
        if product["route"] == "custom" and not quote_accepted:
            raise ValueError("Для товара под заказ сначала согласуйте предложение.")
        if payment not in {"online", "on_receipt"} or fulfillment not in {"pickup", "delivery"}:
            raise ValueError("Недопустимый способ оплаты/получения.")
        if product["route"] == "food" and (zone != "Центр" or fulfillment != "pickup"):
            raise ValueError("В демо пекарни доступен только самовывоз в зоне «Центр».")
        brief = None
        if product["route"] == "custom":
            with self.connect() as db:
                request = db.execute("SELECT * FROM requests WHERE request_key=?", (request_key,)).fetchone()
            if request is None or request["product_id"] != product_id:
                raise ValueError("Сначала сохраните запрос с пожеланиями к этому товару.")
            brief = request["brief"]
        payload = json.dumps({"product_id": product_id, "quantity": quantity, "payment": payment,
                              "fulfillment": fulfillment, "zone": zone, "route": product["route"],
                              "amount_minor": quantity * product["price_minor"], "order_contour": "internal",
                              "custom_brief": brief, "is_demo": True}, sort_keys=True, ensure_ascii=False)
        order_id = "DEMO-" + sha256(request_key.encode()).hexdigest()[:10].upper()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT * FROM orders WHERE request_key=?", (request_key,)).fetchone()
            if previous:
                if previous["payload"] != payload:
                    raise ValueError("Повторный ключ относится к другому составу заказа. Начните новый заказ.")
                return dict(previous)
            db.execute("INSERT INTO orders VALUES (?, ?, ?, 'created', 0)", (order_id, request_key, payload))
            db.execute("INSERT INTO events VALUES (?, 'order_created', ?, 1)", (order_id+"-create", order_id))
            return dict(db.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone())

    def transition(self, order_id, action, event_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
            if row is None:
                raise ValueError("Заказ не найден.")
            previous = db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
            if previous:
                if previous["event_name"] != action or previous["order_id"] != order_id:
                    raise ValueError("Коллизия ключа события.")
                return dict(row)
            payload = json.loads(row["payload"])
            state, paid = row["state"], row["paid"]
            if action == "payment_registered" and state not in {"cancelled", "refunded"} and not paid:
                paid = 1
            elif action == "ready" and state == "created" and (paid or payload["payment"] == "on_receipt"):
                state = "ready"
            elif action == "order_completed" and state == "ready" and (paid or payload["payment"] == "on_receipt"):
                state = "completed"
            elif action == "order_cancelled" and state in {"created", "ready"}:
                state = "cancelled"
            elif action == "refund_registered" and state in {"completed", "cancelled"} and paid:
                state = "refunded"
            else:
                raise ValueError("Переход недоступен для текущего состояния и способа оплаты.")
            db.execute("UPDATE orders SET state=?, paid=? WHERE order_id=?", (state, paid, order_id))
            db.execute("INSERT INTO events VALUES (?, ?, ?, 1)", (event_id, action, order_id))
            return dict(db.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone())

    def record_event(self, event_id, name):
        if name not in {"partner_redirect", "consultation_requested", "quote_accepted"}:
            raise ValueError("Неизвестное демонстрационное событие.")
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO events VALUES (?, ?, NULL, 1)", (event_id, name))

    def save_request(self, request_key, product_id, brief):
        if len(brief.strip()) < 5:
            raise ValueError("Опишите пожелания хотя бы несколькими словами.")
        with self.connect() as db:
            if db.execute("SELECT 1 FROM orders WHERE request_key=?", (request_key,)).fetchone():
                raise ValueError("Заказ уже подтверждён. Для изменения пожеланий начните новый заказ.")
            db.execute("INSERT INTO requests VALUES (?, ?, ?) ON CONFLICT(request_key) DO UPDATE SET product_id=excluded.product_id, brief=excluded.brief",
                       (request_key, product_id, brief.strip()))
            db.execute("INSERT OR IGNORE INTO events VALUES (?, 'consultation_requested', NULL, 1)", (request_key+"-consultation",))

    def list_orders(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM orders ORDER BY rowid DESC")]

    def reset(self):
        with self.connect() as db:
            db.execute("DELETE FROM orders")
            db.execute("DELETE FROM events")
            db.execute("DELETE FROM requests")


def internal_sellers(events):
    """Illustrative KPI contract. This function is not applied to workbook aggregates."""
    ids = set()
    seen = set()
    for e in events:
        if e["event_id"] in seen:
            continue
        seen.add(e["event_id"])
        if (e["event_name"] == "order_created" and e.get("order_contour") == "internal"
                and not e.get("is_demo", False) and e.get("is_eligible_goods", False)):
            ids.add(e["business_id"])
    return len(ids)
