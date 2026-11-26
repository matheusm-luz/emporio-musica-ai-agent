import json
from datetime import date, datetime

import pytest

from emporio_agent.config import STORE_TZ
from emporio_agent.data import StoreData
from emporio_agent.policies import PolicyManual
from emporio_agent.tickets import InMemoryTicketStore
from emporio_agent.tools import Catalog, build_tools, lookup_orders, tokens

TODAY = date(2026, 11, 25)


@pytest.fixture(scope="module")
def catalog(store: StoreData) -> Catalog:
    return Catalog(store)


def test_tokens_singularise_and_drop_accents() -> None:
    assert tokens("Violões de 7 cordas") == ["violao", "7", "corda"]


# --- catalog ------------------------------------------------------------------------------------


def test_scenario_a1_guitars_up_to_1000(catalog: Catalog) -> None:
    result = catalog.search(category="violões", max_price=1000, limit=20)
    ids = {p["id"] for p in result["produtos"]}
    assert result["total_encontrado"] == 12
    assert 96 not in ids  # out of stock
    assert 113 not in ids  # discontinued
    assert all(p["disponibilidade"] == "disponível" for p in result["produtos"])
    assert result["indisponiveis_omitidos"] == 2


def test_search_ranks_by_relevance_tier(catalog: Catalog) -> None:
    result = catalog.search(query="ukulele eletroacústico")
    assert {p["id"] for p in result["produtos"]} == {122, 123, 126, 129}


def test_search_reports_named_unavailable_items(catalog: Catalog) -> None:
    result = catalog.search(query="Shelby SN-7C")
    assert result["total_encontrado"] == 0
    assert result["itens_indisponiveis_encontrados"] == [
        {"nome": "Shelby SN-7C 7 Cordas Nylon Natural", "disponibilidade": "descontinuado"}
    ]


def test_search_category_without_products(catalog: Catalog) -> None:
    result = catalog.search(category="saxofone")
    assert result["total_encontrado"] == 0
    assert "Instrumentos de Sopro (Madeiras)" in result["observacao"]


def test_search_unknown_category_lists_valid_ones(catalog: Catalog) -> None:
    assert "Violões" in catalog.search(category="naves espaciais")["erro"]


def test_scenario_a3_takamine_price(catalog: Catalog) -> None:
    details = catalog.details("Takamine GD20")
    assert details["id"] == 95
    assert details["preco"] == "R$ 2.199,00"
    assert details["preco_pix"].startswith("R$ 2.089,05")
    assert details["parcelamento_cartao"] == "até 12x de R$ 183,25 sem juros"
    assert "promocao" not in details  # its 12% promotion is inactive


def test_details_tolerates_typos(catalog: Catalog) -> None:
    assert catalog.details("takamini gd-20")["id"] == 95


def test_details_of_promoted_product(catalog: Catalog) -> None:
    details = catalog.details("Ohana CK-20")
    assert (details["preco"], details["preco_original"], details["desconto"]) == (
        "R$ 439,20",
        "R$ 549,00",
        "20%",
    )
    assert "preco_pix" not in details


@pytest.mark.parametrize(("product", "status"), [("96", "esgotado"), ("113", "descontinuado")])
def test_unavailable_products_come_with_alternatives(
    catalog: Catalog, product: str, status: str
) -> None:
    details = catalog.details(product)
    assert details["disponibilidade"] == status
    alternatives = details["alternativas_disponiveis"]
    assert alternatives and all(a["disponibilidade"] == "disponível" for a in alternatives)
    assert all(a["categoria"] == "Violões" for a in alternatives)


def test_coming_soon_product(catalog: Catalog) -> None:
    assert catalog.details("130")["disponibilidade"] == "em breve"


def test_unreliable_description_is_hidden(catalog: Catalog) -> None:
    assert "descricao" not in catalog.details("135")
    assert "descricao" in catalog.details("95")


def test_unknown_product(catalog: Catalog) -> None:
    assert "erro" in catalog.details("Stradivarius 1715")


def test_only_active_promotions_are_listed(catalog: Catalog) -> None:
    promos = catalog.active_promotions()["promocoes_ativas"]
    assert {p["id"] for p in promos} == {90, 94, 121, 127}
    assert all(p["promocao"] != "Black Friday" for p in promos)


# --- orders (policy §9: owner only) ----------------------------------------------------------


def test_orders_by_phone_with_computed_deadlines(store: StoreData) -> None:
    result = lookup_orders(store, "(67) 98432-1098", None, TODAY)
    assert result["cliente"] == "Pedro"
    delivered = next(o for o in result["pedidos"] if o["pedido"] == 1)
    assert delivered["status"] == "entregue"
    assert delivered["prazos"]["arrependimento_7_dias_apos_recebimento"] == (
        "prazo encerrado em 01/11/2025"
    )


def test_return_window_open_for_recent_delivery(store: StoreData) -> None:
    result = lookup_orders(store, "(67) 98432-1098", 1, date(2025, 10, 28))
    deadlines = result["pedidos"][0]["prazos"]
    assert deadlines["arrependimento_7_dias_apos_recebimento"].startswith("dentro do prazo")


def test_phone_without_area_code_is_accepted(store: StoreData) -> None:
    assert lookup_orders(store, "98432-1098", None, TODAY)["cliente"] == "Pedro"


def test_order_of_another_customer_is_not_revealed(store: StoreData) -> None:
    result = lookup_orders(store, "(67) 98432-1098", 2, TODAY)  # order 2 belongs to customer 7
    assert result == {"erro": "Não encontrei o pedido 2 para este contato."}


def test_shared_email_is_ambiguous(store: StoreData) -> None:
    assert (
        "mais de um cadastro"
        in lookup_orders(store, "bruno.martins@jmail.com", None, TODAY)["erro"]
    )


def test_unknown_or_invalid_contact(store: StoreData) -> None:
    assert "erro" in lookup_orders(store, "(11) 91234-0000", None, TODAY)
    assert "DDD" in lookup_orders(store, "123", None, TODAY)["erro"]


def test_overdue_shipment_is_flagged(store: StoreData) -> None:
    order = lookup_orders(store, "anacarol.ferreira@coldmail.com", 8, TODAY)["pedidos"][0]
    assert order["status"] == "enviado"
    assert order["alerta"] == "a previsão de entrega já passou"


# --- LangChain wrappers -----------------------------------------------------------------------


def test_tool_set_and_ticket_creation(store: StoreData, manual: PolicyManual) -> None:
    tickets = InMemoryTicketStore()
    now = datetime(2026, 11, 25, 10, tzinfo=STORE_TZ)
    tools = {t.name: t for t in build_tools(store, manual, tickets, lambda: now)}
    assert set(tools) == {
        "search_products",
        "get_product_details",
        "list_active_promotions",
        "lookup_orders",
        "get_store_policy",
        "create_support_ticket",
    }

    output = json.loads(
        tools["create_support_ticket"].invoke(
            {"kind": "reclamacao", "summary": "Atraso na entrega", "customer_contact": "x"},
            config={"configurable": {"thread_id": "t-1"}},
        )
    )
    assert output["protocolo"] == "EMP-20261125-0001"
    assert "24 horas úteis" in output["prazo_retorno"]
    assert tickets.tickets[0].thread_id == "t-1"

    assert "Rua 14 de Maio" in tools["get_store_policy"].invoke({"topic": "sobre_contato"})
