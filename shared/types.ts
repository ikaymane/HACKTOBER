// Mirror of backend/app/schemas.py. Keep in sync in the same PR.
// Frontend: copy or import from here (e.g. vite alias "@shared").

export type VehicleType = "truck" | "ambulance";
export type VehicleStatus = "on_mission" | "available" | "breakdown" | "maintenance";
export type Zone = "engine" | "cooling" | "electrical" | "brakes" | "transmission" | "tires" | "fuel";
export type Severity = "ok" | "monitor" | "drive_to_depot" | "stop_now";
export type AgentName = "maintenance" | "fuel" | "delay" | "orchestrator" | "system";

export interface LatLng { lat: number; lng: number }

export interface Telemetry {
  dtc: string[];
  coolant_c: number;
  oil_bar: number;
  battery_v: number;
  brake_wear_pct: number;
  idle_pct_7d: number;
  speed_kmh: number;
  last_service_km: number;
}

export interface Vehicle {
  id: string;
  type: VehicleType;
  model: string;
  plate: string;
  year: number;
  km: number;
  tank_l: number;
  base_l_100km: number;
  status: VehicleStatus;
  home_depot: string;
  position: LatLng;
  mission_id: string | null;
  driver: string;
  telemetry: Telemetry;
}

export interface Depot {
  id: string;
  city: string;
  position: LatLng;
  spare_vehicles: string[];
  has_workshop: boolean;
}

export interface Stop { city: string; window_start: string; window_end: string; cargo: string }

export interface Mission {
  id: string;
  vehicle_id: string;
  kind: "delivery" | "emergency_transfer";
  client: string;
  origin: string;
  stops: Stop[];
  sla_minutes_replacement: number;
  penalty_mad_per_hour: number;
  penalty_flat_mad: number;
  capacity_free_pallets: number;
}

export interface SupplierScore {
  supplier_id: string;
  supplier_name: string;
  part_id: string;
  price_mad: number;
  delivery_hours: number;
  warranty_months: number;
  on_time_pct: number;
  rating: number;
  score: number;
  breakdown: Record<string, number>;
}

export interface Diagnosis {
  part_id: string;
  part_name: string;
  zone: Zone;
  confidence: number;
  severity: Severity;
  evidence: string[];
}

export interface RepairDecision {
  action: "repair" | "replace";
  reason: string;
  cost_mad: number;
  downtime_hours: number;
}

export interface DriverInstruction {
  depot_id: string;
  depot_city: string;
  distance_km: number;
  eta_min: number;
  replacement_vehicle_id: string | null;
  message: string;
}

export interface PenaltyRisk { at_risk: boolean; amount_mad: number; avoided_mad: number; reason: string; mitigation: string | null }

export interface Incident {
  id: string;
  vehicle_id: string;
  mission_id: string | null;
  created_at: string;
  diagnosis: Diagnosis;
  decision: RepairDecision;
  suppliers: SupplierScore[];
  chosen_supplier_id: string | null;
  supplier_reason: string | null;
  driver_instruction: DriverInstruction | null;
  takeover_vehicle_id: string | null;
  penalty: PenaltyRisk;
  report_fr: string;
  approved: boolean;
}

export interface FuelAnomaly {
  vehicle_id: string;
  kind: "overconsumption" | "fill_over_capacity" | "fill_without_km" | "excessive_idle" | "detour";
  value: number;
  expected: number;
  detected_at: string;
  probable_cause: "mechanical" | "behavior" | "fraud" | "detour" | "unknown" | null;
  note: string | null;
}

export interface RouteOption {
  label: "shortest" | "cheapest" | "fastest";
  path: string[];
  km: number;
  hours: number;
  fuel_l: number;
  fuel_cost_mad: number;
  toll_mad: number;
  driver_cost_mad: number;
  total_cost_mad: number;
}

export interface AgentEvent {
  id: string;
  ts: string;
  agent: AgentName;
  kind: "thought" | "tool_call" | "tool_result" | "decision" | "alert" | "handoff" | "message";
  title: string;
  detail: string;
  vehicle_id: string | null;
  data: Record<string, unknown>;
}
