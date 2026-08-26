"""Tests del módulo de presupuesto (quote)."""
import pytest
from backend.quote import QuoteConfig, QuoteInput, QuoteResult, calculate_quote, estimate_weight_grams


def test_defaults():
    cfg = QuoteConfig()
    assert cfg.machine_cost == 329_000
    assert cfg.machine_life_hrs == 8_760
    assert cfg.filament_per_kg == 12_000


def test_machine_per_hr():
    cfg = QuoteConfig(machine_cost=100_000, machine_life_hrs=5_000)
    assert cfg.machine_per_hr() == 20.0


def test_machine_per_hr_zero_life():
    cfg = QuoteConfig(machine_cost=100_000, machine_life_hrs=0)
    assert cfg.machine_per_hr() == 0.0


def test_energy_per_hr():
    cfg = QuoteConfig(power_watts=150, electricity_kwh=50)
    assert cfg.energy_per_hr() == 7.5


def test_calculate_quote_basic():
    cfg = QuoteConfig(
        machine_cost=329_000, machine_life_hrs=8_760,
        electricity_kwh=50, power_watts=150,
        maintenance_per_hr=10, labor_per_hr=3_000,
        filament_per_kg=12_000, profit_pct=30,
    )
    inp = QuoteInput(hours=2, minutes=30, grams=150, difficulty=1.5)
    result = calculate_quote(cfg, inp)

    assert isinstance(result, QuoteResult)
    assert result.total_hours == 2.5
    assert result.grams == 150
    assert result.difficulty == 1.5
    assert result.final_price > 0
    assert result.cost_time > 0
    assert result.cost_material > 0
    assert result.subtotal == result.cost_time + result.cost_material
    assert result.extra_difficulty > 0
    assert result.profit > 0
    assert result.final_price == result.subtotal_with_difficulty + result.profit


def test_calculate_quote_zero():
    cfg = QuoteConfig()
    inp = QuoteInput(hours=0, minutes=0, grams=0, difficulty=1.0)
    result = calculate_quote(cfg, inp)
    assert result.final_price == 0


def test_calculate_quote_no_difficulty():
    cfg = QuoteConfig(profit_pct=0)
    inp = QuoteInput(hours=1, grams=100, difficulty=1.0)
    result = calculate_quote(cfg, inp)
    assert result.extra_difficulty == 0
    assert result.profit == 0
    assert result.final_price == result.subtotal


def test_estimate_weight():
    w = estimate_weight_grams(100, 1.24)
    assert abs(w - 124) < 0.01


def test_result_to_dict():
    cfg = QuoteConfig()
    inp = QuoteInput(hours=1, grams=100)
    result = calculate_quote(cfg, inp)
    d = result.to_dict()
    assert "final_price" in d
    assert "config_snapshot" in d
    assert "timestamp" in d


def test_config_snapshot_in_result():
    cfg = QuoteConfig(machine_cost=500_000, profit_pct=50)
    inp = QuoteInput(hours=1, grams=100)
    result = calculate_quote(cfg, inp)
    assert result.config_snapshot["machine_cost"] == 500_000
    assert result.config_snapshot["profit_pct"] == 50
