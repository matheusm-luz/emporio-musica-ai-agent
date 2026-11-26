from emporio_agent import rules
from emporio_agent.policies import CONTACT_DIVERGENCE_NOTE, PolicyManual, PolicyTopic
from emporio_agent.rules import format_brl


def test_all_ten_sections_are_parsed(manual: PolicyManual) -> None:
    titles = {n: s.title for n, s in manual.sections.items() if n}
    assert titles[2] == "Horário de Funcionamento"
    assert titles[4] == "Política de Trocas e Devoluções"
    assert titles[10] == "Disposições Finais"
    assert sorted(titles) == list(range(1, 11))


def test_numbered_steps_are_not_mistaken_for_sections(manual: PolicyManual) -> None:
    assert "1) Saudação" in manual.sections[7].body


def test_every_topic_returns_text(manual: PolicyManual) -> None:
    for topic in PolicyTopic:
        assert len(manual.get(topic)) > 100, topic


def test_contact_topic_shows_both_whatsapp_numbers(manual: PolicyManual) -> None:
    text = manual.get(PolicyTopic.SOBRE_CONTATO)
    assert "Rua 14 de Maio, 3200" in text
    assert "(67) 3341-4444" in text and "(67) 3321-4500" in text  # SPEC I12
    assert "contato@emporiodamusica.com.br" in text and "contato@empóriodamusica.com.br" in text
    assert text.endswith(CONTACT_DIVERGENCE_NOTE)  # tells the model not to pick one


def test_tables_keep_their_columns(manual: PolicyManual) -> None:
    assert "PIX | Pagamento à vista | 5% de desconto sobre o preço de tabela" in manual.get(
        PolicyTopic.PAGAMENTO
    )


# --- Consistency: rules hard-coded in rules.py must match the manual's text -------------------


def test_opening_hours_match_manual(manual: PolicyManual) -> None:
    text = manual.get(PolicyTopic.HORARIO)
    weekday_open, weekday_close = rules.OPENING_HOURS[0]
    saturday_open, saturday_close = rules.OPENING_HOURS[5]
    assert f"Segunda a Sexta-feira | {weekday_open:%H:%M} às {weekday_close:%H:%M}" in text
    assert f"Sábado | {saturday_open:%H:%M} às {saturday_close:%H:%M}" in text
    assert "Domingo e Feriados | Fechado" in text and 6 not in rules.OPENING_HOURS


def test_payment_rules_match_manual(manual: PolicyManual) -> None:
    text = manual.get(PolicyTopic.PAGAMENTO)
    assert f"{rules.PIX_DISCOUNT * 100:.0f}% de desconto" in text
    for _, minimum in rules.INSTALLMENT_TIERS:
        assert format_brl(minimum) in text
    assert "O desconto de PIX (5%) não se aplica sobre" in manual.get(PolicyTopic.PROMOCOES)
