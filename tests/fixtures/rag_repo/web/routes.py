"""HTTP route handlers for the web tier."""

from auth.service import AuthService


def login_route(auth: AuthService, username: str, password: str) -> dict[str, str]:
    """Handle sign-in attempts coming from the web tier."""
    if auth.verify_password(password, _stored_digest(username)):
        return {"status": "ok", "token": "tok.demo"}
    return {"status": "denied"}


def _stored_digest(username: str) -> str:
    return f"sha256:pepper:{username}"


def invoice_route(lines: list[tuple[str, float]]) -> float:
    """Expose invoice totals to the web tier."""
    from billing.invoice import calculate_invoice_total

    return calculate_invoice_total(lines)
