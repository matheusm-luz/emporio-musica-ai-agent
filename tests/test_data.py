from decimal import Decimal

from emporio_agent.data import StoreData, normalize, phone_digits


def test_tables_are_loaded(store: StoreData) -> None:
    assert len(store.products) == 65
    assert len(store.orders) == 20
    assert len(store.customers) == 50
    assert store.product(95)["name"] == "Takamine GD20 Dreadnought Natural"
    assert store.product(95)["price"] == Decimal("2199")
    assert store.product(95)["category"] == "Violões"


def test_specs_json_is_parsed(store: StoreData) -> None:
    assert store.product(81)["specs"]["strings"] == "nylon"
    assert store.product(135)["specs"]["strings"] == "4"


def test_descriptions_contradicting_the_name_are_flagged(store: StoreData) -> None:
    unreliable = set(store.products.index[~store.products["description_reliable"]])
    assert unreliable == {135, 137, 139, 140, 142, 144}


def test_only_flagged_promotions_are_active(store: StoreData) -> None:
    active = set(store.promotions.loc[store.promotions["is_active"], "product_id"])
    assert active == {90, 94, 121, 127}
    assert store.active_promotions(95).empty  # Takamine GD20: 12% promotion is inactive


def test_data_quality_findings_are_reported(store: StoreData) -> None:
    report = "\n".join(store.warnings)
    assert "product 136 is discontinued but has stock 13" in report
    assert "order 3: recorded total 3450" in report
    assert "order 20: recorded total 1400" in report
    assert "customers [11, 43] share the same email" in report
    for category in ("Cordas Orquestrais", "Instrumentos de Sopro (Madeiras)"):
        assert f"category '{category}' has no products" in report


def test_order_items_are_joined_with_products(store: StoreData) -> None:
    items = store.order_items[store.order_items["order_id"] == 15]
    assert set(items["product_id"]) == {82, 106}
    assert items["line_total"].sum() == store.orders.loc[15, "total"]


def test_missing_values_become_none(store: StoreData) -> None:
    assert store.orders.loc[9, "tracking_code"] is None
    assert store.orders.loc[1, "tracking_code"] == "BRAB1234567BR"


def test_normalize_and_phone_digits() -> None:
    assert normalize("  Violões ") == "violoes"
    assert phone_digits("(67) 98432-1098") == "67984321098"
    assert phone_digits("+55 67 98432-1098") == "67984321098"
