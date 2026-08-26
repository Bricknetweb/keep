# DefinityOS — the engine (not a second competing OS product)

DefinityOS is the engine. BrickNet.xcodeproj is DefinityOS. Latin is the vis-buffer draw path inside DefinityOS, not a different product and not a replacement name. Anatomy viewer is DefinityOS content (entities/systems as layers).

DefinityOS is this engine, not a separate OS we also ship.

Headset demo this month on the on-site Vision Pro: Xcode 26, BrickNet.xcodeproj (DefinityOS), executable BrickNet.app, destination the Vision Pro (not Simulator if possible). Product → Test / scripts/test-latin.sh. Latin is how it draws: CompositorLayer / LayerRenderer, vis-buffer, foveation, occlusion.

Keep: Rasterize instance/triangle IDs first (rg32Uint, reverse-Z). Shade only winning / visible pixels. Foveation on. Real-world occlusion via scene reconstruction depth before vis. LatinControlNet-style control pack (IDs, visibility, foveation, occlusion) is the render control path.

Steal RealityKit entities, anchors, mesh-occlusion components. Do not switch to RealityKit’s renderer.

Anatomy viewer is DefinityOS content, not Comfy/3090 stills. Jon wants a detailed anatomy app: complete human body, all parts/systems, pick a part. That is a DefinityOS ImmersiveSpace content layer (entities + systems as layers: bone, muscle, organs). Latin vis-buffer so hidden tissue is not shaded. Medical/educational. Not a 3090 image farm. Engine on the headset comes first. Anatomy content after ImmersiveSpace actually runs. Slack stays PG, no stills.

Out of scope: Hermes / Comfy / 3090, Cast stills, Furniture Pin, ACP (hermes acp is editor talk, not the headset demo).

Pass: ImmersiveSpace up, sharp where you look, occluders and real-world mesh unshaded, no hitch-stutter.
