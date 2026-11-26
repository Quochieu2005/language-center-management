"""SePay Payment Gateway (Cổng thanh toán) client: signed checkout form, order lookup, IPN key.

Contract mirrors the official SDK ``sepayvn/sepay-pg-php``:
- checkout is a browser form POST to ``https://pay[-sandbox].sepay.vn/v1/checkout/init``;
- ``signature = base64(HMAC_SHA256(secret_key, "k=v,k=v,..."))`` over the signed fields in
  the order they are placed in the form;
- REST ``GET https://pgapi[-sandbox].sepay.vn/v1/order/detail/{invoice}`` with Basic auth
  ``merchant_id:secret_key``;
- IPN is a JSON POST authenticated by the ``X-Secret-Key`` header.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings

_HOSTS = {
    "production": ("https://pay.sepay.vn", "https://pgapi.sepay.vn"),
    "sandbox": ("https://pay-sandbox.sepay.vn", "https://pgapi-sandbox.sepay.vn"),
}
# Fields the SDK signs; their order in the signed string follows the form insertion order.
_SIGNED_FIELDS = {
    "merchant", "env", "operation", "payment_method", "order_amount", "currency",
    "order_invoice_number", "order_description", "customer_id", "agreement_id",
    "agreement_name", "agreement_type", "agreement_payment_frequency",
    "agreement_amount_per_payment", "success_url", "error_url", "cancel_url",
}
PAID_ORDER_STATUSES = {"CAPTURED"}


class GatewayUnavailable(Exception):
    """SePay could not be reached or answered with an unexpected error; the result is unknown."""


def _hosts() -> tuple[str, str]:
    return _HOSTS[settings.SEPAY_ENV]


def sign_fields(fields: dict[str, str], secret_key: str) -> str:
    signed = ",".join(f"{key}={value}" for key, value in fields.items() if key in _SIGNED_FIELDS)
    digest = hmac.new(secret_key.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def build_checkout(*, invoice: str, amount: int, description: str, return_urls: dict[str, str]) -> dict:
    """Return the form ``action`` and ordered hidden ``fields`` (signature last) for the browser."""
    fields: dict[str, str] = {
        "merchant": settings.SEPAY_MERCHANT_ID,
        "currency": "VND",
        "order_amount": str(int(amount)),
        "operation": "PURCHASE",
        "order_description": description,
        "order_invoice_number": invoice,
        "success_url": return_urls["success"],
        "error_url": return_urls["error"],
        "cancel_url": return_urls["cancel"],
    }
    fields["signature"] = sign_fields(fields, settings.SEPAY_SECRET_KEY)
    return {"action": f"{_hosts()[0]}/v1/checkout/init", "method": "POST", "fields": fields}


def money(value: object) -> int | None:
    """Parse "100000" or "100000.00" into whole VND; reject fractions, negatives and booleans."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
        return None
    return int(amount)


def fetch_order(invoice: str) -> dict | None:
    """Return the order dict from SePay, or ``None`` when SePay has no order for this invoice.

    ``None`` is a definite "never paid" only because the invoice is created by us and is
    unique; any other failure raises ``GatewayUnavailable`` so callers keep the attempt open.
    """
    credentials = base64.b64encode(
        f"{settings.SEPAY_MERCHANT_ID}:{settings.SEPAY_SECRET_KEY}".encode("utf-8")
    ).decode("ascii")
    request = Request(
        f"{_hosts()[1]}/v1/order/detail/{quote(invoice, safe='')}",
        # Cloudflare in front of pgapi rejects urllib's default User-Agent (error 1010).
        headers={"Authorization": f"Basic {credentials}", "Accept": "application/json",
                 "Content-Type": "application/json", "User-Agent": "qlttnn-tuition/1.0"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            body = json.loads(response.read(256 * 1024 + 1))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise GatewayUnavailable(f"SePay trả HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise GatewayUnavailable("Không kết nối được SePay.") from exc
    order = body.get("data", body) if isinstance(body, dict) else None
    if isinstance(order, list):
        order = order[0] if len(order) == 1 else None
    if not isinstance(order, dict):
        raise GatewayUnavailable("Phản hồi đơn hàng SePay không đúng định dạng.")
    return order


def ipn_key_valid(header_value: str | None) -> bool:
    expected = settings.SEPAY_IPN_SECRET_KEY
    return bool(expected) and hmac.compare_digest(str(header_value or ""), expected)
