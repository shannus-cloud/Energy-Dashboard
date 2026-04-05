from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Energy Recovery Dashboard", version="1.0.0")


class InputData(BaseModel):
    voltage: float = Field(..., gt=0, description="Battery terminal voltage in volts")
    motor_voltage: float = Field(..., gt=0, description="Motor drive voltage in volts")
    rpm: float = Field(..., ge=0, description="Motor rotational speed in RPM")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_power_series(base_power: float) -> List[float]:
    timeline = np.arange(60)
    ramp = 1 - np.exp(-timeline / 12)
    ripple = 1 + 0.035 * np.sin(timeline / 4)
    power_curve = np.maximum(base_power * ramp * ripple, 0)
    return [round(float(point), 2) for point in power_curve]


def simulate_recovery(data: InputData) -> dict:
    omega = data.rpm * 2 * np.pi / 60

    motor_resistance = 0.42
    back_emf_constant = 0.032
    torque_constant = 0.031
    generator_constant = 0.028
    battery_capacity_ah = 18.0
    battery_capacity_wh = battery_capacity_ah * data.voltage

    back_emf = back_emf_constant * omega
    current = max((data.motor_voltage - back_emf) / motor_resistance, 0.0)
    torque = torque_constant * current
    input_power = data.motor_voltage * current
    mech_power = torque * omega

    inverter_eff = clamp(0.97 - 0.025 * np.exp(-current / 18), 0.90, 0.98)
    motor_eff = clamp(0.83 + 0.12 * (1 - np.exp(-data.rpm / 2300)), 0.82, 0.95)
    drivetrain_eff = 0.94
    generator_eff = clamp(0.80 + 0.13 * (1 - np.exp(-data.rpm / 2800)), 0.79, 0.93)
    rectifier_eff = 0.96
    total_stage_eff = inverter_eff * motor_eff * drivetrain_eff * generator_eff * rectifier_eff

    generator_voltage = generator_constant * omega
    recovered_power_raw = mech_power * drivetrain_eff * generator_eff * rectifier_eff
    voltage_acceptance = clamp(generator_voltage / max(data.voltage, 1e-6), 0.15, 1.18)
    output_power = max(recovered_power_raw * voltage_acceptance, 0.0)
    charge_current = output_power / data.voltage if data.voltage else 0.0

    soc = clamp(22 + (output_power / max(battery_capacity_wh, 1)) * 320, 8, 98)
    charge_deficit_wh = battery_capacity_wh * (1 - soc / 100)
    charging_time_hours = charge_deficit_wh / output_power if output_power > 0 else 0.0
    overall_efficiency = (output_power / input_power) * 100 if input_power > 0 else 0.0

    thermal_loss = max(input_power - mech_power * motor_eff, 0.0)
    mechanical_loss = max(mech_power * (1 - drivetrain_eff), 0.0)
    conversion_loss = max(
        mech_power * drivetrain_eff * generator_eff * (1 - rectifier_eff),
        0.0,
    )

    return {
        "metrics": {
            "input_power": float(round(input_power, 2)),
            "mechanical_power": float(round(mech_power, 2)),
            "output_power": float(round(output_power, 2)),
            "efficiency": float(round(overall_efficiency, 2)),
            "soc": float(round(soc, 2)),
            "charging_time_hours": float(round(charging_time_hours, 2)),
            "charge_current": float(round(charge_current, 2)),
            "back_emf": float(round(back_emf, 2)),
            "generator_voltage": float(round(generator_voltage, 2)),
            "torque": float(round(torque, 3)),
            "status": "Charging" if output_power > 5 else "Standby",
        },
        "stages": {
            "inverter": float(round(inverter_eff * 100, 2)),
            "motor": float(round(motor_eff * 100, 2)),
            "drivetrain": float(round(drivetrain_eff * 100, 2)),
            "generator": float(round(generator_eff * 100, 2)),
            "rectifier": float(round(rectifier_eff * 100, 2)),
            "total": float(round(total_stage_eff * 100, 2)),
        },
        "losses": {
            "thermal": float(round(thermal_loss, 2)),
            "mechanical": float(round(mechanical_loss, 2)),
            "conversion": float(round(conversion_loss, 2)),
        },
        "mini_charts": {
            "voltage_profile": [
                round(data.motor_voltage * factor, 2)
                for factor in [0.82, 0.86, 0.91, 0.95, 1.0, 0.97, 0.94]
            ],
            "rpm_profile": [
                round(data.rpm * factor, 2)
                for factor in [0.45, 0.58, 0.72, 0.81, 0.91, 0.97, 1.0]
            ],
            "efficiency_profile": [
                round(value, 2)
                for value in [
                    inverter_eff * 100,
                    motor_eff * 100,
                    drivetrain_eff * 100,
                    generator_eff * 100,
                    rectifier_eff * 100,
                ]
            ],
        },
        "timeseries": {
            "time_seconds": list(range(60)),
            "power_watts": build_power_series(output_power),
            "soc_projection": [
                round(clamp(soc + idx * charge_current * 0.035, 0, 100), 2)
                for idx in range(12)
            ],
        },
    }


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (BASE_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/api/simulate")
def simulate(data: InputData) -> dict:
    return simulate_recovery(data)
