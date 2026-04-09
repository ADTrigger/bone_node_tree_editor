import bpy
from bpy.props import BoolProperty
from bpy.types import NodeTree, Node

from .constants import (
    TREE_IDNAME,
    TREE_LABEL,
    TREE_ICON,
    BONE_NODE_IDNAME,
    BONE_NODE_LABEL,
    BONE_NODE_ICON,
)
from .services import armature_of, bone_node_tree_of
from .state import is_node_edit_locked


class BoneNodeTree(NodeTree):
    bl_idname = TREE_IDNAME
    bl_label = TREE_LABEL
    bl_icon = TREE_ICON


class BoneNode(Node):
    bl_idname = BONE_NODE_IDNAME
    bl_label = BONE_NODE_LABEL
    bl_icon = BONE_NODE_ICON
    has_parent: BoolProperty(name="has_parent", default=False)  # type: ignore

    def init(self, context):
        self.inputs.new("NodeSocketString", "parent")
        self.outputs.new("NodeSocketString", "Child Of")
        self.hide = True

    def draw_label(self):
        return self.name

    @classmethod
    def poll(self, node_tree):
        return is_node_edit_locked()

    def _set_bone_parent(self, parent: str | None) -> bool:
        context = bpy.context
        armature = armature_of(context)
        if armature:
            if context.mode != "EDIT_ARMATURE":
                bone = armature.bones.get(self.name)
                node_tree = bone_node_tree_of(context)

                for link in self.inputs["parent"].links:
                    node_tree.links.remove(link)
                if bone.parent:
                    node_parent = node_tree.nodes.get(bone.parent.name)
                    if node_parent:
                        node_tree.links.new(
                            node_parent.outputs["Child Of"],
                            self.inputs["parent"],
                        )
                        return False
            else:
                bone = armature.edit_bones.get(self.name)
                bone_parent = None
                if parent:
                    bone_parent = armature.edit_bones.get(parent)
                if bone:
                    bone.parent = bone_parent
                    return True
        return False

    def insert_link(self, link: bpy.types.NodeLink):
        if is_node_edit_locked():
            return

        if bpy.context.mode != "EDIT_ARMATURE":
            link.is_muted = True
            return

        if link.to_node != self:
            return

        if self._set_bone_parent(link.from_node.name):
            self.has_parent = True

    def update(self):
        if is_node_edit_locked():
            return

        if self.inputs["parent"].is_linked:
            link = self.inputs["parent"].links[0]
            if link and link.is_muted:
                self._set_bone_parent(None)
        elif self.has_parent:
            self._set_bone_parent(None)
