"""Calculadora de costos para impresión 3D.

Fórmula basada en la calculadora de referencia (calculatorexample/).
Todo el módulo es puro: sin HTTP, sin filesystem, sin side effects.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class QuoteConfig:
    """Costos y variables configurables por el usuario."""
    machine_cost: float = 329_000       # costo de compra de la impresora
    machine_life_hrs: float = 8_760     # vida útil en horas
    electricity_kwh: float = 50         # costo del kWh
    power_watts: float = 150            # potencia de la impresora
    maintenance_per_hr: float = 10      # costo mantenimiento por hora
    labor_per_hr: float = 3_000         # costo mano de obra por hora
    filament_per_kg: float = 12_000     # costo del filamento por kg
    profit_pct: float = 30              # ganancia deseada (%)

    def machine_per_hr(self) -> float:
        if self.machine_life_hrs <= 0:
            return 0.0
        return self.machine_cost / self.machine_life_hrs

    def energy_per_hr(self) -> float:
        return (self.power_watts / 1000) * self.electricity_kwh


@dataclass
class QuoteInput:
    """Datos de la impresión a cotizar."""
    hours: float = 0
    minutes: float = 0
    grams: float = 0
    difficulty: float = 1.0             # 1.0 simple, 1.5 media, 2.0 compleja
    model_name: str = ""
    notes: str = ""
    dims_mm: list[float] = field(default_factory=list)  # [x, y, z] en mm
    image_base64: str = ""             # captura del modelo (data URL o base64 puro)

    @property
    def total_hours(self) -> float:
        return self.hours + self.minutes / 60


@dataclass
class QuoteResult:
    """Resultado del cálculo de presupuesto."""
    # costos parciales
    machine_per_hr: float = 0
    energy_per_hr: float = 0
    cost_time: float = 0
    cost_material: float = 0
    subtotal: float = 0
    extra_difficulty: float = 0
    subtotal_with_difficulty: float = 0
    profit: float = 0
    final_price: float = 0
    # metadata
    total_hours: float = 0
    grams: float = 0
    difficulty: float = 1.0
    dims_mm: list[float] = field(default_factory=list)
    image_base64: str = ""
    timestamp: str = ""
    config_snapshot: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


PLA_DENSITY_G_CM3 = 1.24


def estimate_weight_grams(volume_cm3: float, density: float = PLA_DENSITY_G_CM3) -> float:
    """Estima peso en gramos a partir del volumen en cm³."""
    return volume_cm3 * density


def calculate_quote(config: QuoteConfig, inp: QuoteInput) -> QuoteResult:
    """Calcula el presupuesto completo. Función pura."""
    machine_hr = config.machine_per_hr()
    energy_hr = config.energy_per_hr()
    ops_hr = config.maintenance_per_hr + config.labor_per_hr

    cost_time = inp.total_hours * (machine_hr + energy_hr + ops_hr)
    cost_material = (inp.grams / 1000) * config.filament_per_kg
    subtotal = cost_time + cost_material

    extra_diff = subtotal * (inp.difficulty - 1)
    sub_with_diff = subtotal + extra_diff
    profit = sub_with_diff * (config.profit_pct / 100)
    final = sub_with_diff + profit

    return QuoteResult(
        machine_per_hr=machine_hr,
        energy_per_hr=energy_hr,
        cost_time=cost_time,
        cost_material=cost_material,
        subtotal=subtotal,
        extra_difficulty=extra_diff,
        subtotal_with_difficulty=sub_with_diff,
        profit=profit,
        final_price=final,
        total_hours=inp.total_hours,
        grams=inp.grams,
        difficulty=inp.difficulty,
        dims_mm=inp.dims_mm,
        image_base64=inp.image_base64,
        timestamp=datetime.now(timezone.utc).isoformat(),
        config_snapshot={
            "machine_cost": config.machine_cost,
            "machine_life_hrs": config.machine_life_hrs,
            "electricity_kwh": config.electricity_kwh,
            "power_watts": config.power_watts,
            "maintenance_per_hr": config.maintenance_per_hr,
            "labor_per_hr": config.labor_per_hr,
            "filament_per_kg": config.filament_per_kg,
            "profit_pct": config.profit_pct,
        },
    )
