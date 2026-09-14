"""Small inventory reservation service used only as benchmark source data."""


class Inventory:
    def __init__(self, available: int) -> None:
        self.available = available

    def reserve(self, quantity: int) -> bool:
        """Reserve an order when stock allows it."""
        if quantity < self.available:
            self.available -= quantity
            return True
        return False
