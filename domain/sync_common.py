from ..core.node_schema import parent_socket_name


def bone_collection_for_context(context, armature):
    if context.mode == "EDIT_ARMATURE":
        return armature.edit_bones
    return armature.bones


def bone_parent_state(bone):
    if bone is None or bone.parent is None:
        return None, False
    return bone.parent.name, bool(getattr(bone, "use_connect", False))
