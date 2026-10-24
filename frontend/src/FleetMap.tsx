import {useEffect,useMemo,useRef,useState} from 'react';
import Map,{Marker,NavigationControl,type MapRef} from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import {PathLayer} from '@deck.gl/layers';
import {ScenegraphLayer} from '@deck.gl/mesh-layers';
import {Truck,Plus,LocateFixed,Layers,Maximize2,MapPin,Activity} from 'lucide-react';
import {api} from './api';
import type {Vehicle} from './types';
import 'maplibre-gl/dist/maplibre-gl.css';
const INITIAL={longitude:-7.1,latitude:32.99,zoom:6.45,pitch:50,bearing:-13};
const depots=[{name:'CASABLANCA HUB',position:[-7.59,33.57]},{name:'MARRAKECH',position:[-7.98,31.63]},{name:'RABAT',position:[-6.84,34.02]}];
export default function FleetMap({vehicles,onSelect,focusId}:{vehicles:Vehicle[];onSelect:(id:string)=>void;focusId:string|null}){
 const [paths,setPaths]=useState<{id:string;path:[number,number][]}[]>([]),[view,setView]=useState(INITIAL),[showRoutes,setShowRoutes]=useState(true),[models,setModels]=useState(false),[modelAvailable,setModelAvailable]=useState(false),[error,setError]=useState(false);const map=useRef<MapRef>(null);
 useEffect(()=>{let active=true;Promise.all(vehicles.map(v=>api.path(v.mission).then(p=>({id:v.id,path:p.path})))).then(p=>{if(active)setPaths(p);}).catch(()=>{});return()=>{active=false;};},[vehicles]);
 useEffect(()=>{if(focusId){const v=vehicles.find(v=>v.id===focusId);if(v)map.current?.flyTo({center:v.position,zoom:9,duration:1500});}},[focusId,vehicles]);
 useEffect(()=>{Promise.all(['/assets/models/truck.glb','/assets/models/ambulance.glb'].map(p=>fetch(p,{method:'HEAD'}).then(r=>r.ok&&!(r.headers.get('content-type')||'').includes('html')))).then(r=>setModelAvailable(r.every(Boolean))).catch(()=>{});},[]);
 const layers=useMemo(()=>[new PathLayer({id:'mission-glow',data:showRoutes?paths:[],getPath:d=>d.path,getColor:[34,211,238,25],getWidth:12,widthUnits:'pixels'}),new PathLayer({id:'missions',data:showRoutes?paths:[],getPath:d=>d.path,getColor:d=>d.id==='T-07'?[239,68,68,200]:[34,211,238,150],getWidth:2,widthUnits:'pixels',rounded:true}),...(models&&modelAvailable?(['truck','ambulance'] as const).map(type=>new ScenegraphLayer({id:'vehicles-'+type,data:vehicles.filter(v=>v.type===type),scenegraph:`/assets/models/${type}.glb`,getPosition:d=>[d.position[0],d.position[1],10] as [number,number,number],getOrientation:[0,90,90],sizeScale:250,_lighting:'pbr',pickable:true,onClick:info=>info.object&&onSelect(info.object.id)})):[])],[paths,vehicles,showRoutes,models,modelAvailable,onSelect]);
 return <div className="map-shell"><div className="map-grid"/>{!error?<DeckGL viewState={view} onViewStateChange={({viewState})=>setView(viewState as typeof INITIAL)} controller layers={layers}><Map ref={map} mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json" onError={e=>{if(e.error.message.includes('WebGL'))setError(true);}} attributionControl={{compact:true}}>
 {depots.map(d=><Marker key={d.name} longitude={d.position[0]} latitude={d.position[1]}><div className="depot-pin"><span/><b>{d.name}</b></div></Marker>)}
 {(!models||!modelAvailable)&&vehicles.map(v=><Marker key={v.id} longitude={v.position[0]} latitude={v.position[1]} anchor="center"><button aria-label={`Inspecter ${v.id}`} className={`vehicle-marker ${v.status} ${focusId===v.id?'focused':''}`} onClick={()=>onSelect(v.id)}>{v.type==='truck'?<Truck size={17}/>:<Plus size={19}/>}<span>{v.id}</span></button></Marker>)}<NavigationControl position="bottom-right" showCompass={false}/></Map></DeckGL>:<div className="map-unavailable"><MapPin/><h3>Carte indisponible</h3><p>Le rendu WebGL n’est pas disponible. Sélectionnez un véhicule dans la flotte pour consulter son diagnostic.</p></div>}
 <div className="map-top"><div className="map-kicker"><span className="live-dot"/> VUE TERRAIN <span className="slash">/</span> MAROC</div><div className="map-actions"><button title="Recentrer la flotte" onClick={()=>{setView(INITIAL);map.current?.flyTo({...INITIAL,duration:1200});}}><LocateFixed size={17}/></button><button title="Afficher les itinéraires" className={showRoutes?'active':''} onClick={()=>setShowRoutes(!showRoutes)}><Layers size={17}/></button><button title="Vue 2D / 3D" onClick={()=>setView(v=>({...v,pitch:v.pitch?0:50}))}><Maximize2 size={17}/></button></div></div>
 <div className="map-title"><span className="eyebrow">L’INTELLIGENCE EN MOUVEMENT</span><h2>Chaque trajet.<br/><span>Une longueur d’avance.</span></h2><p><Activity size={13}/> Télémétrie, décisions et opérations. Connectées.</p></div>
 <div className="map-bottom"><div className="map-legend"><span><i className="ok"/>En mission</span><span><i className="warn"/>À surveiller</span><span><i className="fail"/>Incident</span></div><div className="map-coordinates">32°59′ N &nbsp; 07°06′ W <span>WGS 84</span></div></div>
 {modelAvailable&&<button className="model-toggle" onClick={()=>setModels(!models)}>{models?'Marqueurs':'Véhicules 3D'}</button>}
 </div>;
}
