import pytest

from emporio_agent.policies import get_policy, load_policies, policy_topics

EXPECTED_TOPICS = [
    "about_store",
    "hours",
    "payment",
    "returns_exchanges",
    "shipping",
    "promotions",
    "customer_service",
    "warranty",
    "privacy",
    "final_provisions",
]


def test_all_ten_sections_are_present_in_order():
    assert policy_topics() == EXPECTED_TOPICS


@pytest.mark.parametrize(
    ("topic", "snippet"),
    [
        ("hours", "Segunda a Sexta-feira 09:00 às 18:00"),
        ("payment", "Parcelamento de 7x a 12x: sem juros, parcela mínima de R$ 100,00."),
        ("returns_exchanges", "7 (sete) dias corridos após o recebimento"),
        ("shipping", "Frete grátis para pedidos acima de R$ 500,00."),
        ("promotions", "O desconto de PIX (5%) não se aplica"),
        ("warranty", "garantia legal de 90"),
        ("about_store", "Rua 14 de Maio, 3200"),
    ],
)
def test_sections_contain_their_rules(topic, snippet):
    assert snippet in get_policy(topic)["text"]


def test_numbered_list_inside_section_7_does_not_split_it():
    text = get_policy("customer_service")["text"]
    assert "1. Saudação" in text
    assert "5. Fechamento" in text
    assert "Prazo de retorno: 24 horas úteis." in text


def test_page_headers_and_footer_are_removed():
    all_text = "\n".join(p["text"] for p in load_policies().values())
    assert "Página" not in all_text
    assert "Manual de Políticas e Procedimentos" not in all_text
    assert "Sua música começa aqui" not in all_text


def test_contact_data_is_normalized_to_official_values():
    all_text = "\n".join(p["text"] for p in load_policies().values())
    assert "empóriodamusica" not in all_text
    assert "3321-4500" not in all_text
    assert "contato@emporiodamusica.com.br" in get_policy("about_store")["text"]
    assert "(67) 3341-4444" in get_policy("customer_service")["text"]


def test_unknown_topic_returns_error_with_available_topics():
    result = get_policy("refunds")
    assert "error" in result
    assert result["available_topics"] == EXPECTED_TOPICS
