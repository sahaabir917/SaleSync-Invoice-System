"""
Generates PDF invoices using xhtml2pdf (pure Python, no system libs needed).
Renders a Jinja2 HTML template and converts it to a PDF byte stream.
"""
import io
import logging
from datetime import datetime

from flask import render_template
from xhtml2pdf import pisa

logger = logging.getLogger(__name__)


def compute_totals(data: dict) -> dict:
    """Compute subtotal, discount amount, and total price from invoice data."""
    try:
        quantity = float(data.get("quantity", 1))
        unit_price = float(data.get("unit_price", 0))
        discount_pct = float(str(data.get("discount_pct", 0)).replace("%", ""))
        tax_amount = float(data.get("tax_amount", 0))
    except (ValueError, TypeError):
        quantity = unit_price = discount_pct = tax_amount = 0

    subtotal = quantity * unit_price
    discount_amount = subtotal * (discount_pct / 100)
    total = subtotal - discount_amount + tax_amount

    return {
        "subtotal": round(subtotal, 2),
        "discount_amount": round(discount_amount, 2),
        "total": round(total, 2),
    }


def render_invoice_html(invoice_data: dict, company_name: str, company_address: str) -> str:
    """Render the invoice as an HTML string (for preview or PDF)."""
    totals = compute_totals(invoice_data)
    context = {
        **invoice_data,
        **totals,
        "company_name": company_name,
        "company_address": company_address,
        "generated_at": datetime.now().strftime("%d %b %Y, %H:%M:%S"),
    }
    return render_template("invoice.html", **context)


def generate_pdf(invoice_data: dict, company_name: str, company_address: str) -> bytes:
    """Generate a PDF from invoice data and return as bytes."""
    html_content = render_invoice_html(invoice_data, company_name, company_address)
    pdf_bytes = io.BytesIO()
    result = pisa.CreatePDF(src=html_content, dest=pdf_bytes, encoding="utf-8")
    if result.err:
        logger.error("PDF generation error for order_id=%s: %s", invoice_data.get("order_id"), result.err)
        raise RuntimeError(f"PDF generation failed: {result.err}")
    pdf_bytes.seek(0)
    logger.info("PDF generated for order_id=%s", invoice_data.get("order_id"))
    return pdf_bytes.read()
