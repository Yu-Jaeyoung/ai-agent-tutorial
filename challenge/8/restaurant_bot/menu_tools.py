from __future__ import annotations

from typing import Any

from agents import function_tool

from .menu_catalog import get_menu_item_by_name, search_menu_catalog


def _menu_item_to_payload(item) -> dict[str, Any]:
    return {
        "name": item.name,
        "category": item.category,
        "price": item.price,
        "ingredients": item.ingredients,
        "allergens": item.allergens,
        "spice_level": item.spice_level,
        "dietary_notes": item.dietary_notes,
    }


@function_tool
def search_menu_items(
    query: str | None = None,
    category: str | None = None,
    dietary_note: str | None = None,
    allergen_exclude: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search menu items by name, category, dietary note, or allergen exclusions."""

    results = search_menu_catalog(
        query=query,
        category=category,
        dietary_note=dietary_note,
        allergen_exclude=allergen_exclude,
    )
    return [_menu_item_to_payload(item) for item in results]


@function_tool
def get_menu_item_details(name: str) -> dict[str, Any] | None:
    """Get the full details for one menu item by name."""

    item = get_menu_item_by_name(name)
    if item is None:
        return None
    return _menu_item_to_payload(item)
