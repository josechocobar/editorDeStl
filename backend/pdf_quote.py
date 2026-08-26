"""Generación de PDF y PNG para presupuestos de impresión 3D.

Estética: oscura minimalista, acentos cyan, números grandes.
Funciones puras: reciben QuoteResult, devuelven bytes.
"""
from __future__ import annotations

import base64
import io

from backend.quote import QuoteResult

# ── Paleta oscura minimalista ────────────────────────────────
BG_DARK = (15, 23, 42)       # #0F172A
BG_CARD = (30, 41, 59)       # #1E293B
CYAN = (6, 182, 212)         # #06B6D4
CYAN_DIM = (8, 145, 178)     # #0891B2
WHITE = (248, 250, 252)      # #F8FAFC
SLATE_300 = (203, 213, 225)  # #CBD5E1
SLATE_400 = (148, 163, 184)  # #94A3B8
SLATE_500 = (100, 116, 139)  # #64748B
SLATE_700 = (51, 65, 85)     # #334155
EMERALD = (16, 185, 129)     # #10B981


def _fmt(value: float) -> str:
    return f"$ {value:,.2f}"


def _diff_detail(d: float):
    if d <= 1.0:
        return "Simple", "Llaveros, logos, cajas simples", "0%"
    if d <= 1.5:
        return "Media", "Soportes moderados, riesgo de warping", "+50%"
    return "Compleja", "Soportes intensivos, geometrias organicas", "+100%"


def _decode_image(b64: str) -> bytes | None:
    if not b64:
        return None
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
#  PDF — Estilo oscuro minimalista
# ═══════════════════════════════════════════════════════════════

def generate_pdf(quote: QuoteResult) -> bytes:
    from fpdf import FPDF

    class DarkPDF(FPDF):
        def _accent_bar(self, y: float, h: float = 2):
            self.set_fill_color(*CYAN)
            self.rect(0, y, 210, h, "F")
            return y + h

        def _section(self, title: str, y: float) -> float:
            self.set_fill_color(*BG_CARD)
            self.rect(10, y, 190, 9, "F")
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*CYAN)
            self.set_xy(14, y + 1)
            self.cell(0, 7, title)
            self.set_text_color(*WHITE)
            return y + 11

        def _row(self, label: str, value: str, y: float,
                 label_color=SLATE_400, value_color=WHITE,
                 label_size=9, value_size=9, value_font=""):
            self.set_font("Helvetica", "", label_size)
            self.set_text_color(*label_color)
            self.set_xy(14, y)
            self.cell(50, 6, label)
            self.set_font("Helvetica", value_font, value_size)
            self.set_text_color(*value_color)
            self.set_x(66)
            self.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")
            return y + 7

    pdf = DarkPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # fondo oscuro
    pdf.set_fill_color(*BG_DARK)
    pdf.rect(0, 0, 210, 297, "F")

    # barra cyan superior
    pdf._accent_bar(0, 3)

    # titulo
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(14, 10)
    pdf.cell(0, 12, "PRESUPUESTO")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*SLATE_500)
    pdf.set_xy(14, 23)
    pdf.cell(0, 5, f"STLFiles  |  {quote.timestamp[:10]}")

    y = 32
    y = pdf._accent_bar(y)
    y += 4

    # ── Captura + Dimensiones ──
    img_bytes = _decode_image(quote.image_base64)
    if img_bytes:
        try:
            pdf.image(io.BytesIO(img_bytes), x=14, y=y, w=65)
            pdf.set_draw_color(*CYAN)
            pdf.set_line_width(0.6)
            pdf.rect(14, y, 65, 49, "D")
            pdf.set_line_width(0.2)
        except Exception:
            img_bytes = None

    x_info = 86 if img_bytes else 14

    if quote.dims_mm and len(quote.dims_mm) == 3:
        d = quote.dims_mm
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*SLATE_500)
        pdf.set_xy(x_info, y + 1)
        pdf.cell(0, 5, "DIMENSIONES")
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*WHITE)
        pdf.set_xy(x_info, y + 7)
        pdf.cell(0, 9, f"{d[0]:.1f}  x  {d[1]:.1f}  x  {d[2]:.1f}  mm")
        y_dims = y + 18
    else:
        y_dims = y

    model = quote.config_snapshot.get("model_name", "")
    if model:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*SLATE_300)
        pdf.set_xy(x_info, y_dims + 1)
        pdf.cell(0, 5, model)
        y_dims += 8

    if img_bytes:
        y = max(y + 53, y_dims + 2)
    else:
        y = y_dims + 4

    # ── Datos de impresion ──
    y = pdf._section("Datos de Impresion", y)
    y += 1
    hrs = int(quote.total_hours)
    mins = int((quote.total_hours - hrs) * 60)
    diff_label, diff_desc, diff_pct = _diff_detail(quote.difficulty)

    y = pdf._row("Tiempo", f"{hrs}h {mins}min", y, value_size=10, value_font="B")
    y = pdf._row("Material", f"{quote.grams:.0f} g", y, value_size=10, value_font="B")
    if quote.dims_mm and len(quote.dims_mm) == 3:
        d = quote.dims_mm
        y = pdf._row("Dimensiones", f"{d[0]:.1f} x {d[1]:.1f} x {d[2]:.1f} mm", y)

    # dificultad
    y += 1
    y = pdf._row("Dificultad", f"{diff_label}  ({diff_pct})", y,
                  value_color=CYAN, value_font="B")
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*SLATE_500)
    pdf.set_xy(66, y)
    pdf.cell(0, 4, diff_desc)
    y += 5
    if quote.extra_difficulty > 0:
        pdf.set_xy(66, y)
        pdf.set_text_color(*EMERALD)
        pdf.cell(0, 4, f"+{_fmt(quote.extra_difficulty)} al subtotal")
        y += 5
    y += 3

    # ── Desglose ──
    y = pdf._section("Desglose de Costos", y)
    y += 1

    y = pdf._row("Costo Tiempo", _fmt(quote.cost_time), y)
    y = pdf._row("Costo Material", _fmt(quote.cost_material), y)

    # linea sutil antes del subtotal
    pdf.set_draw_color(*SLATE_700)
    pdf.set_line_width(0.3)
    pdf.line(14, y, 196, y)
    y += 2

    y = pdf._row("Subtotal", _fmt(quote.subtotal), y,
                  label_color=WHITE, value_color=WHITE,
                  label_size=10, value_size=10, value_font="B")

    if quote.extra_difficulty > 0:
        y = pdf._row(f"Extra Dificultad ({diff_pct})",
                     _fmt(quote.extra_difficulty), y, value_color=EMERALD)
    if quote.profit > 0:
        y = pdf._row("Ganancia", _fmt(quote.profit), y)

    # ── PRECIO FINAL ──
    y += 6
    pdf.set_fill_color(*CYAN)
    pdf.rect(14, y, 182, 20, "F")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*BG_DARK)
    pdf.set_xy(20, y + 2)
    pdf.cell(0, 6, "PRECIO FINAL")
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_xy(20, y + 8)
    pdf.cell(0, 10, _fmt(quote.final_price))

    y += 24

    # ── Footer ──
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*SLATE_500)
    cfg = quote.config_snapshot
    pdf.set_xy(10, y)
    pdf.cell(0, 4,
             f"Maquina ${cfg.get('machine_cost', 0):,.0f} / "
             f"{cfg.get('machine_life_hrs', 0):,.0f}hs  |  "
             f"{cfg.get('power_watts', 0)}W @ ${cfg.get('electricity_kwh', 0)}/kWh  |  "
             f"Filamento ${cfg.get('filament_per_kg', 0):,.0f}/kg  |  "
             f"Ganancia {cfg.get('profit_pct', 0)}%",
             new_x="LMARGIN", new_y="NEXT", align="C")

    # barra cyan inferior
    pdf.set_fill_color(*CYAN)
    pdf.rect(0, 295, 210, 2, "F")

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  PNG — Estilo oscuro minimalista
# ═══════════════════════════════════════════════════════════════

def generate_png(quote: QuoteResult) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    W, H = 640, 600
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Fuentes - numeros GRANDES
    try:
        f_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        f_section = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
        f_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        f_value = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        f_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        f_price_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
        f_price = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        f_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
        f_dims = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except OSError:
        f_title = f_section = f_label = f_value = f_big = f_price_label = f_price = f_small = f_dims = ImageFont.load_default()

    # ── Barra cyan superior ──
    draw.rectangle([(0, 0), (W, 4)], fill=CYAN)

    # ── Titulo ──
    y = 18
    draw.text((28, y), "PRESUPUESTO", fill=WHITE, font=f_title)
    y += 32
    draw.text((28, y), f"STLFiles  |  {quote.timestamp[:10]}", fill=SLATE_500, font=f_small)
    y += 14
    draw.line([(28, y), (W - 28, y)], fill=CYAN, width=2)
    y += 8

    # ── Captura del modelo ──
    img_bytes = _decode_image(quote.image_base64)
    model_img = None
    if img_bytes:
        try:
            model_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            model_img = model_img.resize((180, 140), Image.LANCZOS)
        except Exception:
            model_img = None

    if model_img:
        img.paste(model_img, (28, y))
        draw.rectangle([(26, y - 2), (210, y + 142)], outline=CYAN, width=2)
        x_info = 224
    else:
        x_info = 28

    # ── Dimensiones ──
    if quote.dims_mm and len(quote.dims_mm) == 3:
        d = quote.dims_mm
        draw.text((x_info, y + 2), "DIMENSIONES", fill=SLATE_500, font=f_small)
        draw.text((x_info, y + 16), f"{d[0]:.1f} x {d[1]:.1f} x {d[2]:.1f}", fill=WHITE, font=f_dims)
        draw.text((x_info, y + 44), "mm", fill=SLATE_500, font=f_small)
        y_dims = y + 60
    else:
        y_dims = y + 4

    model_name = quote.config_snapshot.get("model_name", "")
    if model_name:
        draw.text((x_info, y_dims), model_name, fill=SLATE_300, font=f_value)
        y_dims += 18

    if model_img:
        y = max(y + 148, y_dims + 4)
    else:
        y = y_dims + 4

    # ── Datos de impresion ──
    # seccion con fondo card
    draw.rounded_rectangle([(24, y), (W - 24, y + 90)], radius=6, fill=BG_CARD)
    draw.text((34, y + 6), "DATOS DE IMPRESION", fill=CYAN, font=f_section)
    y += 24

    hrs = int(quote.total_hours)
    mins = int((quote.total_hours - hrs) * 60)
    diff_label, diff_desc, diff_pct = _diff_detail(quote.difficulty)

    for lbl, val in [("Tiempo", f"{hrs}h {mins}min"), ("Material", f"{quote.grams:.0f} g")]:
        draw.text((40, y), lbl, fill=SLATE_400, font=f_label)
        draw.text((180, y), val, fill=WHITE, font=f_value)
        y += 20

    if quote.dims_mm and len(quote.dims_mm) == 3:
        d = quote.dims_mm
        draw.text((40, y), "Dimensiones", fill=SLATE_400, font=f_label)
        draw.text((180, y), f"{d[0]:.1f} x {d[1]:.1f} x {d[2]:.1f} mm", fill=WHITE, font=f_value)
        y += 20

    # dificultad
    draw.text((40, y), "Dificultad", fill=SLATE_400, font=f_label)
    draw.text((180, y), f"{diff_label}  ({diff_pct})", fill=CYAN, font=f_value)
    y += 18
    draw.text((180, y), diff_desc, fill=SLATE_500, font=f_small)
    y += 12
    if quote.extra_difficulty > 0:
        draw.text((180, y), f"+{_fmt(quote.extra_difficulty)} al subtotal", fill=EMERALD, font=f_small)
        y += 12

    y += 8

    # ── Desglose ──
    draw.text((28, y), "DESGLOSE DE COSTOS", fill=CYAN, font=f_section)
    y += 22

    cost_rows = [
        ("Costo Tiempo", _fmt(quote.cost_time), False),
        ("Costo Material", _fmt(quote.cost_material), False),
    ]
    if quote.extra_difficulty > 0:
        cost_rows.append((f"Extra Dificultad ({diff_pct})", _fmt(quote.extra_difficulty), False))
    if quote.profit > 0:
        cost_rows.append(("Ganancia", _fmt(quote.profit), False))

    for lbl, val, _ in cost_rows:
        draw.text((36, y), lbl, fill=SLATE_400, font=f_label)
        draw.text((400, y), val, fill=SLATE_300, font=f_value)
        y += 20

    # subtotal
    draw.line([(36, y), (W - 36, y)], fill=SLATE_700, width=1)
    y += 4
    draw.text((36, y), "Subtotal", fill=WHITE, font=f_value)
    draw.text((400, y), _fmt(quote.subtotal), fill=WHITE, font=f_big)
    y += 26

    # ── PRECIO FINAL ──
    draw.rounded_rectangle([(24, y), (W - 24, y + 60)], radius=8, fill=CYAN)
    draw.text((40, y + 10), "PRECIO FINAL", fill=BG_DARK, font=f_price_label)
    draw.text((40, y + 28), _fmt(quote.final_price), fill=BG_DARK, font=f_price)

    # ── Barra cyan inferior ──
    draw.rectangle([(0, H - 3), (W, H)], fill=CYAN)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
