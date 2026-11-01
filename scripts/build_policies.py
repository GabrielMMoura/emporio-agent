"""Splits the store policy PDF into one JSON entry per top-level section.

Run once after the PDF changes:  uv run python scripts/build_policies.py
The output (data/processed/policies.json) is committed, so the agent does not need
a PDF parser at runtime.
"""

import json
import re

import pdfplumber

from emporio_agent.config import DATA_DIR, POLICIES_PATH

PDF_PATH = DATA_DIR / "políticas_da_loja.pdf"

# Section titles exactly as they appear in the manual, mapped to tool topics.
# Splitting on known titles (not on any "N. " line) avoids breaking at the
# numbered list inside section 7.2.
SECTIONS = {
    "about_store": "1. Sobre a Empório da Música",
    "hours": "2. Horário de Funcionamento",
    "payment": "3. Formas de Pagamento",
    "returns_exchanges": "4. Política de Trocas e Devoluções",
    "shipping": "5. Política de Frete e Entregas",
    "promotions": "6. Promoções e Descontos",
    "customer_service": "7. Atendimento via WhatsApp",
    "warranty": "8. Garantia",
    "privacy": "9. Privacidade e Proteção de Dados",
    "final_provisions": "10. Disposições Finais",
}

# The manual contradicts itself on contact data. The cover page and section 1.2 give
# (67) 3341-4444; section 7 gives (67) 3321-4500. The cover uses the e-mail without the
# accent, which is the only valid form for a domain. See README "Data notes".
CORRECTIONS = {
    "contato@empóriodamusica.com.br": "contato@emporiodamusica.com.br",
    "(67) 3321-4500": "(67) 3341-4444",
}

PAGE_NOISE = re.compile(r"^(Empório da Música Manual de Políticas e Procedimentos|Página \d+)$")
FOOTER = "Empório da Música — Sua música começa aqui."


def extract_lines() -> list[str]:
    with pdfplumber.open(PDF_PATH) as pdf:
        # Page 1 is the cover; its address/phone also appear in section 1.2.
        text = "\n".join(page.extract_text() for page in pdf.pages[1:])
    lines = [line.strip() for line in text.splitlines()]
    return [line for line in lines if line and not PAGE_NOISE.match(line)]


def split_sections(lines: list[str]) -> dict[str, dict]:
    title_to_topic = {title: topic for topic, title in SECTIONS.items()}
    sections: dict[str, dict] = {}
    current: str | None = None
    for line in lines:
        if line == FOOTER:
            break
        if line in title_to_topic:
            current = title_to_topic[line]
            sections[current] = {"title": line, "lines": []}
        elif current:
            sections[current]["lines"].append(line)

    missing = set(SECTIONS) - set(sections)
    if missing:
        raise ValueError(f"Sections not found in the PDF: {sorted(missing)}")

    result = {}
    for topic, section in sections.items():
        text = "\n".join(section["lines"])
        for wrong, right in CORRECTIONS.items():
            text = text.replace(wrong, right)
        result[topic] = {"title": section["title"], "text": text}
    return result


def main() -> None:
    policies = split_sections(extract_lines())
    POLICIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    POLICIES_PATH.write_text(
        json.dumps(policies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(policies)} sections to {POLICIES_PATH}")


if __name__ == "__main__":
    main()
