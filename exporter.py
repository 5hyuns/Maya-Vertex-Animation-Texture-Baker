# -*- coding: utf-8 -*-
"""
Maya VAT - Mesh Exporter
"""

import maya.cmds as cmds
import maya.mel as mel
import os


def ensure_fbx_plugin():
    """Load FBX plugin if not loaded"""
    if not cmds.pluginInfo('fbxmaya', query=True, loaded=True):
        try:
            cmds.loadPlugin('fbxmaya')
        except:
            raise RuntimeError("FBX plugin not available")


def export_fbx(mesh_name, output_dir, base_name=None, unit=None):
    """
    Export mesh as FBX with VAT UV

    Args:
        mesh_name: Name of mesh to export
        output_dir: Output directory
        base_name: Base name for file (default: mesh_name)
        unit: FBX file unit such as 'cm' (default: Maya working unit)

    Returns:
        Path to exported FBX file
    """
    # Ensure FBX plugin is loaded
    ensure_fbx_plugin()

    if base_name is None:
        base_name = mesh_name.replace(':', '_').replace('|', '_')

    fbx_path = os.path.join(output_dir, "{}.fbx".format(base_name))

    # Store selection
    original_sel = cmds.ls(selection=True)

    # With skins and blend shapes off, the FBX exporter writes the mesh as it
    # is before its deformers (the bind pose), not the pose at the current
    # frame. Export a history-free copy of the current pose instead. The copy
    # sits under copies of its parents with the same names, so the FBX has the
    # same hierarchy and node names as exporting the original would.
    if cmds.objectType(mesh_name, isAType='shape'):
        mesh_name = cmds.listRelatives(mesh_name, parent=True, fullPath=True)[0]
    names = cmds.ls(mesh_name, long=True)[0].split('|')[1:]
    chain = [_uuid('|' + '|'.join(names[:i + 1])) for i in range(len(names))]

    # Only the top node's name is taken: everything below sits under the copy
    restore_name = _free_name(chain[0], names[0])
    copies = []
    try:
        _copy_chain(chain, copies)
        for i, copy in enumerate(copies):
            name = names[i]
            if i == 0 and restore_name is None:
                # The top name is still in use. Drop its namespace instead,
                # so at least every node below keeps its exact name.
                name = ':' + name.split(':')[-1]
                if cmds.objExists('|' + name[1:]):
                    continue
            cmds.rename(_path(copy), name)
        cmds.select(_path(copies[-1]), replace=True)
        _export_selected(fbx_path, unit)
    finally:
        # Leaf first: a copy whose parenting failed is not under the top copy
        for copy in reversed(copies):
            if cmds.ls(copy):
                cmds.delete(_path(copy))
        if restore_name is not None:
            restore_name()

    # Restore selection
    if original_sel:
        cmds.select(original_sel, replace=True)
    else:
        cmds.select(clear=True)

    return fbx_path


def _uuid(node):
    return cmds.ls(node, uuid=True)[0]


def _path(uuid):
    return cmds.ls(uuid, long=True)[0]


def _free_name(uuid, name):
    """
    Rename a top-level node out of the way of a copy that takes its name.

    Returns a function that renames it back, or None when the node cannot be
    renamed: a referenced or locked node. (Renaming a reference's namespace
    instead can crash Maya once the referenced mesh has edits, such as the
    VAT UV set.)
    """
    if cmds.referenceQuery(_path(uuid), isNodeReferenced=True):
        return None
    try:
        cmds.rename(_path(uuid), name + '_vat_source')
    except RuntimeError:
        return None
    return lambda: cmds.rename(_path(uuid), name)


def _copy_chain(chain, copies):
    """
    Copy the mesh (last in chain) and its parents (the rest, top first) as a
    new top-level hierarchy with the same local transforms. Adds the copies'
    UUIDs to copies, top first, as they are made.
    """
    for i, uuid in enumerate(chain):
        if i < len(chain) - 1:
            copy = cmds.duplicate(_path(uuid), parentOnly=True)[0]
        else:
            copy = _snapshot(_path(uuid))
        copy = _uuid(copy)
        copies.append(copy)
        if i:
            cmds.parent(_path(copy), _path(copies[i - 1]), relative=True)


def _snapshot(mesh_name):
    """Copy the mesh as it looks now: no deformers, history or animation"""
    copy = cmds.duplicate(mesh_name, returnRootsOnly=True)[0]
    cmds.delete(copy, constructionHistory=True)
    # The deformers' original-shape node stays behind as an intermediate shape
    for shape in cmds.listRelatives(copy, shapes=True, fullPath=True) or []:
        if cmds.getAttr(shape + '.intermediateObject'):
            cmds.delete(shape)
    return cmds.ls(copy, long=True)[0]


def _export_selected(fbx_path, unit):
    """Write the selection to fbx_path as a static mesh"""
    # FBX export settings
    mel.eval('FBXResetExport')

    # Basic settings
    mel.eval('FBXExportSmoothingGroups -v true')
    mel.eval('FBXExportSmoothMesh -v false')
    mel.eval('FBXExportTangents -v true')
    mel.eval('FBXExportSkins -v false')
    mel.eval('FBXExportShapes -v false')
    mel.eval('FBXExportCameras -v false')
    mel.eval('FBXExportLights -v false')
    mel.eval('FBXExportEmbeddedTextures -v false')
    mel.eval('FBXExportInputConnections -v false')
    mel.eval('FBXExportUseSceneName -v false')
    mel.eval('FBXExportInAscii -v false')
    if unit:
        mel.eval('FBXExportConvertUnitString {}'.format(unit))

    # Animation off. The proxy is a static mesh at the current pose; keyed
    # transforms would otherwise be written as animation curves, which makes
    # engines import an animated (Unreal: skeletal) mesh.
    mel.eval('FBXProperty "Export|IncludeGrp|Animation" -v false')
    mel.eval('FBXExportBakeComplexAnimation -v false')
    mel.eval('FBXExportAnimationOnly -v false')
    mel.eval('FBXExportApplyConstantKeyReducer -v false')

    # Export selected only
    mel.eval('FBXExport -f "{}" -s'.format(fbx_path.replace('\\', '/')))


def export_obj(mesh_name, output_dir, base_name=None):
    """
    Export mesh as OBJ (alternative to FBX)

    Args:
        mesh_name: Name of mesh to export
        output_dir: Output directory
        base_name: Base name for file

    Returns:
        Path to exported OBJ file
    """
    if base_name is None:
        base_name = mesh_name.replace(':', '_').replace('|', '_')

    obj_path = os.path.join(output_dir, "{}.obj".format(base_name))

    # Store selection
    original_sel = cmds.ls(selection=True)

    # Select mesh
    cmds.select(mesh_name, replace=True)

    # Export OBJ
    cmds.file(
        obj_path,
        force=True,
        options="groups=1;ptgroups=1;materials=0;smoothing=1;normals=1",
        type="OBJexport",
        exportSelected=True
    )

    # Restore selection
    if original_sel:
        cmds.select(original_sel, replace=True)
    else:
        cmds.select(clear=True)

    return obj_path
