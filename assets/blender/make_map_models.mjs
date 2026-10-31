// Builds the light models the fleet map draws: body shell + simplified wheels, no engine bay, no animation.
// The full .glb files stay for the 3D inspector.
//
// Setup, anywhere outside the repo: npm i @gltf-transform/core@4 @gltf-transform/functions@4 meshoptimizer@0.22
// Run from that folder: node <repo>/assets/blender/make_map_models.mjs <repo>/frontend/public/models
import { NodeIO } from "@gltf-transform/core";
import { KHRONOS_EXTENSIONS } from "@gltf-transform/extensions";
import { dedup, flatten, join, prune, simplify, weld } from "@gltf-transform/functions";
import { MeshoptSimplifier } from "meshoptimizer";
import path from "node:path";

const dir = process.argv[2];
const KEEP = new Set(["body", "tires"]);
const io = new NodeIO().registerExtensions(KHRONOS_EXTENSIONS);

for (const type of ["truck", "ambulance"]) {
  const doc = await io.read(path.join(dir, `${type}.glb`));
  const root = doc.getRoot();
  root.listAnimations().forEach((a) => a.dispose());
  for (const node of root.listNodes()) {
    const zone = node.getExtras().zone;
    if (zone && !KEEP.has(zone)) node.dispose();
  }
  await doc.transform(
    prune(),
    weld(),
    simplify({ simplifier: MeshoptSimplifier, ratio: 0.3, error: 0.01 }),
    dedup(),
    flatten(),
    join({ keepNamed: false }),
    prune(),
  );
  const tris = root.listMeshes().flatMap((m) => m.listPrimitives()).reduce((s, p) => s + p.getIndices().getCount() / 3, 0);
  await io.write(path.join(dir, `${type}-map.glb`), doc);
  console.log(type, { nodes: root.listNodes().length, primitives: root.listMeshes().flatMap((m) => m.listPrimitives()).length, tris });
}
