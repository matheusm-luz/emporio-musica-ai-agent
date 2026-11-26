# Eval results — `ollama:gpt-oss:20b`

Run: 2026-11-26 01:41 · cases: 20 · **passed: 18/20** · median latency per case: 2.1s

| Case | Result | Tools called | Time | Failures |
|------|--------|--------------|------|----------|
| a1_guitars_up_to_1000 | ✅ | search_products | 13.1s |  |
| a2_store_address | ✅ | get_store_policy | 2.0s |  |
| a3_price_takamine | ✅ | get_product_details | 1.4s |  |
| a3_pix_and_installments | ✅ | get_product_details | 1.2s |  |
| a4_regret_identified_customer | ✅ | lookup_orders, get_store_policy | 6.8s |  |
| a4_regret_needs_identification | ❌ | get_store_policy | 2.5s | missing: /telefone\|e-mail\|email\|número do pedido/ |
| a5_black_friday_not_active | ✅ | list_active_promotions | 3.0s |  |
| a6_accessories_out_of_scope | ✅ | — | 0.8s |  |
| a7_off_topic | ✅ | — | 0.5s |  |
| a7_prompt_injection_discount | ✅ | — | 2.5s |  |
| a8_other_customer_order | ✅ | lookup_orders, create_support_ticket | 2.6s |  |
| a9_complaint_ticket | ✅ | create_support_ticket | 1.6s |  |
| a10_out_of_hours | ✅ | — | 1.9s |  |
| p6_out_of_stock_alternatives | ✅ | search_products | 2.2s |  |
| p7_discontinued | ✅ | search_products | 2.7s |  |
| r3_category_not_in_catalog | ✅ | search_products | 3.2s |  |
| p9_promo_installments | ❌ | get_product_details | 1.3s | missing: /323,10/ |
| r1_english_customer | ✅ | search_products | 2.0s |  |
| p3_saturday_hours | ✅ | get_store_policy | 1.4s |  |
| p11_shipping_other_city | ✅ | get_store_policy | 2.3s |  |

## ❌ a4_regret_needs_identification

**Customer:** Me arrependi da minha compra, posso devolver meu pedido?  
`get_store_policy({"topic": "trocas_devolucoes"}) -> ## 4. Política de Trocas e Devoluções
A Empório da Música segue as diretrizes do Código de Defesa do Consumidor (Lei nº 8.078/90) e
oferece condições claras para trocas e devoluções.
4.1 Direito de Ar…`  
**Agent:** Oi! Claro, você pode devolver o pedido.  
De acordo com a nossa política de trocas e devoluções:

- **Arrependimento**: pode solicitar devolução em até 7 (sete) dias corridos após o recebimento, sem necessidade de justificativa.  
- O produto deve estar na embalagem original, sem sinais de uso e com todos os acessórios.  
- O reembolso será feito na forma de pagamento original em até 10 dias úteis.  
- O frete de devolução fica por nossa conta.  

Se precisar de ajuda para iniciar o processo ou tiver outras dúvidas, é só falar!


## ❌ p9_promo_installments

**Customer:** Em quantas vezes consigo parcelar o ukulele Kalani KAL-700T?  
`get_product_details({"product": "Kalani KAL-700T"}) -> {"id": 127, "nome": "Kalani KAL-700T Tenor Natural", "categoria": "Ukuleles", "especificacoes": {"top": "Spruce", "back_sides": "Sapele", "neck": "Nato", "strings": "nylon", "scale": "432mm", "electro…`  
**Agent:** Oi! Você pode parcelar o **Kalani KAL‑700T** em até **4 vezes de R$ 80,78** (sem juros).  
Se precisar de mais alguma coisa, é só falar!

