# Data notes — findings in the provided sources and how they are handled

The source files in `data/` are used exactly as delivered (checksums enforced by
`tests/test_sources.py`). Every fix happens in memory at load time (`src/emporio_agent/data.py`)
and every finding below is also emitted at runtime in `StoreData.warnings`.

## CSVs

| # | Finding | Evidence | Handling |
|---|---------|----------|----------|
| 1 | Descriptions contradict the product name/brand | #135 "Music Man Bass 1X" described as *Fender Jazz Bass*; #137 Yamaha → *Ibanez*, 5 strings vs `specs.strings = 4`; #139 Yamaha → *Pearl*; #140 Pearl → *Tama*; #142 Korg → *Roland*, 88 keys vs `specs.keys = 61`; #144 Roland → *Yamaha* | Name and specs are authoritative (SPEC I9). A description that mentions a brand absent from the name is hidden from the agent |
| 2 | Status and stock disagree | #136 `discontinued` with stock 13; #96 `active` with stock 0; #130 `coming_soon` with stock 2 | `status` prevails (SPEC I8): discontinued = not for sale, coming soon = not purchasable yet, active + 0 = out of stock (agent suggests alternatives, policy §7.3) |
| 3 | Empty categories | Categories 6, 7, 8 (woodwinds, brass, orchestral strings) have no products, while the manual mentions "300+ instruments" | The catalog in the CSV is the only truth: the agent says the item is not available at the moment and never invents products |
| 4 | Order totals differ from items × prices | Order 3: 2 × R$ 1.749 = R$ 3.498 vs recorded R$ 3.450. Order 20: R$ 799 + R$ 689 = R$ 1.488 vs recorded R$ 1.400 | The recorded total is reported (it is what the customer paid); the mismatch is logged |
| 5 | Delivered order with a "coming soon" product | Order 3 (delivered 2025) contains #130 (`coming_soon`) | Reported as recorded; logged |
| 6 | Installments below the policy minimum | Orders 9 and 16 (`credit_6x` with installments of R$ 58,32 and R$ 71,65 < R$ 80) | Historical data, reported as recorded; new quotes always follow §3.1 |
| 7 | Stale open orders | Orders from Feb–Mar 2026 still `pending`/`confirmed` | The agent reports the system status as-is and offers a support ticket (§7.3) |
| 8 | Several promotions per product | e.g. #96 has two "Semana do Músico" rows (18% and 40%), #93 and #99 two each | Only `is_active = 1` counts (SPEC I10); if several were active the best one would apply (§6.2, not cumulative) |
| 9 | Seasonal campaigns are inactive | All "Black Friday" and "Semana do Músico" rows are inactive, although §6.1 lists Black Friday in November | The agent never promises a campaign that is not active in the system (§7.3) — only 4 promotions are active (#90, #94, #121, #127) |
| 10 | Shared e-mail between customers | Customers 11 and 43 share `bruno.martins@jmail.com` | An e-mail that matches more than one customer is ambiguous: the agent asks for the phone number instead |
| 11 | Missing values | Orders without tracking code / estimated delivery (not shipped yet) | Converted to `None` and described as "not available yet" |
| 12 | Heterogeneous specs | `specs` JSON schema varies per category (and spacing varies) | Parsed to dicts; returned as-is |
| 13 | File names with spaces and an accent | `desafio_tecnico_ai_eng - products.csv`, `políticas_da_loja.pdf` | Files are located by glob (`*products.csv`, `*.pdf`); never renamed |

## Policy manual (PDF)

| # | Finding | Handling |
|---|---------|----------|
| 14 | Two WhatsApp numbers: (67) 3341-4444 (§1.2 "Telefone / WhatsApp") and (67) 3321-4500 (§7 "canal de WhatsApp") | Both are shown as written in the manual — not silently picked (SPEC I12) |
| 15 | E-mail written with and without accent (`contato@empóriodamusica.com.br` in §1.2, `contato@emporiodamusica.com.br` on the cover) | Both versions are visible to the agent in the contact topic |
| 16 | Credit-card minimum installment: the §3 table says R$ 100, §3.1 says R$ 50 (up to 3x) / R$ 80 (4–6x) / R$ 100 (7–12x) | The detailed rule §3.1 prevails (SPEC I7); "no minimum (except below R$ 50)" is read as "installments must be ≥ R$ 50" |
| 17 | "Return within 7 days after receipt" but no receipt date in the data | `estimated_delivery` is used as the receipt date of delivered orders (SPEC I5) |
| 18 | Holidays are "closed" but no holiday calendar is given | Not modelled (SPEC I11, known limitation) |
| 19 | "Suggest partner stores when possible" but no partner is named | None is suggested (SPEC P5) |

## Consistency checks

Rules hard-coded in `rules.py` (opening hours, PIX discount, installment minimums) are asserted
against the manual's text in `tests/test_policies.py`, so a change in the manual breaks the build
instead of silently diverging.
