# DefinityOS — distilled mockup, not a second OS

Working name DefinityOS was a spatial-OS mockup. It does not ship as an OS.

What ships this month on the on-site Vision Pro: BrickNet Latin ImmersiveSpace (vis-buffer).

Anatomy viewer is Latin content, not DefinityOS, not Comfy/3090 stills. Jon wants a detailed anatomy app: complete human body, all parts/systems, pick a part. That is a Latin ImmersiveSpace content layer (entities + systems as layers: bone, muscle, organs). Vis-buffer so hidden tissue is not shaded. Medical/educational. Not a 3090 image farm. Not DefinityOS (DefinityOS does not ship as an OS). Engine on the headset comes first. Anatomy content after ImmersiveSpace actually runs. Slack stays PG, no stills.

Keep: CompositorLayer / LayerRenderer. Rasterize instance/triangle IDs first (rg32Uint, reverse-Z). Shade only winning / visible pixels. Foveation on. Real-world occlusion via scene reconstruction depth before vis. LatinControlNet-style control pack (IDs, visibility, foveation, occlusion) is the render control path.

Steal RealityKit entities, anchors, mesh-occlusion components. Do not switch to RealityKit’s renderer.

Run: Xcode 26, BrickNet.xcodeproj, executable BrickNet.app, destination the Vision Pro (not Simulator if possible). Product → Test / scripts/test-latin.sh.

Out of scope: Hermes / Comfy / 3090, Cast stills, Furniture Pin, ACP (hermes acp is editor talk, not the headset demo).

Pass: ImmersiveSpace up, sharp where you look, occluders and real-world mesh unshaded, no hitch-stutter.
