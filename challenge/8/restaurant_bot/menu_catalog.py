from __future__ import annotations

from .models import MenuItem

MENU_CATALOG: list[MenuItem] = [
    MenuItem(
        name="Grilled Chicken Bowl",
        category="Mains",
        price=12.5,
        ingredients=[
            "grilled chicken",
            "rice",
            "mixed greens",
            "cherry tomatoes",
            "corn",
            "sesame dressing",
        ],
        allergens=["sesame"],
        spice_level="mild",
        dietary_notes=["high protein"],
    ),
    MenuItem(
        name="Tofu Veggie Bowl",
        category="Mains",
        price=11.0,
        ingredients=["tofu", "rice", "broccoli", "mushrooms", "carrots", "soy-garlic sauce"],
        allergens=["soy"],
        spice_level="mild",
        dietary_notes=["vegetarian"],
    ),
    MenuItem(
        name="Truffle Fries",
        category="Sides",
        price=5.5,
        ingredients=["potato", "truffle oil", "parmesan", "parsley"],
        allergens=["milk"],
        spice_level="none",
        dietary_notes=["vegetarian"],
    ),
    MenuItem(
        name="Spicy Buffalo Wings",
        category="Sides",
        price=6.5,
        ingredients=["chicken wings", "buffalo sauce", "butter"],
        allergens=["milk"],
        spice_level="hot",
        dietary_notes=[],
    ),
    MenuItem(
        name="House Lemonade",
        category="Drinks",
        price=3.5,
        ingredients=["lemon", "water", "sugar"],
        allergens=[],
        spice_level="none",
        dietary_notes=["vegan"],
    ),
    MenuItem(
        name="Vanilla Milkshake",
        category="Drinks",
        price=4.5,
        ingredients=["milk", "vanilla ice cream", "whipped cream"],
        allergens=["milk"],
        spice_level="none",
        dietary_notes=["vegetarian"],
    ),
    MenuItem(
        name="Chocolate Brownie",
        category="Desserts",
        price=4.0,
        ingredients=["chocolate", "flour", "butter", "egg"],
        allergens=["wheat", "milk", "egg"],
        spice_level="none",
        dietary_notes=["vegetarian"],
    ),
    MenuItem(
        name="Fruit Cup",
        category="Desserts",
        price=4.0,
        ingredients=["strawberry", "pineapple", "grape", "orange"],
        allergens=[],
        spice_level="none",
        dietary_notes=["vegan", "gluten-free"],
    ),
]


def normalize_text(value: str) -> str:
    return value.casefold().replace(" ", "").replace("-", "")


def build_menu_list() -> str:
    categories: dict[str, list[MenuItem]] = {}
    for item in MENU_CATALOG:
        categories.setdefault(item.category, []).append(item)

    lines = ["Menu data:", ""]
    for category, items in categories.items():
        lines.append(f"[{category}]")
        for index, item in enumerate(items, start=1):
            dietary_notes = ", ".join(item.dietary_notes) if item.dietary_notes else "none"
            allergens = ", ".join(item.allergens) if item.allergens else "none"
            ingredients = ", ".join(item.ingredients)
            lines.extend(
                [
                    f"{index}. {item.name}",
                    f"- Price: {item.price:.1f} USD",
                    f"- Ingredients: {ingredients}",
                    f"- Allergens: {allergens}",
                    f"- Spice level: {item.spice_level}",
                    f"- Dietary notes: {dietary_notes}",
                    "",
                ]
            )
    return "\n".join(lines).strip()


def get_menu_names() -> list[str]:
    return [item.name for item in MENU_CATALOG]


def get_menu_item_by_name(name: str) -> MenuItem | None:
    normalized_query = normalize_text(name)
    for item in MENU_CATALOG:
        if normalize_text(item.name) == normalized_query:
            return item

    for item in MENU_CATALOG:
        if normalized_query and normalized_query in normalize_text(item.name):
            return item
    return None


def search_menu_catalog(
    *,
    query: str | None = None,
    category: str | None = None,
    dietary_note: str | None = None,
    allergen_exclude: list[str] | None = None,
) -> list[MenuItem]:
    normalized_query = normalize_text(query or "")
    normalized_category = normalize_text(category or "")
    normalized_dietary_note = normalize_text(dietary_note or "")
    normalized_allergen_exclude = {normalize_text(item) for item in (allergen_exclude or [])}

    results: list[MenuItem] = []
    for item in MENU_CATALOG:
        if normalized_category and normalize_text(item.category) != normalized_category:
            continue

        if normalized_dietary_note and normalized_dietary_note not in {
            normalize_text(note) for note in item.dietary_notes
        }:
            continue

        if normalized_allergen_exclude and normalized_allergen_exclude.intersection(
            {normalize_text(allergen) for allergen in item.allergens}
        ):
            continue

        if normalized_query:
            haystacks = [item.name, item.category, *item.ingredients, *item.allergens, *item.dietary_notes]
            if not any(normalized_query in normalize_text(candidate) for candidate in haystacks):
                continue

        results.append(item)

    return results
