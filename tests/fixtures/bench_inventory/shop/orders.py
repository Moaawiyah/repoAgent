"""Order placement using inventory reservations."""

from shop.inventory import Inventory


def place_order(inventory: Inventory, quantity: int) -> str:
    """Return an order status after trying to reserve stock."""
    return "confirmed" if inventory.reserve(quantity) else "rejected"
