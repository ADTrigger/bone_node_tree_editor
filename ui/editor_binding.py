from bpy.types import Context

from ..controllers.sync_controller import mark_bound_tree_dirty
from ..core.blender_context import space_data_of
from ..core.binding import ensure_bound_tree, get_bound_tree


def active_editor_tree_for_armature(context: Context, armature):
    space = space_data_of(context)
    if space is None or space.type != "NODE_EDITOR":
        return None

    bound_tree = get_bound_tree(armature)
    current_tree = getattr(space, "edit_tree", None)

    # Respect pinned editors so we do not override intentionally fixed tree views.
    if getattr(space, "pin", False):
        if bound_tree is None or current_tree != bound_tree:
            return None
        return bound_tree

    if bound_tree is None:
        bound_tree = ensure_bound_tree(armature)

    if current_tree != bound_tree:
        space.node_tree = bound_tree
        mark_bound_tree_dirty(armature, "binding", "selection")

    return bound_tree
