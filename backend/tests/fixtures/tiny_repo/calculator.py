"""Small arithmetic helpers used by tests."""


def add(left: int, right: int) -> int:
    """Return the sum of two integers."""
    return left + right


class Calculator:
    """Expose simple arithmetic operations."""

    def multiply(self, left: int, right: int) -> int:
        """Multiply two integers."""
        return left * right
