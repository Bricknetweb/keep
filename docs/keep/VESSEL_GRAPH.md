# DefinityOS — vessel graph layer (circulatory + lymphatic)

Definity is the anatomy product. DefinityOS is the engine. Latin is the vis-buffer draw path.
This layer is how blood and lymph move in the headset without a Comfy movie farm.

## Job

Show arteries, veins, and lymph as a living graph you can peel, isolate, and grab.
Sharp where the eyes are. Hidden tubes are not shaded. Flow is simulated, not filmed.

## Non-goals

- No baked MP4 / Comfy turntables as the source of truth
- No RealityKit renderer swap
- No Navier–Stokes / full CFD on device or on the 3090
- No generating the whole atlas as stills before the headset demo
- Slack stays PG; no anatomy stills there

## Data

Store a directed graph, not a pile of meshes.

- Node: junction or valve. Position, laterality, optional valve direction.
- Edge: vessel segment. Centerline (polyline), radius as a function of arc length, system tag (artery | vein | lymph), stable ID (FMA / Terminologia Anatomica), parent edge, body (the variation set, not a new app).
- Clock: one shared physiology time. Heart phase drives arterial pulse. Lymph is slower and can later take a muscle-pump term.

One mesh per organ stays in the rest of Definity. Vessels do not. They are swept at draw time from the graph so LOD and foveation can change tessellation every frame.

## Latin draw

1. Scene-reconstruction depth first (existing occlusion).
2. Vis-buffer pass: rasterize instance IDs for tube segments in view. Reverse-Z. rg32Uint. Miss = not shaded.
3. Foveation rate map: high tessellation / true tubes in the fovea. Periphery is a cheap capsule or impostor. Same instance ID so picking still works.
4. Shade winners only. Flow color / pulse is a cheap attribute on the winning pixels, not a second geometry pass over the whole body.
5. Particle tracers (optional) only on the selected subgraph and only in the fovea.

If a tube is behind an organ or behind the real-world mesh, it must not shade.

## Flow

1D along the centerline. Prescribed waveforms, not fluid solve.
- Arteries: pulsatile, heart clock, Windkessel-style decay down the tree.
- Veins: slower, toward the heart.
- Lymph: slow, valves as one-way nodes.
Selecting an edge isolates upstream / downstream by walking the graph. Isolation is a visibility flag in the vis-buffer, not a new bake.

## Hands

Pinch an edge to select. Drag along the centerline to follow flow. Peel a system by hiding tags. Search by name highlights IDs.

## First slice

Heart clock, aorta plus a small named arterial tree, one venous return path, one lymph trunk, Latin vis-buffer + foveation + occlusion, pinch-select an edge. Whole-body graphs after ImmersiveSpace runs on the headset.

## Pass / fail

Pass: aorta pulse sharp in the fovea, occluded tubes do not light up, pinch selects the right ID, periphery stays cheap.
Fail: a video, a RealityKit draw, or a 3090 still sequence standing in for the graph.
