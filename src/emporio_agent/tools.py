"""Tools the agent can call. Business logic lives in plain functions (unit-tested without an LLM);
`build_tools` wraps them as LangChain tools returning compact PT-BR JSON with every value already
computed and formatted, so the model only has to relay it.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from rapidfuzz import fuzz

from emporio_agent.data import StoreData, normalize, phone_digits
from emporio_agent.policies import PolicyManual, PolicyTopic
from emporio_agent.rules import (
    DEFECT_EXCHANGE_DAYS,
    LEGAL_WARRANTY_DAYS,
    RETURN_WINDOW_DAYS,
    Availability,
    PriceQuote,
    Promotion,
    availability,
    deadline_status,
    format_brl,
    quote_price,
    store_status,
)
from emporio_agent.tickets import TicketKind, TicketStore

STOPWORDS = {
    "a", "as", "o", "os", "um", "uma", "de", "da", "das", "do", "dos", "e", "em", "no", "na",
    "com", "para", "pra", "por", "que", "tem", "voces", "quero", "algum", "alguma",
}  # fmt: skip
MATCH_THRESHOLD = 85  # rapidfuzz ratio for typo-tolerant token matching
ORDER_STATUS_PT = {
    "pending": "pendente",
    "confirmed": "confirmado",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}
PAYMENT_PT = {"pix": "PIX", "debit": "cartão de débito", "boleto": "boleto bancário"}


# --- text matching ------------------------------------------------------------------------------


def _stem(token: str) -> str:
    """Crude Portuguese singularisation: violões -> violao, guitarras -> guitarra."""
    if token.endswith(("oes", "aes")):
        return token[:-3] + "ao"
    if token.endswith("s") and len(token) > 3 and not token[-2].isdigit():
        return token[:-1]
    return token


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalize(text))
    return [_stem(w) for w in words if w not in STOPWORDS]


def _token_in(token: str, haystack: list[str]) -> bool:
    if token.isdigit():
        return token in haystack
    return any(token == h or fuzz.ratio(token, h) >= MATCH_THRESHOLD for h in haystack)


def match_score(query: str, haystack: list[str]) -> float:
    """Fraction of query tokens found in the haystack (typo-tolerant)."""
    query_tokens = tokens(query)
    if not query_tokens:
        return 0.0
    return sum(_token_in(t, haystack) for t in query_tokens) / len(query_tokens)


def _product_haystack(row: pd.Series) -> list[str]:
    specs = row["specs"]
    extra = []
    if specs.get("electronics") == "yes":
        extra.append("eletrico eletroacustico")
    if specs.get("strings") == "steel":
        extra.append("aco")
    return tokens(" ".join([row["name"], str(row["category"]), *map(str, specs.values()), *extra]))


# --- catalog ------------------------------------------------------------------------------------


@dataclass
class Catalog:
    store: StoreData

    def __post_init__(self) -> None:
        products = self.store.products
        self._haystacks = {pid: _product_haystack(row) for pid, row in products.iterrows()}
        cats = self.store.categories
        self._category_haystacks = {
            row["name"]: tokens(f"{row['name']} {row['description']}") for _, row in cats.iterrows()
        }

    def quote(self, product_id: int) -> PriceQuote:
        promos = self.store.active_promotions(product_id)
        active = [
            Promotion(r["description"], int(r["discount_percent"])) for _, r in promos.iterrows()
        ]
        return quote_price(self.store.product(product_id)["price"], active)

    def availability(self, product_id: int) -> Availability:
        row = self.store.product(product_id)
        return availability(row["status"], int(row["stock_quantity"]))

    def summary(self, product_id: int) -> dict[str, Any]:
        row = self.store.product(product_id)
        quote = self.quote(product_id).to_dict()
        summary = {"id": int(product_id), "nome": row["name"], "categoria": row["category"]}
        summary |= {k: v for k, v in quote.items() if k in ("preco", "preco_original", "desconto")}
        return summary | {"disponibilidade": str(self.availability(product_id))}

    def match_categories(self, category: str) -> list[str]:
        return [
            name
            for name, haystack in self._category_haystacks.items()
            if match_score(category, haystack) == 1.0
        ]

    def search(
        self,
        query: str | None = None,
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        include_unavailable: bool = False,
        limit: int = 10,
    ) -> dict[str, Any]:
        products = self.store.products
        candidates = list(products.index)

        if category:
            categories = self.match_categories(category)
            if not categories:
                valid = ", ".join(self.store.categories["name"])
                return {"erro": f"Categoria '{category}' não reconhecida. Categorias: {valid}"}
            candidates = [p for p in candidates if products.loc[p, "category"] in categories]
            if not candidates:
                return {
                    "total_encontrado": 0,
                    "observacao": f"Não há produtos de {', '.join(categories)} no catálogo "
                    "no momento.",
                }

        scores = {p: 1.0 for p in candidates}
        if query:
            scores = {p: match_score(query, self._haystacks[p]) for p in candidates}
            best = max(scores.values(), default=0.0)
            # keep only the best-matching tier: "ukulele eletroacústico" must not list every ukulele
            scores = {p: s for p, s in scores.items() if s >= max(best, 0.5)}

        def final_price(p: int) -> Decimal:
            return self.quote(p).final_price

        if min_price is not None:
            scores = {p: s for p, s in scores.items() if final_price(p) >= Decimal(str(min_price))}
        if max_price is not None:
            scores = {p: s for p, s in scores.items() if final_price(p) <= Decimal(str(max_price))}

        unavailable = [p for p in scores if self.availability(p) is not Availability.AVAILABLE]
        if not include_unavailable:
            scores = {p: s for p, s in scores.items() if p not in unavailable}
        # A named item that is out of stock / discontinued must be reported as such (§7.3),
        # not silently filtered out.
        unavailable_named = (
            [
                {
                    "nome": self.store.product(p)["name"],
                    "disponibilidade": str(self.availability(p)),
                }
                for p in unavailable[:3]
            ]
            if query and not include_unavailable
            else []
        )

        ranked = sorted(scores, key=lambda p: (-scores[p], final_price(p)))
        result: dict[str, Any] = {
            "total_encontrado": len(ranked),
            "produtos": [self.summary(p) for p in ranked[:limit]],
        }
        if len(ranked) > limit:
            result["observacao"] = f"Mostrando {limit} de {len(ranked)}; refine a busca."
        if unavailable and not include_unavailable:
            result["indisponiveis_omitidos"] = len(unavailable)
        if unavailable_named:
            result["itens_indisponiveis_encontrados"] = unavailable_named
            if not ranked:  # the customer asked for something unavailable: suggest (§7.3)
                result["alternativas_disponiveis"] = self.alternatives(unavailable[0])
        if not ranked:
            result["observacao"] = "Nenhum produto disponível com esses critérios."
        return result

    def find(self, product: str) -> tuple[int | None, list[int]]:
        """Best product for an id or a (possibly misspelled) name, plus other close matches."""
        text = str(product).strip().lstrip("#")
        if text.isdigit() and int(text) in self.store.products.index:
            return int(text), []
        scored = []
        for pid, haystack in self._haystacks.items():
            score = match_score(text, haystack)
            if score >= 0.5:
                name = self.store.product(pid)["name_norm"]
                scored.append((score, fuzz.token_set_ratio(normalize(text), name), pid))
        if not scored:
            return None, []
        scored.sort(reverse=True)
        best_score = scored[0][0]
        others = [pid for score, _, pid in scored[1:4] if score == best_score]
        return scored[0][2], others

    def alternatives(self, product_id: int, limit: int = 3) -> list[dict[str, Any]]:
        """Available products of the same category with the closest price (policy §7.3)."""
        products = self.store.products
        target = self.quote(product_id).final_price
        same_category = products[
            (products["category"] == products.loc[product_id, "category"])
            & (products.index != product_id)
        ].index
        available = [p for p in same_category if self.availability(p) is Availability.AVAILABLE]
        available.sort(key=lambda p: abs(self.quote(p).final_price - target))
        return [self.summary(p) for p in available[:limit]]

    def details(self, product: str) -> dict[str, Any]:
        product_id, others = self.find(product)
        if product_id is None:
            return {
                "erro": f"Produto '{product}' não encontrado no catálogo.",
                "dica": "Use search_products para buscar por categoria ou palavras-chave.",
            }
        row = self.store.product(product_id)
        status = self.availability(product_id)
        result: dict[str, Any] = {
            "id": product_id,
            "nome": row["name"],
            "categoria": row["category"],
            "especificacoes": row["specs"],
            **self.quote(product_id).to_dict(),
            "disponibilidade": str(status),
        }
        if row["description_reliable"] and row["description"]:
            result["descricao"] = row["description"]
        if status is Availability.AVAILABLE:
            result["estoque"] = int(row["stock_quantity"])
        else:
            result["alternativas_disponiveis"] = self.alternatives(product_id)
        if others:
            result["outros_produtos_parecidos"] = [self.store.product(p)["name"] for p in others]
        return result

    def active_promotions(self) -> dict[str, Any]:
        promos = self.store.promotions[self.store.promotions["is_active"]]
        items = []
        for product_id in sorted(set(promos["product_id"])):
            quote = self.quote(product_id).to_dict()
            items.append(
                {
                    "id": int(product_id),
                    "nome": self.store.product(product_id)["name"],
                    "promocao": quote["promocao"],
                    "preco_original": quote["preco_original"],
                    "desconto": quote["desconto"],
                    "preco_promocional": quote["preco"],
                    "disponibilidade": str(self.availability(product_id)),
                }
            )
        return {
            "promocoes_ativas": items,
            "regras": "Promoções não são cumulativas; desconto PIX de 5% não se aplica sobre "
            "preço promocional; sujeitas ao estoque. Somente estas promoções estão vigentes.",
        }


# --- orders -------------------------------------------------------------------------------------


def _payment_pt(method: str | None) -> str | None:
    if method and (match := re.fullmatch(r"credit_(\d+)x", method)):
        return f"cartão de crédito em {match[1]}x"
    return PAYMENT_PT.get(method or "", method)


def _format_order(store: StoreData, order: pd.Series, today: date) -> dict[str, Any]:
    items = store.order_items[store.order_items["order_id"] == order["order_id"]]
    result: dict[str, Any] = {
        "pedido": int(order["order_id"]),
        "data_compra": f"{order['order_date']:%d/%m/%Y}",
        "status": ORDER_STATUS_PT.get(order["status"], order["status"]),
        "itens": [f"{int(i['quantity'])}x {i['name']}" for _, i in items.iterrows()],
        "total": format_brl(order["total"]),
        "pagamento": _payment_pt(order["payment_method"]),
    }
    if order["tracking_code"]:
        result["codigo_rastreio"] = order["tracking_code"]
    if order["notes"]:
        result["observacao"] = order["notes"]
    delivery = order["estimated_delivery"]
    if order["status"] == "shipped" and pd.notna(delivery):
        result["previsao_entrega"] = f"{delivery:%d/%m/%Y}"
        if delivery < today:
            result["alerta"] = "a previsão de entrega já passou"
    elif order["status"] in ("pending", "confirmed"):
        result["previsao_entrega"] = "ainda não definida (pedido não despachado)"
    elif order["status"] == "delivered" and pd.notna(delivery):
        result["recebimento_considerado"] = f"{delivery:%d/%m/%Y} (data prevista de entrega)"
        result["prazos"] = {
            "arrependimento_7_dias_apos_recebimento": deadline_status(
                delivery, RETURN_WINDOW_DAYS, today
            ),
            "troca_por_defeito_30_dias_apos_compra": deadline_status(
                order["order_date"], DEFECT_EXCHANGE_DAYS, today
            ),
            "garantia_legal_90_dias_apos_recebimento": deadline_status(
                delivery, LEGAL_WARRANTY_DAYS, today
            ),
        }
    return result


def lookup_orders(
    store: StoreData, customer_contact: str, order_id: int | None, today: date
) -> dict[str, Any]:
    """Orders of the customer identified by phone or e-mail (policy §9: owner only)."""
    customers = store.customers
    contact = customer_contact.strip()
    if "@" in contact:
        matches = customers[customers["email"] == contact.lower()]
    else:
        digits = phone_digits(contact)
        if len(digits) < 8:
            return {"erro": "Informe o telefone com DDD ou o e-mail usado na compra."}
        matches = customers[customers["phone_digits"].str.endswith(digits)]
    if matches.empty:
        return {
            "erro": "Não encontrei cadastro com esse contato. Peça o telefone com DDD ou o "
            "e-mail usado na compra."
        }
    if len(matches) > 1:
        return {"erro": "Esse contato corresponde a mais de um cadastro. Peça o telefone com DDD."}

    customer = matches.iloc[0]
    orders = store.orders[store.orders["customer_id"] == customer["customer_id"]]
    if order_id is not None:
        orders = orders[orders["order_id"] == order_id]
        if orders.empty:
            return {"erro": f"Não encontrei o pedido {order_id} para este contato."}
    if orders.empty:
        return {"cliente": customer["name"].split()[0], "pedidos": []}
    orders = orders.sort_values("order_date", ascending=False)
    return {
        "cliente": customer["name"].split()[0],
        "pedidos": [_format_order(store, o, today) for _, o in orders.iterrows()],
    }


def customer_first_name(store: StoreData, phone: str) -> str | None:
    digits = phone_digits(phone)
    matches = store.customers[store.customers["phone_digits"] == digits]
    return matches.iloc[0]["name"].split()[0] if len(matches) == 1 else None


# --- LangChain tools ----------------------------------------------------------------------------


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def build_tools(
    store: StoreData,
    manual: PolicyManual,
    tickets: TicketStore,
    clock: Callable[[], datetime],
) -> list[BaseTool]:
    catalog = Catalog(store)
    categories = ", ".join(store.categories["name"])

    @tool(parse_docstring=True)
    def search_products(
        query: str | None = None,
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        include_unavailable: bool = False,
        limit: int = 10,
    ) -> str:
        """Busca produtos no catálogo da loja (preços já calculados, disponibilidade atual).

        Use para perguntas sobre quais instrumentos a loja tem, faixas de preço e opções.
        Os preços consideram promoções ativas.

        Args:
            query: Palavras-chave (marca, modelo, tipo, ex.: "takamine", "nylon", "7 cordas").
            category: Categoria do catálogo (ex.: "violões", "guitarras", "ukuleles").
            min_price: Preço mínimo em reais.
            max_price: Preço máximo em reais.
            include_unavailable: Incluir itens esgotados, descontinuados ou em breve.
            limit: Máximo de produtos retornados.
        """
        return _json(
            catalog.search(query, category, min_price, max_price, include_unavailable, limit)
        )

    search_products.description += f"\nCategorias existentes: {categories}."

    @tool(parse_docstring=True)
    def get_product_details(product: str) -> str:
        """Detalhes de UM produto: preço (com promoção ativa), preço no PIX, parcelamento,
        especificações e disponibilidade. Se indisponível, traz alternativas semelhantes.

        Args:
            product: Nome (pode ser aproximado, ex.: "Takamine GD20") ou id do produto.
        """
        return _json(catalog.details(product))

    @tool
    def list_active_promotions() -> str:
        """Lista as promoções vigentes no sistema, com preço original, desconto e preço
        promocional. Use sempre que o cliente perguntar sobre promoções, descontos ou campanhas
        (ex.: Black Friday) — apenas as promoções listadas aqui estão válidas."""
        return _json(catalog.active_promotions())

    @tool("lookup_orders", parse_docstring=True)
    def lookup_orders_tool(customer_contact: str, order_id: int | None = None) -> str:
        """Consulta pedidos do cliente: status, itens, rastreio, previsão de entrega e prazos de
        devolução/troca/garantia já calculados. Exige o telefone com DDD ou e-mail do titular.

        Args:
            customer_contact: Telefone com DDD ou e-mail usado na compra.
            order_id: Número do pedido, se o cliente informar.
        """
        return _json(lookup_orders(store, customer_contact, order_id, clock().date()))

    @tool(parse_docstring=True)
    def get_store_policy(topic: PolicyTopic) -> str:
        """Consulta o manual de políticas da loja e devolve o texto oficial da seção.

        Tópicos: sobre_contato (endereço, telefones, e-mail, CNPJ), horario, pagamento (formas e
        parcelamento), trocas_devolucoes (arrependimento, defeito, preferência), frete_entregas
        (prazos, rastreio), promocoes (regras de promoções), atendimento (reclamações, situações
        especiais), garantia, privacidade (LGPD).

        Args:
            topic: Tópico da política.
        """
        return manual.get(PolicyTopic(topic))

    @tool(parse_docstring=True)
    def create_support_ticket(
        kind: TicketKind,
        summary: str,
        customer_contact: str | None = None,
        config: RunnableConfig = None,
    ) -> str:
        """Registra uma reclamação ou transfere o atendimento para a equipe humana.

        Use para reclamações (kind="reclamacao") ou quando o caso exigir avaliação humana, ou
        o cliente pedir para falar com uma pessoa (kind="atendimento_humano").

        Args:
            kind: "reclamacao" ou "atendimento_humano".
            summary: Resumo objetivo do caso, em português.
            customer_contact: Telefone ou e-mail do cliente, se conhecido.
        """
        now = clock()
        thread_id = (config or {}).get("configurable", {}).get("thread_id")
        ticket = tickets.create(kind, summary, customer_contact, thread_id, now)
        result = {"protocolo": ticket.protocol, "status_loja": store_status(now)}
        if kind == "reclamacao":
            result["prazo_retorno"] = "até 24 horas úteis (política 7.3)"
        else:
            result["proximo_passo"] = (
                "um atendente humano dará continuidade no horário de atendimento"
            )
        return _json(result)

    return [
        search_products,
        get_product_details,
        list_active_promotions,
        lookup_orders_tool,
        get_store_policy,
        create_support_ticket,
    ]
