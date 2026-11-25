# -*- coding: utf-8 -*-
"""
Regression tests for position bounds, the bake warnings, the animation-free
proxy FBX and the Unreal setup script.

Run with Maya's Python interpreter from the repo root:
    mayapy tests/test_motion.py
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

import maya.standalone
maya.standalone.initialize()

import maya.cmds as cmds

# The UI needs Maya's main window, which standalone Maya does not have
_ui = types.ModuleType('maya_vat.ui')
_ui.show = None
sys.modules['maya_vat.ui'] = _ui

# The repo root is the package; load it as maya_vat whatever the folder name
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    'maya_vat', os.path.join(_ROOT, '__init__.py'),
    submodule_search_locations=[_ROOT])
maya_vat = importlib.util.module_from_spec(_spec)
sys.modules['maya_vat'] = maya_vat
_spec.loader.exec_module(maya_vat)
core = maya_vat.core
utils = maya_vat.utils

MESH = 'box'


def _new_cube(hard_edges=False):
    cmds.file(new=True, force=True)
    cmds.playbackOptions(min=1, max=11)
    cube = cmds.polyCube(name=MESH)[0]
    if not hard_edges:
        cmds.polySoftEdge(cube, angle=180, constructionHistory=False)
    return cube


def _key(node, attr, v0, v1):
    cmds.setKeyframe(node, attribute=attr, time=1, value=v0)
    cmds.setKeyframe(node, attribute=attr, time=11, value=v1)


def scene_transform():
    box = _new_cube()
    _key(box, 'translateY', 0, 5)
    _key(box, 'rotateY', 0, 90)


def scene_translate():
    box = _new_cube()
    _key(box, 'translateX', 0, 5)


def scene_static():
    _new_cube()


def scene_cluster():
    _new_cube()
    _, handle = cmds.cluster(MESH + '.vtx[0:3]')
    _key(handle, 'translateY', 0, 2)


def scene_skin():
    box = _new_cube()
    cmds.select(clear=True)
    root = cmds.joint(position=(0, -0.5, 0))
    cmds.joint(position=(0, 0.5, 0))
    cmds.skinCluster(root, box, toSelectedBones=True)
    _key(root, 'rotateZ', 0, 45)


def scene_blend():
    box = _new_cube()
    target = cmds.duplicate(box, name='target')[0]
    cmds.scale(2, 2, 2, target + '.vtx[*]', relative=True)
    blend = cmds.blendShape(target, box)[0]
    _key(blend, 'w[0]', 0, 1)


class MotionTest(unittest.TestCase):

    def setUp(self):
        self.out = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def bake(self, scene, world, engine='playcanvas'):
        scene()
        result = core.encode_vat(MESH, self.out, include_normals=True,
                                 export_mesh=False, use_world_space=world,
                                 target_engine=engine)
        with open(result['json_path']) as f:
            position = json.load(f)['position']
        span = max(hi - lo for lo, hi in zip(position['min'], position['max']))
        return result, span

    def test_deformers_have_bounds_in_both_spaces(self):
        for scene in (scene_cluster, scene_skin, scene_blend):
            for world in (False, True):
                for engine in core.TARGET_ENGINES:
                    with self.subTest(scene=scene.__name__, world=world,
                                      engine=engine):
                        result, span = self.bake(scene, world, engine)
                        self.assertGreater(span, 0.0)
                        self.assertEqual(result['warnings'], [])

    def test_transform_only_object_space_warns(self):
        for engine in core.TARGET_ENGINES:
            with self.subTest(engine=engine):
                result, span = self.bake(scene_transform, False, engine)
                self.assertEqual(span, 0.0)
                self.assertEqual(len(result['warnings']), 1)
                self.assertIn('World space', result['warnings'][0])

    def test_transform_only_world_space_has_bounds(self):
        result, span = self.bake(scene_transform, True)
        self.assertGreater(span, 0.0)
        self.assertEqual(result['warnings'], [])

    def test_fbx_has_no_animation(self):
        scene_transform()
        result = core.encode_vat(MESH, self.out, export_mesh=True,
                                 use_world_space=True, target_engine='unreal')
        with open(result['fbx_path'], 'rb') as f:
            self.assertEqual(f.read().count(b'AnimationCurveNode'), 0)
        # The scene keeps its keys
        self.assertEqual(cmds.keyframe(MESH, query=True, keyframeCount=True), 4)

    def test_fbx_holds_start_frame_pose(self):
        # Start the bake where the skin is away from its bind pose
        for scene in (scene_skin, scene_blend):
            for engine in core.TARGET_ENGINES:
                with self.subTest(scene=scene.__name__, engine=engine):
                    scene()
                    cmds.currentTime(6)
                    expected = utils.get_vertex_positions(MESH, True)
                    nodes = set(cmds.ls(dag=True, long=True))
                    result = core.encode_vat(MESH, self.out, frame_start=6,
                                             frame_end=11, export_mesh=True,
                                             target_engine=engine)
                    # The export leaves no copy behind and keeps the mesh name
                    self.assertEqual(set(cmds.ls(dag=True, long=True)), nodes)
                    cmds.file(new=True, force=True)
                    cmds.file(result['fbx_path'], i=True, type='FBX')
                    self.assertTrue(cmds.objExists(MESH))
                    self.assertIn('VAT_UV', utils.get_uv_set_names(MESH))
                    got = utils.get_vertex_positions(MESH, True)
                    self.assertEqual(len(got), len(expected))
                    for p, q in zip(got, expected):
                        for axis in range(3):
                            self.assertAlmostEqual(p[axis], q[axis], places=4)

    def test_fbx_keeps_hierarchy_and_names(self):
        # A skinned mesh inside a moved group, used as is and as a reference
        scene_skin()
        group = cmds.group(MESH, cmds.ls(type='joint')[0], name='rig')
        cmds.move(0, 3, 0, group)
        rig_file = os.path.join(self.out, 'rig.ma')
        cmds.file(rename=rig_file)
        cmds.file(save=True, type='mayaAscii')
        for referenced in (False, True):
            with self.subTest(referenced=referenced):
                cmds.file(new=True, force=True)
                cmds.playbackOptions(min=1, max=11)
                prefix = 'ch:' if referenced else ''
                if referenced:
                    cmds.file(rig_file, reference=True, namespace='ch')
                else:
                    cmds.file(rig_file, i=True)
                mesh = prefix + MESH
                cmds.currentTime(6)
                expected = utils.get_vertex_positions(mesh, True)
                nodes = set(cmds.ls(dag=True, long=True))
                namespaces = cmds.namespaceInfo(':', listOnlyNamespaces=True)
                result = core.encode_vat(mesh, self.out, frame_start=6,
                                         frame_end=11, export_mesh=True,
                                         target_engine='unreal')
                # The scene is back as it was, without reference edits
                self.assertEqual(set(cmds.ls(dag=True, long=True)), nodes)
                self.assertEqual(
                    cmds.namespaceInfo(':', listOnlyNamespaces=True), namespaces)
                if referenced:
                    node = cmds.referenceQuery(mesh, referenceNode=True)
                    self.assertFalse(any(
                        '_vat_source' in e or e.startswith('parent')
                        for e in cmds.referenceQuery(node, editStrings=True) or []))
                cmds.file(new=True, force=True)
                cmds.file(result['fbx_path'], i=True, type='FBX')
                cameras = set(cmds.listRelatives(
                    cmds.ls(type='camera'), parent=True, fullPath=True))
                # A referenced top node keeps its name, so its copy drops the
                # namespace; every node below keeps its exact name
                path = '|rig|{}{}'.format(prefix, MESH)
                self.assertEqual(
                    set(cmds.ls(type='transform', long=True)) - cameras,
                    {'|rig', path})
                got = utils.get_vertex_positions(path, True)
                for p, q in zip(got, expected):
                    for axis in range(3):
                        self.assertAlmostEqual(p[axis], q[axis], places=4)

    def test_static_mesh_warns(self):
        for world in (False, True):
            with self.subTest(world=world):
                result, span = self.bake(scene_static, world)
                self.assertEqual(span, 0.0)
                self.assertEqual(len(result['warnings']), 1)
                self.assertIn('does not move', result['warnings'][0])



class NormalWarningTest(unittest.TestCase):
    """Without a normal texture the engine keeps the first-frame normals"""

    def setUp(self):
        self.out = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def bake(self, scene, world, include_normals=False):
        scene()
        return core.encode_vat(MESH, self.out, include_normals=include_normals,
                               export_mesh=False, use_world_space=world)

    def test_turning_mesh_without_normals_warns(self):
        result = self.bake(scene_transform, True)
        self.assertEqual(len(result['warnings']), 1)
        self.assertIn('Export Normals', result['warnings'][0])

    def test_bending_mesh_without_normals_warns(self):
        for scene in (scene_cluster, scene_skin):
            for world in (False, True):
                with self.subTest(scene=scene.__name__, world=world):
                    result = self.bake(scene, world)
                    self.assertEqual(len(result['warnings']), 1)
                    self.assertIn('Export Normals', result['warnings'][0])

    def test_moving_mesh_without_normals_does_not_warn(self):
        result = self.bake(scene_translate, True)
        self.assertEqual(result['warnings'], [])

    def test_object_space_ignores_transform_rotation(self):
        # The engine applies the object's own rotation to the normals at runtime
        result = self.bake(scene_transform, False)
        self.assertEqual(len(result['warnings']), 1)
        self.assertNotIn('Export Normals', result['warnings'][0])

    def test_hard_edges_with_normals_warn(self):
        def scene():
            box = _new_cube(hard_edges=True)
            _key(box, 'rotateY', 0, 90)
        result = self.bake(scene, True, include_normals=True)
        self.assertEqual(len(result['warnings']), 1)
        self.assertIn('hard edge', result['warnings'][0])

    def test_detached_hard_edges_do_not_warn(self):
        def scene():
            box = _new_cube(hard_edges=True)
            cmds.polySplitEdge(box + '.e[*]')
            _key(box, 'rotateY', 0, 90)
        result = self.bake(scene, True, include_normals=True)
        self.assertEqual(result['warnings'], [])


class BoundsAndUnrealScriptTest(unittest.TestCase):

    def setUp(self):
        self.out = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def test_bounds_extension_covers_min_max(self):
        scene_transform()
        result = core.encode_vat(MESH, self.out, export_mesh=False,
                                 use_world_space=True, target_engine='unreal')
        with open(result['json_path']) as f:
            position = json.load(f)['position']
        extension = result['bounds_extension']
        for axis in range(3):
            self.assertEqual(extension['positive'][axis],
                             max(0.0, position['max'][axis]))
            self.assertEqual(extension['negative'][axis],
                             max(0.0, -position['min'][axis]))
            self.assertGreaterEqual(extension['positive'][axis], 0.0)
            self.assertGreaterEqual(extension['negative'][axis], 0.0)

    def _script_constants(self, path):
        with open(path) as f:
            source = f.read()
        compile(source, path, 'exec')
        constants = {}
        # Only the constants header runs outside Unreal
        exec(source.split('\nimport unreal\n')[0], constants)
        return constants

    def test_unreal_bake_writes_setup_script(self):
        for world, include_normals in ((True, True), (False, False)):
            with self.subTest(world=world, include_normals=include_normals):
                scene_skin()
                cmds.currentUnit(time='ntsc', updateAnimation=False)
                result = core.encode_vat(
                    MESH, self.out, include_normals=include_normals,
                    export_mesh=False, use_world_space=world,
                    target_engine='unreal')
                with open(result['json_path']) as f:
                    position = json.load(f)['position']
                c = self._script_constants(result['setup_script_path'])
                self.assertEqual(c['MESH'], MESH)
                self.assertEqual(c['POSITION_TEXTURE'], MESH + '_vat')
                self.assertEqual(c['NORMAL_TEXTURE'],
                                 MESH + '_vnrm' if include_normals else None)
                self.assertEqual(c['SPACE'], 'world' if world else 'object')
                self.assertEqual(c['VAT_UV_INDEX'], 1)
                self.assertEqual(c['FRAMES'], position['frames'])
                self.assertAlmostEqual(c['FPS'], 30.0, places=3)
                for axis in range(3):
                    self.assertAlmostEqual(c['BOUNDS_MIN'][axis],
                                           position['min'][axis], places=5)
                    self.assertAlmostEqual(c['BOUNDS_MAX'][axis],
                                           position['max'][axis], places=5)
                    self.assertAlmostEqual(
                        c['POSITIVE_BOUNDS_EXTENSION'][axis],
                        result['bounds_extension']['positive'][axis], places=5)

    def test_other_engines_write_no_setup_script(self):
        for engine in ('playcanvas', 'unity'):
            with self.subTest(engine=engine):
                scene_skin()
                result = core.encode_vat(MESH, self.out, export_mesh=False,
                                         target_engine=engine)
                self.assertIsNone(result['setup_script_path'])
                self.assertFalse(any(name.endswith('_ue_setup.py')
                                     for _, _, files in os.walk(self.out)
                                     for name in files))


if __name__ == '__main__':
    unittest.main(verbosity=2)
