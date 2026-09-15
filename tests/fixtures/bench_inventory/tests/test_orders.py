from shop.inventory import Inventory
from shop.orders import place_order
from shop.pricing import order_total


def test_small_order_is_confirmed():
    assert place_order(Inventory(10), 3) == "confirmed"


def test_total_applies_discount():
    assert order_total(10.0, 2, 0.5) == 10.0
