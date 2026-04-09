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
from .state import is_node_edit_locked, set_node_edit_lock


class BoneNodeTree(NodeTree):
    bl_idname = TREE_IDNAME
    bl_label = TREE_LABEL
    bl_icon = TREE_ICON

    def update(self):
        # 在 Blender 4.x 中，节点连线变更由 NodeTree.update 统一处理更稳定
        if is_node_edit_locked():
            return

        context = bpy.context
        if context.mode != "EDIT_ARMATURE":
            return

        armature = armature_of(context)
        if armature is None:
            return

        set_node_edit_lock(True)
        try:
            for node in self.nodes:
                if not isinstance(node, BoneNode):
                    continue

                parent = None
                is_connected_parent = False

                connected_parent_input = node.inputs.get(BoneNode.CONNECTED_PARENT_SOCKET_NAME)
                if (
                    connected_parent_input
                    and connected_parent_input.is_linked
                    and connected_parent_input.links
                ):
                    link = connected_parent_input.links[0]
                    if link.from_node and link.from_node != node:
                        parent = link.from_node.name
                        is_connected_parent = True
                else:
                    parent_input = node.inputs.get(BoneNode.PARENT_SOCKET_NAME)
                    if parent_input and parent_input.is_linked and parent_input.links:
                        link = parent_input.links[0]
                        if link.from_node and link.from_node != node:
                            parent = link.from_node.name

                if node._set_bone_parent(parent, is_connected_parent):
                    node.has_parent = parent is not None
                    node.is_connected_parent = is_connected_parent
        finally:
            set_node_edit_lock(False)


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
        # 左侧输入接口：当前骨骼的父级
        parent_socket = self.inputs.new("NodeSocketString", self.PARENT_SOCKET_NAME)
        parent_socket.hide_value = True
        # 左侧输入接口：当前骨骼与父级末端相连
        connected_parent_socket = self.inputs.new("NodeSocketString", self.CONNECTED_PARENT_SOCKET_NAME)
        connected_parent_socket.hide_value = True
        # 右侧输出接口：当前骨骼可作为其它骨骼的父级
        self.outputs.new("NodeSocketString", self.CHILD_SOCKET_NAME)
        # 使用展开样式显示节点与接口
        self.hide = False

    def draw_label(self):
        return self.name

    @classmethod
    def poll(self, node_tree):
        return is_node_edit_locked()

    def _set_bone_parent(self, parent: str | None, is_connected_parent: bool = False) -> bool:
        context = bpy.context
        armature = armature_of(context)
        if armature:
            if context.mode != "EDIT_ARMATURE":
                bone = armature.bones.get(self.name)
                node_tree = bone_node_tree_of(context)

                for link in list(self.inputs[self.PARENT_SOCKET_NAME].links):
                    node_tree.links.remove(link)
                for link in list(self.inputs[self.CONNECTED_PARENT_SOCKET_NAME].links):
                    node_tree.links.remove(link)
                if bone.parent:
                    node_parent = node_tree.nodes.get(bone.parent.name)
                    if node_parent:
                        parent_socket_name = (
                            self.CONNECTED_PARENT_SOCKET_NAME
                            if bone.use_connect
                            else self.PARENT_SOCKET_NAME
                        )
                        node_tree.links.new(
                            node_parent.outputs[self.CHILD_SOCKET_NAME],
                            self.inputs[parent_socket_name],
                        )
                        return False
            else:
                bone = armature.edit_bones.get(self.name)
                bone_parent = None
                if parent:
                    bone_parent = armature.edit_bones.get(parent)
                if bone:
                    if bone_parent == bone:
                        return False

                    ancestor = bone_parent
                    while ancestor:
                        if ancestor == bone:
                            return False
                        ancestor = ancestor.parent

                    bone.parent = bone_parent
                    bone.use_connect = bool(bone_parent and is_connected_parent)
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

        if link.to_socket.name == self.PARENT_SOCKET_NAME:
            for other_link in list(self.inputs[self.CONNECTED_PARENT_SOCKET_NAME].links):
                link.id_data.links.remove(other_link)
            is_connected_parent = False
        elif link.to_socket.name == self.CONNECTED_PARENT_SOCKET_NAME:
            for other_link in list(self.inputs[self.PARENT_SOCKET_NAME].links):
                link.id_data.links.remove(other_link)
            is_connected_parent = True
        else:
            return

        if self._set_bone_parent(link.from_node.name, is_connected_parent):
            self.has_parent = True
            self.is_connected_parent = is_connected_parent

    def update(self):
        if is_node_edit_locked():
            return

        active_input = None
        if self.inputs[self.CONNECTED_PARENT_SOCKET_NAME].is_linked:
            active_input = self.inputs[self.CONNECTED_PARENT_SOCKET_NAME]
        elif self.inputs[self.PARENT_SOCKET_NAME].is_linked:
            active_input = self.inputs[self.PARENT_SOCKET_NAME]

        if active_input and active_input.is_linked:
            link = active_input.links[0]
            if link and link.is_muted:
                self._set_bone_parent(None, False)
                self.has_parent = False
                self.is_connected_parent = False
        elif self.has_parent:
            self._set_bone_parent(None, False)
            self.has_parent = False
            self.is_connected_parent = False
