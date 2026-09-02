"""Build the cohesive, rigged cartoon Effendi GLB used by the web interface.

Run with Blender in background mode:
    blender --background --python scripts/build_effendi_3d.py
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "models" / "effendi-cartoon.glb"


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.armatures):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.58, metallic: float = 0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def finish(obj, name: str, mat, smooth: bool = True):
    obj.name = name
    obj.data.materials.append(mat)
    if smooth and hasattr(obj.data, "polygons"):
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    return obj


def sphere(name, location, scale, mat, segments=32, rings=20):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=location)
    obj = bpy.context.object
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, mat)


def cube(name, location, scale, mat, bevel=0.12):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    modifier = obj.modifiers.new("Soft edges", "BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    return finish(obj, name, mat)


def cylinder_between(name, start, end, radius, mat, vertices=28):
    start_v, end_v = Vector(start), Vector(end)
    direction = end_v - start_v
    midpoint = (start_v + end_v) * 0.5
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=direction.length, location=midpoint)
    obj = bpy.context.object
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(direction.normalized())
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, mat)


def cone(name, location, radius1, radius2, depth, mat, vertices=36):
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius1,
        radius2=radius2,
        depth=depth,
        location=location,
    )
    return finish(bpy.context.object, name, mat)


def parent_to_bone(obj, armature, bone_name: str) -> None:
    matrix = obj.matrix_world.copy()
    if obj.type == "MESH":
        obj.parent = armature
        obj.matrix_world = matrix
        group = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
        group.add(range(len(obj.data.vertices)), 1.0, "REPLACE")
        modifier = obj.modifiers.new("EffendiRig", "ARMATURE")
        modifier.object = armature
    else:
        obj.parent = armature
        obj.parent_type = "BONE"
        obj.parent_bone = bone_name
        obj.matrix_world = matrix


def add_shape_key(obj, name: str, transform) -> None:
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Basis")
    key = obj.shape_key_add(name=name)
    for point, basis_point in zip(key.data, obj.data.shape_keys.key_blocks["Basis"].data):
        point.co = transform(basis_point.co.copy())


def add_facial_shape_keys(mouth, eyes, eyebrows) -> None:
    identity = lambda co: co
    add_shape_key(mouth, "Neutral", identity)
    add_shape_key(mouth, "MouthClosed", lambda co: Vector((co.x, co.y, co.z * 0.34)))
    add_shape_key(mouth, "JawOpen", lambda co: Vector((co.x * 0.9, co.y, co.z * 2.35)))
    add_shape_key(mouth, "Viseme_AI", lambda co: Vector((co.x * 1.22, co.y, co.z * 1.55)))
    add_shape_key(mouth, "Viseme_E", lambda co: Vector((co.x * 1.48, co.y, co.z * 0.72)))
    add_shape_key(mouth, "Viseme_O", lambda co: Vector((co.x * 0.66, co.y, co.z * 1.72)))
    add_shape_key(mouth, "Viseme_U", lambda co: Vector((co.x * 0.55, co.y, co.z * 1.38)))
    add_shape_key(mouth, "Viseme_MBP", lambda co: Vector((co.x, co.y, co.z * 0.26)))
    add_shape_key(
        mouth,
        "Smile",
        lambda co: Vector((co.x * 1.3, co.y, co.z + abs(co.x) * 0.22)),
    )
    for eye, name in eyes:
        add_shape_key(eye, name, lambda co: Vector((co.x, co.y, co.z * 0.1)))
    for brow, prefix in eyebrows:
        add_shape_key(brow, "BrowRaise", lambda co: Vector((co.x, co.y, co.z + 0.13)))
        direction = -1 if prefix == "L" else 1
        add_shape_key(
            brow,
            "BrowConcern",
            lambda co, direction=direction: Vector((co.x, co.y, co.z + co.x * direction * 0.18)),
        )


def create_animation_clips(armature) -> None:
    """Create stable named clips matching the web avatar contract."""

    bpy.context.scene.render.fps = 30
    clip_specs = {
        "Idle": {
            1: {"Spine": (0, 0, 0), "Head": (0, 0, 0)},
            45: {"Spine": (0.025, 0, 0.012), "Head": (0.012, 0, -0.01)},
            90: {"Spine": (0, 0, 0), "Head": (0, 0, 0)},
        },
        "Listening": {
            1: {"Spine": (0, 0, 0), "Head": (0, 0, 0)},
            25: {"Spine": (-0.045, 0, 0), "Head": (0.06, 0, 0.025)},
            50: {"Spine": (-0.025, 0, 0), "Head": (0.02, 0, -0.015)},
            75: {"Spine": (-0.045, 0, 0), "Head": (0.06, 0, 0.025)},
        },
        "Thinking": {
            1: {"Head": (0, 0, 0), "Spine": (0, 0, 0)},
            45: {"Head": (-0.035, 0.1, -0.075), "Spine": (0.01, 0, -0.02)},
            90: {"Head": (-0.02, -0.04, -0.045), "Spine": (0, 0, 0)},
        },
        "Talking": {
            1: {"Head": (0, 0, 0), "UpperArm.L": (0, 0, 0), "UpperArm.R": (0, 0, 0)},
            30: {"Head": (0.025, 0.04, 0), "UpperArm.L": (0.08, 0, 0.24), "UpperArm.R": (-0.08, 0, -0.24)},
            60: {"Head": (-0.015, -0.03, 0), "UpperArm.L": (-0.04, 0, 0.12), "UpperArm.R": (0.04, 0, -0.12)},
            90: {"Head": (0, 0, 0), "UpperArm.L": (0, 0, 0), "UpperArm.R": (0, 0, 0)},
        },
        "Greeting": {
            1: {"UpperArm.R": (0, 0, 0), "Forearm.R": (0, 0, 0)},
            22: {"UpperArm.R": (0.12, -0.15, -1.15), "Forearm.R": (0.1, 0, -1.15)},
            40: {"UpperArm.R": (0.12, 0.12, -1.15), "Forearm.R": (0.1, 0.15, -1.15)},
            58: {"UpperArm.R": (0.12, -0.12, -1.15), "Forearm.R": (0.1, -0.15, -1.15)},
            80: {"UpperArm.R": (0, 0, 0), "Forearm.R": (0, 0, 0)},
        },
        "Success": {
            1: {"Head": (0, 0, 0), "Spine": (0, 0, 0)},
            18: {"Head": (0.12, 0, 0), "Spine": (-0.025, 0, 0)},
            38: {"Head": (-0.025, 0, 0), "Spine": (0.01, 0, 0)},
            60: {"Head": (0, 0, 0), "Spine": (0, 0, 0)},
        },
        "Error": {
            1: {"Head": (0, 0, 0), "Spine": (0, 0, 0)},
            35: {"Head": (-0.09, 0, 0.045), "Spine": (0.025, 0, 0)},
            70: {"Head": (-0.05, 0, -0.025), "Spine": (0.01, 0, 0)},
        },
    }
    armature.animation_data_create()
    for clip_name, frames in clip_specs.items():
        action = bpy.data.actions.new(clip_name)
        armature.animation_data.action = action
        for pose_bone in armature.pose.bones:
            pose_bone.rotation_mode = "XYZ"
            pose_bone.rotation_euler = (0, 0, 0)
        for frame, transforms in frames.items():
            for bone_name, rotation in transforms.items():
                bone = armature.pose.bones.get(bone_name)
                if bone is None:
                    continue
                bone.rotation_euler = rotation
                bone.keyframe_insert("rotation_euler", frame=frame, group=bone_name)
        action.frame_start = min(frames)
        action.frame_end = max(frames)
    armature.animation_data.action = None


def curve_chain(name, points, mat, bevel_depth=0.025):
    curve_data = bpy.data.curves.new(name, "CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 2
    curve_data.bevel_depth = bevel_depth
    curve_data.bevel_resolution = 3
    spline = curve_data.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, coordinate in zip(spline.bezier_points, points):
        point.co = coordinate
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def build_armature():
    armature_data = bpy.data.armatures.new("EffendiRig")
    armature = bpy.data.objects.new("EffendiRig", armature_data)
    bpy.context.collection.objects.link(armature)
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    armature.show_in_front = True
    bpy.ops.object.mode_set(mode="EDIT")

    specs = {
        "Root": ((0, 0, 0), (0, 0, 1), None),
        "Hips": ((0, 0, 3.45), (0, 0, 4.15), "Root"),
        "Spine": ((0, 0, 4.15), (0, 0, 5.55), "Hips"),
        "Chest": ((0, 0, 5.25), (0, 0, 6.15), "Spine"),
        "Neck": ((0, 0, 6.05), (0, 0, 6.5), "Chest"),
        "Head": ((0, 0, 6.45), (0, 0, 7.75), "Neck"),
        "UpperArm.L": ((-0.96, 0, 5.75), (-1.45, 0, 4.9), "Chest"),
        "Forearm.L": ((-1.45, 0, 4.9), (-1.5, 0, 4.05), "UpperArm.L"),
        "Hand.L": ((-1.5, 0, 4.05), (-1.5, 0, 3.65), "Forearm.L"),
        "UpperArm.R": ((0.96, 0, 5.75), (1.45, 0, 4.9), "Chest"),
        "Forearm.R": ((1.45, 0, 4.9), (1.5, 0, 4.05), "UpperArm.R"),
        "Hand.R": ((1.5, 0, 4.05), (1.5, 0, 3.65), "Forearm.R"),
        "Thigh.L": ((-0.42, 0, 3.55), (-0.42, 0, 2.15), "Hips"),
        "Shin.L": ((-0.42, 0, 2.15), (-0.42, 0, 0.72), "Thigh.L"),
        "Foot.L": ((-0.42, 0, 0.72), (-0.42, -0.48, 0.32), "Shin.L"),
        "Thigh.R": ((0.42, 0, 3.55), (0.42, 0, 2.15), "Hips"),
        "Shin.R": ((0.42, 0, 2.15), (0.42, 0, 0.72), "Thigh.R"),
        "Foot.R": ((0.42, 0, 0.72), (0.42, -0.48, 0.32), "Shin.R"),
    }
    bones = {}
    for name, (head, tail, parent_name) in specs.items():
        bone = armature_data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        if parent_name:
            bone.parent = bones[parent_name]
        bones[name] = bone
    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


def build_character():
    skin = material("Skin", (0.73, 0.32, 0.14, 1), 0.64)
    skin_light = material("SkinHighlight", (0.92, 0.52, 0.27, 1), 0.58)
    suit = material("SuitBlack", (0.018, 0.021, 0.026, 1), 0.46)
    vest = material("Vest", (0.028, 0.032, 0.038, 1), 0.5)
    white = material("ShirtWhite", (0.92, 0.94, 0.91, 1), 0.54)
    black = material("MustacheBlack", (0.006, 0.004, 0.003, 1), 0.42)
    eye_white = material("EyeWhite", (0.95, 0.95, 0.89, 1), 0.35)
    iris = material("IrisBrown", (0.18, 0.055, 0.012, 1), 0.3)
    gold = material("PocketGold", (0.72, 0.35, 0.025, 1), 0.3, 0.7)
    shoe = material("Shoes", (0.009, 0.01, 0.012, 1), 0.24, 0.12)
    mouth_mat = material("Mouth", (0.18, 0.015, 0.012, 1), 0.52)

    armature = build_armature()

    # Cohesive torso and formal Baghdadi outfit.
    torso = sphere("JacketTorso", (0, 0.02, 4.95), (1.12, 0.58, 1.22), suit)
    vest_body = sphere("VestFront", (0, -0.52, 4.85), (0.68, 0.13, 0.73), vest)
    shirt = sphere("ShirtFront", (0, -0.61, 5.66), (0.3, 0.07, 0.36), white)
    tie = cone("Tie", (0, -0.69, 5.35), 0.13, 0.055, 0.74, black, vertices=5)
    pocket = cube("PocketSquare", (0.72, -0.62, 5.4), (0.16, 0.035, 0.11), white, 0.03)
    for index, z in enumerate((5.15, 4.83, 4.5)):
        button = sphere(f"JacketButton{index}", (0, -0.67, z), (0.07, 0.035, 0.07), gold, 20, 12)
        parent_to_bone(button, armature, "Spine")
    chain = curve_chain("PocketWatchChain", ((0.05, -0.72, 4.95), (0.28, -0.76, 4.55), (0.61, -0.68, 4.72)), gold)
    for obj in (torso, vest_body, shirt, tie, pocket, chain):
        parent_to_bone(obj, armature, "Spine")

    # Head and readable cartoon face.
    neck = cylinder_between("NeckMesh", (0, 0, 5.93), (0, 0, 6.48), 0.37, skin)
    head = sphere("HeadMesh", (0, -0.03, 7.12), (0.92, 0.72, 1.05), skin_light)
    ear_l = sphere("Ear.L", (-0.88, -0.02, 7.14), (0.2, 0.14, 0.29), skin_light)
    ear_r = sphere("Ear.R", (0.88, -0.02, 7.14), (0.2, 0.14, 0.29), skin_light)
    nose = sphere("Nose", (0, -0.73, 6.98), (0.25, 0.25, 0.29), skin_light)
    for obj in (neck,):
        parent_to_bone(obj, armature, "Neck")
    for obj in (head, ear_l, ear_r, nose):
        parent_to_bone(obj, armature, "Head")

    facial_eyes = []
    facial_brows = []
    for side, x in (("L", -0.35), ("R", 0.35)):
        eye = sphere(f"Eye.{side}", (x, -0.655, 7.3), (0.29, 0.12, 0.34), eye_white)
        iris_obj = sphere(f"Iris.{side}", (x, -0.765, 7.29), (0.13, 0.055, 0.16), iris)
        pupil = sphere(f"Pupil.{side}", (x, -0.815, 7.29), (0.06, 0.03, 0.08), black)
        eyebrow = sphere(f"Eyebrow.{side}", (x, -0.71, 7.7), (0.32, 0.07, 0.09), black)
        eyebrow.rotation_euler[1] = math.radians(-8 if side == "L" else 8)
        for obj in (eye, iris_obj, pupil, eyebrow):
            parent_to_bone(obj, armature, "Head")
        facial_eyes.append((eye, "BlinkLeft" if side == "L" else "BlinkRight"))
        facial_brows.append((eyebrow, side))

    mouth = sphere("Mouth", (0, -0.735, 6.66), (0.23, 0.06, 0.075), mouth_mat)
    moustache_l = sphere("Mustache.L", (-0.24, -0.79, 6.84), (0.34, 0.09, 0.115), black)
    moustache_r = sphere("Mustache.R", (0.24, -0.79, 6.84), (0.34, 0.09, 0.115), black)
    moustache_l.rotation_euler[1] = math.radians(-13)
    moustache_r.rotation_euler[1] = math.radians(13)
    tip_l = sphere("MustacheTip.L", (-0.53, -0.77, 6.9), (0.16, 0.07, 0.075), black)
    tip_r = sphere("MustacheTip.R", (0.53, -0.77, 6.9), (0.16, 0.07, 0.075), black)
    for obj in (mouth, moustache_l, moustache_r, tip_l, tip_r):
        parent_to_bone(obj, armature, "Head")
    add_facial_shape_keys(mouth, facial_eyes, facial_brows)

    hat = cone("FaisaliSidara", (0, -0.01, 8.25), 0.73, 0.59, 1.08, black, vertices=48)
    hat.rotation_euler[1] = math.radians(-2)
    parent_to_bone(hat, armature, "Head")

    # Limbs overlap beneath the jacket, so joints never expose gaps.
    limb_specs = (
        ("UpperArm.L.Mesh", (-0.92, 0, 5.72), (-1.43, 0, 4.88), 0.36, suit, "UpperArm.L"),
        ("Forearm.L.Mesh", (-1.43, 0, 4.98), (-1.5, 0, 4.02), 0.31, suit, "Forearm.L"),
        ("UpperArm.R.Mesh", (0.92, 0, 5.72), (1.43, 0, 4.88), 0.36, suit, "UpperArm.R"),
        ("Forearm.R.Mesh", (1.43, 0, 4.98), (1.5, 0, 4.02), 0.31, suit, "Forearm.R"),
        ("Thigh.L.Mesh", (-0.42, 0, 3.63), (-0.42, 0, 2.08), 0.39, suit, "Thigh.L"),
        ("Shin.L.Mesh", (-0.42, 0, 2.2), (-0.42, 0, 0.68), 0.34, suit, "Shin.L"),
        ("Thigh.R.Mesh", (0.42, 0, 3.63), (0.42, 0, 2.08), 0.39, suit, "Thigh.R"),
        ("Shin.R.Mesh", (0.42, 0, 2.2), (0.42, 0, 0.68), 0.34, suit, "Shin.R"),
    )
    for name, start, end, radius, mat, bone in limb_specs:
        obj = cylinder_between(name, start, end, radius, mat)
        parent_to_bone(obj, armature, bone)

    shoulder_l = sphere("Shoulder.L", (-1.02, 0, 5.67), (0.43, 0.42, 0.48), suit)
    shoulder_r = sphere("Shoulder.R", (1.02, 0, 5.67), (0.43, 0.42, 0.48), suit)
    parent_to_bone(shoulder_l, armature, "UpperArm.L")
    parent_to_bone(shoulder_r, armature, "UpperArm.R")

    for side, x in (("L", -1.5), ("R", 1.5)):
        cuff = cylinder_between(f"Cuff.{side}", (x, 0, 4.17), (x, 0, 3.95), 0.32, white)
        hand = sphere(f"Hand.{side}", (x, -0.01, 3.72), (0.34, 0.25, 0.47), skin_light)
        thumb_x = x + (0.24 if side == "L" else -0.24)
        thumb = sphere(f"Thumb.{side}", (thumb_x, -0.17, 3.78), (0.13, 0.11, 0.25), skin_light)
        parent_to_bone(cuff, armature, f"Forearm.{side}")
        parent_to_bone(hand, armature, f"Hand.{side}")
        parent_to_bone(thumb, armature, f"Hand.{side}")

    for side, x in (("L", -0.42), ("R", 0.42)):
        shoe_obj = sphere(f"Shoe.{side}", (x, -0.25, 0.42), (0.43, 0.72, 0.28), shoe)
        shoe_obj.rotation_euler[0] = math.radians(-5)
        parent_to_bone(shoe_obj, armature, f"Foot.{side}")

    # A hidden low-poly base helps establish a stable ground contact in viewers.
    create_animation_clips(armature)
    bpy.ops.object.select_all(action="SELECT")
    return armature


def export_glb() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT.with_suffix(".blend")))
    bpy.ops.export_scene.gltf(
        filepath=str(OUTPUT),
        export_format="GLB",
        export_apply=False,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_skins=True,
        export_morph=True,
        export_yup=True,
    )
    print(f"Exported {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


clear_scene()
build_character()
export_glb()
