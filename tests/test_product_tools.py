import json

from emporio_agent.tools import (
    execute_tool,
    get_product_details,
    list_categories,
    search_products,
    tool_schemas,
)


def names(result):
    return [p["name"] for p in result["products"]]


def test_list_categories():
    categories = [c["name"] for c in list_categories()["categories"]]
    assert len(categories) == 9
    assert "Violões" in categories


def test_search_is_accent_and_case_insensitive_and_partial():
    result = search_products(query="takamine gd20")
    assert names(result) == ["Takamine GD20 Dreadnought Natural"]


def test_search_handles_portuguese_plural_and_accents():
    result = search_products(query="violoes", max_price=500)
    assert "Tagima Memphis AC-39 Nylon Natural" in names(result)


def test_browse_available_guitars_up_to_1000():
    result = search_products(category="Violões", max_price=1000, available_only=True, limit=20)
    products = result["products"]
    assert products
    assert all(p["availability"] == "available" for p in products)
    assert "Giannini GF-3D Dreadnought Sunburst" not in names(result)  # stock 0
    assert "Shelby SN-7C 7 Cordas Nylon Natural" not in names(result)  # discontinued
    prices = [float(p["price"][3:].replace(".", "").replace(",", ".")) for p in products]
    assert prices == sorted(prices)
    assert max(prices) <= 1000


def test_max_price_uses_promotional_price():
    # Ohana CK-20 costs 549 with 20% off -> 439,20: inside a 450 budget.
    result = search_products(query="ohana ck-20", max_price=450)
    assert names(result) == ["Ohana CK-20 Concert Natural"]


def test_unavailable_products_are_returned_with_their_status():
    result = search_products(query="giannini gf-3d")
    product = result["products"][0]
    assert product["availability"] == "out_of_stock"
    assert "units_in_stock" not in product


def test_coming_soon_is_not_sold_even_with_stock():
    product = search_products(query="KA-ABP-CTG")["products"][0]
    assert product["availability"] == "coming_soon"
    assert "units_in_stock" not in product


def test_unknown_category_returns_error_and_valid_names():
    result = search_products(category="Pedais")
    assert "error" in result
    assert len(result["categories"]) == 9


def test_partial_match_is_flagged():
    result = search_products(query="yamaha theremin")
    assert result["note"]
    assert all("Yamaha" in n for n in names(result))


def test_no_match_returns_empty_list():
    result = search_products(query="theremin")
    assert result["total_matches"] == 0
    assert result["products"] == []


def test_promotion_shows_original_price_and_discount():
    details = get_product_details(90)
    assert details["promotion"] == {
        "name": "Desconto Exclusivo",
        "original_price": "R$ 2.399,00",
        "discount_percent": 18,
        "promotional_price": "R$ 1.967,18",
    }
    assert details["price"] == "R$ 1.967,18"
    assert details["price_display"] == "R$ 1.967,18 (de R$ 2.399,00, 18% de desconto)"


def test_expired_promotion_is_not_shown():
    details = get_product_details(95)  # Takamine GD20, only inactive promotions
    assert "promotion" not in details
    assert details["price"] == "R$ 2.199,00"
    assert details["price_display"] == "R$ 2.199,00"


def test_details_include_specs_and_no_alternatives_when_available():
    details = get_product_details(81)
    assert details["specs"]["strings"] == "nylon"
    assert "alternatives" not in details


def test_unavailable_product_gets_available_alternatives_in_same_category_and_range():
    details = get_product_details(96)  # Giannini GF-3D, 799,90, out of stock
    alternatives = details["alternatives"]
    assert len(alternatives) == 3
    for alt in alternatives:
        assert alt["category"] == "Violões"
        assert alt["availability"] == "available"
        value = float(alt["price"][3:].replace(".", "").replace(",", "."))
        assert 799.9 * 0.7 <= value <= 799.9 * 1.3


def test_discontinued_product_gets_alternatives():
    details = get_product_details(136)  # Ibanez Bass 2X
    assert details["availability"] == "discontinued"
    assert details["alternatives"]
    assert all(a["category"] == "Baixos" for a in details["alternatives"])


def test_unknown_product():
    assert "error" in get_product_details(9999)


def test_execute_tool_returns_json_and_handles_errors():
    ok = json.loads(execute_tool("get_product_details", '{"product_id": 95}'))
    assert ok["name"] == "Takamine GD20 Dreadnought Natural"
    assert "error" in json.loads(execute_tool("nope", "{}"))
    assert "error" in json.loads(execute_tool("get_product_details", '{"wrong": 1}'))
    assert "error" in json.loads(execute_tool("get_product_details", "not json"))


def test_every_tool_has_a_valid_schema():
    for schema in tool_schemas():
        assert schema["type"] == "function"
        assert schema["function"]["description"]
        assert schema["function"]["parameters"]["type"] == "object"


def test_contradictory_description_is_withheld_and_not_searched():
    details = get_product_details(144)  # "Roland Synth 3" described as a Yamaha arranger
    assert "description" not in details
    assert details["description_note"]
    assert "Teclado Sintetizador Roland Synth 3 Pro" not in names(search_products(query="yamaha"))


def test_partial_matches_are_ranked_by_relevance_before_price():
    # Cheaper nylon guitars match one term; the Takamine nylon models match two.
    result = search_products(query="takamine nylon theremin", limit=20)
    assert result["note"]
    assert result["products"][0]["name"] == "Takamine GC1CE Elétrico Nylon Natural"


def test_specific_lookup_of_unavailable_product_includes_alternatives():
    result = search_products(query="giannini gf-3d")
    assert [p["product_id"] for p in result["products"]] == [96]
    assert len(result["alternatives"]) == 3
    assert all(a["availability"] == "available" for a in result["alternatives"])


def test_available_or_multiple_matches_have_no_alternatives():
    assert "alternatives" not in search_products(query="takamine gd20")
    assert "alternatives" not in search_products(query="giannini")
