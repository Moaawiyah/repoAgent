"""Invoice math for subscription billing."""

TAX_RATE = 0.19


def calculate_invoice_total(
    lines: list[tuple[str, float]], discount: float = 0.0
) -> float:
    """Sum line amounts, subtract a discount, then add tax."""
    subtotal = sum(amount for _, amount in lines)
    discounted = subtotal - discount
    return round(discounted * (1 + TAX_RATE), 2)


def apply_discount(subtotal: float, percentage: float) -> float:
    """Reduce an amount by a percentage."""
    return subtotal * (1 - percentage)
