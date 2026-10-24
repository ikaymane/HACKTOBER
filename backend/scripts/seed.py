"""Generate all simulated data into backend/data/*.json.

Run:  python backend/scripts/seed.py
Edit this file (not the JSON) when you need different data, then re-run. Deterministic (fixed RNG seed).
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
rng = random.Random(42)
TODAY = datetime(2026, 10, 24, 8, 0)

# ---------------------------------------------------------------- cities + roads
CITIES = {
    "casablanca": ("Casablanca", 33.5731, -7.5898),
    "rabat": ("Rabat", 34.0209, -6.8416),
    "kenitra": ("Kénitra", 34.2610, -6.5802),
    "tanger": ("Tanger", 35.7595, -5.8340),
    "meknes": ("Meknès", 33.8935, -5.5473),
    "fes": ("Fès", 34.0181, -5.0078),
    "oujda": ("Oujda", 34.6814, -1.9086),
    "settat": ("Settat", 33.0010, -7.6166),
    "benguerir": ("Benguerir", 32.2359, -7.9542),
    "marrakech": ("Marrakech", 31.6295, -7.9811),
    "eljadida": ("El Jadida", 33.2316, -8.5007),
    "safi": ("Safi", 32.2994, -9.2372),
    "khouribga": ("Khouribga", 32.8811, -6.9063),
    "benimellal": ("Béni Mellal", 32.3373, -6.3498),
    "agadir": ("Agadir", 30.4278, -9.5981),
    "laayoune": ("Laâyoune", 27.1253, -13.1625),
}

# (a, b, km, toll_mad_class1, road)  -- toll is for a car; trucks pay meta.truck_toll_multiplier x
ROADS = [
    ("casablanca", "rabat", 87, 23, "highway"),
    ("casablanca", "rabat", 92, 0, "national"),
    ("rabat", "kenitra", 40, 9, "highway"),
    ("kenitra", "tanger", 210, 63, "highway"),
    ("rabat", "meknes", 140, 39, "highway"),
    ("kenitra", "meknes", 125, 0, "national"),
    ("meknes", "fes", 60, 15, "highway"),
    ("fes", "oujda", 330, 96, "highway"),
    ("casablanca", "settat", 70, 18, "highway"),
    ("casablanca", "settat", 75, 0, "national"),
    ("settat", "benguerir", 100, 27, "highway"),
    ("benguerir", "marrakech", 70, 20, "highway"),
    ("settat", "marrakech", 160, 0, "national"),
    ("casablanca", "eljadida", 100, 25, "highway"),
    ("eljadida", "safi", 145, 0, "national"),
    ("safi", "marrakech", 160, 0, "national"),
    ("marrakech", "agadir", 245, 75, "highway"),
    ("safi", "agadir", 290, 0, "national"),
    ("agadir", "laayoune", 640, 0, "national"),
    ("casablanca", "khouribga", 125, 0, "national"),
    ("settat", "khouribga", 80, 0, "national"),
    ("khouribga", "benimellal", 100, 0, "national"),
    ("benimellal", "marrakech", 190, 0, "national"),
    ("benimellal", "fes", 290, 0, "national"),
    ("khouribga", "rabat", 165, 0, "national"),
]
SPEED = {"highway": {"truck": 85, "ambulance": 110}, "national": {"truck": 65, "ambulance": 85}}

road_graph = {
    "meta": {
        "diesel_mad_per_l": 11.6,
        "driver_cost_mad_per_hour": 60,
        "truck_toll_multiplier": 1.6,
        "speed_kmh": SPEED,
        "note": "Tolls approximate ADM class-1 rates; speeds are average incl. traffic.",
    },
    "cities": [{"id": k, "name": v[0], "lat": v[1], "lng": v[2]} for k, v in CITIES.items()],
    "edges": [{"from": a, "to": b, "km": km, "toll_mad": t, "road": r} for a, b, km, t, r in ROADS],
}

# ---------------------------------------------------------------- depots
def pos(city):
    return {"lat": CITIES[city][1], "lng": CITIES[city][2]}

DEPOTS = [
    {"id": "DEP-CASA", "city": "casablanca", "position": pos("casablanca"), "spare_vehicles": ["T-11"], "has_workshop": True},
    {"id": "DEP-RABAT", "city": "rabat", "position": pos("rabat"), "spare_vehicles": ["T-10"], "has_workshop": True},
    {"id": "DEP-SETTAT", "city": "settat", "position": pos("settat"), "spare_vehicles": ["A-04"], "has_workshop": False},
    {"id": "DEP-MARRAKECH", "city": "marrakech", "position": pos("marrakech"), "spare_vehicles": [], "has_workshop": True},
    {"id": "DEP-FES", "city": "fes", "position": pos("fes"), "spare_vehicles": ["T-08"], "has_workshop": True},
    {"id": "DEP-AGADIR", "city": "agadir", "position": pos("agadir"), "spare_vehicles": [], "has_workshop": False},
]

# ---------------------------------------------------------------- vehicles
def tele(**kw):
    t = {
        "dtc": [],
        "coolant_c": round(rng.uniform(86, 92), 1),
        "oil_bar": round(rng.uniform(3.6, 4.4), 1),
        "battery_v": round(rng.uniform(13.8, 14.3), 2),
        "brake_wear_pct": round(rng.uniform(15, 55)),
        "idle_pct_7d": round(rng.uniform(5, 12), 1),
        "speed_kmh": 0,
        "last_service_km": 0,
    }
    t.update(kw)
    return t

def truck(id_, plate, model, year, km, status, depot, lat, lng, mission, driver, **tkw):
    return {
        "id": id_, "type": "truck", "model": model, "plate": plate, "year": year, "km": km,
        "tank_l": 400, "base_l_100km": 32.0, "status": status, "home_depot": depot,
        "position": {"lat": lat, "lng": lng}, "mission_id": mission, "driver": driver,
        "telemetry": tele(last_service_km=km - rng.randint(5000, 35000), speed_kmh=80 if status == "on_mission" else 0, **tkw),
    }

def ambulance(id_, plate, model, year, km, status, depot, lat, lng, mission, driver, **tkw):
    return {
        "id": id_, "type": "ambulance", "model": model, "plate": plate, "year": year, "km": km,
        "tank_l": 80, "base_l_100km": 12.5, "status": status, "home_depot": depot,
        "position": {"lat": lat, "lng": lng}, "mission_id": mission, "driver": driver,
        "telemetry": tele(last_service_km=km - rng.randint(3000, 15000), speed_kmh=95 if status == "on_mission" else 0, **tkw),
    }

VEHICLES = [
    truck("T-01", "12345-A-6", "Volvo FH 460", 2019, 412000, "on_mission", "DEP-CASA", 33.79, -7.16, "M-101", "Youssef B."),
    truck("T-02", "23456-A-1", "Renault T 480", 2020, 356000, "on_mission", "DEP-RABAT", 35.19, -6.15, "M-102", "Hamid E."),
    truck("T-03", "34567-A-6", "Mercedes Actros 1845", 2021, 248000, "on_mission", "DEP-CASA", 32.70, -7.80, "M-103", "Rachid K."),
    truck("T-04", "45678-A-15", "Scania R450", 2018, 498000, "on_mission", "DEP-FES", 34.22, -3.99, "M-104", "Said M."),
    truck("T-05", "56789-A-6", "Volvo FM 420", 2017, 561000, "on_mission", "DEP-CASA", 33.10, -8.60, "M-105", "Khalid A."),
    truck("T-06", "67890-A-6", "DAF XF 480", 2016, 640000, "maintenance", "DEP-CASA", 33.5731, -7.5898, None, "Omar T."),
    truck("T-07", "78901-A-6", "Renault T 460", 2018, 487000, "on_mission", "DEP-CASA", 32.45, -7.90, "M-107", "Mustapha R."),
    truck("T-08", "89012-A-15", "Mercedes Actros 1845", 2022, 151000, "available", "DEP-FES", 34.0181, -5.0078, None, "Nabil H."),
    truck("T-09", "90123-A-40", "Iveco S-Way 460", 2020, 330000, "on_mission", "DEP-MARRAKECH", 30.95, -9.00, "M-109", "Abdelali Z.", idle_pct_7d=31.0),
    truck("T-10", "11223-A-1", "Volvo FH 460", 2021, 230000, "available", "DEP-RABAT", 34.0209, -6.8416, None, "Hicham L."),
    truck("T-11", "22334-A-6", "Scania R450", 2022, 140000, "available", "DEP-CASA", 33.5731, -7.5898, None, "Driss F."),
    truck("T-12", "33445-A-6", "Renault T 480", 2019, 433000, "on_mission", "DEP-CASA", 33.82, -6.07, "M-112", "Aziz O.", brake_wear_pct=81),
    ambulance("A-01", "44556-A-1", "Mercedes Sprinter 319", 2021, 185000, "on_mission", "DEP-RABAT", 33.90, -7.00, "M-201", "Karim S."),
    ambulance("A-02", "55667-A-6", "Renault Master L3", 2020, 212000, "available", "DEP-CASA", 33.5731, -7.5898, None, "Samir D."),
    ambulance("A-03", "66778-A-40", "Mercedes Sprinter 319", 2019, 268000, "on_mission", "DEP-MARRAKECH", 32.55, -7.85, "M-203", "Yassine N."),
    ambulance("A-04", "77889-A-6", "Volkswagen Crafter", 2022, 98000, "available", "DEP-SETTAT", 33.0010, -7.6166, None, "Anas G."),
]

# ---------------------------------------------------------------- missions
def stop(city, start, end, cargo):
    return {"city": city, "window_start": f"2026-10-24T{start}", "window_end": f"2026-10-24T{end}", "cargo": cargo}

TRUCK_SLA = dict(sla_minutes_replacement=90, penalty_mad_per_hour=1500, penalty_flat_mad=8000)
AMB_SLA = dict(sla_minutes_replacement=60, penalty_mad_per_hour=5000, penalty_flat_mad=25000)

MISSIONS = [
    {"id": "M-101", "vehicle_id": "T-01", "kind": "delivery", "client": "Marjane Rabat", "origin": "casablanca",
     "stops": [stop("rabat", "10:00", "11:00", "18 palettes produits secs")], **TRUCK_SLA},
    {"id": "M-102", "vehicle_id": "T-02", "kind": "delivery", "client": "Tanger Med Logistics", "origin": "rabat",
     "stops": [stop("tanger", "11:30", "12:30", "Conteneur pièces auto")], **TRUCK_SLA},
    {"id": "M-103", "vehicle_id": "T-03", "kind": "delivery", "client": "Souss Distribution", "origin": "casablanca",
     "stops": [stop("marrakech", "11:00", "12:00", "12 palettes électroménager"),
               stop("agadir", "15:30", "17:00", "8 palettes électroménager")], **TRUCK_SLA, "capacity_free_pallets": 14},
    {"id": "M-104", "vehicle_id": "T-04", "kind": "delivery", "client": "Oriental Agro", "origin": "fes",
     "stops": [stop("oujda", "12:00", "13:00", "Engrais 20 t")], **TRUCK_SLA},
    {"id": "M-105", "vehicle_id": "T-05", "kind": "delivery", "client": "Atlantic Fish Safi", "origin": "casablanca",
     "stops": [stop("eljadida", "09:30", "10:00", "Emballages"), stop("safi", "12:00", "13:00", "Emballages")], **TRUCK_SLA},
    {"id": "M-107", "vehicle_id": "T-07", "kind": "delivery", "client": "Pharma Sud Marrakech", "origin": "casablanca",
     "stops": [stop("marrakech", "11:30", "12:30", "10 palettes médicaments (chaîne du froid)")], **TRUCK_SLA},
    {"id": "M-109", "vehicle_id": "T-09", "kind": "delivery", "client": "Agadir Primeurs", "origin": "marrakech",
     "stops": [stop("agadir", "11:00", "12:00", "Cagettes vides")], **TRUCK_SLA},
    {"id": "M-112", "vehicle_id": "T-12", "kind": "delivery", "client": "Fès Textile", "origin": "casablanca",
     "stops": [stop("meknes", "11:00", "11:45", "Rouleaux tissu"), stop("fes", "12:30", "13:30", "Rouleaux tissu")], **TRUCK_SLA},
    {"id": "M-201", "vehicle_id": "A-01", "kind": "emergency_transfer", "client": "CHU Ibn Sina → CHU Ibn Rochd", "origin": "rabat",
     "stops": [stop("casablanca", "09:15", "09:30", "Patient transfert cardiologie")], **AMB_SLA},
    {"id": "M-203", "vehicle_id": "A-03", "kind": "emergency_transfer", "client": "CHU Mohammed VI → CHU Ibn Rochd", "origin": "marrakech",
     "stops": [stop("casablanca", "10:15", "10:30", "Patient transfert neurologie")], **AMB_SLA},
]

# ---------------------------------------------------------------- parts
def part(id_, fr, en, zone, dtc, symptoms, critical, repairable, repair_cost, repair_h, labor_h, life_km):
    return {"id": id_, "name_fr": fr, "name_en": en, "zone": zone, "dtc_codes": dtc, "symptoms": symptoms,
            "safety_critical": critical, "repairable": repairable, "repair_cost_mad": repair_cost,
            "repair_hours": repair_h, "replace_labor_hours": labor_h, "typical_life_km": life_km}

PARTS = [
    part("P-ALT", "Alternateur", "Alternator", "electrical", ["P0562", "P0620", "P0622"],
         ["voyant batterie", "tension basse", "phares faibles", "équipements médicaux qui coupent"], False, True, 1200, 3, 1.5, 200000),
    part("P-BATT", "Batterie", "Battery", "electrical", ["P0562"], ["démarrage difficile", "tension basse moteur coupé"], False, False, 0, 0, 0.5, 120000),
    part("P-STARTER", "Démarreur", "Starter motor", "electrical", ["P0615", "P0616"], ["clic au démarrage", "moteur ne démarre pas"], False, True, 1100, 3, 2, 250000),
    part("P-WPUMP", "Pompe à eau", "Water pump", "cooling", ["P0217", "P0128", "P0118"],
         ["surchauffe", "fuite liquide de refroidissement", "bruit roulement avant moteur"], True, True, 900, 4, 3, 250000),
    part("P-THERM", "Thermostat", "Thermostat", "cooling", ["P0128", "P0217"], ["température instable", "surchauffe en côte"], False, False, 0, 0, 1, 200000),
    part("P-RAD", "Radiateur", "Radiator", "cooling", ["P0217"], ["surchauffe", "fuite liquide", "niveau liquide bas"], True, True, 1500, 5, 3, 400000),
    part("P-BCAL", "Étrier de frein", "Brake caliper", "brakes", ["C0040", "C0045"],
         ["bruit au freinage", "véhicule tire d'un côté", "roue chaude", "surconsommation carburant", "usure plaquettes rapide"], True, True, 800, 3, 2, 300000),
    part("P-BPAD", "Plaquettes de frein", "Brake pads", "brakes", ["C0040"], ["grincement", "usure plaquettes élevée"], True, False, 0, 0, 1, 80000),
    part("P-INJ", "Injecteur", "Fuel injector", "fuel", ["P0201", "P0263", "P0300"],
         ["fumée noire", "surconsommation carburant", "ratés moteur"], False, True, 600, 2, 2, 300000),
    part("P-TURBO", "Turbocompresseur", "Turbocharger", "engine", ["P0299", "P0234"], ["perte de puissance", "sifflement", "fumée bleue"], False, True, 4500, 8, 5, 450000),
    part("P-EGR", "Vanne EGR", "EGR valve", "engine", ["P0401", "P0404"], ["perte de puissance", "fumée noire", "mode dégradé"], False, True, 700, 2, 2, 250000),
    part("P-OILP", "Pompe à huile", "Oil pump", "engine", ["P0520", "P0524"], ["pression huile basse", "voyant huile"], True, False, 0, 0, 5, 500000),
    part("P-DPF", "Filtre à particules", "Diesel particulate filter", "engine", ["P2002", "P2463"], ["mode dégradé", "régénération impossible"], False, True, 1800, 4, 2, 350000),
    part("P-CLUTCH", "Kit embrayage", "Clutch kit", "transmission", ["P0806"], ["patinage", "passage vitesses difficile"], False, False, 0, 0, 6, 400000),
    part("P-TIRE", "Pneu", "Tire", "tires", ["C0750"], ["perte pression", "vibration"], True, True, 150, 0.5, 0.5, 120000),
]

# ---------------------------------------------------------------- suppliers (fictional companies)
BASE_PRICE = {"P-ALT": 4200, "P-BATT": 2100, "P-STARTER": 3600, "P-WPUMP": 2400, "P-THERM": 550, "P-RAD": 5200,
              "P-BCAL": 3100, "P-BPAD": 1100, "P-INJ": 3200, "P-TURBO": 11500, "P-EGR": 2400, "P-OILP": 3100,
              "P-DPF": 14500, "P-CLUTCH": 7400, "P-TIRE": 3700}

SUPPLIER_DEFS = [
    # id, name, city, rating, on_time, price_factor, base_delivery_h, warranty, catalog_share
    ("SUP-ATLAS", "AutoPièces Atlas", "casablanca", 4.3, 92, 1.00, 6, 12, 1.0),
    ("SUP-MTP", "Maroc Truck Parts", "settat", 3.9, 84, 0.88, 10, 6, 0.85),
    ("SUP-SAHARA", "Sahara Diesel Supply", "marrakech", 4.0, 88, 0.93, 5, 12, 0.8),
    ("SUP-OEM", "Distributeur Constructeur (OEM)", "rabat", 4.8, 97, 1.30, 24, 24, 1.0),
    ("SUP-SOUSS", "Souss Pièces Poids Lourds", "agadir", 3.6, 78, 0.80, 18, 3, 0.7),
    ("SUP-MEDI", "Medi-Fleet Équipement", "casablanca", 4.5, 95, 1.10, 3, 12, 0.5),
]

SUPPLIERS = []
for sid, name, city, rating, on_time, pf, dh, warranty, share in SUPPLIER_DEFS:
    offers = []
    for pid, price in BASE_PRICE.items():
        if pid in ("P-ALT", "P-WPUMP", "P-BCAL") or rng.random() < share:  # demo parts always offered
            in_stock = rng.random() < 0.8
            offers.append({
                "part_id": pid,
                "price_mad": int(round(price * pf * rng.uniform(0.95, 1.05), -1)),
                "delivery_hours": round(dh * (1 if in_stock else 3) * rng.uniform(0.8, 1.2), 1),
                "warranty_months": warranty,
                "in_stock": in_stock,
            })
    SUPPLIERS.append({"id": sid, "name": name, "city": city, "position": pos(city),
                      "rating": rating, "on_time_pct": on_time, "offers": offers,
                      "vehicle_types": ["ambulance"] if sid == "SUP-MEDI" else ["truck", "ambulance"]})

# ---------------------------------------------------------------- fuel logs (30 days)
STATIONS = list(CITIES)
DAILY_KM = {"truck": 380, "ambulance": 190}

def fuel_logs():
    logs, n = [], 0
    for v in VEHICLES:
        if v["status"] == "maintenance":
            continue
        odo = v["km"] - DAILY_KM[v["type"]] * 30
        t = TODAY - timedelta(days=30)
        while t < TODAY:
            gap_days = rng.uniform(1.5, 3.0) if v["type"] == "truck" else rng.uniform(2.5, 4.5)
            t += timedelta(days=gap_days)
            if t >= TODAY:
                break
            km = DAILY_KM[v["type"]] * gap_days * rng.uniform(0.85, 1.15)
            factor = rng.uniform(0.95, 1.06)
            recent = (TODAY - t).days <= 7
            if v["id"] == "T-12" and recent:
                factor *= 1.22  # dragging brake caliper
            if v["id"] == "T-09":
                factor *= 1.08  # idling
            litres = km * v["base_l_100km"] / 100 * factor
            odo += km
            n += 1
            logs.append({"id": f"F-{n:04d}", "vehicle_id": v["id"], "ts": t.strftime("%Y-%m-%dT%H:%M"),
                         "litres": round(litres, 1), "odometer_km": int(odo), "station_city": rng.choice(STATIONS),
                         "price_mad_l": round(rng.uniform(11.3, 11.9), 2), "card_id": f"CARD-{v['id']}"})
    # T-05: fuel card fraud signals
    n += 1
    logs.append({"id": f"F-{n:04d}", "vehicle_id": "T-05", "ts": "2026-10-21T22:40", "litres": 455.0,
                 "odometer_km": logs[-1]["odometer_km"] if logs[-1]["vehicle_id"] == "T-05" else 560500,
                 "station_city": "eljadida", "price_mad_l": 11.6, "card_id": "CARD-T-05"})
    t05 = [l for l in logs if l["vehicle_id"] == "T-05"]
    n += 1
    logs.append({"id": f"F-{n:04d}", "vehicle_id": "T-05", "ts": "2026-10-22T06:10", "litres": 180.0,
                 "odometer_km": t05[-1]["odometer_km"], "station_city": "eljadida", "price_mad_l": 11.6, "card_id": "CARD-T-05"})
    logs.sort(key=lambda l: (l["vehicle_id"], l["ts"]))
    return logs

# ---------------------------------------------------------------- scenarios (telemetry injected by simulator)
SCENARIOS = [
    {"id": 1, "title": "Ambulance A-03: panne alternateur sur l'A7 entre Benguerir et Settat", "vehicle_id": "A-03",
     "telemetry": {"dtc": ["P0562", "P0620"], "battery_v": 11.2, "speed_kmh": 60},
     "driver_report": "Voyant batterie allumé, le moniteur cardiaque est passé sur batterie interne et les phares baissent.",
     "expected": {"part_id": "P-ALT", "depot": "DEP-SETTAT", "replacement": "A-04", "penalty": False}},
    {"id": 2, "title": "Camion T-07: surchauffe moteur sur l'A7", "vehicle_id": "T-07",
     "telemetry": {"dtc": ["P0217"], "coolant_c": 118, "speed_kmh": 40},
     # Darija/French WhatsApp-style message: the LLM has to read it, keyword lookup alone can't.
     "driver_report": "Salam chef, lmoteur skhoun bzaf, l'aiguille wslat l7mer. Kayna ri7a dial liquide w chwiya d dokhan byed kaykhrej mn capot. W kayn wa7d sda3 bhal roulement l9eddam dial lmoteur. Nw9ef wla nkemmel?",
     "expected": {"part_id": "P-WPUMP", "depot": None, "replacement": None, "penalty": True, "mitigation_vehicle": "T-03"}},
    {"id": 3, "title": "Camion T-12: surconsommation carburant + freins", "vehicle_id": "T-12",
     "telemetry": {"dtc": ["C0040"], "brake_wear_pct": 84},
     "driver_report": "Le camion freine un peu tout seul, la roue avant droite est très chaude à l'arrêt.",
     "expected": {"part_id": "P-BCAL", "fuel_anomaly": "overconsumption", "route": ["casablanca", "fes"]}},
]


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    files = {
        "road_graph.json": road_graph, "depots.json": DEPOTS, "vehicles.json": VEHICLES, "missions.json": MISSIONS,
        "parts.json": PARTS, "suppliers.json": SUPPLIERS, "fuel_logs.json": fuel_logs(), "scenarios.json": SCENARIOS,
    }
    for name, obj in files.items():
        (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {name}: {len(obj) if isinstance(obj, list) else 'obj'}")


if __name__ == "__main__":
    main()
