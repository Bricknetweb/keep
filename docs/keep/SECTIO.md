# DefinityOS — sectio / Aspectus (planar cut, not a new mesh)

Definity is the product. DefinityOS is the engine. Latin is the vis-buffer draw path.

Aspectus is the view wheel. Flattening general view is a clip plane (sectio), not a sliced mesh and not a VesselGraph change. Do not touch the 3090.

## Latin → plane

Body frame: +Y up, +Z anterior, origin at corpus.

- planum sagittale / medianum — normal +X
- planum coronale / frontale — normal +Z
- planum transversum / horizontale — normal +Y
- sectio = the cut those plana make
- transversus = the transverse stop on the wheel
- aspectus = the view wheel; aspectus generalis flattens to the current planum

## Bind

1. One plane (point + normal). Peel = slide the point along the normal.
2. Flatten = enable clip. Do not shade fragments with dot(P - point, normal) < 0. Same rule as a vis-buffer miss. Optional thin slab: |dot| < thickness.
3. RealityView proto: ShaderGraph / Metal clip, not a new mesh.
4. Latin vis-buffer: reject those samples before shade. Hidden side stays unshaded.
5. Wheel stops: sagittalis / coronalis / transversa pick the normal. Pinch-zoom stays on the body. Tap still picks. Do not bind pinch to isolate.

## Pass / fail

Pass: named planum flattens the live figure, occluded / clipped side does not light up, pick still works.
Fail: a pre-sliced mesh, a RealityKit renderer swap, or a 3090 still standing in for the cut.
