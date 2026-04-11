import bpy
from bpy.props import BoolProperty
from bpy.types import Node, NodeTree

from .binding import get_bound_armature
from .constants import (
    BONE_NODE_ICON,
    BONE_NODE_IDNAME,
    BONE_NODE_LABEL,
    TREE_ICON,
    TREE_IDNAME,
    TREE_LABEL,
)
from .state import is_node_edit_locked
from .sync import (
    apply_node_parent_link_edit,
    capture_node_layout_snapshot,
    restore_locked_tree_layout,
)


class BoneNodeTree(NodeTree):
    bl_idname = TREE_IDNAME
    bl_label = TREE_LABEL
    bl_icon = TREE_ICON

    def update(self):
        if is_node_edit_locked():
            return

        mode = getattr(bpy.context, "mode", None)
        if mode == "OBJECT":
            restore_locked_tree_layout(self)
        return


class BoneNode(Node):
    bl_idname = BONE_NODE_IDNAME
    bl_label = BONE_NODE_LABEL
    bl_icon = BONE_NODE_ICON
    PARENT_SOCKET_NAME = "Parent"
    CONNECTED_PARENT_SOCKET_NAME = "Connected Parent"
    CHILD_SOCKET_NAME = "Child Of"
    has_parent: BoolProperty(name="has_parent", default=False)  # type: ignore
    is_connected_parent: BoolProperty(name="is_connected_parent", default=False)  # type: ignore

    def init(self, context):
        del context
        parent_socket = self.inputs.new("NodeSocketString", self.PARENT_SOCKET_NAME)
        parent_socket.hide_value = True
        connected_parent_socket = self.inputs.new("NodeSocketString", self.CONNECTED_PARENT_SOCKET_NAME)
        connected_parent_socket.hide_value = True
        self.outputs.new("NodeSocketString", self.CHILD_SOCKET_NAME)
        self.hide = False

    def draw_label(self):
        return self.name

    @classmethod
    def poll(self, node_tree):
        del node_tree
        return is_node_edit_locked()

    def insert_link(self, link: bpy.types.NodeLink):
        if is_node_edit_locked():
            return

        node_tree = self.id_data
        armature = get_bound_armature(node_tree)
        if armature is None:
            return

        if bpy.context.mode != "EDIT_ARMATURE":
            link.is_muted = True
            if link.to_node == self:
                apply_node_parent_link_edit(bpy.context, armature, node_tree, self)
            return

        if link.to_node != self:
            return

        if link.to_socket.name not in {
            self.PARENT_SOCKET_NAME,
            self.CONNECTED_PARENT_SOCKET_NAME,
        }:
            return

        apply_node_parent_link_edit(
            bpy.context,
            armature,
            node_tree,
            self,
            preferred_socket_name=link.to_socket.name,
        )

    def update(self):
        if is_node_edit_locked():
            return

        node_tree = self.id_data
        armature = get_bound_armature(node_tree)
        if armature is None:
            return

        preferred_socket_name = None
        if self.inputs[self.CONNECTED_PARENT_SOCKET_NAME].is_linked:
            preferred_socket_name = self.CONNECTED_PARENT_SOCKET_NAME
        elif self.inputs[self.PARENT_SOCKET_NAME].is_linked:
            preferred_socket_name = self.PARENT_SOCKET_NAME

        apply_node_parent_link_edit(
            bpy.context,
            armature,
            node_tree,
            self,
            preferred_socket_name=preferred_socket_name,
        )

        if bpy.context.mode != "OBJECT":
            capture_node_layout_snapshot(node_tree, self)
