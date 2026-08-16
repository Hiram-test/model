from __future__ import annotations  # 启用延迟类型注解，避免协议与数据类前向引用问题。
from dataclasses import dataclass  # 定义统一比较上下文与方法输出对象。
from pathlib import Path  # 管理比较输出目录和外部模型交换文件。
from typing import Any  # 标注异质审计字典。
from typing import Protocol  # 定义可替换网格方法的结构化接口。
from tbeam_fem_core import Action  # 复用三维T梁五维网格动作定义。
from tbeam_fem_core import Geometry  # 复用三维T梁几何定义。
from tbeam_fem_core import Load  # 复用三维T梁载荷定义。
from tbeam_fem_core import Material  # 复用三维T梁材料定义。
from tbeam_fem_core import Mesh  # 复用三维T梁网格对象。
from tbeam_fem_core import Solution  # 复用三维有限元求解结果对象。
from tbeam_fem_core import ZZ  # 复用恢复型误差指标对象。
@dataclass(frozen=True)  # 将单次方法调用所需状态定义为不可变对象。
class BenchmarkContext:  # 保存同一粗解下所有比较方法共享的公平输入。
    geometry: Geometry  # 保存三维T梁几何。
    material: Material  # 保存线弹性材料。
    load: Load  # 保存端部载荷。
    goal: str  # 保存自然语言任务目标。
    target_dof: int  # 保存统一终局自由度预算。
    coarse_action: Action  # 保存统一粗网格动作。
    coarse_mesh: Mesh  # 保存统一粗网格。
    coarse_solution: Solution  # 保存统一粗解。
    coarse_zz: ZZ  # 保存统一粗解恢复型误差指标。
    state_image: Path  # 保存供VLM审阅的粗解图像路径。
    work_dir: Path  # 保存当前方法的隔离工作目录。
@dataclass(frozen=True)  # 将任一方法提出的终局网格动作定义为统一对象。
class MethodProposal:  # 保存方法动作、成本记账和可审计证据。
    method: str  # 保存方法唯一名称。
    action: Action | None  # 保存终局五维动作，缺失表示外部组件尚未接入。
    status: str  # 保存ready、external_component_required或failed等状态。
    audit: dict[str, Any]  # 保存不含隐藏推理的可审计决策记录。
    surrogate_evaluations: int  # 保存低成本代理评价次数。
    mesh_compilations: int  # 保存确定性网格编译次数。
    local_predictions: int  # 保存局部预测或patch评价次数。
    internal_full_fem_solves: int  # 保存方法内部完整有限元求解次数。
    offline_training_required: bool  # 标记是否需要离线训练或专家标签。
    terminal_solve_required: bool  # 标记返回动作后是否还需统一终局求解。
class MeshMethod(Protocol):  # 定义一次性网格方法的最小协议。
    name: str  # 要求每个方法提供稳定名称。
    def propose(self, context: BenchmarkContext) -> MethodProposal:  # 要求方法从统一上下文提出终局动作。
        ...  # 仅定义协议，不提供默认实现。
def action_to_dict(action: Action | None) -> dict[str, float] | None:  # 将可选动作转换为JSON可序列化字典。
    if action is None:  # 检查方法是否尚未返回动作。
        return None  # 对未接入外部模型的方法保留空值。
    return {"hx_root": float(action.hx_root), "hx_mid": float(action.hx_mid), "hx_tip": float(action.hx_tip), "h_web": float(action.h_web), "h_flange": float(action.h_flange)}  # 按固定顺序返回五维动作。
