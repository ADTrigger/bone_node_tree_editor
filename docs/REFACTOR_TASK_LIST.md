# Bone Node Tree Editor 重构任务清单

## 1. 文档用途

本文档是 [`ARCHITECTURE_IMPROVEMENT_PLAN.md`](/d:/Codes/Blender_Addons/bone_node_tree_editor/ARCHITECTURE_IMPROVEMENT_PLAN.md) 的执行拆解版，用于把架构改进方案转换为可落地的重构任务。

适用场景：

- 制定重构排期
- 规划里程碑
- 分配开发任务
- 在重构过程中逐项验收

## 2. 使用约定

- 优先级：`P0` 表示应优先处理；`P1` 表示核心增强；`P2` 表示中期建设。
- 规模：`S` 表示小改动；`M` 表示中等规模；`L` 表示跨模块重构。
- 状态：初始统一视为 `Todo`，执行时可改为 `Doing`、`Blocked`、`Done`。
- 验收标准：用于判断任务是否真正完成，避免“代码写了但系统边界没收住”。

## 3. 推荐里程碑

### M1 架构止血

目标：

- 统一同步入口
- 去掉全局状态隐患
- 让当前架构先稳定下来

完成标志：

- 同步逻辑不再依赖多条分散入口
- 状态管理不再使用全局级锁控制所有树
- 未接线接口被正式接入或清理

### M2 同步解耦

目标：

- 将选择、拓扑、布局从 `sync.py` 中拆分出来
- 建立快照和差异驱动模型

完成标志：

- `sync.py` 不再同时承担所有同步职责
- 同步逻辑可按类型独立演进

### M3 性能重构

目标：

- 从高频轮询改为事件驱动为主
- 只同步 dirty tree
- 降低热路径成本

完成标志：

- 高开销全量扫描明显减少
- 定时器只承担兜底职责

### M4 深度开发基础设施

目标：

- 建立稳定 ID、迁移机制、测试基线和 profiling 能力

完成标志：

- 架构具备长期演进和兼容升级能力

## 4. 任务总览

| 编号 | 名称 | 优先级 | 规模 | 所属里程碑 |
| --- | --- | --- | --- | --- |
| R01 | 统一同步入口 | P0 | M | M1 |
| R02 | 引入 TreeSession | P0 | M | M1 |
| R03 | 补齐 Session 生命周期清理 | P0 | S | M1 |
| R04 | 收敛未接线接口与死路径 | P0 | S | M1 |
| R05 | 提取快照模型与差异函数 | P1 | M | M2 |
| R06 | 拆分选择同步控制器 | P1 | M | M2 |
| R07 | 拆分拓扑同步控制器 | P1 | L | M2 |
| R08 | 拆分布局同步控制器 | P1 | M | M2 |
| R09 | 引入 Dirty Flags | P0 | M | M3 |
| R10 | 建立事件桥接层 | P1 | L | M3 |
| R11 | 将 Timer 降级为兜底机制 | P0 | M | M3 |
| R12 | 隔离 `bpy.context` 与 `bpy.ops` | P0 | M | M3 |
| R13 | 升级绑定为稳定 ID | P1 | M | M4 |
| R14 | 引入 `schema_version` 与迁移逻辑 | P1 | M | M4 |
| R15 | 建立回归测试与性能基线 | P1 | M | M4 |

## 5. 详细任务清单

### R01 统一同步入口

- 状态：`Done`
- 优先级：`P0`
- 规模：`M`
- 目标：
将当前“手动更新”“节点更新回调”“定时器轮询”这几条不同同步路径收敛为统一入口，明确同步总控流程。
- 当前主要涉及文件：
[`ui.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/ui.py), [`operators.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/operators.py), [`sync.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/sync.py), [`nodes.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/nodes.py)
- 建议产出：
新增一个统一的同步调度函数，例如 `sync_controller.py` 或 `sync_entry.py`。
- 具体动作：
- 将手动操作符调用改为统一入口。
- 将 UI 轮询中直接调用的同步逻辑改为统一入口。
- 将节点回调中的写回路径统一转发到同步入口或命令入口。
- 验收标准：
- 所有同步路径都能追溯到同一个调度入口。
- `sync_tree_from_armature` 不再处于“定义了但未真正接线”的状态。
- 发生问题时，能够明确判断是哪一种同步类型触发了写回。
- 依赖：
无

### R02 引入 TreeSession

- 状态：`Done`
- 优先级：`P0`
- 规模：`M`
- 目标：
将当前 `_node_edit_lock` 和 `_tree_sync_snapshots` 的全局状态改为每棵树独立的 session。
- 当前主要涉及文件：
[`state.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/state.py), [`sync.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/sync.py), [`nodes.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/nodes.py)
- 建议产出：
新增 `session.py`，定义 `TreeSession` 和 `SessionStore`。
- 建议 session 字段：
- `mutation_depth`
- `topology_signature`
- `selection_snapshot`
- `layout_cache`
- `last_sync_origin`
- `dirty_flags`
- 验收标准：
- 不再存在全局单例锁控制所有树编辑。
- 同时打开多棵树时，不会互相干扰锁和快照状态。
- `snapshot_for_tree()` 这类能力被 session API 替代。
- 依赖：
R01

### R03 补齐 Session 生命周期清理

- 状态：`Done`
- 优先级：`P0`
- 规模：`S`
- 目标：
确保 session 在插件卸载、树销毁、重建或重新绑定时被正确清理。
- 当前主要涉及文件：
[`__init__.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/__init__.py), [`state.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/state.py), 未来的 `session.py`
- 具体动作：
- 在 `register()` / `unregister()` 补齐清理调用。
- 在树被重建或解绑时显式清理旧 session。
- 明确 session key 的来源，避免继续直接依赖裸 `as_pointer()`。
- 验收标准：
- 插件重载后不会残留旧 session。
- 删除或替换树对象后不会误用旧缓存。
- 不再存在“定义了清理函数但没接线”的状态。
- 依赖：
R02

### R04 收敛未接线接口与死路径

- 状态：`Done`
- 优先级：`P0`
- 规模：`S`
- 目标：
清理当前仓库中定义了但未稳定使用的接口，减少旁路和误导。
- 当前主要涉及文件：
[`services.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/services.py), [`sync.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/sync.py), [`state.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/state.py)
- 重点检查对象：
- `bone_node_tree_of`
- `rebuild_tree_from_armature`
- `sync_tree_from_armature`
- `clear_tree_snapshot`
- `clear_all_tree_snapshots`
- 处理原则：
- 真正需要的接口正式接线。
- 暂时不需要的接口删除或标记为内部兜底接口。
- 验收标准：
- 仓库中不再保留容易误判用途的半成品同步入口。
- 每个保留接口都能说明调用方和存在理由。
- 依赖：
R01, R03

### R05 提取快照模型与差异函数

- 状态：`Done`
- 优先级：`P1`
- 规模：`M`
- 目标：
把当前散落在 `sync.py` 中的状态采集和比较逻辑提炼成纯数据模型与 diff 函数。
- 当前主要涉及文件：
[`sync.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/sync.py)
- 建议新增文件：
- `snapshots.py`
- `diff.py`
- 建议提取对象：
- `ArmatureSnapshot`
- `TreeTopologySnapshot`
- `SelectionSnapshot`
- `LayoutSnapshot`
- 验收标准：
- 快照采集、差异计算和 Blender API 写回不再混在同一函数中。
- 至少拓扑和选择状态拥有独立的 diff 表达。
- 依赖：
R02

### R06 拆分选择同步控制器

- 状态：`Done`
- 优先级：`P1`
- 规模：`M`
- 目标：
把选择同步从 `sync.py` 中独立出来，形成单独控制器。
- 当前主要涉及文件：
[`sync.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/sync.py), [`ui.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/ui.py), [`operators.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/operators.py)
- 建议新增文件：
`selection_controller.py`
- 范围建议：
- `sync_selection_state`
- `sync_node_selection_to_bone`
- `sync_bone_selection_to_node`
- active bone / active node 仲裁
- 验收标准：
- 选择同步逻辑不再和拓扑修复逻辑混在一起。
- 选择同步可以独立被调用和测试。
- 依赖：
R01, R05

### R07 拆分拓扑同步控制器

- 状态：`Done`
- 优先级：`P1`
- 规模：`L`
- 目标：
把拓扑、父子关系修复、链接规范化和树重建逻辑拆为独立控制器。
- 当前主要涉及文件：
[`sync.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/sync.py), [`nodes.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/nodes.py), [`layout.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/layout.py)
- 建议新增文件：
`topology_controller.py`
- 建议纳入范围：
- `normalize_parent_links`
- `apply_parent_link_change`
- `restore_node_parent_from_bone`
- `apply_node_parent_link_edit`
- `reconcile_tree_from_armature`
- `rebuild_tree_from_armature`
- 验收标准：
- 父子关系编辑与拓扑同步有清晰边界。
- 拓扑控制器可以明确区分“增量 patch”和“全量重建兜底”。
- `sync.py` 不再继续承担结构级写回主逻辑。
- 依赖：
R05

### R08 拆分布局同步控制器

- 状态：`Done`
- 优先级：`P1`
- 规模：`M`
- 目标：
将布局快照记录、布局恢复、自动排布从主同步流程中剥离。
- 当前主要涉及文件：
[`sync.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/sync.py), [`layout.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/layout.py), [`nodes.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/nodes.py)
- 建议新增文件：
`layout_controller.py`
- 处理重点：
- 明确哪些情况允许记录布局
- 明确哪些情况允许恢复布局
- Object 模式的“锁定”从被动回滚改为明确策略
- 验收标准：
- 布局逻辑独立于选择同步和拓扑同步。
- 不再依赖整树被动恢复来限制交互。
- 依赖：
R02, R05

### R09 引入 Dirty Flags

- 状态：`Done`
- 优先级：`P0`
- 规模：`M`
- 目标：
把“每次都扫一遍”的同步策略改成“只处理脏树、脏状态”。
- 当前主要涉及文件：
[`ui.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/ui.py), [`sync.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/sync.py), 未来的 `session.py`
- 建议 dirty 分类：
- `selection_dirty`
- `topology_dirty`
- `layout_dirty`
- `binding_dirty`
- 验收标准：
- 未发生变更时，不触发不必要的重同步。
- 同步调度可以根据 dirty 类型选择不同控制器。
- 依赖：
R02, R06, R07, R08

### R10 建立事件桥接层

- 状态：`Done`
- 优先级：`P1`
- 规模：`L`
- 目标：
用事件机制代替当前主要依赖轮询的同步模式。
- 当前主要涉及文件：
[`ui.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/ui.py), [`__init__.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/__init__.py)
- 建议新增文件：
`event_bridge.py`
- 优先研究方向：
- `depsgraph_update_post`
- `undo_post`
- `load_post`
- `msgbus`
- 验收标准：
- 拓扑变化和主要状态变化可通过事件标记 dirty。
- 不再依赖高频轮询作为主触发手段。
- 依赖：
R09

### R11 将 Timer 降级为兜底机制

- 状态：`Done`
- 优先级：`P0`
- 规模：`M`
- 目标：
保留 timer，但让它只承担低频保底同步，而不是高频主同步入口。
- 当前主要涉及文件：
[`ui.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/ui.py)
- 建议动作：
- 降低执行频率
- 只检查 dirty tree
- 不再扫描所有窗口下的所有编辑器作为常规路径
- 验收标准：
- timer 关闭后，事件驱动仍能完成大部分同步。
- timer 开启时，其主要作用是兜底修复，而不是主逻辑。
- 依赖：
R09, R10

### R12 隔离 `bpy.context` 与 `bpy.ops`

- 状态：`Done`
- 优先级：`P0`
- 规模：`M`
- 目标：
将核心逻辑对全局上下文和 Blender operator 的直接依赖降到最低。
- 当前主要涉及文件：
[`services.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/services.py), [`nodes.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/nodes.py), [`sync.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/sync.py), [`ui.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/ui.py)
- 建议新增文件：
- `blender_context.py`
- `armature_repo.py`
- `node_tree_repo.py`
- 重点动作：
- 将热路径中的 `bpy.ops.object.vertex_group_set_active` 评估为直接数据 API 或隔离封装
- 将直接读取 `bpy.context` 的逻辑改为显式传参或适配层调用
- 验收标准：
- 业务层不再到处直接抓取全局 `bpy.context`
- `bpy.ops` 不再出现在高频同步热路径里
- 依赖：
R01, R05

### R13 升级绑定为稳定 ID

- 状态：`Done`
- 优先级：`P1`
- 规模：`M`
- 目标：
将当前基于名称的 Armature 与 NodeTree 绑定升级为稳定标识绑定。
- 当前主要涉及文件：
[`binding.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/binding.py)
- 建议动作：
- 为 Armature 和 NodeTree 建立 UUID
- 保留必要的向后兼容逻辑
- 将名称推断降级为兼容兜底，而不是主绑定策略
- 验收标准：
- Armature 重命名后不会丢失绑定
- 复制对象时能识别并处理过期绑定
- 依赖：
R02

### R14 引入 `schema_version` 与迁移逻辑

- 状态：`Done`
- 优先级：`P1`
- 规模：`M`
- 目标：
为未来持续演进提供版本升级与兼容入口。
- 当前主要涉及文件：
[`binding.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/binding.py), [`__init__.py`](/d:/Codes/Blender_Addons/bone_node_tree_editor/__init__.py)
- 建议新增文件：
`migration.py`
- 迁移范围建议：
- 自定义属性结构
- 绑定字段
- session 初始化兼容
- 旧版本 tree 数据恢复
- 验收标准：
- 插件升级后能够识别旧数据并执行迁移。
- 新旧版本的绑定和树数据不会静默冲突。
- 依赖：
R13

### R15 建立回归测试与性能基线

- 状态：`Todo`
- 优先级：`P1`
- 规模：`M`
- 目标：
给后续重构建立最低限度的质量保护网和性能对比基线。
- 当前主要涉及范围：
全仓库
- 建议产出：
- 基础测试目录
- 最小 rig 测试样例
- 中等规模 rig 测试样例
- profiling 记录模板
- 建议优先覆盖场景：
- 节点选择同步
- 骨骼选择同步
- 父子关系编辑回写
- 树重建与增量同步
- Armature 重命名与复制绑定
- 验收标准：
- 关键同步路径至少有基础回归验证手段。
- 重构前后能比较主要场景的耗时变化。
- 依赖：
R06, R07, R11, R12, R14

## 6. 建议执行顺序

如果希望以“风险最低、收益最高”的方式推进，建议按下面顺序执行：

1. R01 统一同步入口
2. R02 引入 TreeSession
3. R03 补齐 Session 生命周期清理
4. R04 收敛未接线接口与死路径
5. R05 提取快照模型与差异函数
6. R06 拆分选择同步控制器
7. R07 拆分拓扑同步控制器
8. R08 拆分布局同步控制器
9. R09 引入 Dirty Flags
10. R10 建立事件桥接层
11. R11 将 Timer 降级为兜底机制
12. R12 隔离 `bpy.context` 与 `bpy.ops`
13. R13 升级绑定为稳定 ID
14. R14 引入 `schema_version` 与迁移逻辑
15. R15 建立回归测试与性能基线

## 7. 第一批建议直接开工的任务

如果只先做第一轮重构，推荐先开以下 6 项：

- [ ] R01 统一同步入口
- [ ] R02 引入 TreeSession
- [ ] R03 补齐 Session 生命周期清理
- [ ] R04 收敛未接线接口与死路径
- [ ] R09 引入 Dirty Flags
- [ ] R12 隔离 `bpy.context` 与 `bpy.ops`

原因：

- 这几项能最先降低当前架构的失控风险。
- 它们会直接影响后续拆分控制器时的成本。
- 做完这几项后，后续的大拆分会更顺手。

## 8. 每个里程碑的完成定义

### M1 完成定义

- 同步入口已经统一
- 全局锁已被树级状态替代
- 生命周期清理完整
- 当前仓库接口边界更清晰

### M2 完成定义

- `sync.py` 不再是所有同步逻辑的唯一承载点
- 选择、拓扑、布局三个方向已有清晰边界
- 快照与差异逻辑已可独立演进

### M3 完成定义

- 主同步触发方式从轮询转向事件
- 只处理 dirty tree
- 热路径中高成本操作明显下降

### M4 完成定义

- 绑定关系具备稳定 ID
- 存在版本化和迁移入口
- 重构具备最基本的回归和性能验证能力

## 9. 备注

执行本清单时建议遵循两个原则：

- 每次重构尽量同时完成“接口收敛 + 行为验证”，避免只做搬家不做边界治理。
- 每做完一个阶段就补一次最小验证用例，否则重构越往后越难判断行为是否回归。

这份清单不是一次性全部完成的硬性要求，更适合作为接下来几个迭代的主干任务池。
