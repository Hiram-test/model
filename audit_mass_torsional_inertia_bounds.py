"""审计现有空间质量对全局扭转平动惯量的几何上界。

本脚本并不把 ``sum(m*y^2)`` 冒充真实模态广义质量。它只回答一个更窄、但可审计的
问题：如果只在现有猫道宽度内重新摆放 MASS21 附件质量，最多能把关于顺桥轴的横向
平动惯量提高多少；该上界是否足以解释 R195 诊断中 TS2 仍偏高的频差。

单位统一采用当前 MAPDL 模型的 ``tonne-mm-s-N`` 体系：质量为 tonne，坐标为 mm，
横向平动惯量为 tonne*mm^2。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


# SCRIPT_DIR 是 V2.0 工作目录；所有输入和输出均以它为锚点，避免依赖调用者当前目录。
SCRIPT_DIR = Path(__file__).resolve().parent
# PROJECT_ROOT 是项目根目录；parents[1] 对应 ``D:\张靖皋大桥``。
PROJECT_ROOT = SCRIPT_DIR.parents[1]
# BASE_MODEL_DIR 保存基础索网节点/单元 CSV；其 CAD x 坐标对应当前 APDL 横桥 Y。
BASE_MODEL_DIR = (
    PROJECT_ROOT
    / "02_CAD几何模型"
    / "Catwalk_FullLine_ANSYS_AIValidation_V1.0"
)
# MASS_NODE_CSV 保存空间化后的全部 MASS21 节点、质量、系统及构件来源。
MASS_NODE_CSV = SCRIPT_DIR / "mass21_spatialized_v2_nodes.csv"
# OUTPUT_JSON 是机器可读审计结果；浮点值保留双精度而不在中间步骤四舍五入。
OUTPUT_JSON = SCRIPT_DIR / "audit" / "torsional_mass_inertia_bound_audit.json"
# OUTPUT_MD 是人工复核摘要；其中必须显式说明这只是几何惯量界而非模态质量。
OUTPUT_MD = SCRIPT_DIR / "audit" / "扭转质量空间惯量上界审计_V2.0.md"


# LINK_AREA_MM2 是 LINK180 转换后实际截面面积；数值来自正式初始状态 include。
LINK_AREA_MM2 = {
    1: 1393.668228093791,
    2: 1400.496622996084,
}
# LINK_DENSITY_TONNE_PER_MM3 是权威恒载 include 最终覆盖的材料1/2密度。
LINK_DENSITY_TONNE_PER_MM3 = {
    1: 1.264848052212931e-8,
    2: 8.598817050785234e-9,
}
# OUTERMOST_TRANSVERSE_MM 是两幅猫道最外侧底索的绝对横桥坐标。
OUTERMOST_TRANSVERSE_MM = 24120.0
# FULL_MODEL_MASS_TONNE 来自正式静力质量闭合文件，用于揭示本几何积分未覆盖的小残差。
FULL_MODEL_MASS_TONNE = 4108.466907581062
# R195_TS2_HZ 是材料1/2同时改为195 GPa时，经跨算例 MAC 跟踪的 TS2 频率。
R195_TS2_HZ = 0.1711579261584322
# TARGET_TS2_HZ 是附件2-3表4-1的 TS2 目标频率。
TARGET_TS2_HZ = 0.1571


def read_base_nodes() -> dict[int, tuple[float, float, float]]:
    """读取基础索网节点坐标。

    返回：
        以节点号为键、``(CAD横桥x, CAD顺桥y, CAD竖向z)`` 为值的字典。
    """

    # node_path 是生成正式 APDL 基础网格时使用的同源节点表。
    node_path = BASE_MODEL_DIR / "full_line_beam4_nodes.csv"
    # nodes 保存全部节点坐标；后续单元积分必须能查到每个端点。
    nodes: dict[int, tuple[float, float, float]] = {}
    # utf-8-sig 同时兼容有/无 BOM 的 CSV；newline='' 避免 Windows 空行问题。
    with node_path.open("r", encoding="utf-8-sig", newline="") as handle:
        # reader 用表头取值，避免依赖列顺序。
        reader = csv.DictReader(handle)
        # 每一行代表一个基础网格节点；坐标均按 mm 读取为 float64 Python 浮点。
        for row in reader:
            # node_id 是后续单元端点的稳定主键。
            node_id = int(row["node_id"])
            # 三个坐标保持原 CSV 口径；横向惯量只使用第一项，但长度需要全部三项。
            nodes[node_id] = (
                float(row["x_mm"]),
                float(row["y_mm"]),
                float(row["z_mm"]),
            )
    # 空节点表意味着输入路径或编码错误，必须提前失败而不是输出零惯量。
    if not nodes:
        raise ValueError(f"基础节点表为空：{node_path}")
    # 返回节点映射供索单元质量积分使用。
    return nodes


def integrate_link_mass_and_inertia(
    nodes: dict[int, tuple[float, float, float]],
) -> tuple[float, float]:
    """按索单元中点积分材料1/2的质量与横向平动惯量。

    参数：
        nodes：``read_base_nodes`` 返回的节点坐标映射。

    返回：
        ``(索质量/tonne, sum(m*y^2)/(tonne*mm^2))``。
    """

    # element_path 保存基础 LINK10/BEAM4 拓扑；正式模型只把材料1/2索转换成 LINK180。
    element_path = BASE_MODEL_DIR / "full_line_beam4_elements.csv"
    # total_mass 累积材料1/2索的分布质量。
    total_mass = 0.0
    # transverse_inertia 累积关于顺桥轴的横向平动惯量近似 sum(m*y^2)。
    transverse_inertia = 0.0
    # 逐单元读取可以避免把大型表一次性加载到内存。
    with element_path.open("r", encoding="utf-8-sig", newline="") as handle:
        # reader 按稳定表头解析端点和材料号。
        reader = csv.DictReader(handle)
        # 每次循环处理一根基础单元。
        for row in reader:
            # material_id 决定该单元是否属于本次索质量积分。
            material_id = int(row["material_id"])
            # 材料3/4横梁在正式恒载 include 中密度为零，其质量已进入 MASS21，必须跳过。
            if material_id not in LINK_AREA_MM2:
                continue
            # point_i 和 point_j 是索单元两端的三维坐标。
            point_i = nodes[int(row["n1"])]
            point_j = nodes[int(row["n2"])]
            # element_length 使用三维欧氏距离，不能只用顺桥投影长度。
            element_length = math.dist(point_i, point_j)
            # element_mass=面积×密度×长度，单位闭合为 tonne。
            element_mass = (
                LINK_AREA_MM2[material_id]
                * LINK_DENSITY_TONNE_PER_MM3[material_id]
                * element_length
            )
            # transverse_midpoint 是单元中点横桥坐标；本模型同一根索横坐标恒定，
            # 中点积分在横向惯量上实际是精确的。
            transverse_midpoint = 0.5 * (point_i[0] + point_j[0])
            # 累积索质量。
            total_mass += element_mass
            # 累积横向平动惯量；符号在平方后自动消除，符合双幅对称体系。
            transverse_inertia += element_mass * transverse_midpoint**2
    # 未积分到索说明材料号或路径发生变化，应立即报错。
    if total_mass <= 0.0:
        raise ValueError(f"没有从基础单元表积分到材料1/2索质量：{element_path}")
    # 返回索质量和横向惯量。
    return total_mass, transverse_inertia


def integrate_mass21() -> tuple[float, float, dict[str, dict[str, float]]]:
    """汇总空间化 MASS21 的质量、横向惯量和系统分组。

    返回：
        ``(MASS21总质量, MASS21横向惯量, system分组统计)``。
    """

    # total_mass 累积每个合并 MASS21 节点的平动质量。
    total_mass = 0.0
    # transverse_inertia 累积 MASS21 的 sum(m*y^2)。
    transverse_inertia = 0.0
    # grouped 记录 gate/passage/original 三个系统的质量与惯量，便于定位可移动部分。
    grouped: dict[str, dict[str, float]] = {}
    # 读取空间质量节点表；每行已合并同一节点上的多个构件质量。
    with MASS_NODE_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        # reader 使用明确列名，避免组件字符串中的分号影响解析。
        reader = csv.DictReader(handle)
        # 每次循环汇总一个 MASS21 节点。
        for row in reader:
            # mass_tonne 是三个平动方向相同的节点质量标量。
            mass_tonne = float(row["mass_tonne"])
            # transverse_y_mm 是当前 APDL 横桥 Y 坐标。
            transverse_y_mm = float(row["y_mm"])
            # system 区分保留原节点、门架空间化和横通道空间化质量。
            system = row["system"]
            # node_inertia 是该节点对 sum(m*y^2) 的贡献。
            node_inertia = mass_tonne * transverse_y_mm**2
            # 累积总质量与总横向惯量。
            total_mass += mass_tonne
            transverse_inertia += node_inertia
            # setdefault 为首次出现的系统创建零值统计容器。
            bucket = grouped.setdefault(system, {"mass_tonne": 0.0, "inertia_tonne_mm2": 0.0})
            # 把当前节点质量计入所属系统。
            bucket["mass_tonne"] += mass_tonne
            # 把当前节点横向惯量计入所属系统。
            bucket["inertia_tonne_mm2"] += node_inertia
    # MASS21质量必须与空间化审计的963.811 t量级一致；零值一定是输入错误。
    if total_mass <= 0.0:
        raise ValueError(f"MASS21节点表为空或质量非正：{MASS_NODE_CSV}")
    # 返回总量和分组。
    return total_mass, transverse_inertia, grouped


def build_audit() -> dict[str, object]:
    """计算当前惯量、物理重分布上界和TS2所需惯量比。

    返回：
        可直接序列化为 JSON 的审计字典。
    """

    # nodes 为基础索网坐标映射。
    nodes = read_base_nodes()
    # link_mass 和 link_inertia 是材料1/2索的积分结果。
    link_mass, link_inertia = integrate_link_mass_and_inertia(nodes)
    # mass21_mass、mass21_inertia 和 grouped 是空间质量汇总结果。
    mass21_mass, mass21_inertia, grouped = integrate_mass21()
    # covered_mass 是本脚本明确覆盖的索质量与MASS21之和。
    covered_mass = link_mass + mass21_mass
    # uncovered_mass 主要来自四根下拉等效索等小项；单独列出，禁止静默并入零横距。
    uncovered_mass = FULL_MODEL_MASS_TONNE - covered_mass
    # current_inertia 是当前已覆盖质量的横向平动惯量。
    current_inertia = link_inertia + mass21_inertia
    # mass21_outer_bound 假设所有MASS21质量都移到最外底索；这是宽度内的极端上界，
    # 并不代表可接受的真实质量布置。
    mass21_outer_bound = link_inertia + mass21_mass * OUTERMOST_TRANSVERSE_MM**2
    # all_covered_outer_bound 连索质量也全部移到最外侧，只用于展示绝对几何极限。
    all_covered_outer_bound = covered_mass * OUTERMOST_TRANSVERSE_MM**2
    # required_ratio 根据频率平方反比于广义质量的单自由度关系估算；该关系只作为
    # “纯质量修正至少需要多少”的必要量级，不是多模态精确预测。
    required_ratio = (R195_TS2_HZ / TARGET_TS2_HZ) ** 2
    # mass21_bound_ratio 是只移动现有MASS21时可达到的最大惯量倍率。
    mass21_bound_ratio = mass21_outer_bound / current_inertia
    # all_bound_ratio 是把全部已覆盖质量移到最外侧的非物理绝对倍率。
    all_bound_ratio = all_covered_outer_bound / current_inertia
    # result 保存输入证据、当前值、上界和判定，便于后续机器审计。
    result: dict[str, object] = {
        "scope": "geometric_transverse_inertia_bound_not_modal_generalized_mass",
        "units": {
            "mass": "tonne",
            "coordinate": "mm",
            "inertia": "tonne*mm^2",
        },
        "inputs": {
            "base_nodes_csv": str(BASE_MODEL_DIR / "full_line_beam4_nodes.csv"),
            "base_elements_csv": str(BASE_MODEL_DIR / "full_line_beam4_elements.csv"),
            "mass21_nodes_csv": str(MASS_NODE_CSV),
            "outermost_transverse_mm": OUTERMOST_TRANSVERSE_MM,
            "r195_ts2_hz": R195_TS2_HZ,
            "target_ts2_hz": TARGET_TS2_HZ,
        },
        "mass_closure": {
            "link_material_1_2_mass_tonne": link_mass,
            "mass21_mass_tonne": mass21_mass,
            "covered_mass_tonne": covered_mass,
            "full_model_mass_tonne": FULL_MODEL_MASS_TONNE,
            "uncovered_small_items_mass_tonne": uncovered_mass,
        },
        "current_inertia": {
            "link_material_1_2_tonne_mm2": link_inertia,
            "mass21_tonne_mm2": mass21_inertia,
            "covered_total_tonne_mm2": current_inertia,
            "mass21_system_breakdown": grouped,
        },
        "bounds": {
            "mass21_all_at_outer_inertia_tonne_mm2": mass21_outer_bound,
            "mass21_all_at_outer_ratio": mass21_bound_ratio,
            "mass21_all_at_outer_frequency_ratio_sqrt_inverse": math.sqrt(1.0 / mass21_bound_ratio),
            "all_covered_mass_at_outer_inertia_tonne_mm2": all_covered_outer_bound,
            "all_covered_mass_at_outer_ratio": all_bound_ratio,
            "all_covered_mass_at_outer_frequency_ratio_sqrt_inverse": math.sqrt(1.0 / all_bound_ratio),
        },
        "ts2_mass_only_requirement": {
            "required_inertia_ratio": required_ratio,
            "mass21_width_bound_is_sufficient": mass21_bound_ratio >= required_ratio,
            "shortfall_ratio_points": required_ratio - mass21_bound_ratio,
        },
        "conclusion": (
            "只在既有宽度内重排全部MASS21的极端上界仍不足以把R195的TS2降到附件目标；"
            "需要独立约束/刚度机制，或改变分布索质量这一更强且缺少依据的参数。"
        ),
    }
    # 返回完整机器审计结构。
    return result


def write_outputs(audit: dict[str, object]) -> None:
    """写出 JSON 与 Markdown 审计产物。

    参数：
        audit：``build_audit`` 返回的完整审计字典。

    返回：
        无；函数只负责稳定写盘。
    """

    # 创建审计目录；exist_ok=True 允许脚本重复运行并覆盖同名派生产物。
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    # JSON 使用无BOM UTF-8和缩进，供后续脚本稳定读取与版本比较。
    OUTPUT_JSON.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    # 为提高可读性，把深层字段提取成局部变量；这些变量不改变原始精度。
    mass_closure = audit["mass_closure"]
    current = audit["current_inertia"]
    bounds = audit["bounds"]
    requirement = audit["ts2_mass_only_requirement"]
    # lines 按最终Markdown行顺序组装，避免多段字符串缩进混入正文。
    lines = [
        "# 扭转质量空间惯量上界审计（V2.0）",
        "",
        "> 本审计计算的是几何量 `Σ(m·Y²)`，不是质量矩阵加权的真实模态广义质量。",
        "> 它只能用于排除“仅移动现有 MASS21 就足够”的假设，不能替代一次 MAPDL 模态求解。",
        "",
        "## 1. 当前覆盖范围",
        "",
        f"- 材料1/2分布索质量：`{mass_closure['link_material_1_2_mass_tonne']:.9f} t`。",
        f"- 空间化 MASS21：`{mass_closure['mass21_mass_tonne']:.9f} t`。",
        f"- 本脚本覆盖质量：`{mass_closure['covered_mass_tonne']:.9f} t`。",
        f"- 正式全模型质量：`{mass_closure['full_model_mass_tonne']:.9f} t`。",
        f"- 未纳入几何积分的小项：`{mass_closure['uncovered_small_items_mass_tonne']:.9f} t`，约占全质量"
        f" `{100.0 * mass_closure['uncovered_small_items_mass_tonne'] / mass_closure['full_model_mass_tonne']:.3f}%`。",
        "",
        "## 2. 横向平动惯量与极端上界",
        "",
        f"- 当前已覆盖质量 `Σ(m·Y²)`：`{current['covered_total_tonne_mm2']:.6e} t·mm²`。",
        f"- 假定**全部 MASS21**移到 `|Y|={OUTERMOST_TRANSVERSE_MM:.0f} mm`：惯量倍率"
        f" `{bounds['mass21_all_at_outer_ratio']:.6f}`，对应纯惯量频率倍率"
        f" `{bounds['mass21_all_at_outer_frequency_ratio_sqrt_inverse']:.6f}`。",
        f"- 甚至把全部已覆盖索质量也移到最外侧：绝对几何倍率 `{bounds['all_covered_mass_at_outer_ratio']:.6f}`；"
        "该情景违反16根底索的真实横向分布，只能作为非物理上限。",
        "",
        "## 3. 与 R195 的 TS2 需求比较",
        "",
        f"- R195 跟踪 TS2：`{R195_TS2_HZ:.9f} Hz`；附件目标：`{TARGET_TS2_HZ:.4f} Hz`。",
        f"- 若只靠增加模态惯量，最低所需倍率约为 `(f_calc/f_target)² = "
        f"{requirement['required_inertia_ratio']:.6f}`。",
        f"- MASS21 宽度内极端上界只有 `{bounds['mass21_all_at_outer_ratio']:.6f}`；"
        f"是否足够：`{requirement['mass21_width_bound_is_sufficient']}`。",
        "",
        "## 4. 结论",
        "",
        "只重排门架、横通道和保留集中质量，即使把它们全部推到最外底索，也不足以解释R195下TS2的全部偏高。",
        "因此后续必须检查与现有材料倍率方向独立的参数：转索鞍/端部纵向滑移、连接转角运动学，或有明确来源的"
        "分布索质量/转动惯量。不得以无依据的 MASS21 外移把频率硬调到目标。",
        "",
        "机器结果：`torsional_mass_inertia_bound_audit.json`。",
    ]
    # Markdown采用UTF-8 BOM，保证Windows记事本/Excel链路正确显示中文。
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8-sig", newline="\n")


def main() -> None:
    """执行完整审计并写出两类产物。

    参数：
        无。

    返回：
        无；异常直接传播并令命令行返回非零状态。
    """

    # audit 保存全部计算结果和判定。
    audit = build_audit()
    # 写出机器/人工两个稳定产物。
    write_outputs(audit)
    # 命令行打印JSON路径，便于调度器记录唯一机器入口。
    print(OUTPUT_JSON)


# 只有直接运行脚本时才执行，导入函数做单元测试时不会产生文件副作用。
if __name__ == "__main__":
    main()
