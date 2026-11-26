"""Policy manual (PDF) -> numbered sections, served to the agent by topic.

The PDF is parsed once at startup with pypdf's layout mode (keeps table columns). Parsing fails
loudly if the expected structure (sections 1..10) is not found, so a changed manual cannot be
served half-parsed.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pypdf import PdfReader

from emporio_agent.config import DATA_DIR

PAGE_HEADER = "Empório da Música Manual de Políticas e Procedimentos"
EXPECTED_SECTIONS = 10
_HEADING = re.compile(r"^(\d{1,2})\. ([^:|]+)$")
_PAGE_FOOTER = re.compile(r"^\|?\s*Página \d+$")


class PolicyTopic(StrEnum):
    SOBRE_CONTATO = "sobre_contato"
    HORARIO = "horario"
    PAGAMENTO = "pagamento"
    TROCAS_DEVOLUCOES = "trocas_devolucoes"
    FRETE_ENTREGAS = "frete_entregas"
    PROMOCOES = "promocoes"
    ATENDIMENTO = "atendimento"
    GARANTIA = "garantia"
    PRIVACIDADE = "privacidade"


# Topic -> manual sections. "sobre_contato" also carries the cover and the WhatsApp channel line
# from §7, because the manual lists two different WhatsApp numbers (SPEC I12). The note tells the
# model that the divergence is in the manual itself, so it shows both instead of picking one.
CONTACT_DIVERGENCE_NOTE = (
    "Observação interna: há dois números de WhatsApp (§1.2 e §7) e duas grafias do e-mail "
    "(capa e §1.2). Ao informar contatos ao cliente, apresente todos como contatos da loja, "
    "exatamente como escritos acima; não escolha um."
)
TOPIC_SECTIONS: dict[PolicyTopic, tuple[int, ...]] = {
    PolicyTopic.SOBRE_CONTATO: (0, 1),
    PolicyTopic.HORARIO: (2,),
    PolicyTopic.PAGAMENTO: (3,),
    PolicyTopic.TROCAS_DEVOLUCOES: (4,),
    PolicyTopic.FRETE_ENTREGAS: (5,),
    PolicyTopic.PROMOCOES: (6,),
    PolicyTopic.ATENDIMENTO: (7, 10),
    PolicyTopic.GARANTIA: (8,),
    PolicyTopic.PRIVACIDADE: (9,),
}


@dataclass(frozen=True)
class Section:
    number: int
    title: str
    body: str

    def render(self) -> str:
        return f"## {self.number}. {self.title}\n{self.body}" if self.number else self.body


def _clean_lines(page_text: str) -> list[str]:
    """Normalise pypdf layout output: tables as 'a | b', bullets as '- ', wrapped lines joined."""
    lines: list[str] = []
    for raw in page_text.splitlines():
        line = re.sub(r"[ \t]{3,}", " | ", raw).strip()
        if not line or line == PAGE_HEADER or _PAGE_FOOTER.match(line):
            continue
        if line.startswith("| • | "):
            lines.append("- " + line.removeprefix("| • | "))
        elif match := re.match(r"^\| (\d+)\. \| (.*)$", line):
            lines.append(f"{match[1]}) {match[2]}")  # numbered steps, kept apart from headings
        elif line.startswith("| ") and " | " not in line[2:] and lines:
            lines[-1] += " " + line.removeprefix("| ")  # wrapped continuation line
        else:
            lines.append(line.removeprefix("| "))
    return lines


def parse_policy_pdf(pdf_path: Path) -> dict[int, Section]:
    pages = [p.extract_text(extraction_mode="layout") for p in PdfReader(pdf_path).pages]
    cover = "\n".join(
        line.removeprefix("| ").strip() for line in pages[0].splitlines() if line.strip()
    )
    sections: dict[int, Section] = {0: Section(0, "Capa", "Capa do manual:\n" + cover)}

    current: tuple[int, str] | None = None
    body: list[str] = []
    for line in (line for page in pages[1:] for line in _clean_lines(page)):
        heading = _HEADING.match(line)
        expected = current[0] + 1 if current else 1
        if heading and int(heading[1]) == expected:  # only the next section number is a heading
            if current:
                sections[current[0]] = Section(current[0], current[1], "\n".join(body))
            current, body = (int(heading[1]), heading[2].strip()), []
        else:
            body.append(line)
    if current:
        sections[current[0]] = Section(current[0], current[1], "\n".join(body))

    if len(sections) != EXPECTED_SECTIONS + 1:
        raise ValueError(
            f"Policy manual: expected sections 1..{EXPECTED_SECTIONS}, got {sorted(sections)}"
        )
    return sections


class PolicyManual:
    def __init__(self, sections: dict[int, Section]) -> None:
        self.sections = sections

    @classmethod
    def load(cls, data_dir: Path = DATA_DIR) -> "PolicyManual":
        pdfs = sorted(data_dir.glob("*.pdf"))
        if len(pdfs) != 1:
            raise FileNotFoundError(f"Expected exactly one policy PDF in {data_dir}, got {pdfs}")
        return cls(parse_policy_pdf(pdfs[0]))

    def whatsapp_channel_line(self) -> str:
        """First paragraph of §7, which names the WhatsApp channel."""
        return self.sections[7].body.split("\n7.1", 1)[0].strip()

    def get(self, topic: PolicyTopic) -> str:
        parts = [self.sections[n].render() for n in TOPIC_SECTIONS[topic]]
        if topic is PolicyTopic.SOBRE_CONTATO:
            parts.append(f"## 7. Atendimento via WhatsApp (trecho)\n{self.whatsapp_channel_line()}")
            parts.append(CONTACT_DIVERGENCE_NOTE)
        return "\n\n".join(parts)
