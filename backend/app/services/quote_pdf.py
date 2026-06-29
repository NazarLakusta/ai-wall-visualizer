from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models import Lead, Store

DEJAVU_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
DEJAVU_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


def _find_fonts() -> tuple[Path, Path]:
    if DEJAVU_REGULAR.is_file() and DEJAVU_BOLD.is_file():
        return DEJAVU_REGULAR, DEJAVU_BOLD
    raise FileNotFoundError("DejaVu fonts not found. Install fonts-dejavu-core in the container.")


def _safe(text: str | None) -> str:
    if not text:
        return ""
    return str(text).replace("\r", "")


def _money(amount: float | None) -> str:
    if amount is None:
        return "—"
    return f"₴{amount:,.0f}".replace(",", " ")


class _QuotePDF:
    def __init__(self) -> None:
        from fpdf import FPDF

        class QuotePDF(FPDF):
            pass

        self._pdf = QuotePDF()
        regular, bold = _find_fonts()
        self._pdf.add_font("DejaVu", "", str(regular))
        self._pdf.add_font("DejaVu", "B", str(bold))
        self._pdf.set_auto_page_break(auto=True, margin=18)

    def __getattr__(self, name):
        return getattr(self._pdf, name)

    def section_title(self, title: str) -> None:
        self._pdf.set_font("DejaVu", "B", 12)
        self._pdf.set_text_color(44, 62, 80)
        self._pdf.multi_cell(0, 8, title)
        self._pdf.ln(2)

    def body_line(self, label: str, value: str) -> None:
        self._pdf.set_font("DejaVu", "B", 10)
        self._pdf.set_text_color(80, 80, 80)
        self._pdf.cell(45, 7, label)
        self._pdf.set_font("DejaVu", "", 10)
        self._pdf.set_text_color(30, 30, 30)
        self._pdf.multi_cell(0, 7, _safe(value))
        self._pdf.ln(1)

    def paragraph(self, text: str) -> None:
        self._pdf.set_font("DejaVu", "", 10)
        self._pdf.set_text_color(30, 30, 30)
        self._pdf.multi_cell(0, 6, _safe(text))
        self._pdf.ln(2)

    def output_bytes(self) -> bytes:
        raw = self._pdf.output()
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
        return raw.encode("latin-1")


def build_lead_quote_pdf(store: Store, lead: Lead, customer_username: str | None = None) -> bytes:
    pdf = _QuotePDF()
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 18)
    pdf.set_text_color(44, 62, 80)
    pdf.multi_cell(0, 10, _safe(store.name or "Магазин"), align="C")
    pdf.ln(2)

    pdf.set_font("DejaVu", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 6, "Кошторис / пропозиція", align="C")
    pdf.ln(6)

    pdf.section_title("Магазин")
    if store.phone:
        pdf.body_line("Телефон:", store.phone)
    if store.address:
        pdf.body_line("Адреса:", store.address)
    if store.telegram_username:
        pdf.body_line("Telegram:", f"@{store.telegram_username.lstrip('@')}")

    pdf.ln(3)
    pdf.section_title("Клієнт")
    pdf.body_line("Ім'я:", lead.customer_name or "—")
    pdf.body_line("Телефон:", lead.phone)
    if customer_username:
        pdf.body_line("Telegram:", f"@{customer_username.lstrip('@')}")
    if lead.created_at:
        pdf.body_line("Дата заявки:", lead.created_at.strftime("%d.%m.%Y %H:%M"))

    pdf.ln(3)
    pdf.section_title("Розрахунок")
    if lead.wall_area_sqm:
        pdf.body_line("Площа стін:", f"{lead.wall_area_sqm:g} м²")
    if lead.selection_summary:
        pdf.body_line("Вибір:", lead.selection_summary)
    if lead.paint_plan_summary:
        pdf.body_line("План матеріалів:", "")
        pdf.paragraph(lead.paint_plan_summary)
    pdf.body_line("Разом:", _money(lead.estimated_total_uah))

    if lead.comment:
        pdf.ln(3)
        pdf.section_title("Коментар клієнта")
        pdf.paragraph(lead.comment)

    pdf.ln(8)
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(130, 130, 130)
    generated = datetime.now().strftime("%d.%m.%Y %H:%M")
    pdf.multi_cell(
        0,
        5,
        f"Документ згенеровано {generated}. Орієнтовна вартість — не є публічною офертою.",
        align="C",
    )

    return pdf.output_bytes()
