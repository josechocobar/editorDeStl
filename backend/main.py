import io
import json
import logging
import re
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import connectors, mesh_ops, supports
from backend.quote import QuoteConfig, QuoteInput, calculate_quote

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("stlfiles")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODELS_DIR = DATA / "models"
JOBS_DIR = DATA / "jobs"
WEB_DIR = ROOT / "web"

app = FastAPI(title="STLFiles API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectorSpec(BaseModel):
    type: Literal["none", "pin", "prism"] = "none"
    diameter: float = Field(default=6.0, gt=0.5, le=40)
    depth: float = Field(default=8.0, gt=1, le=50)
    clearance: float = Field(default=0.25, ge=0, le=2)
    count: int = Field(default=2, ge=1, le=8)


from backend.operations.supports import SupportsParams


class SupportsSpec(SupportsParams):
    enabled: bool = False


from backend.operations.cut import CutParams


class CutRequest(CutParams):
    model_id: str
    connector: ConnectorSpec = ConnectorSpec()
    supports: Optional[SupportsSpec] = None


# --- Presupuesto ---


class QuoteConfigModel(BaseModel):
    machine_cost: float = Field(default=329_000, ge=0)
    machine_life_hrs: float = Field(default=8_760, gt=0)
    electricity_kwh: float = Field(default=50, ge=0)
    power_watts: float = Field(default=150, ge=0)
    maintenance_per_hr: float = Field(default=10, ge=0)
    labor_per_hr: float = Field(default=3_000, ge=0)
    filament_per_kg: float = Field(default=12_000, ge=0)
    profit_pct: float = Field(default=30, ge=0, le=500)


class QuoteInputModel(BaseModel):
    hours: float = Field(default=0, ge=0)
    minutes: float = Field(default=0, ge=0, lt=60)
    grams: float = Field(default=0, ge=0)
    difficulty: float = Field(default=1.0, ge=1.0, le=3.0)
    model_name: str = ""
    notes: str = ""
    dims_mm: list[float] = Field(default_factory=list)
    image_base64: str = ""


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,79}$")


def _model_paths(model_id: str):
    if not _ID_RE.fullmatch(model_id):
        raise HTTPException(400, "model_id inválido")
    stl = MODELS_DIR / f"{model_id}.stl"
    meta = MODELS_DIR / f"{model_id}.json"
    if not stl.exists() or not meta.exists():
        raise HTTPException(404, "Modelo no encontrado")
    return stl, meta


def _slug(name: str) -> str:
    base = Path(name).stem
    slug = re.sub(r"[^\w\-]+", "_", base, flags=re.UNICODE).strip("._ ")
    return slug[:80].lower() or "modelo"


def _preview_response(stl_path: Path, download_name: Optional[str] = None):
    preview = stl_path.with_suffix(".preview.stl")
    if not preview.exists() or preview.stat().st_mtime < stl_path.stat().st_mtime:
        decimated = mesh_ops.decimate_for_preview(mesh_ops.load_mesh(stl_path))
        decimated.export(preview)
        logger.info("preview %s: %d tris", preview.name, len(decimated.faces))
    return FileResponse(
        preview,
        media_type="model/stl",
        filename=download_name,
    )


@app.post("/api/models")
async def upload_model(file: UploadFile = File(...), replace: bool = Query(False)):
    if not file.filename or not file.filename.lower().endswith(".stl"):
        raise HTTPException(400, "Solo se aceptan archivos .stl")
    raw = await file.read()
    if len(raw) > 200 * 1024 * 1024:
        raise HTTPException(400, "Archivo demasiado grande (máx 200 MB)")

    model_id = _slug(file.filename)
    stl_path = MODELS_DIR / f"{model_id}.stl"
    meta_path = MODELS_DIR / f"{model_id}.json"
    preview_path = stl_path.with_suffix(".preview.stl")

    if stl_path.exists() and not replace:
        existing = {}
        if meta_path.exists():
            existing = json.loads(meta_path.read_text())
        return JSONResponse(
            status_code=409,
            content={
                "detail": f"Ya existe '{file.filename}'",
                "existing": existing,
            },
        )

    tmp = MODELS_DIR / f"tmp_{uuid.uuid4().hex}.stl"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(raw)
    try:
        mesh = mesh_ops.load_mesh(tmp)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        logger.warning("upload invalido %s: %s", file.filename, exc)
        raise HTTPException(400, f"STL inválido: {exc}") from exc
    finally:
        tmp.unlink(missing_ok=True)

    stl_path.write_bytes(raw)
    info = mesh_ops.model_info(mesh)
    meta = {"id": model_id, "name": file.filename, **info}
    meta_path.write_text(json.dumps(meta))
    preview_path.unlink(missing_ok=True)
    logger.info("modelo subido %s (%s)", file.filename, info["dims_mm"])
    return meta


@app.get("/api/models")
def list_models():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(MODELS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            items.append(json.loads(p.read_text()))
        except Exception:
            logger.warning("meta corrupta: %s", p.name)
    return items


@app.get("/api/models/{model_id}")
def get_model(model_id: str):
    _, meta_path = _model_paths(model_id)
    return json.loads(meta_path.read_text())


@app.delete("/api/models/{model_id}")
def delete_model(model_id: str):
    if not _ID_RE.fullmatch(model_id):
        raise HTTPException(400, "model_id inválido")
    stl = MODELS_DIR / f"{model_id}.stl"
    meta = MODELS_DIR / f"{model_id}.json"
    preview = stl.with_suffix(".preview.stl")
    if not stl.exists() and not meta.exists():
        raise HTTPException(404, "Modelo no encontrado")
    for p in (stl, meta, preview):
        p.unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/models/{model_id}/file")
def get_model_file(model_id: str):
    stl_path, _ = _model_paths(model_id)
    return FileResponse(stl_path, media_type="model/stl", filename=f"{model_id}.stl")


@app.get("/api/models/{model_id}/preview")
def get_model_preview(model_id: str):
    stl_path, _ = _model_paths(model_id)
    return _preview_response(stl_path)


@app.get("/api/models/{model_id}/suggest-connector")
def suggest_connector(
    model_id: str,
    axis: Literal["x", "y", "z"] = "z",
    position: float = Query(default=0.5, ge=0.02, le=0.98),
    mode: Literal["half", "multi"] = "half",
):
    stl_path, _ = _model_paths(model_id)
    mesh = mesh_ops.load_mesh(stl_path)
    if mode == "multi":
        lo, hi = mesh.bounds
        longest = int(np.argmax(hi - lo))
        origin = np.zeros(3)
        normal = np.zeros(3)
        origin[longest] = (lo[longest] + hi[longest]) / 2.0
        normal[longest] = 1.0
        hint = "estimado para la primera división (eje más largo)"
    else:
        try:
            origin, normal = mesh_ops.plane_for(axis, position, mesh.bounds)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        hint = f"cara de corte eje {axis} @ {int(position * 100)}%"
    try:
        sug = connectors.suggest(mesh, origin, normal)
    except connectors.ConnectorError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**sug, "basis": hint}


def _export_job(pieces, names, base, operation, *, request_dump=None,
                splits=None, supports_meta=None, warnings=None):
    """Exporta las piezas como job y arma el meta común a las operaciones."""
    job_id = uuid.uuid4().hex[:12]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    out_pieces = []
    for i, piece in enumerate(pieces):
        piece_path = job_dir / f"{i}.stl"
        piece.export(piece_path)
        lo, hi = piece.bounds
        out_pieces.append({
            "index": i,
            "name": names[i],
            "file_url": f"/api/jobs/{job_id}/pieces/{i}",
            "dims_mm": [round(float(e), 2) for e in (hi - lo)],
            "volume_cm3": round(abs(piece.volume) / 1000.0, 2),
            "watertight": bool(piece.is_watertight),
        })

    job_meta = {
        "job_id": job_id,
        "operation": operation,
        "model_name": base,
        "request": request_dump or {},
        "pieces": out_pieces,
        "splits": splits if splits is not None else [],
        "supports": supports_meta or [],
        "warnings": warnings or [],
    }
    (job_dir / "meta.json").write_text(json.dumps(job_meta))
    return job_meta


@app.post("/api/models/{model_id}/supports")
def add_model_supports(model_id: str, spec: SupportsParams):
    """Aplica soportes árbol al modelo completo (sin cortar) y devuelve un
    job de una sola pieza lista para descargar."""
    stl_path, meta_path = _model_paths(model_id)
    meta = json.loads(meta_path.read_text())
    try:
        mesh = mesh_ops.load_mesh(stl_path)
        from backend.operations.supports import run as run_supports
        result = run_supports(mesh, spec, _slug(meta.get("name") or "modelo"))
    except supports.SupportError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("fallo la generación de soportes de %s", model_id)
        raise HTTPException(500, f"Error procesando la malla: {exc}") from exc
    job_meta = _export_job(
        result.pieces, result.names, _slug(meta.get("name") or "modelo"),
        result.operation,
        request_dump={"model_id": model_id, **spec.model_dump()},
        supports_meta=result.supports_meta,
    )
    logger.info("job %s listo: modelo con soportes", job_meta["job_id"])
    return job_meta


@app.post("/api/cut")
def cut_model(req: CutRequest):
    stl_path, meta_path = _model_paths(req.model_id)
    meta = json.loads(meta_path.read_text())
    try:
        mesh = mesh_ops.load_mesh(stl_path)
        from backend.operations.cut import run as run_cut
        result = run_cut(
            mesh,
            req,
            connector_spec=req.connector,
            supports_spec=req.supports,
            model_name=_slug(meta.get("name") or "modelo"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("fallo el corte de %s", req.model_id)
        raise HTTPException(500, f"Error procesando la malla: {exc}") from exc
    base = _slug(meta.get("name") or "modelo")
    job_meta = _export_job(
        result.pieces, result.names, base, result.operation,
        request_dump=req.model_dump(),
        splits=result.splits,
        supports_meta=result.supports_meta,
        warnings=result.warnings,
    )
    logger.info("job %s listo: %d piezas, %d avisos",
                job_meta["job_id"], len(result.pieces), len(result.warnings))
    return job_meta


@app.get("/api/jobs/{job_id}/pieces/{index}")
def get_piece(job_id: str, index: int):
    job_dir = JOBS_DIR / _safe(job_id)
    meta_path = job_dir / "meta.json"
    path = job_dir / f"{index}.stl"
    if not path.exists():
        raise HTTPException(404, "Pieza no encontrada")
    name = None
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        for p in meta["pieces"]:
            if p["index"] == index:
                name = p["name"]
                break
    return FileResponse(path, media_type="model/stl", filename=name or f"pieza_{index}.stl")


@app.get("/api/jobs/{job_id}/pieces/{index}/preview")
def get_piece_preview(job_id: str, index: int):
    job_dir = JOBS_DIR / _safe(job_id)
    path = job_dir / f"{index}.stl"
    if not path.exists():
        raise HTTPException(404, "Pieza no encontrada")
    return _preview_response(path)


@app.get("/api/jobs/{job_id}/zip")
def get_job_zip(job_id: str):
    job_dir = JOBS_DIR / _safe(job_id)
    meta_path = job_dir / "meta.json"
    if not meta_path.exists():
        raise HTTPException(404, "Job no encontrado")
    meta = json.loads(meta_path.read_text())
    operation = meta.get("operation", "corte")
    info_name = "corte_info.json" if operation == "corte" else f"{operation}_info.json"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in meta["pieces"]:
            zf.write(job_dir / f"{p['index']}.stl", p["name"])
        zf.writestr(info_name, json.dumps(meta, indent=2, ensure_ascii=False))
    buf.seek(0)
    safe_name = (meta.get("model_name") or "modelo").rsplit(".", 1)[0]
    suffix = "piezas" if operation == "corte" else operation
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_{suffix}.zip"'},
    )


# --- Presupuesto ---


class QuoteRequest(BaseModel):
    config: QuoteConfigModel = QuoteConfigModel()
    input: QuoteInputModel = QuoteInputModel()


@app.post("/api/quote")
def api_quote(req: QuoteRequest):
    config = QuoteConfig(**req.config.model_dump())
    data = QuoteInput(**req.input.model_dump())
    result = calculate_quote(config, data)
    return result.to_dict()


@app.post("/api/quote/pdf")
def api_quote_pdf(req: QuoteRequest):
    from backend.pdf_quote import generate_pdf
    config = QuoteConfig(**req.config.model_dump())
    data = QuoteInput(**req.input.model_dump())
    result = calculate_quote(config, data)
    pdf_bytes = generate_pdf(result)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="presupuesto.pdf"'},
    )


@app.post("/api/quote/png")
def api_quote_png(req: QuoteRequest):
    from backend.pdf_quote import generate_png
    config = QuoteConfig(**req.config.model_dump())
    data = QuoteInput(**req.input.model_dump())
    result = calculate_quote(config, data)
    png_bytes = generate_png(result)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="presupuesto.png"'},
    )


def _safe(job_id: str) -> str:
    if not job_id.isalnum() or len(job_id) > 40:
        raise HTTPException(400, "job_id inválido")
    return job_id


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
