"""Operación de soportes: aplica soportes árbol a una malla completa."""
from pydantic import BaseModel, Field

from backend import supports
from backend.operations import OperationResult


class SupportsParams(BaseModel):
    angle: float = Field(default=50.0, ge=20, le=80)
    tip_diameter: float = Field(default=0.8, gt=0.2, le=4)
    contact_diameter: float = Field(default=0.5, ge=0.2, le=3)
    spacing: float = Field(default=1.8, gt=0.5, le=8)
    z_gap: float = Field(default=0.2, ge=0, le=2)
    base_thickness: float = Field(default=1.2, ge=0.4, le=6)


def run(mesh, params, model_name: str = "modelo") -> OperationResult:
    """Aplica soportes y devuelve OperationResult con una sola pieza."""
    spec = params.model_dump() if hasattr(params, "model_dump") else params
    supported, sup_info = supports.add_supports(mesh, spec)
    name = f"{model_name}_con_soportes.stl"
    return OperationResult(
        pieces=[supported],
        names=[name],
        operation="soportes",
        supports_meta=[{"index": 0, **sup_info}],
    )
