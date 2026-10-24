"""Shared data contracts. Source of truth for backend + frontend (mirrored in shared/types.ts).

Change a model here -> update shared/types.ts and shared/contracts.md in the same PR.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

VehicleType = Literal["truck", "ambulance"]
VehicleStatus = Literal["on_mission", "available", "breakdown", "maintenance"]
Zone = Literal["engine", "cooling", "electrical", "brakes", "transmission", "tires", "fuel"]
Severity = Literal["ok", "monitor", "drive_to_depot", "stop_now"]
AgentName = Literal["maintenance", "fuel", "delay", "orchestrator", "system"]


class LatLng(BaseModel):
    lat: float
    lng: float


# ---------- fleet ----------

class Telemetry(BaseModel):
    dtc: list[str] = []
    coolant_c: float
    oil_bar: float
    battery_v: float
    brake_wear_pct: float
    idle_pct_7d: float
    speed_kmh: float = 0
    last_service_km: int


class Vehicle(BaseModel):
    id: str
    type: VehicleType
    model: str
    plate: str
    year: int
    km: int
    tank_l: float
    base_l_100km: float
    status: VehicleStatus
    home_depot: str
    position: LatLng
    mission_id: Optional[str] = None
    driver: str
    telemetry: Telemetry


class Depot(BaseModel):
    id: str
    city: str
    position: LatLng
    spare_vehicles: list[str]  # vehicle ids parked and ready
    has_workshop: bool


class Stop(BaseModel):
    city: str
    window_start: str  # ISO time "2026-10-24T14:00"
    window_end: str
    cargo: str


class Mission(BaseModel):
    id: str
    vehicle_id: str
    kind: Literal["delivery", "emergency_transfer"]
    client: str
    origin: str
    stops: list[Stop]
    sla_minutes_replacement: int  # max minutes to get a replacement vehicle rolling
    penalty_mad_per_hour: int  # late penalty once SLA is broken
    penalty_flat_mad: int  # one-off penalty if no replacement at all
    capacity_free_pallets: int = 0  # spare room, lets another truck absorb a broken truck's load


# ---------- parts / suppliers ----------

class Part(BaseModel):
    id: str
    name_fr: str
    name_en: str
    zone: Zone
    dtc_codes: list[str]
    symptoms: list[str]
    safety_critical: bool
    repairable: bool
    repair_cost_mad: int
    repair_hours: float
    replace_labor_hours: float
    typical_life_km: int


class SupplierOffer(BaseModel):
    part_id: str
    price_mad: int
    delivery_hours: float
    warranty_months: int
    in_stock: bool


class Supplier(BaseModel):
    id: str
    name: str
    city: str
    position: LatLng
    rating: float  # 1-5
    on_time_pct: float  # 0-100
    offers: list[SupplierOffer]
    vehicle_types: list[VehicleType] = ["truck", "ambulance"]


class SupplierScore(BaseModel):
    supplier_id: str
    supplier_name: str
    part_id: str
    price_mad: int
    delivery_hours: float
    warranty_months: int
    on_time_pct: float
    rating: float
    score: float  # 0-100, higher is better
    breakdown: dict[str, float]  # kpi -> weighted points


# ---------- outputs of agents ----------

class Diagnosis(BaseModel):
    part_id: str
    part_name: str
    zone: Zone
    confidence: float  # 0-1
    severity: Severity
    evidence: list[str]


class RepairDecision(BaseModel):
    action: Literal["repair", "replace"]
    reason: str
    cost_mad: int
    downtime_hours: float


class DriverInstruction(BaseModel):
    depot_id: str
    depot_city: str
    distance_km: float
    eta_min: float
    replacement_vehicle_id: Optional[str]
    message: str


class PenaltyRisk(BaseModel):
    at_risk: bool
    amount_mad: int
    reason: str
    mitigation: Optional[str] = None


class Incident(BaseModel):
    id: str
    vehicle_id: str
    mission_id: Optional[str]
    created_at: str
    diagnosis: Diagnosis
    decision: RepairDecision
    suppliers: list[SupplierScore] = []  # ranked, [0] = chosen
    chosen_supplier_id: Optional[str] = None
    supplier_reason: Optional[str] = None
    driver_instruction: Optional[DriverInstruction] = None
    takeover_vehicle_id: Optional[str] = None  # truck on the road that absorbs the load
    penalty: PenaltyRisk
    report_fr: str  # text sent to the company


class FuelAnomaly(BaseModel):
    vehicle_id: str
    kind: Literal["overconsumption", "fill_over_capacity", "fill_without_km", "excessive_idle", "detour"]
    value: float  # e.g. +22 (% over expected), litres, km
    expected: float
    detected_at: str
    probable_cause: Optional[Literal["mechanical", "behavior", "fraud", "detour", "unknown"]] = None
    note: Optional[str] = None  # LLM explanation


class RouteOption(BaseModel):
    label: Literal["shortest", "cheapest", "fastest"]
    path: list[str]  # city ids
    km: float
    hours: float
    fuel_l: float
    fuel_cost_mad: float
    toll_mad: float
    driver_cost_mad: float
    total_cost_mad: float


class AgentEvent(BaseModel):
    """One line on the live timeline (SSE /events)."""
    id: str
    ts: str
    agent: AgentName
    kind: Literal["thought", "tool_call", "tool_result", "decision", "alert", "handoff", "message"]
    title: str
    detail: str = ""
    vehicle_id: Optional[str] = None
    data: dict = Field(default_factory=dict)  # e.g. {"incident_id": ...} or tool args
