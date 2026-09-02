# 3D Effendi avatar

The assistant uses a local Three.js renderer and a single GLB character. Runtime use does not require Blender or an internet connection.

## Files

- `frontend/models/effendi-cartoon.glb` — model loaded by the browser.
- `frontend/models/effendi-cartoon.blend` — editable Blender source.
- `frontend/effendi-3d.js` — renderer, motion state machine, turn cycle, blinking and speech animation.
- `scripts/build_effendi_3d.py` — reproducible Blender model generator.
- `frontend/vendor/three` — local Three.js runtime.

## Rebuild

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --background `
  --python scripts\build_effendi_3d.py
```

The web renderer observes `#ai-character[data-state]`. Supported states are `idle`, `greeting`, `thinking`, and `speaking`. A full 360-degree turn is inserted into the autonomous 24-second motion cycle. The 2D puppet remains in the page as an automatic fallback when WebGL or the GLB cannot load.
