from bpy.types import Operator

from ..controllers.sync_controller import sync_context_tree
from ..domain.services import armature_of


class OT_UpdateBoneNodeTree(Operator):
    bl_idname = "bnte.update_bone_node_tree"
    bl_label = "更新骨骼节点树"
    bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        armature = armature_of(context)
        if armature is None:
            self.report({"INFO"}, "没有选中骨架")
            return {"CANCELLED"}

        _, node_tree = sync_context_tree(
            context,
            should_arrange=True,
            origin="operator_update_bone_node_tree",
        )
        if node_tree is None:
            return {"CANCELLED"}
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

        _, node_tree = sync_context_tree(
            context,
            selection_only=True,
            origin="operator_sync_bone_node_selection",
        )
        if node_tree is None:
            return {"CANCELLED"}
        return {"FINISHED"}
