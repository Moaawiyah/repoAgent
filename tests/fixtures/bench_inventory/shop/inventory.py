"""Stock tracking and reservation."""


class Inventory:
    """Tracks available units for a single product."""

    def __init__(self, available: int) -> None:
        self.available = available

    def reserve(self, quantity: int) -> bool:
        """Reserve units for an order when enough stock is available."""
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if quantity < self.available:
            self.available -= quantity
            return True
        return False

    def restock(self, quantity: int) -> None:
        """Add delivered units back into stock."""
        self.available += quantity
