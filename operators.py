from bpy.types import Operator

from .binding import ensure_bound_tree
from .services import armature_of
from .sync import reconcile_tree_from_armature, sync_bone_selection_to_node


class OT_UpdateBoneNodeTree(Operator):
    bl_idname = "bnte.update_bone_node_tree"
    bl_label = "更新骨骼节点树"
    bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        armature = armature_of(context)
        if armature is None:
            self.report({"INFO"}, "没有选中骨架")
            return {"CANCELLED"}

        node_tree = ensure_bound_tree(armature)
        reconcile_tree_from_armature(context, armature, node_tree, should_arrange=True)
        return {"FINISHED"}


class OT_SyncBoneNodeSelection(Operator):
    bl_idname = "bnte.sync_bone_node_selection"
    bl_label = "同步骨骼选择"

    @classmethod
    def poll(cls, context):
        del context
        return True

    def execute(self, context):
        armature = armature_of(context)
        if armature is None:
            self.report({"INFO"}, "没有选中骨架")
            return {"CANCELLED"}

        if context.mode == "EDIT_ARMATURE":
            bones = armature.edit_bones
        else:
            bones = armature.bones

        node_tree = ensure_bound_tree(armature)
        sync_bone_selection_to_node(bones, node_tree)
        return {"FINISHED"}
