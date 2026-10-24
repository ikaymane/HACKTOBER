export type Zone = 'engine'|'cooling'|'electrical'|'brakes'|'transmission'|'tires'|'fuel';
export type Status = 'ok'|'warn'|'fail';
export interface Vehicle {id:string; type:'truck'|'ambulance'; model:string; plate:string; driver:string; mission:string; destination:string; origin:string; status:Status; position:[number,number]; speed:number; fuel:number; health:number; incident_id?:string}
export interface HealthZone {zone:Zone; status:Status; reasons:string[]}
export interface Supplier {id:string; name:string; price:number; delivery_h:number; on_time:number; warranty_months:number; rating:number; chosen:boolean}
export interface Incident {id:string; vehicle_id:string; zone:Zone; part:string; severity:Status; confidence:number; diagnosis:{evidence:string[]}; proposal:{action:'REPAIR'|'REPLACE'; reason:string; cost_mad:number; downtime_h:number}; suppliers:Supplier[]; supplier_reason:string; driver_instruction:{depot:string; km:number; eta_min:number; replacement_vehicle:string}; penalty:{at_risk:number; avoided:number; mitigation:string}; report_fr:string}
export interface AgentEvent {id:string; timestamp:string; agent:string; title:string; message:string; type:'info'|'warning'|'decision'|'success'; vehicle_id?:string; data?:{incident_id?:string}; tool?:{name:string; input:unknown; output:unknown}}
export interface FuelData {expected:number; delta_pct:number; series:{km:string;actual:number;expected:number}[]; fillups:{date:string;station:string;liters:number;cost:number}[]; anomalies:{title:string;note:string;severity:Status}[]}
export interface RouteOption {id:string;label:string;km:number;minutes:number;cost:number;recommended:boolean}
export const zoneLabels:Record<Zone,string>={engine:'Moteur',cooling:'Refroidissement',electrical:'Électrique',brakes:'Freinage',transmission:'Transmission',tires:'Pneumatiques',fuel:'Carburant'};
