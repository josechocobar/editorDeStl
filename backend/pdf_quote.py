"""Generación de PDF y PNG para presupuestos de impresión 3D.

Estética: Persona 5 / cyber-comic / neobrutalista.
Funciones puras: reciben QuoteResult, devuelven bytes.
"""
from __future__ import annotations

import base64
import io

from backend.quote import QuoteResult

# ── Paleta Persona 5 ──────────────────────────────────────────
RED = (230, 57, 70)        # #E63946
BLACK = (13, 13, 13)       # #0D0D0D
DARK_BG = (26, 26, 46)     # #1A1A2E
WHITE = (255, 255, 255)
GOLD = (255, 215, 0)       # #FFD700
LIGHT_GRAY = (180, 180, 180)
MID_GRAY = (100, 100, 100)


def _fmt(value: float) -> str:
    return f"$ {value:,.2f}"


def _diff_detail(d: float):
    """Devuelve (label, description, pct_str) para el nivel de dificultad."""
    if d <= 1.0:
        return "SIMPLE", "Llaveros, logos, cajas simples", "0%"
    if d <= 1.5:
        return "MEDIA", "Soportes moderados, riesgo de warping", "+50%"
    return "COMPLEJA", "Soportes intensivos, geometrias organicas", "+100%"


def _decode_image(b64: str) -> bytes | None:
    """Decodifica base64 (con o sin prefijo data:) a bytes PNG."""
    if not b64:
        return None
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
#  PDF — Estilo Persona 5 / Neobrutalista
# ═══════════════════════════════════════════════════════════════

def generate_pdf(quote: QuoteResult) -> bytes:
    from fpdf import FPDF

    class P5PDF(FPDF):
        """PDF con estilo cyberpunk: barras rojas, bordes gruesos."""

        def _red_bar(self, y: float, h: float = 3):
            self.set_fill_color(*RED)
            self.rect(0, y, 210, h, "F")
            return y + h

        def _section_title(self, title: str, y: float) -> float:
            # fondo negro + texto rojo
            self.set_fill_color(*BLACK)
            self.rect(10, y, 190, 10, "F")
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*RED)
            self.set_xy(14, y + 1)
            self.cell(0, 8, title.upper())
            self.set_text_color(*BLACK)
            return y + 12

        def _thick_line(self, y: float):
            self.set_draw_color(*BLACK)
            self.set_line_width(0.8)
            self.line(10, y, 200, y)
            self.set_line_width(0.2)

    pdf = P5PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── Barra roja superior ──
    pdf.set_fill_color(*RED)
    pdf.rect(0, 0, 210, 6, "F")

    # ── Título ──
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*RED)
    pdf.set_xy(10, 12)
    pdf.cell(0, 12, "PRESUPUESTO", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MID_GRAY)
    pdf.set_x(10)
    pdf.cell(0, 5, f"STLFiles  //  {quote.timestamp[:10]}", new_x="LMARGIN", new_y="NEXT")

    y = pdf.get_y() + 2
    y = pdf._red_bar(y)
    y += 4

    # ── Captura del modelo + Dimensiones ──
    img_bytes = _decode_image(quote.image_base64)
    if img_bytes:
        try:
            pdf.image(io.BytesIO(img_bytes), x=10, y=y, w=70)
            #Marco rojo alrededor de la imagen
            pdf.set_draw_color(*RED)
            pdf.set_line_width(1.2)
            pdf.rect(10, y, 70, 52, "D")
            pdf.set_line_width(0.2)
        except Exception:
            img_bytes = None

    x_info = 85 if img_bytes else 10

    # Dimensiones
    if quote.dims_mm and len(quote.dims_mm) == 3:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*BLACK)
        pdf.set_xy(x_info, y + 2)
        pdf.cell(0, 6, "DIMENSIONES", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 18)
        pdf.set_text_color(*RED)
        pdf.set_x(x_info)
        dims = quote.dims_mm
        pdf.cell(0, 10,
                 f"{dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*BLACK)

    # Modelo
    model = quote.config_snapshot.get("model_name", "")
    if model:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_xy(x_info, pdf.get_y() + 2)
        pdf.cell(0, 6, f"MODELO: {model}", new_x="LMARGIN", new_y="NEXT")

    if img_bytes:
        y = y + 56
    else:
        y = pdf.get_y() + 4

    # ── Datos de impresion ──
    y = pdf._section_title("Datos de Impresion", y)
    y += 2
    hrs = int(quote.total_hours)
    mins = int((quote.total_hours - hrs) * 60)
    diff_label, diff_desc, diff_pct = _diff_detail(quote.difficulty)

    label_val = [
        ("Tiempo", f"{hrs}h {mins}min"),
        ("Material", f"{quote.grams:.0f} g"),
        ("Dimensiones", f"{quote.dims_mm[0]:.1f} x {quote.dims_mm[1]:.1f} x {quote.dims_mm[2]:.1f} mm" if len(quote.dims_mm) == 3 else "-"),
    ]
    for lbl, val in label_val:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MID_GRAY)
        pdf.set_xy(14, y)
        pdf.cell(40, 5, lbl)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*BLACK)
        pdf.set_x(55)
        pdf.cell(0, 5, val, new_x="LMARGIN", new_y="NEXT")
        y += 6

    # Dificultad
    y += 2
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*MID_GRAY)
    pdf.set_xy(14, y)
    pdf.cell(40, 5, "Dificultad")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*RED)
    pdf.set_x(55)
    pdf.cell(0, 5, f"{diff_label}  (recargo {diff_pct})", new_x="LMARGIN", new_y="NEXT")
    y += 6
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MID_GRAY)
    pdf.set_x(55)
    pdf.cell(0, 4, diff_desc, new_x="LMARGIN", new_y="NEXT")
    if quote.extra_difficulty > 0:
        pdf.set_x(55)
        pdf.set_text_color(*RED)
        pdf.cell(0, 4, f"+{_fmt(quote.extra_difficulty)} al subtotal", new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y() + 4

    # ── Desglose de costos ──
    y = pdf._section_title("Desglose de Costos", y)
    y += 2

    cost_rows = [
        ("COSTO TIEMPO", _fmt(quote.cost_time), False),
        ("COSTO MATERIAL", _fmt(quote.cost_material), False),
        ("SUBTOTAL", _fmt(quote.subtotal), True),
    ]
    if quote.extra_difficulty > 0:
        cost_rows.append((f"EXTRA DIFICULTAD ({diff_pct})", _fmt(quote.extra_difficulty), False))
    if quote.profit > 0:
        cost_rows.append(("GANANCIA", _fmt(quote.profit), False))

    for lbl, val, is_bold in cost_rows:
        f = "B" if is_bold else ""
        pdf.set_font("Helvetica", f, 9 if not is_bold else 10)
        pdf.set_text_color(*BLACK)
        pdf.set_xy(14, y)
        pdf.cell(100, 6, lbl)
        pdf.set_font("Helvetica", "B", 9 if not is_bold else 10)
        pdf.set_x(120)
        pdf.cell(0, 6, val, new_x="LMARGIN", new_y="NEXT")
        if is_bold:
            pdf._thick_line(y + 7)
        y += 8

    # ── PRECIO FINAL — gran bloque rojo ──
    y += 6
    pdf.set_fill_color(*RED)
    pdf.rect(10, y, 190, 22, "F")
    # diagonal negra decorativa (simula estilo P5)
    pdf.set_fill_color(*BLACK)
    pdf.polygon([(10, y), (40, y), (10, y + 22)], "F")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(44, y + 2)
    pdf.cell(0, 7, "PRECIO FINAL")
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_xy(44, y + 9)
    pdf.cell(0, 10, _fmt(quote.final_price))

    y += 26

    # ── Footer config ──
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*LIGHT_GRAY)
    cfg = quote.config_snapshot
    pdf.set_xy(10, y)
    pdf.cell(0, 4,
             f"Maquina ${cfg.get('machine_cost', 0):,.0f} / {cfg.get('machine_life_hrs', 0):,.0f}hs  |  "
             f"{cfg.get('power_watts', 0)}W @ ${cfg.get('electricity_kwh', 0)}/kWh  |  "
             f"Filamento ${cfg.get('filament_per_kg', 0):,.0f}/kg  |  "
             f"Ganancia {cfg.get('profit_pct', 0)}%",
             new_x="LMARGIN", new_y="NEXT", align="C")

    # barra roja inferior
    pdf.set_fill_color(*RED)
    pdf.rect(0, 287, 210, 3, "F")

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  PNG — Estilo Persona 5 / Cyberpunk / Neobrutalista
# ═══════════════════════════════════════════════════════════════

def _halftone_overlay(img, color=RED, spacing=8, dot_max=3, opacity=40):
    """Superpone patron de halftone (dots) al estilo comic/punk."""
    from PIL import Image, ImageDraw
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    r, g, b = color
    for yy in range(0, img.size[1], spacing):
        for xx in range(0, img.size[0], spacing):
            # variar tamaño de punto segun posicion (efecto degradado)
            factor = (yy / img.size[1])
            radius = max(1, int(dot_max * (1 - factor * 0.6)))
            draw_ov.ellipse(
                [xx - radius, yy - radius, xx + radius, yy + radius],
                fill=(r, g, b, opacity),
            )
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))
    return img


def _draw_diagonal_stripes(draw, x0, y0, x1, y1, color=RED, width=3, spacing=12):
    """Rayas diagonales al estilo Persona 5."""
    for offset in range(0, (x1 - x0) + (y1 - y0), spacing):
        draw.line(
            [(x0 + offset, y0), (x0, y0 + offset)],
            fill=color, width=width,
        )


def generate_png(quote: QuoteResult) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    W, H = 640, 580
    img = Image.new("RGB", (W, H), DARK_BG)
    draw = ImageDraw.Draw(img)

    # Fuentes
    try:
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        fh = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        fr = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
        fbody = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        fsm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
        fbig = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        fprice = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
    except OSError:
        fb = fh = fr = fbody = fsm = fbig = fprice = ImageFont.load_default()

    # ── Barra roja superior ──
    draw.rectangle([(0, 0), (W, 6)], fill=RED)

    # ── Halftone sutil de fondo ──
    _halftone_overlay(img, color=RED, spacing=16, dot_max=2, opacity=18)
    draw = ImageDraw.Draw(img)  # refresco despues del overlay

    # ── Titulo ──
    y = 16
    draw.text((24, y), "PRESUPUESTO", fill=RED, font=fb)
    y += 28
    draw.text((24, y), f"STLFiles  //  {quote.timestamp[:10]}", fill=MID_GRAY, font=fsm)
    y += 16
    draw.line([(24, y), (W - 24, y)], fill=RED, width=3)
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
        img.paste(model_img, (24, y))
        #Marco rojo
        draw.rectangle([(22, y - 2), (24 + 182, y + 142)], outline=RED, width=3)
        # rayas diagonales decorativas en esquina
        _draw_diagonal_stripes(draw, 24, y, 60, y + 40, color=(*RED, ), width=2, spacing=8)
        x_info = 220
    else:
        x_info = 24

    # ── Dimensiones ──
    if quote.dims_mm and len(quote.dims_mm) == 3:
        d = quote.dims_mm
        draw.text((x_info, y + 2), "DIMENSIONES", fill=LIGHT_GRAY, font=fsm)
        draw.text((x_info, y + 14), f"{d[0]:.1f} x {d[1]:.1f} x {d[2]:.1f}", fill=WHITE, font=fbig)
        draw.text((x_info, y + 38), "mm", fill=MID_GRAY, font=fsm)
        y_dims = y + 56
    else:
        y_dims = y + 4

    # Modelo
    model_name = quote.config_snapshot.get("model_name", "")
    if model_name:
        draw.text((x_info, y_dims), f"MODELO: {model_name}", fill=LIGHT_GRAY, font=fbody)
        y_dims += 16

    if model_img:
        y = max(y + 148, y_dims + 4)
    else:
        y = y_dims + 4

    # ── Datos de impresion ──
    draw.rectangle([(20, y), (W - 20, y + 18)], fill=BLACK)
    draw.text((28, y + 3), "DATOS DE IMPRESION", fill=RED, font=fh)
    y += 24

    hrs = int(quote.total_hours)
    mins = int((quote.total_hours - hrs) * 60)
    diff_label, diff_desc, diff_pct = _diff_detail(quote.difficulty)

    for lbl, val in [("Tiempo", f"{hrs}h {mins}min"), ("Material", f"{quote.grams:.0f} g")]:
        draw.text((32, y), lbl, fill=MID_GRAY, font=fbody)
        draw.text((140, y), val, fill=WHITE, font=fr)
        y += 16

    # Dimensiones en datos
    if quote.dims_mm and len(quote.dims_mm) == 3:
        d = quote.dims_mm
        draw.text((32, y), "Dimensiones", fill=MID_GRAY, font=fbody)
        draw.text((140, y), f"{d[0]:.1f} x {d[1]:.1f} x {d[2]:.1f} mm", fill=WHITE, font=fr)
        y += 16

    # Dificultad
    draw.text((32, y), "Dificultad", fill=MID_GRAY, font=fbody)
    draw.text((140, y), f"{diff_label}  (recargo {diff_pct})", fill=RED, font=fr)
    y += 14
    draw.text((140, y), diff_desc, fill=MID_GRAY, font=fsm)
    y += 12
    if quote.extra_difficulty > 0:
        draw.text((140, y), f"+{_fmt(quote.extra_difficulty)} al subtotal", fill=GOLD, font=fsm)
        y += 14
    y += 4

    # ── Desglose ──
    draw.line([(24, y), (W - 24, y)], fill=RED, width=2)
    y += 6
    draw.text((28, y), "DESGLOSE DE COSTOS", fill=RED, font=fh)
    y += 20

    cost_rows = [
        ("COSTO TIEMPO", _fmt(quote.cost_time), False),
        ("COSTO MATERIAL", _fmt(quote.cost_material), False),
        ("SUBTOTAL", _fmt(quote.subtotal), True),
    ]
    if quote.extra_difficulty > 0:
        cost_rows.append((f"EXTRA DIFICULTAD ({diff_pct})", _fmt(quote.extra_difficulty), False))
    if quote.profit > 0:
        cost_rows.append(("GANANCIA", _fmt(quote.profit), False))

    for lbl, val, is_bold in cost_rows:
        f = fr if is_bold else fbody
        c = WHITE if is_bold else LIGHT_GRAY
        draw.text((32, y), lbl, fill=c, font=f)
        draw.text((380, y), val, fill=WHITE if is_bold else GOLD, font=f)
        y += 18
        if is_bold:
            draw.line([(32, y - 2), (W - 32, y - 2)], fill=RED, width=2)

    # ── PRECIO FINAL — gran bloque rojo con diagonal negra ──
    y += 10
    # Fondo rojo
    draw.rectangle([(20, y), (W - 20, y + 56)], fill=RED)
    # Triangulo negro decorativo (estilo P5)
    draw.polygon([(20, y), (70, y), (20, y + 56)], fill=BLACK)
    # Rayas diagonales en el triangulo
    _draw_diagonal_stripes(draw, 20, y, 70, y + 56, color=RED, width=1, spacing=6)

    draw.text((80, y + 8), "PRECIO FINAL", fill=WHITE, font=fh)
    draw.text((80, y + 28), _fmt(quote.final_price), fill=WHITE, font=fprice)

    # ── Barra roja inferior ──
    draw.rectangle([(0, H - 4), (W, H)], fill=RED)

    # ── Halftone sutil encima de todo (efecto comic) ──
    # ya aplicado al inicio

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
