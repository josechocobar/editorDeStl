import io
import json
import logging
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import connectors, mesh_ops

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


class CutRequest(BaseModel):
    model_id: str
    mode: Literal["half", "multi"] = "half"
    axis: Literal["x", "y", "z"] = "z"
    position: float = Field(default=0.5, ge=0.02, le=0.98)
    parts: int = Field(default=4, ge=2, le=16)
    connector: ConnectorSpec = ConnectorSpec()


def _model_paths(model_id: str):
    if not model_id.isalnum() or len(model_id) > 40:
        raise HTTPException(400, "model_id inválido")
    stl = MODELS_DIR / f"{model_id}.stl"
    meta = MODELS_DIR / f"{model_id}.json"
    if not stl.exists() or not meta.exists():
        raise HTTPException(404, "Modelo no encontrado")
    return stl, meta


@app.post("/api/models")
async def upload_model(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".stl"):
        raise HTTPException(400, "Solo se aceptan archivos .stl")
    raw = await file.read()
    if len(raw) > 200 * 1024 * 1024:
        raise HTTPException(400, "Archivo demasiado grande (máx 200 MB)")
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

    model_id = uuid.uuid4().hex[:12]
    stl_path = MODELS_DIR / f"{model_id}.stl"
    stl_path.write_bytes(raw)
    info = mesh_ops.model_info(mesh)
    meta = {"id": model_id, "name": file.filename, **info}
    (MODELS_DIR / f"{model_id}.json").write_text(json.dumps(meta))
    logger.info("modelo subido %s (%s)", file.filename, info["dims_mm"])
    return meta


@app.get("/api/models/{model_id}")
def get_model(model_id: str):
    _, meta_path = _model_paths(model_id)
    return json.loads(meta_path.read_text())


@app.get("/api/models/{model_id}/file")
def get_model_file(model_id: str):
    stl_path, _ = _model_paths(model_id)
    return FileResponse(stl_path, media_type="model/stl", filename=f"{model_id}.stl")


@app.post("/api/cut")
def cut_model(req: CutRequest):
    stl_path, meta_path = _model_paths(req.model_id)
    meta = json.loads(meta_path.read_text())
    try:
        mesh = mesh_ops.load_mesh(stl_path)
        if req.mode == "half":
            pieces, splits = mesh_ops.cut_half(mesh, req.axis, req.position)
            logger.info("corte mitad eje=%s pos=%.2f", req.axis, req.position)
        else:
            pieces, splits = mesh_ops.split_multi(mesh, req.parts)
            logger.info("corte multiple partes=%d", req.parts)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("fallo el corte de %s", req.model_id)
        raise HTTPException(500, f"Error procesando la malla: {exc}") from exc

    warnings = []
    conn_meta = None
    spec = req.connector
    if spec.type != "none":
        for split in splits:
            a_idx, b_idx = split["a_index"], split["b_index"]
            origin = np.array(split["origin"])
            normal = np.array(split["normal"])
            try:
                sites = connectors.compute_sites(
                    pieces[a_idx], origin, normal, spec.count, spec.diameter
                )
                pieces[a_idx], pieces[b_idx], conn_meta = connectors.apply_connector(
                    pieces[a_idx], pieces[b_idx], origin, normal,
                    sites, spec.type, spec.diameter, spec.depth, spec.clearance,
                )
                split["connector"] = {
                    "type": spec.type,
                    "sites_mm": [[round(float(c), 2) for c in s] for s in sites],
                    **conn_meta,
                }
            except connectors.ConnectorError as exc:
                warnings.append(f"Conectores omitidos en corte {a_idx + 1}-{b_idx + 1}: {exc}")
                logger.warning("conector falló: %s", exc)

    job_id = uuid.uuid4().hex[:12]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    out_pieces = []
    for i, piece in enumerate(pieces):
        name = f"pieza_{i + 1}_de_{len(pieces)}.stl"
        piece_path = job_dir / f"{i}.stl"
        piece.export(piece_path)
        lo, hi = piece.bounds
        out_pieces.append({
            "index": i,
            "name": name,
            "file_url": f"/api/jobs/{job_id}/pieces/{i}",
            "dims_mm": [round(float(e), 2) for e in (hi - lo)],
            "volume_cm3": round(abs(piece.volume) / 1000.0, 2),
            "watertight": bool(piece.is_watertight),
        })

    job_meta = {
        "job_id": job_id,
        "model_name": meta.get("name"),
        "request": req.model_dump(),
        "pieces": out_pieces,
        "splits": splits,
        "warnings": warnings,
    }
    (job_dir / "meta.json").write_text(json.dumps(job_meta))
    logger.info("job %s listo: %d piezas, %d avisos", job_id, len(pieces), len(warnings))
    return job_meta


@app.get("/api/jobs/{job_id}/pieces/{index}")
def get_piece(job_id: str, index: int):
    job_dir = JOBS_DIR / _safe(job_id)
    path = job_dir / f"{index}.stl"
    if not path.exists():
        raise HTTPException(404, "Pieza no encontrada")
    return FileResponse(path, media_type="model/stl")


@app.get("/api/jobs/{job_id}/zip")
def get_job_zip(job_id: str):
    job_dir = JOBS_DIR / _safe(job_id)
    meta_path = job_dir / "meta.json"
    if not meta_path.exists():
        raise HTTPException(404, "Job no encontrado")
    meta = json.loads(meta_path.read_text())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in meta["pieces"]:
            zf.write(job_dir / f"{p['index']}.stl", p["name"])
        zf.writestr("corte_info.json", json.dumps(meta, indent=2, ensure_ascii=False))
    buf.seek(0)
    safe_name = (meta.get("model_name") or "modelo").rsplit(".", 1)[0]
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_piezas.zip"'},
    )


def _safe(job_id: str) -> str:
    if not job_id.isalnum() or len(job_id) > 40:
        raise HTTPException(400, "job_id inválido")
    return job_id


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
