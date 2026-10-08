# Maya VAT Encoder
[![Maya](https://img.shields.io/badge/Maya-2022+-00B4FF?style=flat-square&logo=autodesk)](https://www.autodesk.com/products/maya)
[![Python](https://img.shields.io/badge/Python-Pure-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.1.0-blue?style=flat-square)]()

🌐 English | [한국어](README.ko.md) · 🔗 **[Project Page](https://5hyuns.github.io/Maya-Vertex-Animation-Texture-Baker/)** · ⬇️ **[Download](https://github.com/5hyuns/Maya-Vertex-Animation-Texture-Baker/releases/latest)**

**Vertex Animation Texture Encoder for Maya** - Convert skinned meshes, deformers, and anything that moves into VAT!

A free, open-source **Maya VAT baker** — bake skeletal (skinCluster), blend shape, and deformer animation into **vertex animation textures** directly inside Autodesk Maya, **no Houdini required**. Outputs a position texture, optional normal texture, bounds JSON and a proxy FBX that you can play back with a vertex shader in real-time engines (Unreal Engine, Unity, PlayCanvas, three.js / WebGL) — ideal for crowds and large numbers of animated instances.

![Demo](https://github.com/user-attachments/assets/e7b50f13-9a43-4ebe-9f14-aee65729311b)
<sub>*Astro Bot*™ © Sony Interactive Entertainment. Unofficial fan remake.</sub>

## Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Options](#options)
- [Output](#output)
- [Example Output](#example-output)
- [Texture Format](#texture-format)
- [Playing VAT in an Engine](#playing-vat-in-an-engine)
- [Python API](#python-api)
- [Notes](#notes)

---

## Features

- **Zero Dependencies** - Pure Python, no additional installation required
- **Object/World Space** - Choose coordinate space for your needs
- **Auto VAT UV Generation** - Automatic UV assignment based on vertex ID
- **Skip First Frame** - Option to exclude T-Pose
- **One-Click Export** - Batch generation of PNG + JSON + FBX

---

## Installation

1. Download the [latest release](https://github.com/5hyuns/Maya-Vertex-Animation-Texture-Baker/releases/latest) (or *Code > Download ZIP*) and extract it.
2. **Rename** the extracted folder (e.g. `Maya-Vertex-Animation-Texture-Baker-main`) to **`maya_vat`** — the folder name is the Python package name.
3. Copy the `maya_vat` folder to your Maya scripts path:
   ```
   # Windows
   C:/Users/<username>/Documents/maya/<version>/scripts/

   # macOS
   ~/Library/Preferences/Autodesk/maya/<version>/scripts/

   # Linux
   ~/maya/<version>/scripts/
   ```
4. Restart Maya, then run the Quick Start code in the Script Editor.

**Requirements:** Maya 2022 or later (PySide2 / PySide6). The FBX plugin (`fbxmaya`) is needed only for mesh export.

---

## Quick Start

```python
import maya_vat
maya_vat.show()
```

1. Select the animated mesh and click `<<` next to **Target Mesh**.
2. Set the **Frame Range** (`Timeline` fills it from the timeline), **Coordinate Space** and options.
3. Choose an **Output Directory** and click **Encode VAT**.

---

## Options

![UI](https://github.com/user-attachments/assets/dd124ec8-42ee-4941-a186-06b7c061b25c)

### Coordinate Space

| Option | Use Case |
|--------|----------|
| **Object (Local)** | Character needs runtime movement/rotation **(Recommended)** |
| **World** | Fixed transform (background objects, etc.) |

### Skip First Frame

| Situation | Setting |
|-----------|---------|
| First frame is T-Pose/Bind Pose | **ON** |
| Animation starts from first frame | **OFF** |

With this ON, the first frame is still used as the proxy (rest) pose but is left out of the texture, so the texture has one fewer row.

### Other Options

| Option | Description |
|--------|-------------|
| **Export Normals (separate texture)** | Also writes `<mesh>_vnrm.png` |
| **Export Mesh (FBX)** | Exports the proxy mesh at the first frame |
| **UV Set Name** / **Overwrite if exists** | Name of the VAT UV set to create. With overwrite on, an existing set is deleted and regenerated. **Create VAT UV** creates only the UV set. |

---

## Output

```
output_dir/
+-- <mesh>_vat/
    +-- <mesh>_vat.png       # Position delta texture
    +-- <mesh>_vnrm.png      # Normal texture (optional)
    +-- <mesh>_remap.json    # Min/max bounds for decoding
    +-- <mesh>.fbx           # Proxy mesh (optional)
```

`:` and `|` in mesh names are replaced with `_`.

---

## Example Output

These are the real textures baked from the Astro Bot mesh in the demo above: **2253 vertices × 524 frames**, so each texture is 2253 × 524 px (the previews below are resized to 1024 px wide).

**Position texture** (`_vat.png`)

![Example position texture](docs/assets/example_vat.png)

**Normal texture** (`_vnrm.png`)

![Example normal texture](docs/assets/example_vnrm.png)

How to read them:

- **One column = one vertex** (column x = vertex ID). **One row = one frame** (the top row is the first frame).
- **Position texture:** each pixel is the vertex's XYZ offset from the proxy pose, remapped to RGB using the min/max in the JSON. Calm, uniform areas are vertices that barely move. Saturated vertical bands are parts that move a lot, such as the arms and legs. Horizontal bands are frames where the whole body moves together.
- **Normal texture:** each pixel is the vertex normal, remapped from -1..1 to 0..255. It changes with the surface direction, so it is far more colorful than the position texture.
- Neighboring columns look similar because vertex IDs tend to follow the modeling order, so nearby vertices often belong to the same body part.

---

## Texture Format

```
Width  = Number of vertices
Height = Number of frames

        V0    V1    V2    V3   ...   Vn
      +-----+-----+-----+-----+---+-----+
  F0  | RGB | RGB | RGB | RGB |...| RGB |  <- Row 0
  F1  | RGB | RGB | RGB | RGB |...| RGB |  <- Row 1
  F2  | RGB | RGB | RGB | RGB |...| RGB |  <- Row 2
   :  |     |     |     |     |   |     |
      +-----+-----+-----+-----+---+-----+

Pixel RGB = (deltaX, deltaY, deltaZ) normalized to 0-255
```

| Item | Value |
|------|-------|
| Format | 8-bit RGB PNG |
| Position | `delta = position(frame) - position(proxy)`, remapped per axis with a single global min/max |
| Normal | -1..1 → 0..255, **X axis negated** (PlayCanvas compatibility) |
| VAT UV | `U = (vertex_id + 0.5) / vertex_count`, `V` = center of the first row |
| Proxy | Mesh pose at the first frame of the range |

### `<mesh>_remap.json`

```json
{
    "position": {
        "min": [-2.5, -1.0, -0.5],
        "max": [3.2, 4.5, 1.2],
        "frames": 60,
        "vertices": 1024,
        "space": "object"
    },
    "normal": {
        "min": [-1, -1, -1],
        "max": [1, 1, 1]
    }
}
```

`normal` is present only when normals are exported.

---

## Playing VAT in an Engine

In the vertex shader, sample the texture with the `VAT_UV` set and add the decoded offset to the proxy position.

```hlsl
// vatUV        : VAT_UV of the vertex
// frame        : current frame, 0 .. frames-1
// boundsMin/Max: position.min / position.max from remap.json
float2 uv     = float2(vatUV.x, (frame + 0.5) / frames);
float3 enc    = tex2Dlod(_VatPosition, float4(uv, 0, 0)).rgb;
float3 offset = lerp(boundsMin, boundsMax, enc);
float3 posOS  = proxyPositionOS + offset;

float3 n = tex2Dlod(_VatNormal, float4(uv, 0, 0)).rgb * 2 - 1;
n.x = -n.x;   // Undo the X flip (skip this if your engine expects the PlayCanvas convention)
```

Texture import settings:

- **Point / Nearest** filtering, **no mipmaps**
- **Linear** (turn sRGB off), **no compression**
- If your engine loads textures with V flipped, flip V (for example `1 - v`).

8-bit precision is `(max - min) / 255` per axis, so larger motion ranges give coarser steps.

---

## Python API

### VAT Encoding

```python
from maya_vat import core, utils

result = core.encode_vat(
    mesh_name="pCube1",
    output_dir="C:/output",
    frame_start=0,
    frame_end=60,
    include_normals=True,
    export_mesh=True,
    use_world_space=False,      # Object Space recommended
    uv_set_name="VAT_UV",
    force_uv=False,
    skip_first_frame=True       # Exclude T-Pose
)

# Returns
# {
#     "success": True,
#     "png_path": "C:/output/pCube1_vat/pCube1_vat.png",
#     "json_path": "C:/output/pCube1_vat/pCube1_remap.json",
#     "fbx_path": "C:/output/pCube1_vat/pCube1.fbx",
#     "width": 8,
#     "height": 60,
#     ...
# }
```

### Standalone VAT UV Generation

```python
uv_result = utils.create_vat_uv(
    mesh_name="pCube1",
    num_verts=1024,
    num_frames=60,
    uv_set_name="VAT_UV",
    force=False  # Skip if exists
)

# Check if UV set exists
exists = utils.uv_set_exists("pCube1", "VAT_UV")
```

### Package Layout

```
maya_vat/
+-- __init__.py      # Package entry point (show, encode_vat)
+-- core.py          # VAT encoding logic, PNG writer
+-- utils.py         # Maya API utilities, VAT UV creation
+-- exporter.py      # FBX/OBJ export
+-- ui.py            # PySide2/6 UI
```

---

## Notes

### Object Space vs World Space

| Situation | Object | World |
|-----------|:------:|:-----:|
| Runtime movement/rotation | O | X |
| Root motion animation | O | X (double transformation) |
| Fixed transform | O | O |

### UV Sets

- Avoid name conflicts with existing UV sets.
- Checking `Overwrite if exists` deletes and regenerates the existing UV set.
- Verify in UV Editor > UV Sets.

### FBX Export

- Skinning-free (VAT replaces skeletal deformation)
- Excludes blend shapes
- Excludes animation (first frame only)

### Limitations

- The vertex count and order must stay the same for the whole frame range (topology-changing animation is not supported).
- Texture width equals the vertex count. Check your target engine's maximum texture size for high-poly meshes.

---

## License

[MIT License](LICENSE)

---

**Contact:** 555hyuns@gmail.com
