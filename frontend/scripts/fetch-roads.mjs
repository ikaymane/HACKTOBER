import {mkdir,writeFile} from 'node:fs/promises';
const missions={
 'M-107':[[-7.59,33.57],[-7.735,32.492],[-7.98,31.63]],
 'M-103':[[-6.84,34.02],[-7.167,33.756],[-7.59,33.57]],
 'M-112':[[-7.59,33.57],[-7.058,32.838],[-6.36,32.34]],
 'M-104':[[-7.98,31.63],[-8.139,31.248],[-9.6,30.42]],
 'M-101':[[-6.84,34.02],[-6.125,33.849],[-5,34.03]],
 'M-109':[[-6.84,34.02],[-6.372,34.619],[-5.81,35.76]],
 'M-102':[[-7.59,33.57],[-8.029,33.324],[-8.5,33.24]],
 'M-105':[[-5,34.03],[-5.307,33.904],[-5.55,33.89]]
};
const roads={},positions={};
for(const [id,points] of Object.entries(missions)){
 const result=await fetch(`https://router.project-osrm.org/route/v1/driving/${points.map(p=>p.join(',')).join(';')}?overview=full&geometries=geojson`,{signal:AbortSignal.timeout(30000)}).then(r=>r.json());
 if(result.code!=='Ok')throw new Error(`Routing failed: ${id}`);
 roads[id]=result.routes[0].geometry.coordinates;
 positions[id]=result.waypoints[1].location;
 console.log(id,roads[id].length,'road coordinates');
}
await mkdir('public/data',{recursive:true});
await writeFile('public/data/roads.json',JSON.stringify(roads));
await writeFile('public/data/positions.json',JSON.stringify(positions));
await writeFile('src/road-positions.json',JSON.stringify(positions));
