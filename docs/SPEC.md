# Specification — Empório da Música customer-service agent

This spec is the contract for the implementation. Every requirement is traced to one of the
original sources and mapped to the test, eval or artifact that verifies it.

## Sources of truth

| ID | Source | Notes |
|----|--------|-------|
| S1 | Challenge statement (`desafio_tecnico_ai_eng_artefact.pdf`) | Hiring-process document; kept out of the public repo |
| S2 | `data/políticas_da_loja.pdf` — store policy manual v2.1 (June 2025) | Used by the agent at runtime |
| S3 | `data/*.csv` — products, categories, promotions, orders, order items, customers | Used by the agent at runtime; never modified |
| S4 | Recruiter e-mail (2026-11-25) | Deadline, language and submission rules |

Anything not stated in S1–S4 is an **interpretation** and is listed in [Interpretations](#interpretations-and-assumptions).

## Functional requirements (S1)

| ID | Requirement | Acceptance criteria | Verified by |
|----|-------------|---------------------|-------------|
| R1 | Persona aligned with the store's identity and tone | Speaks as the Empório da Música virtual assistant (no invented personal name); tone per P1 | evals `persona_*`, examples |
| R2 | Receive and answer text messages using the provided context | Multi-turn chat in CLI and web UI; history persisted per session | `tests/test_graph.py`, manual check |
| R3 | Know when to query **data** (availability, price, order status) | Price, stock and order answers always come from a tool call | evals (expected tools) |
| R4 | Know when to query **policies** (exchanges, hours, payment) | Policy answers come from `get_store_policy` | evals (expected tools) |
| R5 | Handle out-of-scope questions | Accessories redirected (P5); unrelated topics politely declined; prompt injection refused | evals `scope_*` |
| R6 | Python as the main language | — | repository |

## Deliverables (S1, S4)

| ID | Deliverable | Acceptance criteria |
|----|-------------|---------------------|
| D1 | Public GitHub repository | Progressive commit history, no force-push, no changes after the deadline (Fri 2026-11-27 23:59 BRT) |
| D2 | README.md | Run instructions (environment, model provider, commands); justification of technical decisions (framework, LLM, retrieval architecture, prompt strategy); known limitations and next steps; AI coding-assistant usage and workflow |
| D3 | Example conversations | 3–5 `.md` files covering varied scenarios; at least one non-trivial (real-time data lookup or policy application) |
| D4 | Language | All written deliverables in English (S4) |
| D5 | Submission | PDF named `Matheus Monteiro da Luz - Senior AI Engineer` via Google Forms (S4) **and** reply to the e-mail with the repo link (S1) |

## Policy-derived behaviour (S2)

| ID | Section | Behaviour |
|----|---------|-----------|
| P1 | 7.1 Tone | Informal but professional, welcoming — "a friend who knows music"; never robotic or overly formal |
| P2 | 7.1 Accurate information | Never state prices, stock or delivery times without querying the system |
| P3 | 2, 7.1 Hours | Mon–Fri 09:00–18:00, Sat 09:00–13:00, Sun/holidays closed. Outside business hours, tell the customer when the team is back |
| P4 | 7.2 Standard flow | Greet (by name when known) → understand → query → answer clearly with prices and conditions → offer further help |
| P5 | 1, 7.1 Scope | Musical instruments only. Accessories (strings, picks, cables, cases, pedals, amplifiers) are politely redirected. Partner stores may be suggested "when possible" — none are named in the sources, so none are suggested |
| P6 | 7.3 Out of stock | Say it is temporarily unavailable and suggest similar available items; never confirm availability without checking stock |
| P7 | 7.3 Discontinued | Say it is no longer in the catalog and offer equivalent models |
| P8 | 6.2, 7.3 Promotions | Only promotions active in the system; always show original price + promotional price + discount %; promotions are not cumulative; the 5% PIX discount does not apply on top of promotional prices; never promise an expired promotion |
| P9 | 3, 3.1 Payment | PIX (5% off list price), debit, credit up to 12x interest-free subject to minimum-installment rules, boleto (clears in up to 3 business days); combining methods allowed above R$ 2,000 |
| P10 | 4 Returns and exchanges | 7-day right of regret for online purchases (from receipt); 30-day defect exchange (from purchase); 7-day preference exchange; non-eligible items (4.4) |
| P11 | 5 Shipping | Metro area: free above R$ 500, otherwise R$ 35, 1–3 business days. Other cities: PAC / SEDEX / Jadlog estimates; tracking code format |
| P12 | 7.3 Complaints | Listen with empathy, register the complaint and forward it; reply within 24 business hours |
| P13 | 8 Warranty | 90-day legal warranty from receipt; manufacturer warranty 6 months–2 years; exclusions (8.3) |
| P14 | 9 Privacy (LGPD) | Personal data is used only for order handling; order data is disclosed only to its verified owner |
| P15 | 10 Doubts | When unsure how a policy applies, escalate to management instead of guessing |

## Acceptance scenarios

| ID | Customer message (PT-BR) | Expected behaviour | Requirements |
|----|--------------------------|--------------------|--------------|
| A1 | "Quais opções de violões disponíveis custando até R$1000?" | `search_products(category=Violões, max_price=1000)`; lists only active, in-stock items; excludes #96 (out of stock) and #113 (discontinued) | R3, P2, P6 |
| A2 | "Qual o endereço da loja?" | `get_store_policy(sobre_contato)` → Rua 14 de Maio, 3200 — Centro, Campo Grande/MS, CEP 79202-333 | R4 |
| A3 | "Quanto custa o Takamine GD20?" | `get_product_details` → R$ 2.199,00; its 12% promotion is inactive and is not offered; PIX R$ 2.089,05 | R3, P8, P9 |
| A4 | "Me arrependi da minha compra, posso devolver meu pedido?" | Asks for identification → `lookup_orders` + `get_store_policy(trocas_devolucoes)` → applies the 7-day rule to the actual order | R3, R4, P10, P14 |
| A5 | "Tem desconto de Black Friday?" | Lists only promotions active in the system; does not promise Black Friday discounts | P8 |
| A6 | "Vocês vendem cordas e amplificador?" | Explains the store sells instruments only, without naming partner stores | R5, P5 |
| A7 | Off-topic request or prompt injection | Polite refusal, brings the conversation back to the store | R5 |
| A8 | Asking for another customer's order | No personal or order data disclosed | P14 |
| A9 | Complaint | Empathy + support ticket with the 24-business-hour SLA | P12 |
| A10 | Message outside business hours | Answers and informs when the team is back | P3 |

## Interpretations and assumptions

| ID | Topic | Interpretation |
|----|-------|----------------|
| I1 | Role | E-mail subject says "Data Engineer"; body and S1 say "Senior AI Engineer" → Senior AI Engineer |
| I2 | Submission | S4 (Google Forms PDF) and S1 (reply with repo link) differ → do both |
| I3 | Language | Written deliverables in English; the agent replies in the customer's language (PT-BR by default) because the store's customers are Brazilian and S1's sample questions are in Portuguese |
| I4 | "Today" | Real clock in `America/Campo_Grande`, overridable with `AGENT_NOW` for reproducible evals and examples |
| I5 | Receipt date | Data has no actual delivery date → `estimated_delivery` is used as the receipt date for delivered orders |
| I6 | Online purchases | Orders in the system have shipping/tracking data → treated as online purchases (policy 4.1 applies) |
| I7 | Installments | Section 3.1 (detailed) prevails over the summary table in section 3: up to 3x requires installments ≥ R$ 50; 4–6x ≥ R$ 80; 7–12x ≥ R$ 100 |
| I8 | Product status vs stock | `status` prevails: `discontinued` is not sold even with stock; `coming_soon` is not purchasable yet |
| I9 | Name vs description | When a product description contradicts its name/brand, name and specs are authoritative and the description is not shown |
| I10 | Active promotion | A promotion is active only when `is_active = 1`; the campaign calendar in S2 §6.1 is informational |
| I11 | Holidays | No holiday calendar in the sources → not modelled (known limitation) |
| I12 | Conflicting contacts | S2 lists two WhatsApp numbers (§1.2 and §7) and two spellings of the e-mail → shown as written in the manual, not silently picked |
| I13 | Free-tier data usage | Gemini's free tier may use prompts to improve Google products. Acceptable for this case's fictional data; real customer data (LGPD) requires a paid tier or a local model |

## Non-functional requirements

| ID | Requirement |
|----|-------------|
| N1 | KISS: no component without a requirement behind it |
| N2 | Runs with a free local model (Ollama), a free cloud tier (Gemini, no credit card) or OpenAI (paid) by configuration only — one code path; the default local model is chosen by the eval suite |
| N3 | Conversation history persisted in Postgres, with an in-memory fallback when no database is configured |
| N4 | Business rules (pricing, installments, availability, privacy) are deterministic Python and unit-tested |
| N5 | LLM behaviour (tool choice, key facts, forbidden claims) is measured by an eval suite |
| N6 | Invariants whose violation would deceive a customer (e.g. a complaint "registered" with an invented protocol) are enforced in code, not only requested in the prompt |
