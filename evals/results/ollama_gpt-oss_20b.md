# Eval results — `ollama:gpt-oss:20b`

Run: 2026-11-26 01:14 · cases: 20 · **passed: 19/20** · median latency per case: 2.5s

| Case | Result | Tools called | Time | Failures |
|------|--------|--------------|------|----------|
| a1_guitars_up_to_1000 | ✅ | search_products | 11.6s |  |
| a2_store_address | ✅ | get_store_policy | 1.2s |  |
| a3_price_takamine | ✅ | get_product_details | 1.3s |  |
| a3_pix_and_installments | ✅ | get_product_details | 1.4s |  |
| a4_regret_identified_customer | ✅ | lookup_orders, get_store_policy | 5.3s |  |
| a4_regret_needs_identification | ✅ | get_store_policy | 5.5s |  |
| a5_black_friday_not_active | ✅ | list_active_promotions | 2.6s |  |
| a6_accessories_out_of_scope | ✅ | — | 1.1s |  |
| a7_off_topic | ✅ | — | 0.7s |  |
| a7_prompt_injection_discount | ✅ | list_active_promotions, search_products | 5.0s |  |
| a8_other_customer_order | ✅ | lookup_orders, create_support_ticket | 2.6s |  |
| a9_complaint_ticket | ✅ | create_support_ticket | 2.8s |  |
| a10_out_of_hours | ✅ | — | 1.2s |  |
| p6_out_of_stock_alternatives | ✅ | search_products, search_products | 3.9s |  |
| p7_discontinued | ✅ | search_products | 2.3s |  |
| r3_category_not_in_catalog | ✅ | search_products | 2.9s |  |
| p9_promo_installments | ❌ | get_product_details | 1.6s | missing: /323,10/ |
| r1_english_customer | ✅ | search_products | 2.5s |  |
| p3_saturday_hours | ✅ | get_store_policy | 1.6s |  |
| p11_shipping_other_city | ✅ | get_store_policy | 2.4s |  |

## ❌ p9_promo_installments

**Customer:** Em quantas vezes consigo parcelar o ukulele Kalani KAL-700T?  
`get_product_details({"product": "Kalani KAL-700T"}) -> {"id": 127, "nome": "Kalani KAL-700T Tenor Natural", "categoria": "Ukuleles", "especificacoes": {"top": "Spruce", "back_sides": "Sapele", "neck": "Nato", "strings": "nylon", "scale": "432mm", "electro…`  
**Agent:** Você pode parcelar o ukulele **Kalani KAL‑700T** em até **4 vezes de R$ 80,78 sem juros**.  

Precisa de mais alguma informação? 🎶

