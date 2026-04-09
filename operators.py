from bpy.props import BoolProperty
from bpy.types import Operator

from .nodes import BoneNode
from .services import armature_of, bone_node_tree_of, sync_bone_color_to_node
from .state import set_node_edit_lock


class OT_UpdateBoneNodeTree(Operator):
    bl_idname = "bnte.update_bone_node_tree"
    bl_label = "更新骨骼节点树"
    bl_options = {"REGISTER", "UNDO"}
    only_visible: BoolProperty(name="only_visible", default=False)  # type: ignore

    def arrange_nodes(self, root_bones: list, nodes):
        subtree_height_map = {}
        default_node_height = 50

        def calculate_subtree_height(bone):
            result = 0
            if not bone.children:
                result = default_node_height
            else:
                result = sum(calculate_subtree_height(c) for c in bone.children)
            subtree_height_map[bone.name] = result
            return result

        def layout_node(bone, x, y):
            nodes.get(bone.name).location = (x, y)

            total_height2 = 0
            for child_bone in bone.children:
                total_height2 += subtree_height_map[child_bone.name]
            if total_height2 == 0:
                return

            start_y2 = -(total_height2) / 2
            start_y2 += y
            for child_bone in bone.children:
                subtree_height2 = subtree_height_map[child_bone.name]
                layout_node(child_bone, x + 150, start_y2 + (subtree_height2 / 2))
                start_y2 += subtree_height2

        total_height = 0
        for root_bone in root_bones:
            subtree_height = calculate_subtree_height(root_bone)
            total_height += subtree_height
        start_y = total_height / 2
        for root_bone in root_bones:
            subtree_height = subtree_height_map[root_bone.name]
            layout_node(root_bone, 0, start_y - (subtree_height / 2))
            start_y -= subtree_height

    def execute(self, context):
        node_tree = bone_node_tree_of(context)
        nodes = node_tree.nodes
        nodes.clear()

        armature = armature_of(context)
        if armature is None:
            self.report({"INFO"}, "没有选中骨架")
            return {"CANCELLED"}

        set_node_edit_lock(True)

        if context.mode == "EDIT_ARMATURE":
            bones = armature.edit_bones
        else:
            bones = armature.bones

        for bone in bones:
            node = nodes.new(BoneNode.bl_idname)
            node.name = bone.name
            node.width = len(node.name) * 8
            node.select = bone.select
            node.has_parent = bone.parent is not None
            sync_bone_color_to_node(bone.color, node)
            if bones.active == bone:
                nodes.active = node

        root_bones = []
        node_tree.links.clear()
        for bone in bones:
            node = nodes.get(bone.name)
            if bone.parent:
                parent_node = nodes.get(bone.parent.name)
                if parent_node:
                    node_tree.links.new(
                        parent_node.outputs["Child Of"],
                        node.inputs["parent"],
                    )
            else:
                root_bones.append(bone)

        set_node_edit_lock(False)
        self.arrange_nodes(root_bones, nodes)
        return {"FINISHED"}


class OT_SyncBoneNodeSelection(Operator):
    bl_idname = "bnte.sync_bone_node_selection"
    bl_label = "同步骨骼选择"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        node_tree = bone_node_tree_of(context)
        nodes = node_tree.nodes
        for node in nodes:
            node.select = False

        if context.mode == "EDIT_ARMATURE":
            selected_bones = context.selected_editable_bones
            active_bone = context.active_bone
        elif context.mode == "POSE" or context.mode == "PAINT_WEIGHT":
            selected_bones = context.selected_pose_bones
            active_bone = context.active_pose_bone
        elif context.mode == "OBJECT":
            armature = armature_of(context)
            if armature is None:
                self.report({"INFO"}, "没有选中骨架")
                return {"CANCELLED"}
            active_bone = armature.bones.active
            if active_bone is None:
                active_bone = armature.edit_bones.active

            selected_bones = []
            for bone in armature.bones:
                if bone.select:
                    selected_bones.append(bone)
            if len(selected_bones) == 0:
                for bone in armature.edit_bones:
                    if bone.select:
                        selected_bones.append(bone)
        else:
            selected_bones = context.selected_bones
            active_bone = context.active_bone

        for bone in selected_bones:
            node = nodes.get(bone.name)
            if node:
                node.select = True

        if active_bone:
            nodes.active = nodes.get(active_bone.name)
        else:
            nodes.active = None

        return {"FINISHED"}
