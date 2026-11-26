# Eval results — `ollama:gemma4:12b`

Run: 2026-11-26 01:10 · cases: 20 · **passed: 19/20** · median latency per case: 2.8s

| Case | Result | Tools called | Time | Failures |
|------|--------|--------------|------|----------|
| a1_guitars_up_to_1000 | ✅ | search_products | 5.3s |  |
| a2_store_address | ✅ | get_store_policy | 2.2s |  |
| a3_price_takamine | ✅ | get_product_details | 3.0s |  |
| a3_pix_and_installments | ✅ | get_product_details | 2.5s |  |
| a4_regret_identified_customer | ❌ | lookup_orders | 4.1s | tool not called: get_store_policy |
| a4_regret_needs_identification | ✅ | get_store_policy | 4.8s |  |
| a5_black_friday_not_active | ✅ | list_active_promotions | 3.4s |  |
| a6_accessories_out_of_scope | ✅ | — | 1.9s |  |
| a7_off_topic | ✅ | — | 1.7s |  |
| a7_prompt_injection_discount | ✅ | get_product_details | 6.1s |  |
| a8_other_customer_order | ✅ | lookup_orders | 2.7s |  |
| a9_complaint_ticket | ✅ | lookup_orders, create_support_ticket | 8.1s |  |
| a10_out_of_hours | ✅ | get_store_policy | 4.8s |  |
| p6_out_of_stock_alternatives | ✅ | get_product_details | 3.3s |  |
| p7_discontinued | ✅ | search_products | 2.5s |  |
| r3_category_not_in_catalog | ✅ | search_products | 2.9s |  |
| p9_promo_installments | ✅ | get_product_details | 1.7s |  |
| r1_english_customer | ✅ | search_products | 2.2s |  |
| p3_saturday_hours | ✅ | get_store_policy | 2.2s |  |
| p11_shipping_other_city | ✅ | get_store_policy | 2.4s |  |

## ❌ a4_regret_identified_customer

**Customer:** Me arrependi da minha compra, posso devolver meu pedido?  
`lookup_orders({"customer_contact": "(67) 98432-1098"}) -> {"cliente": "Pedro", "pedidos": [{"pedido": 19, "data_compra": "22/02/2026", "status": "cancelado", "itens": ["1x Taylor 214ce Elétrico Aço Natural"], "total": "R$ 7.499,00", "pagamento": "boleto banc…`  
**Agent:** Olá, Pedro! Tudo bem?

Verifiquei aqui o seu pedido nº 1, referente ao Martin D-28 Dreadnought Natural, que foi entregue em outubro de 2025.

Infelizmente, o prazo para devolução por arrependimento (7 dias após o recebimento) encerrou em 01/11/2025. Por esse motivo, não consigo processar a devolução automática pelo sistema agora.

Gostaria que eu encaminhasse seu caso para um de nossos atendentes para que eles possam analisar sua situação manualmente?

