from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from agents import function_tool

from .menu_catalog import get_menu_item_by_name, search_menu_catalog
from .models import OrderRequestItem


def _to_positive_quantity(value: Any) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    if isinstance(value, float):
        if value.is_integer() and value > 0:
            return int(value)
        return None

    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            parsed = int(stripped)
            return parsed if parsed > 0 else None

    return None


@function_tool
def calculate_order_total(order_items: list[OrderRequestItem]) -> dict[str, Any]:
    """Validate menu items and calculate a mock order total from item names and quantities."""

    valid_items: list[dict[str, Any]] = []
    invalid_items: list[dict[str, Any]] = []
    subtotal = 0.0

    for raw_item in order_items:
        name = raw_item.name.strip()
        quantity = _to_positive_quantity(raw_item.quantity)

        if not name or quantity is None:
            invalid_items.append(
                {
                    "name": name,
                    "reason": "invalid_name_or_quantity",
                    "suggestions": [],
                }
            )
            continue

        menu_item = get_menu_item_by_name(name)
        if menu_item is None:
            suggestions = [
                item.name
                for item in search_menu_catalog(query=name)
            ][:3]
            invalid_items.append(
                {
                    "name": name,
                    "reason": "menu_item_not_found",
                    "suggestions": suggestions,
                }
            )
            continue

        line_total = round(menu_item.price * quantity, 2)
        subtotal = round(subtotal + line_total, 2)
        valid_items.append(
            {
                "name": menu_item.name,
                "quantity": quantity,
                "unit_price": menu_item.price,
                "line_total": line_total,
            }
        )

    return {
        "items": valid_items,
        "subtotal": subtotal,
        "total": subtotal,
        "currency": "USD",
        "invalid_items": invalid_items,
    }


@function_tool
def simulate_payment(
    amount: float,
    method: Literal["card", "pay_on_arrival"],
) -> dict[str, Any]:
    """Simulate a payment result for card or onsite payment."""

    if amount < 0:
        return {
            "status": "invalid_amount",
            "method": method,
            "transaction_id": None,
            "message": "유효하지 않은 결제 금액입니다.",
        }

    if method == "card":
        transaction_id = f"pay_{uuid4().hex[:10]}"
        return {
            "status": "approved",
            "method": method,
            "transaction_id": transaction_id,
            "message": "카드 결제가 승인되었습니다.",
        }

    return {
        "status": "onsite_payment",
        "method": method,
        "transaction_id": None,
        "message": "결제는 매장에서 진행됩니다.",
    }
