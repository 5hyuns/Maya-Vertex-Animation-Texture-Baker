# -*- coding: utf-8 -*-
"""
Regression tests for position bounds, the empty-bake warning and the
animation-free proxy FBX.

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

MESH = 'box'


def _new_cube():
    cmds.file(new=True, force=True)
    cmds.playbackOptions(min=1, max=11)
    return cmds.polyCube(name=MESH)[0]


def _key(node, attr, v0, v1):
    cmds.setKeyframe(node, attribute=attr, time=1, value=v0)
    cmds.setKeyframe(node, attribute=attr, time=11, value=v1)


def scene_transform():
    box = _new_cube()
    _key(box, 'translateY', 0, 5)
    _key(box, 'rotateY', 0, 90)


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

    def test_static_mesh_warns(self):
        for world in (False, True):
            with self.subTest(world=world):
                result, span = self.bake(scene_static, world)
                self.assertEqual(span, 0.0)
                self.assertEqual(len(result['warnings']), 1)
                self.assertIn('does not move', result['warnings'][0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
