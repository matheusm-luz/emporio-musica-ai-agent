# Eval results — `openai:gpt-6-luna`

Run: 2026-11-26 01:39 · cases: 20 · **passed: 20/20** · median latency per case: 3.5s

| Case | Result | Tools called | Time | Failures |
|------|--------|--------------|------|----------|
| a1_guitars_up_to_1000 | ✅ | search_products | 4.7s |  |
| a2_store_address | ✅ | get_store_policy | 3.2s |  |
| a3_price_takamine | ✅ | get_product_details | 3.3s |  |
| a3_pix_and_installments | ✅ | get_product_details | 3.0s |  |
| a4_regret_identified_customer | ✅ | lookup_orders, get_store_policy | 5.6s |  |
| a4_regret_needs_identification | ✅ | get_store_policy, lookup_orders | 5.4s |  |
| a5_black_friday_not_active | ✅ | list_active_promotions | 3.8s |  |
| a6_accessories_out_of_scope | ✅ | search_products, search_products, get_store_policy | 6.6s |  |
| a7_off_topic | ✅ | — | 1.6s |  |
| a7_prompt_injection_discount | ✅ | search_products | 3.7s |  |
| a8_other_customer_order | ✅ | lookup_orders | 3.2s |  |
| a9_complaint_ticket | ✅ | lookup_orders, create_support_ticket | 5.2s |  |
| a10_out_of_hours | ✅ | get_store_policy | 3.1s |  |
| p6_out_of_stock_alternatives | ✅ | search_products, get_product_details | 5.4s |  |
| p7_discontinued | ✅ | search_products | 3.4s |  |
| r3_category_not_in_catalog | ✅ | search_products | 3.1s |  |
| p9_promo_installments | ✅ | get_product_details | 3.2s |  |
| r1_english_customer | ✅ | search_products | 13.2s |  |
| p3_saturday_hours | ✅ | get_store_policy | 3.2s |  |
| p11_shipping_other_city | ✅ | get_store_policy | 3.5s |  |
