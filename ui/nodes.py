import bpy
from bpy.props import BoolProperty
from bpy.types import Node, NodeTree

from ..controllers.layout_controller import (
    capture_node_layout_snapshot,
    restore_locked_node_layout,
    should_capture_layout,
    should_restore_layout,
)
from ..controllers.sync_controller import apply_node_parent_edit
from ..core.blender_context import current_context, is_edit_armature_mode
from ..core.binding import get_bound_armature
from ..core.constants import (
    BONE_NODE_ICON,
    BONE_NODE_IDNAME,
    BONE_NODE_LABEL,
    TREE_ICON,
    TREE_IDNAME,
    TREE_LABEL,
)
from ..core.session import is_tree_mutating


class BoneNodeTree(NodeTree):
    bl_idname = TREE_IDNAME
    bl_label = TREE_LABEL
    bl_icon = TREE_ICON

    def update(self):
        if is_tree_mutating(self):
            return
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
        return is_tree_mutating(node_tree)

    def insert_link(self, link: bpy.types.NodeLink):
        node_tree = self.id_data
        if is_tree_mutating(node_tree):
            return

        armature = get_bound_armature(node_tree)
        if armature is None:
            return

        context = current_context()
        if not is_edit_armature_mode(context):
            link.is_muted = True
            if link.to_node == self:
                apply_node_parent_edit(
                    context,
                    armature,
                    node_tree,
                    self,
                    origin="node_insert_link_restore",
                )
            return

        if link.to_node != self:
            return

        if link.to_socket.name not in {
            self.PARENT_SOCKET_NAME,
            self.CONNECTED_PARENT_SOCKET_NAME,
        }:
            return

        apply_node_parent_edit(
            context,
            armature,
            node_tree,
            self,
            preferred_socket_name=link.to_socket.name,
            origin="node_insert_link",
        )

    def update(self):
        node_tree = self.id_data
        if is_tree_mutating(node_tree):
            return

        armature = get_bound_armature(node_tree)
        if armature is None:
            return

        context = current_context()
        preferred_socket_name = None
        if self.inputs[self.CONNECTED_PARENT_SOCKET_NAME].is_linked:
            preferred_socket_name = self.CONNECTED_PARENT_SOCKET_NAME
        elif self.inputs[self.PARENT_SOCKET_NAME].is_linked:
            preferred_socket_name = self.PARENT_SOCKET_NAME

        apply_node_parent_edit(
            context,
            armature,
            node_tree,
            self,
            preferred_socket_name=preferred_socket_name,
            origin="node_update",
        )

        if should_restore_layout(context):
            restore_locked_node_layout(node_tree, self)
            return

        if should_capture_layout(context):
            capture_node_layout_snapshot(node_tree, self)
