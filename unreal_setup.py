# -*- coding: utf-8 -*-
"""
Maya VAT - Unreal Engine setup script

Writes <mesh>_ue_setup.py next to an Unreal Engine bake. Run inside the Unreal
Editor, it applies the texture and static mesh settings the bake needs and
builds a VAT material, so none of them has to be set by hand.
"""


def _vec(values):
    return "({!r}, {!r}, {!r})".format(*(round(float(v), 6) for v in values))


def write_setup_script(path, mesh, position_texture, normal_texture, space,
                       uv_index, frames, fps, position_min, position_max,
                       extension):
    """
    Write the Unreal setup script for one bake.

    Args:
        path: Output .py path
        mesh: Static mesh asset name (the FBX file name)
        position_texture: Position texture asset name
        normal_texture: Normal texture asset name, or None
        space: 'world' or 'object'
        uv_index: UV channel of the VAT UV set in the imported mesh
        frames: Number of texture rows
        fps: Playback frames per second
        position_min / position_max: remap.json position min/max
        extension: bounds_extension() result
    """
    header = [
        "# -*- coding: utf-8 -*-",
        '"""',
        "Unreal Engine setup for the VAT bake of '{}' (written by Maya VAT).".format(mesh),
        "",
        "1. Import {0}.fbx (as a Static Mesh) and the textures of this folder"
        .format(mesh),
        "   into one Content Browser folder.",
        "2. Select the static mesh in the Content Browser and run this file",
        "   (Tools > Execute Python Script).",
        "",
        "It sets the texture settings, Use Full Precision UVs, Nanite off and the",
        "bounds extension, then builds M_{0}_VAT and assigns it to the mesh."
        .format(mesh),
        '"""',
        "",
        "MESH = {!r}".format(mesh),
        "POSITION_TEXTURE = {!r}".format(position_texture),
        "NORMAL_TEXTURE = {!r}".format(normal_texture),
        "SPACE = {!r}".format(space),
        "VAT_UV_INDEX = {!r}".format(int(uv_index)),
        "FRAMES = {!r}".format(int(frames)),
        "FPS = {!r}".format(round(float(fps), 6)),
        "BOUNDS_MIN = {}".format(_vec(position_min)),
        "BOUNDS_MAX = {}".format(_vec(position_max)),
        "POSITIVE_BOUNDS_EXTENSION = {}".format(_vec(extension["positive"])),
        "NEGATIVE_BOUNDS_EXTENSION = {}".format(_vec(extension["negative"])),
        "",
    ]
    with open(path, 'w') as f:
        f.write("\n".join(header))
        f.write(_BODY)
    return path


# The fixed part of the script. It runs in the Unreal Editor's Python.
_BODY = r'''
import math
import unreal

# Reads one texel per vertex: column = VAT UV x, row = frame
VAT_HLSL = (
    "float2 uv  = float2(VatUV.x, (floor(Frame) + 0.5) / Frames);\n"
    "float3 enc = Texture2DSampleLevel(VatTex, VatTexSampler, uv, 0).rgb;\n"
    "return lerp(BoundsMin, BoundsMax, enc);"
)
VAT_INPUTS = ("VatTex", "VatUV", "Frame", "Frames", "BoundsMin", "BoundsMax")

MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary


def log(message):
    unreal.log("[Maya VAT] " + message)


def asset_name(path):
    return path.rsplit("/", 1)[-1].split(".")[0]


def folder_of(asset):
    return asset.get_path_name().rsplit("/", 1)[0]


def selected_assets():
    try:
        return list(unreal.EditorUtilityLibrary.get_selected_assets())
    except Exception:
        return []


def find_asset(name, cls, folder=None):
    """An asset of the class with this name, preferring the given folder"""
    for asset in selected_assets():
        if isinstance(asset, cls) and asset.get_name() == name:
            return asset
    if folder:
        path = folder + "/" + name
        if EAL.does_asset_exist(path):
            asset = EAL.load_asset(path)
            if isinstance(asset, cls):
                return asset
    for path in EAL.list_assets("/Game", recursive=True, include_folder=False):
        if asset_name(path) == name:
            asset = EAL.load_asset(path)
            if isinstance(asset, cls):
                return asset
    return None


def find_mesh():
    """The selected static mesh, or the only one in the project with this name"""
    meshes = [a for a in selected_assets() if isinstance(a, unreal.StaticMesh)]
    if len(meshes) == 1:
        return meshes[0]
    if len(meshes) > 1:
        raise RuntimeError(
            "Several static meshes are selected. Select only '{}'.".format(MESH))
    paths = [p for p in EAL.list_assets("/Game", recursive=True, include_folder=False)
             if asset_name(p) == MESH
             and isinstance(EAL.load_asset(p), unreal.StaticMesh)]
    if len(paths) > 1:
        raise RuntimeError(
            "Several static meshes are named '{}' ({}). Select the one to set "
            "up in the Content Browser and run again."
            .format(MESH, ", ".join(p.split(".")[0] for p in paths)))
    return EAL.load_asset(paths[0]) if paths else None


def setup_texture(texture):
    texture.set_editor_property(
        "compression_settings",
        unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
    texture.set_editor_property("srgb", False)
    texture.set_editor_property("filter", unreal.TextureFilter.TF_NEAREST)
    texture.set_editor_property(
        "mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    EAL.save_loaded_asset(texture)
    log("Texture settings: " + texture.get_name())


def mesh_library():
    if hasattr(unreal, "StaticMeshEditorSubsystem"):
        return unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    return unreal.EditorStaticMeshLibrary


def setup_mesh(mesh):
    # Unreal builds the bounds from the first-frame pose. Shadows and culling
    # use them, so they must hold the whole animation, or the mesh and its
    # shadow disappear while it moves.
    mesh.set_editor_property(
        "positive_bounds_extension", unreal.Vector(*POSITIVE_BOUNDS_EXTENSION))
    mesh.set_editor_property(
        "negative_bounds_extension", unreal.Vector(*NEGATIVE_BOUNDS_EXTENSION))

    # With Nanite the bounds extension alone does not cover the offset: the
    # shadow leaves trails on the ground or disappears (see set_max_offset)
    nanite = mesh.get_editor_property("nanite_settings")
    if nanite.get_editor_property("enabled"):
        nanite.set_editor_property("enabled", False)
        mesh.set_editor_property("nanite_settings", nanite)

    # 16-bit UVs cannot address single texels in wide textures
    library = mesh_library()
    build = library.get_lod_build_settings(mesh, 0)
    build.set_editor_property("use_full_precision_u_vs", True)
    library.set_lod_build_settings(mesh, 0, build)

    EAL.save_loaded_asset(mesh)
    log("Static mesh settings: {} (bounds extension +{} / -{})".format(
        mesh.get_name(), POSITIVE_BOUNDS_EXTENSION, NEGATIVE_BOUNDS_EXTENSION))


def expression(material, cls, x, y):
    return MEL.create_material_expression(material, cls, x, y)


def vector_constant(material, value, x, y):
    node = expression(material, unreal.MaterialExpressionConstant3Vector, x, y)
    node.set_editor_property("constant", unreal.LinearColor(value[0], value[1], value[2], 0.0))
    return node


def vat_lookup(material, texture, low, high, frame, frames, y):
    """Custom node that decodes one VAT texel per vertex"""
    tex = expression(material, unreal.MaterialExpressionTextureObject, -900, y)
    tex.set_editor_property("texture", texture)
    tex.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    uv = expression(material, unreal.MaterialExpressionTextureCoordinate, -900, y + 160)
    uv.set_editor_property("coordinate_index", VAT_UV_INDEX)
    low_node = vector_constant(material, low, -900, y + 240)
    high_node = vector_constant(material, high, -900, y + 340)

    custom = expression(material, unreal.MaterialExpressionCustom, -500, y)
    custom.set_editor_property("code", VAT_HLSL)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    inputs = []
    for name in VAT_INPUTS:
        item = unreal.CustomInput()
        item.set_editor_property("input_name", name)
        inputs.append(item)
    custom.set_editor_property("inputs", inputs)

    for node, name in ((tex, "VatTex"), (uv, "VatUV"), (frame, "Frame"),
                       (frames, "Frames"), (low_node, "BoundsMin"),
                       (high_node, "BoundsMax")):
        if not MEL.connect_material_expressions(node, "", custom, name):
            raise RuntimeError("Could not connect the Custom node input " + name)
    return custom


def local_to_world(material, node, x, y):
    transform = expression(material, unreal.MaterialExpressionTransform, x, y)
    transform.set_editor_property(
        "transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
    transform.set_editor_property(
        "transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
    MEL.connect_material_expressions(node, "", transform, "")
    return transform


def build_graph(material, position_texture, normal_texture):
    """
    Add the VAT nodes. Returns (offset node, normal node or None): the offset
    goes to World Position Offset, the normal (already passed through a
    VertexInterpolator) to Normal with Tangent Space Normal off.
    """
    # Frame = fmod(Time * FPS, FRAMES)
    time = expression(material, unreal.MaterialExpressionTime, -1500, -200)
    speed = expression(material, unreal.MaterialExpressionMultiply, -1300, -200)
    speed.set_editor_property("const_b", FPS)
    MEL.connect_material_expressions(time, "", speed, "A")
    frames = expression(material, unreal.MaterialExpressionConstant, -1300, -80)
    frames.set_editor_property("r", float(FRAMES))
    frame = expression(material, unreal.MaterialExpressionFmod, -1100, -200)
    MEL.connect_material_expressions(speed, "", frame, "A")
    MEL.connect_material_expressions(frames, "", frame, "B")

    offset = vat_lookup(material, position_texture, BOUNDS_MIN, BOUNDS_MAX, frame, frames, 0)
    if SPACE == "object":
        offset = local_to_world(material, offset, -250, 0)

    interpolator = None
    if normal_texture is not None:
        # Normals are decoded per vertex and passed on, because VAT_UV is
        # interpolated across each triangle in the pixel stage
        normal = vat_lookup(material, normal_texture, (-1.0, -1.0, -1.0), (1.0, 1.0, 1.0),
                            frame, frames, 600)
        if SPACE == "object":
            normal = local_to_world(material, normal, -250, 600)
        interpolator = expression(material, unreal.MaterialExpressionVertexInterpolator, -50, 600)
        MEL.connect_material_expressions(normal, "", interpolator, "VS")
        material.set_editor_property("tangent_space_normal", False)

    set_max_offset(material)
    return offset, interpolator


def set_max_offset(material):
    """
    Tell the engine how far World Position Offset moves the vertices. Culling
    and shadows (Nanite included) grow by this distance, and the engine may
    clamp the offset to it, so use the length of the largest offset on every axis.
    """
    limit = math.sqrt(sum(max(abs(lo), abs(hi)) ** 2
                          for lo, hi in zip(BOUNDS_MIN, BOUNDS_MAX)))
    try:
        material.set_editor_property("max_world_position_offset_displacement", limit)
    except Exception:
        log("This engine version has no Max World Position Offset Displacement; "
            "keep Nanite off and the bounds extension.")


def build_material(mesh, position_texture, normal_texture):
    """Returns (material, created, world position offset connected)"""
    folder = folder_of(mesh)
    name = "M_{}_VAT".format(MESH)
    path = folder + "/" + name
    if EAL.does_asset_exist(path):
        log("{} already exists and was left unchanged. Delete it and run "
            "again to rebuild it.".format(path))
        return EAL.load_asset(path), False, None

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    offset, normal = build_graph(material, position_texture, normal_texture)

    # Some engine versions keep World Position Offset out of Python
    wpo = getattr(unreal.MaterialProperty, "MP_WORLD_POSITION_OFFSET", None)
    connected = bool(wpo is not None and MEL.connect_material_property(offset, "", wpo))
    if not connected:
        offset.set_editor_property("desc", "Connect to World Position Offset")
    if normal is not None:
        MEL.connect_material_property(normal, "", unreal.MaterialProperty.MP_NORMAL)
    # Neutral grey to start from; replace it with the mesh's own textures
    base_color = vector_constant(material, (0.5, 0.5, 0.5), -250, -300)
    MEL.connect_material_property(base_color, "", unreal.MaterialProperty.MP_BASE_COLOR)

    MEL.recompile_material(material)
    EAL.save_loaded_asset(material)
    return material, True, connected


def main():
    mesh = find_mesh()
    if mesh is None:
        raise RuntimeError(
            "Static mesh '{}' not found. Import the FBX first, or select the "
            "static mesh in the Content Browser.".format(MESH))
    folder = folder_of(mesh)

    position_texture = find_asset(POSITION_TEXTURE, unreal.Texture2D, folder)
    if position_texture is None:
        raise RuntimeError("Texture '{}' not found. Import it first.".format(POSITION_TEXTURE))
    normal_texture = None
    if NORMAL_TEXTURE:
        normal_texture = find_asset(NORMAL_TEXTURE, unreal.Texture2D, folder)
        if normal_texture is None:
            log("Normal texture '{}' not found, so the material uses the mesh "
                "normals.".format(NORMAL_TEXTURE))

    for texture in (position_texture, normal_texture):
        if texture is not None:
            setup_texture(texture)
    setup_mesh(mesh)

    material, created, connected = build_material(mesh, position_texture, normal_texture)
    if created:
        mesh.set_material(0, material)
        EAL.save_loaded_asset(mesh)
        log("Material: {} (assigned to {})".format(material.get_path_name(), mesh.get_name()))
        if not connected:
            unreal.log_warning(
                "[Maya VAT] Open {} and connect the node marked 'Connect to World "
                "Position Offset' to World Position Offset.".format(material.get_name()))
    log("Done. Reopen the level to clear shadows cached before this change.")


main()
'''
