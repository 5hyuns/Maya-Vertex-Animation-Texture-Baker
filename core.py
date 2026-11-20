# -*- coding: utf-8 -*-
"""
Maya VAT - Core VAT Encoding Logic
"""

import maya.cmds as cmds
import os
import struct
import zlib

from . import utils


# Target engines. Each one stores deltas and normals in the axes and units
# that the engine's FBX importer gives the proxy mesh, so the decoded offset
# can be added to the imported vertex position without any swizzle.
#   playcanvas: Maya axes, Maya internal units (cm); normal X negated
#   unreal:     Z-up, left-handed, centimeters.
#               The FBX is written Y-up (a Z-up scene is rotated to Y-up on
#               export). The importer turns it into Z-up with -Y front, then
#               negates Y: Y-up scene -> (x, z, y), Z-up scene -> (x, -y, z)
#               (assumes the default import option Force Front XAxis = off)
#   unity:      Y-up, left-handed, meters.
#               The importer negates X and converts units -> (-x, y, z) * 0.01.
#               It keeps the object transform (and, for a Z-up scene, the
#               up-axis rotation) on the GameObject, so mesh-local axes follow
#               the Maya object axes in both Y-up and Z-up scenes.
TARGET_ENGINES = ('playcanvas', 'unreal', 'unity')

# Maya's internal unit (what the API returns) is centimeters.
# Unity's importer converts the file to meters with Convert Units on.
_UNITY_SCALE = 0.01


def _swizzle(v, target_engine, z_up):
    x, y, z = v
    if target_engine == 'unreal':
        return (x, -y, z) if z_up else (x, z, y)
    if target_engine == 'unity':
        return (-x, y, z)
    return (x, y, z)


def to_engine_position(v, target_engine, z_up=False):
    """Convert a Maya-space position delta to the target engine's axes/units"""
    x, y, z = _swizzle(v, target_engine, z_up)
    if target_engine == 'unity':
        return (x * _UNITY_SCALE, y * _UNITY_SCALE, z * _UNITY_SCALE)
    return (x, y, z)


def to_engine_normal(n, target_engine, z_up=False):
    """Convert a Maya-space normal to the target engine's axes"""
    if target_engine == 'playcanvas':
        # PlayCanvas convention: X negated
        return (-n[0], n[1], n[2])
    # Axis swaps and mirrors are orthogonal, so normals use the same mapping
    return _swizzle(n, target_engine, z_up)


def encode_vat(mesh_name, output_dir, frame_start=None, frame_end=None,
               include_normals=False, export_mesh=True, use_world_space=True,
               uv_set_name='VAT_UV', force_uv=False, skip_first_frame=False,
               target_engine='playcanvas'):
    """
    Main VAT encoding function

    Args:
        mesh_name: Name of the mesh to encode
        output_dir: Output directory path
        frame_start: Start frame (default: timeline start)
        frame_end: End frame (default: timeline end)
        include_normals: Whether to create separate normal texture
        export_mesh: Whether to export FBX
        use_world_space: If True, use world space (kWorld).
                        If False, use object/local space (kObject).
                        Recommended: False for characters with runtime movement.
        uv_set_name: Name of the VAT UV set (default: VAT_UV)
        force_uv: If True, overwrite existing UV set. If False, skip if exists.
        skip_first_frame: If True, use first frame only as proxy reference.
                         The first frame will NOT be included in the texture.
                         Useful when first frame is T-Pose or bind pose.
        target_engine: 'playcanvas' (default), 'unreal' or 'unity'.
                       Sets the axes and units of the stored deltas and
                       normals to match the engine's FBX import.

    Returns:
        dict with results info
    """
    # Validate mesh
    if not cmds.objExists(mesh_name):
        raise ValueError("Mesh '{}' not found".format(mesh_name))

    if target_engine not in TARGET_ENGINES:
        raise ValueError("Unknown target_engine '{}'. Use one of: {}".format(
            target_engine, ", ".join(TARGET_ENGINES)))

    z_up = cmds.upAxis(q=True, axis=True) == 'z'

    # Get frame range
    if frame_start is None or frame_end is None:
        fs, fe = utils.get_frame_range()
        frame_start = frame_start or fs
        frame_end = frame_end or fe

    total_frames = frame_end - frame_start + 1
    num_verts = utils.get_vertex_count(mesh_name)

    # Validate skip_first_frame
    if skip_first_frame and total_frames < 2:
        raise ValueError("Skip First Frame requires at least 2 frames")

    # Texture frames (exclude first frame if skip_first_frame)
    num_frames = total_frames - 1 if skip_first_frame else total_frames
    texture_start_frame = frame_start + 1 if skip_first_frame else frame_start

    # Texture is num_verts x num_frames. Many WebGL/mobile devices stop at
    # 8192 px per side; desktop Unreal/Unity stop at 16384.
    max_side = max(num_verts, num_frames)
    if max_side > 8192:
        cmds.warning(
            "VAT texture will be {} x {} px. Sides over 8192 px fail on many "
            "WebGL/mobile devices; over 16384 px fail in Unreal and Unity."
            .format(num_verts, num_frames))

    # The normal texture holds one normal per vertex, so a vertex on a hard
    # edge gets the average of its face normals and renders smooth.
    if include_normals:
        hard_edges = utils.count_hard_edges(mesh_name)
        if hard_edges:
            cmds.warning(
                "'{}' has {} hard edge(s). The normal texture stores one normal "
                "per vertex, so hard edges will look smooth in the engine."
                .format(mesh_name, hard_edges))

    # Create output directory
    base_name = mesh_name.replace(':', '_').replace('|', '_')
    object_dir = os.path.join(output_dir, "{}_vat".format(base_name))
    utils.ensure_directory(object_dir)

    # Store original frame
    original_frame = utils.get_current_frame()

    # Step 1: Get proxy positions (first frame)
    utils.set_current_frame(frame_start)
    proxy_positions = utils.get_vertex_positions(mesh_name, use_world_space)

    # Unreal bakes the object's transform into static mesh vertices on import,
    # so object-space data goes through the proxy-pose transform (no
    # translation) to match the imported mesh. World-space data already does.
    bake_matrix = None
    if target_engine == 'unreal' and not use_world_space:
        bake_matrix = utils.get_world_matrix(mesh_name)
        bake_nrm_matrix = utils.normal_matrix(bake_matrix)
    world_normals = target_engine == 'unreal' and use_world_space

    # Step 2: Collect all frame positions and calculate deltas
    all_deltas = {}
    all_normals = {} if include_normals else None

    for frame in range(frame_start, frame_end + 1):
        utils.set_current_frame(frame)
        positions = utils.get_vertex_positions(mesh_name, use_world_space)

        # Calculate delta from proxy
        deltas = []
        for i, pos in enumerate(positions):
            delta = (
                pos[0] - proxy_positions[i][0],
                pos[1] - proxy_positions[i][1],
                pos[2] - proxy_positions[i][2]
            )
            if bake_matrix is not None:
                delta = utils.transform_vector(delta, bake_matrix)
            deltas.append(to_engine_position(delta, target_engine, z_up))

        all_deltas[frame] = deltas

        if include_normals:
            normals = utils.get_vertex_normals(mesh_name, world_normals)
            if bake_matrix is not None:
                normals = [utils.transform_normal(n, bake_nrm_matrix) for n in normals]
            all_normals[frame] = normals

    # Step 3: Find min/max for remapping
    min_x, min_y, min_z, max_x, max_y, max_z = utils.find_min_max(all_deltas)

    # Step 4: Create image data (width=num_verts, height=num_frames)
    width = num_verts
    height = num_frames

    # RGB image data
    image_data = []

    # Start from texture_start_frame (skips first frame if skip_first_frame is True)
    for frame in range(texture_start_frame, frame_end + 1):
        row = []
        deltas = all_deltas[frame]

        for delta in deltas:
            r = utils.remap_value(delta[0], min_x, max_x, 0, 255)
            g = utils.remap_value(delta[1], min_y, max_y, 0, 255)
            b = utils.remap_value(delta[2], min_z, max_z, 0, 255)
            row.append((r, g, b))

        image_data.append(row)

    # Step 5: Save PNG
    png_path = os.path.join(object_dir, "{}_vat.png".format(base_name))
    save_png(image_data, width, height, png_path)

    # Step 6: Save normal texture if needed
    if include_normals:
        normal_image_data = []
        # Start from texture_start_frame (same as position texture)
        for frame in range(texture_start_frame, frame_end + 1):
            row = []
            normals = all_normals[frame]
            for normal in normals:
                # Normals are -1 to 1, remap to 0-255
                nx, ny, nz = to_engine_normal(normal, target_engine, z_up)
                r = utils.remap_value(nx, -1, 1, 0, 255)
                g = utils.remap_value(ny, -1, 1, 0, 255)
                b = utils.remap_value(nz, -1, 1, 0, 255)
                row.append((r, g, b))
            normal_image_data.append(row)

        normal_png_path = os.path.join(object_dir, "{}_vnrm.png".format(base_name))
        save_png(normal_image_data, width, height, normal_png_path)

    # Step 7: Save JSON metadata
    json_data = {
        "target": target_engine,
        "position": {
            "min": [min_x, min_y, min_z],
            "max": [max_x, max_y, max_z],
            "frames": num_frames,
            "vertices": num_verts,
            "space": "world" if use_world_space else "object"
        }
    }

    if include_normals:
        json_data["normal"] = {
            "min": [-1, -1, -1],
            "max": [1, 1, 1]
        }

    json_path = os.path.join(object_dir, "{}_remap.json".format(base_name))
    utils.write_json(json_data, json_path)

    # Step 8: Create VAT UV at the proxy pose. On a mesh with animated
    # deformers, UV edits only hold at the frame they were made on, so they
    # must be made on the same frame the FBX is exported at.
    utils.set_current_frame(frame_start)
    uv_result = utils.create_vat_uv(mesh_name, num_verts, num_frames, uv_set_name, force_uv)

    # Step 9: Export mesh if requested
    fbx_path = None
    if export_mesh:
        # Set frame to frame_start for correct proxy mesh pose
        utils.set_current_frame(frame_start)
        from . import exporter
        # Engine targets write the FBX in centimeters, the same unit as the
        # stored deltas, whatever the Maya working unit is
        fbx_unit = None if target_engine == 'playcanvas' else 'cm'
        fbx_path = exporter.export_fbx(mesh_name, object_dir, base_name, fbx_unit)

    # Restore original frame
    utils.set_current_frame(original_frame)

    return {
        "success": True,
        "png_path": png_path,
        "json_path": json_path,
        "fbx_path": fbx_path,
        "width": width,
        "height": height,
        "num_verts": num_verts,
        "num_frames": num_frames,
        "total_frames": total_frames,
        "skip_first_frame": skip_first_frame,
        "space": "world" if use_world_space else "object",
        "target_engine": target_engine,
        "uv_set_name": uv_set_name,
        "uv_created": uv_result.get('created', False),
        "uv_skipped": uv_result.get('skipped', False)
    }


def save_png(image_data, width, height, filepath):
    """
    Save image data as PNG (pure Python, no external dependencies)

    Args:
        image_data: 2D list of (R, G, B) tuples
        width: Image width
        height: Image height
        filepath: Output path
    """
    def write_chunk(f, chunk_type, data):
        """Write PNG chunk"""
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xffffffff
        f.write(struct.pack('>I', len(data)))
        f.write(chunk)
        f.write(struct.pack('>I', crc))

    with open(filepath, 'wb') as f:
        # PNG signature
        f.write(b'\x89PNG\r\n\x1a\n')

        # IHDR chunk
        ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        write_chunk(f, b'IHDR', ihdr_data)

        # IDAT chunk (image data)
        raw_data = b''
        for y in range(height):
            raw_data += b'\x00'  # Filter type: None
            for x in range(width):
                r, g, b = image_data[y][x]
                raw_data += struct.pack('BBB', r, g, b)

        compressed = zlib.compress(raw_data, 9)
        write_chunk(f, b'IDAT', compressed)

        # IEND chunk
        write_chunk(f, b'IEND', b'')
