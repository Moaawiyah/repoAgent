"""Order pricing rules."""


def order_total(unit_price: float, quantity: int, discount: float = 0.0) -> float:
    """Compute the discounted total for an order line."""
    return round(unit_price * quantity * (1 - discount), 2)
