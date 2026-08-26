"""Tests exhaustivos del módulo de presupuesto (quote).

Descompuestos en capas:
  1. Funciones puras individuales (cost_time, cost_material, etc.)
  2. QuoteConfig métodos
  3. QuoteInput/QuoteResult
  4. calculate_quote integración
  5. Multi-modelo
  6. Edge cases
"""
import pytest
from backend.quote import (
    QuoteConfig, QuoteInput, QuoteResult,
    calculate_quote, estimate_weight_grams,
    cost_per_hour, cost_time, cost_material,
    subtotal, difficulty_extra, profit_amount, final_price,
    PLA_DENSITY_G_CM3,
)


# ═══════════════════════════════════════════════════════════════
#  QuoteConfig
# ═══════════════════════════════════════════════════════════════

class TestQuoteConfigDefaults:
    def test_machine_cost(self):
        assert QuoteConfig().machine_cost == 329_000

    def test_machine_life_hrs(self):
        assert QuoteConfig().machine_life_hrs == 8_760

    def test_electricity_kwh(self):
        assert QuoteConfig().electricity_kwh == 50

    def test_power_watts(self):
        assert QuoteConfig().power_watts == 150

    def test_maintenance_per_hr(self):
        assert QuoteConfig().maintenance_per_hr == 10

    def test_labor_per_hr(self):
        assert QuoteConfig().labor_per_hr == 3_000

    def test_filament_per_kg(self):
        assert QuoteConfig().filament_per_kg == 12_000

    def test_profit_pct(self):
        assert QuoteConfig().profit_pct == 30


class TestMachinePerHr:
    def test_normal(self):
        cfg = QuoteConfig(machine_cost=100_000, machine_life_hrs=5_000)
        assert cfg.machine_per_hr() == 20.0

    def test_zero_life_returns_zero(self):
        cfg = QuoteConfig(machine_cost=100_000, machine_life_hrs=0)
        assert cfg.machine_per_hr() == 0.0

    def test_negative_life_returns_zero(self):
        cfg = QuoteConfig(machine_cost=100_000, machine_life_hrs=-100)
        assert cfg.machine_per_hr() == 0.0

    def test_zero_cost(self):
        cfg = QuoteConfig(machine_cost=0, machine_life_hrs=8_760)
        assert cfg.machine_per_hr() == 0.0

    def test_defaults(self):
        cfg = QuoteConfig()
        expected = 329_000 / 8_760
        assert abs(cfg.machine_per_hr() - expected) < 0.01


class TestEnergyPerHr:
    def test_defaults(self):
        cfg = QuoteConfig(power_watts=150, electricity_kwh=50)
        assert cfg.energy_per_hr() == 7.5

    def test_zero_watts(self):
        cfg = QuoteConfig(power_watts=0, electricity_kwh=50)
        assert cfg.energy_per_hr() == 0.0

    def test_zero_kwh(self):
        cfg = QuoteConfig(power_watts=150, electricity_kwh=0)
        assert cfg.energy_per_hr() == 0.0

    def test_high_power(self):
        cfg = QuoteConfig(power_watts=1000, electricity_kwh=100)
        assert cfg.energy_per_hr() == 100.0


# ═══════════════════════════════════════════════════════════════
#  Funciones puras individuales
# ═══════════════════════════════════════════════════════════════

class TestCostPerHour:
    def test_defaults(self):
        cfg = QuoteConfig()
        # machine_per_hr + energy_per_hr + maintenance + labor
        expected = (329_000 / 8_760) + 7.5 + 10 + 3_000
        assert abs(cost_per_hour(cfg) - expected) < 0.01

    def test_zero_everything(self):
        cfg = QuoteConfig(
            machine_cost=0, machine_life_hrs=1,
            power_watts=0, electricity_kwh=0,
            maintenance_per_hr=0, labor_per_hr=0,
        )
        assert cost_per_hour(cfg) == 0.0

    def test_only_labor(self):
        cfg = QuoteConfig(
            machine_cost=0, machine_life_hrs=1,
            power_watts=0, electricity_kwh=0,
            maintenance_per_hr=0, labor_per_hr=5_000,
        )
        assert cost_per_hour(cfg) == 5_000.0


class TestCostTime:
    def test_basic(self):
        cfg = QuoteConfig()
        cph = cost_per_hour(cfg)
        assert abs(cost_time(2.5, cfg) - 2.5 * cph) < 0.01

    def test_zero_hours(self):
        cfg = QuoteConfig()
        assert cost_time(0, cfg) == 0.0

    def test_fractional_hours(self):
        cfg = QuoteConfig(labor_per_hr=1_000, machine_cost=0,
                          machine_life_hrs=1, power_watts=0,
                          electricity_kwh=0, maintenance_per_hr=0)
        # only labor = 1000/hr, 0.5 hr = 500
        assert cost_time(0.5, cfg) == 500.0


class TestCostMaterial:
    def test_defaults(self):
        cfg = QuoteConfig()
        # 200g / 1000 * 12_000 = 2_400
        assert cost_material(200, cfg) == 2_400.0

    def test_zero_grams(self):
        cfg = QuoteConfig()
        assert cost_material(0, cfg) == 0.0

    def test_one_kg(self):
        cfg = QuoteConfig(filament_per_kg=15_000)
        assert cost_material(1000, cfg) == 15_000.0

    def test_fractional_grams(self):
        cfg = QuoteConfig(filament_per_kg=12_000)
        # 50.5g / 1000 * 12000 = 606.0
        assert abs(cost_material(50.5, cfg) - 606.0) < 0.01


class TestSubtotal:
    def test_basic(self):
        assert subtotal(1000, 500) == 1500

    def test_zeros(self):
        assert subtotal(0, 0) == 0

    def test_one_zero(self):
        assert subtotal(1000, 0) == 1000
        assert subtotal(0, 500) == 500


class TestDifficultyExtra:
    def test_no_difficulty(self):
        assert difficulty_extra(1000, 1.0) == 0.0

    def test_medium(self):
        assert difficulty_extra(1000, 1.5) == 500.0

    def test_hard(self):
        assert difficulty_extra(1000, 2.0) == 1000.0

    def test_custom(self):
        assert difficulty_extra(2000, 1.25) == 500.0

    def test_zero_subtotal(self):
        assert difficulty_extra(0, 2.0) == 0.0


class TestProfitAmount:
    def test_basic(self):
        assert profit_amount(1000, 30) == 300.0

    def test_zero_pct(self):
        assert profit_amount(1000, 0) == 0.0

    def test_100_pct(self):
        assert profit_amount(1000, 100) == 1000.0

    def test_zero_subtotal(self):
        assert profit_amount(0, 30) == 0.0


class TestFinalPrice:
    def test_basic(self):
        assert final_price(1000, 300) == 1300

    def test_zeros(self):
        assert final_price(0, 0) == 0

    def test_negative_profit(self):
        assert final_price(1000, -100) == 900


# ═══════════════════════════════════════════════════════════════
#  QuoteInput
# ═══════════════════════════════════════════════════════════════

class TestQuoteInput:
    def test_total_hours_hours_only(self):
        inp = QuoteInput(hours=3, minutes=0)
        assert inp.total_hours == 3.0

    def test_total_hours_minutes_only(self):
        inp = QuoteInput(hours=0, minutes=90)
        assert inp.total_hours == 1.5

    def test_total_hours_mixed(self):
        inp = QuoteInput(hours=2, minutes=30)
        assert inp.total_hours == 2.5

    def test_total_hours_zero(self):
        inp = QuoteInput()
        assert inp.total_hours == 0.0

    def test_defaults(self):
        inp = QuoteInput()
        assert inp.hours == 0
        assert inp.minutes == 0
        assert inp.grams == 0
        assert inp.difficulty == 1.0
        assert inp.model_name == ""
        assert inp.notes == ""
        assert inp.dims_mm == []
        assert inp.image_base64 == ""
        assert inp.models == []

    def test_custom_values(self):
        inp = QuoteInput(hours=5, grams=300, difficulty=2.0, model_name="test")
        assert inp.total_hours == 5
        assert inp.grams == 300
        assert inp.difficulty == 2.0
        assert inp.model_name == "test"


# ═══════════════════════════════════════════════════════════════
#  QuoteResult
# ═══════════════════════════════════════════════════════════════

class TestQuoteResult:
    def test_to_dict_has_all_keys(self):
        result = QuoteResult(final_price=1234.56)
        d = result.to_dict()
        expected_keys = {
            "machine_per_hr", "energy_per_hr", "cost_time", "cost_material",
            "subtotal", "extra_difficulty", "subtotal_with_difficulty",
            "profit", "final_price", "total_hours", "grams", "difficulty",
            "dims_mm", "image_base64", "models", "timestamp", "config_snapshot",
        }
        assert expected_keys == set(d.keys())

    def test_to_dict_preserves_values(self):
        result = QuoteResult(final_price=999, cost_time=100, profit=50)
        d = result.to_dict()
        assert d["final_price"] == 999
        assert d["cost_time"] == 100
        assert d["profit"] == 50

    def test_to_dict_models_preserved(self):
        models = [{"name": "a", "volume_cm3": 10}]
        result = QuoteResult(models=models)
        assert result.to_dict()["models"] == models


# ═══════════════════════════════════════════════════════════════
#  calculate_quote integración
# ═══════════════════════════════════════════════════════════════

class TestCalculateQuoteIntegration:
    def test_basic(self):
        cfg = QuoteConfig()
        inp = QuoteInput(hours=2, minutes=30, grams=150, difficulty=1.5)
        r = calculate_quote(cfg, inp)

        assert isinstance(r, QuoteResult)
        assert r.total_hours == 2.5
        assert r.grams == 150
        assert r.difficulty == 1.5
        assert r.final_price > 0
        assert r.cost_time > 0
        assert r.cost_material > 0
        assert r.subtotal == r.cost_time + r.cost_material
        assert r.extra_difficulty > 0
        assert r.profit > 0
        assert r.final_price == r.subtotal_with_difficulty + r.profit

    def test_zero_everything(self):
        cfg = QuoteConfig()
        inp = QuoteInput()
        r = calculate_quote(cfg, inp)
        assert r.final_price == 0
        assert r.cost_time == 0
        assert r.cost_material == 0
        assert r.extra_difficulty == 0
        assert r.profit == 0

    def test_no_difficulty_no_profit(self):
        cfg = QuoteConfig(profit_pct=0)
        inp = QuoteInput(hours=1, grams=100, difficulty=1.0)
        r = calculate_quote(cfg, inp)
        assert r.extra_difficulty == 0
        assert r.profit == 0
        assert r.final_price == r.subtotal

    def test_only_time(self):
        cfg = QuoteConfig(filament_per_kg=0)
        inp = QuoteInput(hours=1, grams=0, difficulty=1.0)
        r = calculate_quote(cfg, inp)
        assert r.cost_material == 0
        assert r.final_price > 0

    def test_only_material(self):
        cfg = QuoteConfig()
        inp = QuoteInput(hours=0, minutes=0, grams=100, difficulty=1.0)
        r = calculate_quote(cfg, inp)
        assert r.cost_time == 0
        assert r.cost_material > 0

    def test_high_difficulty_doubles(self):
        cfg = QuoteConfig(profit_pct=0)
        inp = QuoteInput(hours=1, grams=0, difficulty=2.0)
        r = calculate_quote(cfg, inp)
        # difficulty=2.0 → extra = subtotal * 1.0 → subtotal_with_diff = 2 * subtotal
        assert r.extra_difficulty == r.subtotal
        assert r.subtotal_with_difficulty == 2 * r.subtotal

    def test_profit_compounds_with_difficulty(self):
        cfg = QuoteConfig(profit_pct=50)
        inp = QuoteInput(hours=1, grams=0, difficulty=2.0)
        r = calculate_quote(cfg, inp)
        # subtotal * 2 (diff) * 1.5 (profit) = 3 * subtotal
        assert abs(r.final_price - 3 * r.subtotal) < 0.01

    def test_config_snapshot_matches(self):
        cfg = QuoteConfig(machine_cost=999, profit_pct=42)
        inp = QuoteInput(hours=1, grams=100)
        r = calculate_quote(cfg, inp)
        assert r.config_snapshot["machine_cost"] == 999
        assert r.config_snapshot["profit_pct"] == 42

    def test_timestamp_set(self):
        cfg = QuoteConfig()
        inp = QuoteInput(hours=1)
        r = calculate_quote(cfg, inp)
        assert r.timestamp != ""
        assert "T" in r.timestamp  # ISO format

    def test_dims_passed_through(self):
        cfg = QuoteConfig()
        inp = QuoteInput(dims_mm=[100, 200, 50])
        r = calculate_quote(cfg, inp)
        assert r.dims_mm == [100, 200, 50]

    def test_image_passed_through(self):
        cfg = QuoteConfig()
        inp = QuoteInput(image_base64="data:image/png;base64,abc123")
        r = calculate_quote(cfg, inp)
        assert r.image_base64 == "data:image/png;base64,abc123"

    def test_machine_per_hr_in_result(self):
        cfg = QuoteConfig(machine_cost=100_000, machine_life_hrs=5_000)
        inp = QuoteInput(hours=1)
        r = calculate_quote(cfg, inp)
        assert r.machine_per_hr == 20.0

    def test_energy_per_hr_in_result(self):
        cfg = QuoteConfig(power_watts=150, electricity_kwh=50)
        inp = QuoteInput(hours=1)
        r = calculate_quote(cfg, inp)
        assert r.energy_per_hr == 7.5


# ═══════════════════════════════════════════════════════════════
#  Multi-modelo
# ═══════════════════════════════════════════════════════════════

class TestMultiModel:
    def test_models_passed_through(self):
        models = [
            {"name": "piece1", "dims_mm": [50, 50, 50], "volume_cm3": 10, "weight_g": 12.4},
            {"name": "piece2", "dims_mm": [30, 30, 30], "volume_cm3": 5, "weight_g": 6.2},
        ]
        cfg = QuoteConfig()
        inp = QuoteInput(hours=2, grams=18.6, models=models)
        r = calculate_quote(cfg, inp)
        assert len(r.models) == 2
        assert r.models[0]["name"] == "piece1"
        assert r.models[1]["name"] == "piece2"

    def test_empty_models_list(self):
        cfg = QuoteConfig()
        inp = QuoteInput(hours=1, grams=100, models=[])
        r = calculate_quote(cfg, inp)
        assert r.models == []

    def test_single_model_in_list(self):
        models = [{"name": "only", "dims_mm": [10, 10, 10], "volume_cm3": 1, "weight_g": 1.24}]
        cfg = QuoteConfig()
        inp = QuoteInput(hours=0.5, grams=1.24, models=models)
        r = calculate_quote(cfg, inp)
        assert len(r.models) == 1

    def test_multi_model_to_dict(self):
        models = [{"name": "a"}, {"name": "b"}]
        cfg = QuoteConfig()
        inp = QuoteInput(models=models)
        r = calculate_quote(cfg, inp)
        d = r.to_dict()
        assert len(d["models"]) == 2


# ═══════════════════════════════════════════════════════════════
#  estimate_weight_grams
# ═══════════════════════════════════════════════════════════════

class TestEstimateWeight:
    def test_pla_default_density(self):
        assert abs(estimate_weight_grams(100) - 124) < 0.01

    def test_custom_density(self):
        assert estimate_weight_grams(100, 2.0) == 200.0

    def test_zero_volume(self):
        assert estimate_weight_grams(0) == 0.0

    def test_small_volume(self):
        w = estimate_weight_grams(0.1)
        assert abs(w - 0.124) < 0.001

    def test_pla_density_constant(self):
        assert PLA_DENSITY_G_CM3 == 1.24


# ═══════════════════════════════════════════════════════════════
#  Edge cases numéricos
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_very_large_hours(self):
        cfg = QuoteConfig()
        inp = QuoteInput(hours=1000, grams=0)
        r = calculate_quote(cfg, inp)
        assert r.final_price > 0
        assert r.final_price == r.final_price  # not NaN

    def test_very_large_grams(self):
        cfg = QuoteConfig()
        inp = QuoteInput(hours=0, grams=100_000)
        r = calculate_quote(cfg, inp)
        assert r.final_price > 0

    def test_fractional_minutes(self):
        cfg = QuoteConfig()
        inp = QuoteInput(hours=0, minutes=1)
        r = calculate_quote(cfg, inp)
        assert r.total_hours == pytest.approx(1/60)

    def test_difficulty_exactly_one(self):
        cfg = QuoteConfig()
        inp = QuoteInput(hours=1, grams=100, difficulty=1.0)
        r = calculate_quote(cfg, inp)
        assert r.extra_difficulty == 0

    def test_profit_0_percent(self):
        cfg = QuoteConfig(profit_pct=0)
        inp = QuoteInput(hours=1, grams=100, difficulty=1.5)
        r = calculate_quote(cfg, inp)
        assert r.profit == 0
        assert r.final_price == r.subtotal_with_difficulty

    def test_profit_100_percent(self):
        cfg = QuoteConfig(profit_pct=100)
        inp = QuoteInput(hours=1, grams=0, difficulty=1.0)
        r = calculate_quote(cfg, inp)
        assert r.final_price == 2 * r.subtotal

    def test_negative_profit(self):
        cfg = QuoteConfig(profit_pct=-10)
        inp = QuoteInput(hours=1, grams=0, difficulty=1.0)
        r = calculate_quote(cfg, inp)
        assert r.profit < 0
        assert r.final_price < r.subtotal

    def test_many_models(self):
        models = [{"name": f"m{i}", "volume_cm3": i} for i in range(1, 101)]
        total_g = sum(estimate_weight_grams(m["volume_cm3"]) for m in models)
        cfg = QuoteConfig()
        inp = QuoteInput(hours=10, grams=total_g, models=models)
        r = calculate_quote(cfg, inp)
        assert len(r.models) == 100
        assert r.final_price > 0

    def test_result_independent_of_timestamp(self):
        """Two calls with same input produce same price (ignoring timestamp)."""
        cfg = QuoteConfig()
        inp = QuoteInput(hours=2, grams=200, difficulty=1.5)
        r1 = calculate_quote(cfg, inp)
        r2 = calculate_quote(cfg, inp)
        assert r1.final_price == r2.final_price
        assert r1.cost_time == r2.cost_time
        assert r1.extra_difficulty == r2.extra_difficulty
