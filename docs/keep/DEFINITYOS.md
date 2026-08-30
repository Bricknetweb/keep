# DefinityOS

- Definity = the product: the anatomy viewer on the Vision Pro.
- DefinityOS = the engine (BrickNet.xcodeproj). This file names the engine.
- Latin = how it draws (vis-buffer / CompositorLayer).

Everything else is in service of Definity. Month still starts with ImmersiveSpace actually running on the headset. Anatomy content after that.

Vessel graph layer: VESSEL_GRAPH.md.

Headset demo this month on the on-site Vision Pro: Xcode 26, BrickNet.xcodeproj (DefinityOS), executable BrickNet.app, destination the Vision Pro (not Simulator if possible). Product → Test / scripts/test-latin.sh. Latin is how it draws: CompositorLayer / LayerRenderer, vis-buffer, foveation, occlusion.

Keep: Rasterize instance/triangle IDs first (rg32Uint, reverse-Z). Shade only winning / visible pixels. Foveation on. Real-world occlusion via scene reconstruction depth before vis. LatinControlNet-style control pack (IDs, visibility, foveation, occlusion) is the render control path.

Steal RealityKit entities, anchors, mesh-occlusion components. Do not switch to RealityKit’s renderer.

Definity is the anatomy viewer on the Vision Pro, running on DefinityOS, drawn with Latin. Jon wants a detailed anatomy app: complete human body, all parts/systems, pick a part. That is Definity content (entities + systems as layers: bone, muscle, organs). Latin vis-buffer so hidden tissue is not shaded. Medical/educational. Not a 3090 image farm. ImmersiveSpace on the headset comes first. Anatomy content after ImmersiveSpace actually runs. Slack stays PG, no stills.

Out of scope: Hermes / Comfy / 3090, Cast stills, Furniture Pin, ACP (hermes acp is editor talk, not the headset demo).

Pass: ImmersiveSpace up, sharp where you look, occluders and real-world mesh unshaded, no hitch-stutter.
