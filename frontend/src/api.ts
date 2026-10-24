import {fleetSeed,incidentsSeed,initialEvents,mockFuel,mockRoutes} from './mock';
import type {Vehicle,Incident,HealthZone,FuelData,RouteOption,AgentEvent,Zone} from './types';
const env=import.meta as ImportMeta & {env:Record<string,string>};
export const liveMode=env.env?.VITE_DATA_MODE==='live';
const base=(env.env?.VITE_API_BASE_URL||'/api').replace(/\/$/,'');
const clone=<T,>(x:T):T=>structuredClone(x);
let fleet=clone(fleetSeed),incidents=clone(incidentsSeed);
let demoRoads:Promise<Record<string,[number,number][]>>|undefined;
async function request<T>(path:string,options?:RequestInit):Promise<T>{const response=await fetch(base+path,{...options,signal:AbortSignal.timeout(12000)});if(!response.ok)throw new Error(`API ${response.status} · ${path}`);if(response.status===204)return undefined as T;return response.json();}
export const api={
 fleet:()=>liveMode?request<Vehicle[]>('/fleet'):Promise.resolve(clone(fleet)),
 incident:(id:string)=>liveMode?request<Incident>(`/incidents/${encodeURIComponent(id)}`):Promise.resolve(clone(incidents.find(x=>x.id===id)!)),
 health:(id:string)=>liveMode?request<HealthZone[]>(`/vehicles/${encodeURIComponent(id)}/health`):Promise.resolve((['engine','cooling','electrical','brakes','transmission','tires','fuel'] as Zone[]).map(zone=>{const incident=incidents.find(x=>x.vehicle_id===id&&x.zone===zone);return {zone,status:incident?.severity||'ok',reasons:incident?incident.diagnosis.evidence:['Paramètres dans les plages de fonctionnement normales.','Aucun problème détecté sur les signaux disponibles.']};})),
 fuel:(id:string)=>liveMode?request<FuelData>(`/fuel/${encodeURIComponent(id)}`):Promise.resolve(mockFuel(id)),
 routes:(id:string)=>liveMode?request<RouteOption[]>(`/route/compare?vehicle_id=${encodeURIComponent(id)}`):Promise.resolve(clone(mockRoutes)),
 path:(id:string)=>liveMode?request<{path:[number,number][]}>(`/missions/${encodeURIComponent(id)}/path`):(demoRoads??=fetch('/data/roads.json').then(r=>{if(!r.ok)throw new Error('Géométrie routière indisponible');return r.json();})).then(data=>({path:data[id]||[]})),
 scenario:async(id:number)=>{if(liveMode){await request('/scenarios/'+id,{method:'POST'});return;} fleet=clone(fleetSeed);incidents=clone(incidentsSeed);const selected=incidents.find(x=>x.id===['INC-001','INC-002','INC-003'][id-1])!;fleet=fleet.map(v=>({...v,status:v.id===selected.vehicle_id?selected.severity:'ok',health:v.id===selected.vehicle_id?62:98,incident_id:v.id===selected.vehicle_id?selected.id:undefined}));incidents=[selected];},
 reset:async()=>{if(liveMode){await request('/reset',{method:'POST'});return;}fleet=clone(fleetSeed);incidents=clone(incidentsSeed);},
 events:()=>liveMode?[]:clone(initialEvents),
 subscribe:(onEvent:(event:AgentEvent)=>void,onConnection:(connected:boolean)=>void)=>{if(!liveMode){onConnection(true);return ()=>{};}const source=new EventSource(base+'/events');source.onopen=()=>onConnection(true);source.onerror=()=>onConnection(false);source.onmessage=e=>{try{onEvent(JSON.parse(e.data));}catch{console.warn('Invalid agent event');}};return ()=>source.close();}
};
