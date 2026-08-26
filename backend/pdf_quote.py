"""Generación de PDF y PNG para presupuestos de impresión 3D.

Funciones puras: reciben QuoteResult, devuelven bytes.
"""
from __future__ import annotations

import io

from backend.quote import QuoteResult


def _fmt(value: float) -> str:
    return f"$ {value:,.2f}"


def generate_pdf(quote: QuoteResult) -> bytes:
    """Genera un PDF profesional con el desglose del presupuesto."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # encabezado
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Presupuesto - Impresion 3D", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"STLFiles  |  {quote.timestamp[:10]}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    # modelo / notas
    if quote.config_snapshot.get("model_name"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, f"Modelo: {quote.config_snapshot['model_name']}", new_x="LMARGIN", new_y="NEXT")
    if quote.config_snapshot.get("notes"):
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, f"Notas: {quote.config_snapshot['notes']}")
    pdf.ln(4)

    # datos de la impresión
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Datos de la Impresion", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)

    hrs = int(quote.total_hours)
    mins = int((quote.total_hours - hrs) * 60)
    diff_label = {1.0: "Simple", 1.5: "Media", 2.0: "Compleja"}.get(quote.difficulty, f"x{quote.difficulty}")

    rows_data = [
        ("Tiempo estimado", f"{hrs}h {mins}min"),
        ("Material", f"{quote.grams:.0f} g"),
        ("Dificultad", diff_label),
    ]
    for label, val in rows_data:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(60, 6, label)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, val, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # desglose de costos
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Desglose de Costos", new_x="LMARGIN", new_y="NEXT")
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    cost_rows = [
        ("Costo Tiempo", _fmt(quote.cost_time)),
        ("Costo Material", _fmt(quote.cost_material)),
        ("Subtotal", _fmt(quote.subtotal)),
    ]
    if quote.extra_difficulty > 0:
        cost_rows.append(("Extra Dificultad", _fmt(quote.extra_difficulty)))
    if quote.profit > 0:
        cost_rows.append(("Ganancia", _fmt(quote.profit)))

    for label, val in cost_rows:
        is_subtotal = label == "Subtotal"
        pdf.set_font("Helvetica", "B" if is_subtotal else "", 10)
        pdf.cell(60, 7, label)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, val, new_x="LMARGIN", new_y="NEXT")
        if is_subtotal:
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(1)

    # precio final
    pdf.ln(3)
    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 12, f"  PRECIO FINAL:  {_fmt(quote.final_price)}",
             new_x="LMARGIN", new_y="NEXT", fill=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    # config utilizada
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(140, 140, 140)
    cfg = quote.config_snapshot
    pdf.cell(0, 5,
             f"Config: Maquina ${cfg.get('machine_cost', 0):,.0f} / "
             f"{cfg.get('machine_life_hrs', 0):,.0f}hs  |  "
             f"Energia {cfg.get('power_watts', 0)}W @ ${cfg.get('electricity_kwh', 0)}/kWh  |  "
             f"Filamento ${cfg.get('filament_per_kg', 0):,.0f}/kg  |  "
             f"Ganancia {cfg.get('profit_pct', 0)}%",
             new_x="LMARGIN", new_y="NEXT", align="C")

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def generate_png(quote: QuoteResult) -> bytes:
    """Genera una imagen PNG con el resumen del presupuesto."""
    from PIL import Image, ImageDraw, ImageFont

    W, H = 600, 420
    img = Image.new("RGB", (W, H), "#ffffff")
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_heading = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    except OSError:
        font_title = ImageFont.load_default()
        font_heading = font_title
        font_body = font_title
        font_big = font_title

    y = 20
    # titulo
    draw.text((W // 2, y), "Presupuesto - Impresion 3D", fill="#2563eb", font=font_title, anchor="mt")
    y += 28
    draw.text((W // 2, y), f"STLFiles  |  {quote.timestamp[:10]}", fill="#888888", font=font_body, anchor="mt")
    y += 24

    # separador
    draw.line([(20, y), (W - 20, y)], fill="#dddddd", width=1)
    y += 12

    # datos impresion
    draw.text((30, y), "Datos de la Impresion", fill="#333333", font=font_heading)
    y += 20
    hrs = int(quote.total_hours)
    mins = int((quote.total_hours - hrs) * 60)
    diff_label = {1.0: "Simple", 1.5: "Media", 2.0: "Compleja"}.get(quote.difficulty, f"x{quote.difficulty}")
    for label, val in [("Tiempo", f"{hrs}h {mins}min"), ("Material", f"{quote.grams:.0f} g"), ("Dificultad", diff_label)]:
        draw.text((40, y), f"{label}:", fill="#666666", font=font_body)
        draw.text((160, y), val, fill="#222222", font=font_body)
        y += 18
    y += 8

    # desglose
    draw.line([(20, y), (W - 20, y)], fill="#dddddd", width=1)
    y += 10
    draw.text((30, y), "Desglose de Costos", fill="#333333", font=font_heading)
    y += 22

    cost_rows = [
        ("Costo Tiempo", _fmt(quote.cost_time)),
        ("Costo Material", _fmt(quote.cost_material)),
        ("Subtotal", _fmt(quote.subtotal)),
    ]
    if quote.extra_difficulty > 0:
        cost_rows.append(("Extra Dificultad", _fmt(quote.extra_difficulty)))
    if quote.profit > 0:
        cost_rows.append(("Ganancia", _fmt(quote.profit)))

    for label, val in cost_rows:
        is_subtotal = label == "Subtotal"
        f = font_heading if is_subtotal else font_body
        draw.text((40, y), label, fill="#333333" if is_subtotal else "#555555", font=f)
        draw.text((350, y), val, fill="#222222", font=f)
        y += 20
        if is_subtotal:
            draw.line([(40, y - 4), (W - 40, y - 4)], fill="#cccccc", width=1)

    # precio final
    y += 10
    draw.rounded_rectangle([(30, y), (W - 30, y + 44)], radius=8, fill="#2563eb")
    draw.text((W // 2, y + 10), "PRECIO FINAL", fill="#ffffff", font=font_body, anchor="mt")
    draw.text((W // 2, y + 26), _fmt(quote.final_price), fill="#ffffff", font=font_big, anchor="mt")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
