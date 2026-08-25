"""Operación de corte: divide una malla en piezas, aplica conectores y soportes."""
from typing import Literal, Optional

import numpy as np
from pydantic import BaseModel, Field

from backend import connectors, mesh_ops, supports
from backend.operations import OperationResult


class CutParams(BaseModel):
    mode: Literal["half", "multi"] = "half"
    axis: Literal["x", "y", "z"] = "z"
    position: float = Field(default=0.5, ge=0.02, le=0.98)
    parts: int = Field(default=4, ge=2, le=16)


def run(
    mesh,
    params: CutParams,
    connector_spec=None,
    supports_spec=None,
    model_name: str = "modelo",
) -> OperationResult:
    """Ejecuta corte + conectores + soportes. Devuelve OperationResult."""
    pieces, splits = _cut(mesh, params)
    warnings = _check_shortfall(params, pieces)
    warnings += _apply_connectors(pieces, splits, connector_spec)
    supports_meta, sup_warns = _apply_supports(pieces, supports_spec)
    warnings += sup_warns
    names = _generate_names(model_name, pieces)

    return OperationResult(
        pieces=pieces,
        names=names,
        operation="corte",
        splits=splits,
        supports_meta=supports_meta,
        warnings=warnings,
    )


def _cut(mesh, params: CutParams):
    if params.mode == "half":
        return mesh_ops.cut_half(mesh, params.axis, params.position)
    return mesh_ops.split_multi(mesh, params.parts)


def _check_shortfall(params: CutParams, pieces: list) -> list:
    if params.mode == "multi" and len(pieces) < params.parts:
        return [
            f"Se generaron {len(pieces)} de {params.parts} partes: el modelo no "
            f"admite más cortes en esa dirección"
        ]
    return []


def _apply_connectors(pieces, splits, spec) -> list:
    if not spec or spec.type == "none":
        return []
    warnings = []
    for split in splits:
        a_idx, b_idx = split["a_index"], split["b_index"]
        origin = np.array(split["origin"])
        normal = np.array(split["normal"])
        try:
            sites = connectors.compute_sites(
                pieces[a_idx], pieces[b_idx], origin, normal,
                spec.count, spec.diameter, spec.depth,
            )
            pieces[a_idx], pieces[b_idx], conn_meta = connectors.apply_connector(
                pieces[a_idx], pieces[b_idx], origin, normal,
                sites, spec.type, spec.diameter, spec.depth, spec.clearance,
            )
            if len(sites) < spec.count:
                warnings.append(
                    f"Corte {a_idx + 1}-{b_idx + 1}: se ubicaron {len(sites)} de "
                    f"{spec.count} conectores (material compartido insuficiente en la cara)"
                )
            split["connector"] = {
                "type": spec.type,
                "sites_mm": [[round(float(c), 2) for c in s] for s in sites],
                **conn_meta,
            }
        except connectors.ConnectorError as exc:
            warnings.append(f"Conectores omitidos en corte {a_idx + 1}-{b_idx + 1}: {exc}")
    return warnings


def _apply_supports(pieces, spec) -> tuple:
    if not spec or not spec.enabled:
        return [], []
    supports_meta = []
    warnings = []
    s = spec.model_dump() if hasattr(spec, "model_dump") else spec
    for i, piece in enumerate(pieces):
        try:
            pieces[i], sup_info = supports.add_supports(piece, s)
            supports_meta.append({"index": i, **sup_info})
        except supports.SupportError as exc:
            warnings.append(f"Soportes omitidos en pieza {i + 1}: {exc}")
    return supports_meta, warnings


def _generate_names(model_name: str, pieces: list) -> list:
    return [
        f"{model_name}_pieza_{i + 1}_de_{len(pieces)}.stl"
        for i in range(len(pieces))
    ]
