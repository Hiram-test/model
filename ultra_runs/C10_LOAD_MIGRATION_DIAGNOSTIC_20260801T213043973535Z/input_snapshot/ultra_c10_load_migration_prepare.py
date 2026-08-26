from __future__ import annotations  # 启用延迟类型注解，避免运行期解析复杂容器注解增加依赖。

import csv  # 严格读取二期 MASS21 节点、质量和来源字段，禁止按字符串切分破坏含分号的证据列。
import json  # 生成机器可读的准备结果、运行清单和审计对象，JSON 字段说明另写 Markdown。
import math  # 检查转换为求解器浮点数后的节点修正力仍为有限值，拒绝 NaN 与无穷。
import re  # 严格识别权威旧恒载 include 中唯一允许的 F,node,FZ,value 命令格式。
import shutil  # 将父求解输入和原始质量 CSV 逐字节复制到新的唯一运行目录与输入快照。
from datetime import datetime, timezone  # 生成包含微秒的 UTC 身份，保证运行目录和作业名不覆盖历史结果。
from decimal import Decimal, getcontext  # 以十进制定点精度完成 15,071 个节点的总荷载守恒对账。
from pathlib import Path  # 安全处理包含中文的绝对工程路径及运行目录相对路径。
from typing import Any  # 标注 JSON 审计字典允许容纳字符串、数字、布尔值和嵌套对象。

import ultra_c10_static_diagnostic_prepare as base  # 复用已冻结的父谱系验证、哈希、唯一替换与静力截断实现。


getcontext().prec = 50  # 使用五十位十进制有效数字，使 963.811 tonne 的逐节点抵消误差远低于 1E-6 N 守恒门。
PREPARER_BASE_SHA256 = "e9fe2684244bcdde461617c2111f8a3e8d7c2a8f12139ae60e815d191b5ba847"  # 冻结被复用静力准备模块的六十四位小写 SHA-256 字节身份。
MASS_CSV_NAME = "mass21_spatialized_v2_nodes.csv"  # 指定 33,003 个动态质量节点的唯一权威源文件名。
MASS_CSV_SHA256 = "067997d002caa3d41337ecf2ffc28d5c2f17f9abe4db7f27fbd875abbaa39db0"  # 冻结二期空间化质量 CSV 的完整字节身份。
DEADLOAD_INCLUDE_NAME = "apply_authoritative_mct_deadload_v1.inp"  # 指定原 MCT 平衡荷载位置所在的权威恒载 include。
DEADLOAD_INCLUDE_SHA256 = "3feb7eec692762d8324865611ae600a39e4b13cd777d8d5bb29896b2e1a1223e"  # 冻结 23,028 个原始 FZ 节点荷载的 include 字节身份。
MASS_INCLUDE_NAME = "apply_dynamic_mass21_spatialized_v2.inp"  # 指定建立 33,003 个 TYPE71 MASS21 并删除旧 FZ 的动态质量 include。
MASS_INCLUDE_SHA256 = "4f9cf3cac4d1b032abccf0c3dcca208f3a9e5c7d064b25fb47ebcdd3e6bcbc9f"  # 冻结当前空间化 MASS21 求解输入字节身份。
CORRECTION_INCLUDE_NAME = "apply_constant_total_load_position_migration_v1.inp"  # 指定 LS1 恢复旧荷载位置、LS2 删除修正力并由 KBC 线性迁移的 include 名称。
MIGRATION_MAIN_NAME = "c10_load_migration_static_main.inp"  # 指定新运行唯一允许启动的静力主控文件名。
EXPECTED_OLD_FZ_NODE_COUNT = 23028  # 冻结权威旧恒载中非零竖向节点荷载记录数，单位为条。
EXPECTED_MASS_NODE_COUNT = 33003  # 冻结空间化 MASS21 的节点质量记录数，单位为条。
EXPECTED_UNION_NODE_COUNT = 34975  # 冻结旧荷载节点与新质量节点的并集数量，单位为节点。
EXPECTED_INTERSECTION_NODE_COUNT = 21056  # 冻结旧荷载节点与新质量节点的交集数量，单位为节点。
EXPECTED_CORRECTION_NODE_COUNT = 15071  # 冻结抵消后仍需显式施加修正力的节点数量，单位为节点。
EXPECTED_NUMERICAL_DUST_NODE_COUNT = 19904  # 冻结旧力与新质量重力仅因源文本尾数产生的小于阈值数值尘埃节点数。
EXPECTED_POSITIVE_CORRECTION_COUNT = 11947  # 冻结质量独有及少量重叠节点上的正向抵消修正数量。
EXPECTED_NEGATIVE_CORRECTION_COUNT = 3124  # 冻结旧荷载独有及少量重叠节点上的负向恢复修正数量。
EXPECTED_OLD_FZ_SUM_N = Decimal("-9451134.400000000084")  # 冻结旧二期节点恒载总和，单位 N，负号表示全局 -Z。
EXPECTED_MASS_SUM_TONNE = Decimal("963.81138078727311813886")  # 冻结 33,003 个空间化 MASS21 总质量，单位 tonne。
GRAVITY_MM_S2 = Decimal("9806")  # 冻结与模型 ACEL 一致的重力加速度，单位 mm/s²。
FORCE_SUM_TOLERANCE_N = Decimal("1E-6")  # 要求源端与渲染后修正力总和绝对值均小于一微牛，防止总荷载漂移。
SOURCE_SUM_TOLERANCE = Decimal("1E-18")  # 对冻结十进制源总和使用 1E-18 的绝对容差，只容许解析尾差不容许数据漂移。
CORRECTION_ZERO_TOLERANCE_N = Decimal("1E-9")  # 将小于等于一纳牛的源文本尾差统一裁零；真实最小修正超过 10 N，间隔大于十个数量级。
MAX_CORRECTION_ABS_N = Decimal("3600")  # 限制任一节点修正力绝对值不超过 3.6 kN，超过即视为映射或单位错误。
LS2_INITIAL_SUBSTEPS = 20  # LS2 初始采用二十个荷载位置迁移子步，使每步只迁移约 5% 的二期重力位置。
LS2_MAX_SUBSTEPS = 200  # LS2 自动步长最多允许二百个子步，为局部非线性提供十倍细分余量。
LS2_MIN_SUBSTEPS = 20  # LS2 不允许少于二十个子步，避免求解器把迁移路径放大为粗糙跃迁。
EXPECTED_MASS_HEADER = ["apdl_node_id", "x_mm", "y_mm", "z_mm", "mass_tonne", "is_generated_node", "system", "assembly_name", "role", "component_ids", "component_masses_tonne"]  # 冻结质量 CSV 十一列名称和顺序，任一证据字段漂移即拒绝。
OLD_FZ_PATTERN = re.compile(r"^F,(\d+),FZ,([+\-0-9.Ee]+)$")  # 只接受无空字段、全局 FZ 和科学计数值的权威 APDL 荷载行。


def require(condition: bool, message: str) -> None:  # 输入布尔条件和失败原因；条件不满足时终止准备且不返回业务值。
    if not condition:  # 仅在身份、数量、单位、守恒或控制流门禁失败时进入拒绝分支。
        raise RuntimeError(message)  # 抛出明确异常，禁止生成可被误启动的半成品运行目录。


def load_old_fz(path: Path) -> dict[int, Decimal]:  # 输入冻结旧恒载 include 路径并返回节点号到负竖向力 N 的唯一映射。
    require(path.is_file(), f"缺少权威旧恒载 include：{path}")  # 在解析前拒绝缺失或被移动的权威源。
    require(base.sha256_file(path) == DEADLOAD_INCLUDE_SHA256, "权威旧恒载 include SHA-256 漂移")  # 防止未登记恒载版本进入迁移。
    forces: dict[int, Decimal] = {}  # 初始化节点唯一映射，重复节点必须报错而不是后值覆盖前值。
    executable_f_count = 0  # 统计全部以 F, 开头的可执行节点力命令，确保没有非 FZ 分量被漏掉。
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):  # 按真实行号逐行检查完整 include，便于错误定位。
        if line.startswith("F,"):  # 仅对可执行节点力命令增加独立覆盖计数，排除 FDELE 与 FINISH。
            executable_f_count += 1  # 把当前 F 命令加入总覆盖计数。
        match = OLD_FZ_PATTERN.fullmatch(line)  # 对当前整行执行严格 FZ 格式匹配，不接受多余字段或局部坐标分量。
        if match is None:  # 非 FZ 行可能是注释、处理器命令或 QA 参数，不进入荷载映射。
            continue  # 跳过与节点 FZ 无关的合法行并继续完整扫描。
        node_id = int(match.group(1))  # 将第一捕获组解析为 MAPDL 正整数节点号。
        force_n = Decimal(match.group(2))  # 将第二捕获组按十进制精确解析为单位 N 的竖向力。
        require(node_id > 0, f"旧恒载第 {line_number} 行节点号不是正整数")  # 禁止零号或负号节点进入有限元荷载。
        require(force_n.is_finite() and force_n < Decimal("0"), f"旧恒载节点 {node_id} 不是有限 -Z 力")  # 保证源荷载方向和数值有效。
        require(node_id not in forces, f"旧恒载重复节点号：{node_id}")  # 防止同节点多条 F 命令在 MAPDL 中被覆盖而审计误认为叠加。
        forces[node_id] = force_n  # 保存通过格式、符号与唯一性门的节点竖向力。
    require(executable_f_count == len(forces), "旧恒载 include 含未被严格解析的 F 命令")  # 关闭其他自由度或格式漂移的漏检路径。
    require(len(forces) == EXPECTED_OLD_FZ_NODE_COUNT, "旧恒载 FZ 节点数不是 23,028")  # 固定权威旧荷载位置覆盖。
    source_sum = sum(forces.values(), Decimal("0"))  # 以十进制精确累计全部负竖向力，单位 N。
    require(abs(source_sum - EXPECTED_OLD_FZ_SUM_N) <= SOURCE_SUM_TOLERANCE, "旧恒载 FZ 总和漂移")  # 拒绝节点值发生任何工程量级改变。
    return forces  # 返回已通过身份、数量、符号、唯一性与总和门的旧荷载映射。


def load_spatial_mass(path: Path) -> tuple[dict[int, Decimal], dict[str, int]]:  # 输入冻结质量 CSV 并返回节点质量映射与原始/生成节点数量审计。
    require(path.is_file(), f"缺少空间化 MASS21 CSV：{path}")  # 在解析前拒绝缺失或被移动的质量证据。
    require(base.sha256_file(path) == MASS_CSV_SHA256, "空间化 MASS21 CSV SHA-256 漂移")  # 防止质量位置或数值未经登记改变。
    masses: dict[int, Decimal] = {}  # 初始化节点到 tonne 质量的唯一映射。
    generated_count = 0  # 统计有限门架和横向通道生成节点上的质量记录数。
    original_count = 0  # 统计原始 MCT 网格节点上的质量记录数。
    with path.open("r", encoding="utf-8-sig", newline="") as handle:  # 以 UTF-8-SIG 消费冻结文件的三字节 BOM，并用 CSV 原生换行模式只读打开权威表。
        reader = csv.DictReader(handle)  # 用列名读取，避免逗号或分号证据字段破坏位置解析。
        require(reader.fieldnames == EXPECTED_MASS_HEADER, "空间化 MASS21 CSV 表头或列顺序漂移")  # 冻结十一列数据契约。
        for row_number, row in enumerate(reader, start=2):  # 从含表头后的真实第二行开始记录错误行号。
            node_id = int(row["apdl_node_id"])  # 解析 MASS21 所在 MAPDL 节点号。
            mass_tonne = Decimal(row["mass_tonne"])  # 以十进制精确读取单节点质量，单位 tonne。
            generated_flag = row["is_generated_node"]  # 读取 0/1 节点来源标志供独立计数。
            require(node_id > 0, f"质量 CSV 第 {row_number} 行节点号不是正整数")  # 拒绝非法节点身份。
            require(mass_tonne.is_finite() and mass_tonne > Decimal("0"), f"质量节点 {node_id} 不是有限正质量")  # 禁止零、负、NaN 或无穷质量。
            require(generated_flag in {"0", "1"}, f"质量节点 {node_id} 的生成标志不是 0/1")  # 保证来源分类可审计。
            require(node_id not in masses, f"质量 CSV 重复节点号：{node_id}")  # 防止 MASS21 真实常数被重复聚合或覆盖。
            masses[node_id] = mass_tonne  # 保存通过格式、符号与唯一性门的节点质量。
            generated_count += 1 if generated_flag == "1" else 0  # 生成节点记录只在标志为 1 时增加一条。
            original_count += 1 if generated_flag == "0" else 0  # 原始节点记录只在标志为 0 时增加一条。
    require(len(masses) == EXPECTED_MASS_NODE_COUNT, "空间化 MASS21 节点数不是 33,003")  # 固定完整质量离散覆盖。
    require(generated_count + original_count == EXPECTED_MASS_NODE_COUNT, "质量节点来源计数未闭合")  # 保证每条记录恰归一类。
    mass_sum = sum(masses.values(), Decimal("0"))  # 以十进制精确累计空间化二期质量，单位 tonne。
    require(abs(mass_sum - EXPECTED_MASS_SUM_TONNE) <= SOURCE_SUM_TOLERANCE, "空间化 MASS21 总质量漂移")  # 拒绝质量总量变化。
    return masses, {"generated_node_record_count": generated_count, "original_node_record_count": original_count}  # 返回质量映射和来源数量审计。


def build_corrections(old_forces: dict[int, Decimal], masses: dict[int, Decimal]) -> tuple[dict[int, Decimal], dict[str, Any]]:  # 输入旧 FZ 与新质量并返回保持总荷载不变的节点修正力及审计。
    all_nodes = set(old_forces) | set(masses)  # 构造旧荷载位置与新质量位置的完整节点并集。
    intersection = set(old_forces) & set(masses)  # 构造同时含旧节点力和新节点质量的交集供映射覆盖检查。
    require(len(all_nodes) == EXPECTED_UNION_NODE_COUNT, "旧荷载与新质量节点并集不是 34,975")  # 固定两套位置映射的总体覆盖。
    require(len(intersection) == EXPECTED_INTERSECTION_NODE_COUNT, "旧荷载与新质量节点交集不是 21,056")  # 固定重合位置覆盖。
    corrections: dict[int, Decimal] = {}  # 初始化超过一纳牛阈值的真实节点修正力映射，单位 N。
    all_correction_values: list[Decimal] = []  # 保存并集中审计 34,975 个并集节点的未裁剪十进制修正值。
    numerical_dust_values: list[Decimal] = []  # 保存被一纳牛阈值裁掉的源文本尾数差，供数量和最大值审计。
    for node_id in sorted(all_nodes):  # 按节点号稳定递增计算，确保输出字节与审计顺序可复现。
        old_force_n = old_forces.get(node_id, Decimal("0"))  # 读取该节点原 MCT 负 FZ；旧位置不存在时取零。
        new_mass_gravity_n = masses.get(node_id, Decimal("0")) * GRAVITY_MM_S2  # 计算该节点 MASS21 的正抵消力，单位 N。
        correction_n = old_force_n + new_mass_gravity_n  # 叠加旧负力与新重力反力，形成 beta=1 的位置恢复修正。
        all_correction_values.append(correction_n)  # 保存未裁剪值，使总力闭合不依赖稀疏化阈值。
        if abs(correction_n) > CORRECTION_ZERO_TOLERANCE_N:  # 只有绝对值超过一纳牛的真实位置差才写入 APDL。
            corrections[node_id] = correction_n  # 保存真实修正力供 include 生成和守恒审计。
        else:  # 小于等于一纳牛且与真实最小值相隔十个数量级的记录属于源文本尾数尘埃。
            numerical_dust_values.append(correction_n)  # 保存被裁零的微小值供数量和最大尘埃复核。
    require(len(corrections) == EXPECTED_CORRECTION_NODE_COUNT, "非零位置迁移修正节点数不是 15,071")  # 固定抵消后的稀疏向量规模。
    require(len(numerical_dust_values) == EXPECTED_NUMERICAL_DUST_NODE_COUNT, "被裁零的数值尘埃节点数不是 19,904")  # 固定旧力与新重力文本尾差覆盖。
    full_correction_sum_n = sum(all_correction_values, Decimal("0"))  # 累计裁剪前全部并集节点修正力，单位 N。
    retained_correction_sum_n = sum(corrections.values(), Decimal("0"))  # 累计实际写入 APDL 的 15,071 个修正力，单位 N。
    require(abs(full_correction_sum_n) <= FORCE_SUM_TOLERANCE_N, "裁剪前修正力总和超过 1E-6 N")  # 证明两套荷载场源总量一致。
    require(abs(retained_correction_sum_n) <= FORCE_SUM_TOLERANCE_N, "裁剪后修正力总和超过 1E-6 N")  # 保证稀疏化不改变全桥竖向总荷载。
    max_node_id, max_value_n = max(corrections.items(), key=lambda item: abs(item[1]))  # 查找绝对值最大的节点修正力供单位异常门禁。
    require(abs(max_value_n) <= MAX_CORRECTION_ABS_N, "最大节点修正力超过 3.6 kN")  # 阻断 tonne、kg 或重力单位误乘。
    positive_count = sum(1 for value in corrections.values() if value > Decimal("0"))  # 统计用于抵消新质量重力的正向修正节点数。
    negative_count = sum(1 for value in corrections.values() if value < Decimal("0"))  # 统计用于恢复旧 MCT 荷载的负向修正节点数。
    require(positive_count == EXPECTED_POSITIVE_CORRECTION_COUNT and negative_count == EXPECTED_NEGATIVE_CORRECTION_COUNT, "修正力正负节点数量不是 11,947/3,124")  # 关闭符号方向和节点族覆盖门。
    minimum_retained_abs_n = min(abs(value) for value in corrections.values())  # 读取真实修正向量的最小绝对值，单位 N。
    maximum_dust_abs_n = max(abs(value) for value in numerical_dust_values)  # 读取被裁零尾尘的最大绝对值，单位 N。
    require(minimum_retained_abs_n > Decimal("10") and maximum_dust_abs_n < CORRECTION_ZERO_TOLERANCE_N, "真实修正与数值尘埃未形成安全量级间隔")  # 防止阈值误删工程荷载。
    audit = {"schema_version": 1, "status": "PASSED", "old_fz_node_count": len(old_forces), "mass_node_count": len(masses), "union_node_count": len(all_nodes), "intersection_node_count": len(intersection), "correction_zero_tolerance_n": str(CORRECTION_ZERO_TOLERANCE_N), "numerical_dust_node_count": len(numerical_dust_values), "maximum_numerical_dust_abs_n": str(maximum_dust_abs_n), "correction_node_count": len(corrections), "positive_correction_node_count": positive_count, "negative_correction_node_count": negative_count, "minimum_retained_correction_abs_n": str(minimum_retained_abs_n), "old_fz_sum_n": str(sum(old_forces.values(), Decimal("0"))), "mass_sum_tonne": str(sum(masses.values(), Decimal("0"))), "mass_gravity_sum_n": str(sum(masses.values(), Decimal("0")) * GRAVITY_MM_S2), "full_source_correction_sum_n": str(full_correction_sum_n), "retained_correction_sum_n": str(retained_correction_sum_n), "maximum_absolute_correction_node": max_node_id, "maximum_absolute_correction_n": str(max_value_n), "total_load_change_allowed_n": str(FORCE_SUM_TOLERANCE_N), "physical_identity": "FULL_GRAVITY_PLUS_BETA_TIMES_OLD_FZ_PLUS_MASS21_COUNTERFORCE", "beta_1_role": "RESTORE_OLD_MCT_BALANCED_LOAD_POSITIONS", "beta_0_role": "FINAL_SPATIAL_MASS21_GRAVITY_WITH_FIXED_NODE_SET_EXPLICIT_ZERO_CORRECTION"}  # 汇总阈值、尘埃、数量、总和、极值、符号和 beta 两端的工程语义。
    return corrections, audit  # 返回通过全量身份、数量、单位与守恒门的修正向量和审计对象。


def render_correction_include(corrections: dict[int, Decimal], audit: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:  # 输入非零修正力并返回逐命令中文说明的 APDL include 与渲染审计。
    lines: list[str] = []  # 初始化稳定 LF 文本行列表，禁止平台默认换行改变摘要。
    lines.append("! 恒总荷载位置迁移 V1：LS1 的 C10_BETA=1 恢复原 MCT 平衡荷载位置，LS2 的 C10_BETA=0 在同一节点集显式写零。")  # 说明本 include 的两次调用和固定节点集更新语义。
    lines.append("! ACEL 始终保持 +Z 9806 mm/s2；KBC,0 只在 LS2 把同一总量的二期重力从旧节点连续迁移到 MASS21 实际节点。")  # 明确总重力不作数值卸载或重新加载。
    lines.append("! 修正定义为 old_FZ + mass_tonne*9806，单位 N；全部修正力渲染后总和必须小于 1E-6 N。")  # 固定符号、单位与守恒阈值。
    lines.append("! 恢复全部实体选择，确保上一门禁的局部选择不会缩小后续 F 命令作用域。")  # 为下一条选择命令说明安全作用域。
    lines.append("ALLSEL,ALL")  # 在当前 /SOLU 处理器中恢复完整节点和单元选择。
    lines.append("! 对固定 15,071 节点集逐项重发 beta 缩放值；不使用 FDELE，避免 KBC=0 把删除动作解释为阶跃卸载。")  # 说明安全的 replacement 更新策略。
    lines.append("! 显式固定后续 F 命令采用替换而非累加，避免会话中任何既有 FCUM 设置泄漏到本路径。")  # 为下一条累计控制命令说明幂等语义。
    lines.append("FCUM,REPL")  # 将节点力操作固定为 replacement，使 beta=0 的零值覆盖 beta=1 端点。
    rendered_values: list[Decimal] = []  # 收集 APDL 实际文本精度的修正力供独立渲染后守恒审计。
    for node_id, correction_n in sorted(corrections.items()):  # 按节点号递增生成 15,071 组可复算注释与 F 命令。
        rendered_value = format(correction_n, ".16E")  # 使用十七位有效数字渲染，远高于工程精度且保持 MAPDL 双精度可读。
        rendered_decimal = Decimal(rendered_value)  # 重新解析即将写入求解器的文本值，审计真正执行的数据而非源对象。
        require(math.isfinite(float(rendered_decimal)), f"节点 {node_id} 的渲染修正力不是有限双精度值")  # 拒绝溢出或非法格式。
        rendered_values.append(rendered_decimal)  # 保存当前文本精度值供总和和极值复核。
        lines.append(f"! 节点 {node_id}：基准修正 FZ={rendered_value} N；实际端点值为 C10_BETA 乘该值，beta=0 时显式写 0 N。")  # 在每条可执行 F 命令前记录节点、方向、数值、单位和缩放语义。
        lines.append(f"F,{node_id},FZ,C10_BETA*({rendered_value})")  # 在同一节点上以 replacement 方式写入 beta 缩放值，使 KBC=0 从旧值连续迁移到零。
    lines.append("! 再次恢复全部实体选择，防止 include 向后泄漏任何选择状态。")  # 为末尾选择恢复说明目的。
    lines.append("ALLSEL,ALL")  # 恢复完整模型选择并把控制权返回静力主控。
    rendered_sum_n = sum(rendered_values, Decimal("0"))  # 累计 APDL 文本中实际写入的 15,071 个修正力，单位 N。
    require(abs(rendered_sum_n) <= FORCE_SUM_TOLERANCE_N, "APDL 渲染后修正力总和超过 1E-6 N")  # 保证格式舍入不破坏恒总荷载路径。
    rendered = ("\n".join(lines) + "\n").encode("utf-8")  # 用 UTF-8 与唯一末尾 LF 生成可哈希的确定性 include 字节。
    include_audit = dict(audit)  # 复制源精度审计，避免原对象被渲染字段原地污染。
    include_audit.update({"rendered_correction_sum_n": str(rendered_sum_n), "rendered_force_significant_digits": 17, "include_sha256": base.sha256_bytes(rendered), "include_command_count_f": len(corrections), "include_fdele_count": 0, "include_fcum_repl_count": 1, "include_beta_scaled_replacement_count": len(corrections), "fixed_update_node_set": True})  # 追加真实文本总和、精度、摘要和固定节点 replacement 命令计数。
    return rendered, include_audit  # 返回通过文本级守恒门的 include 字节和完整审计。


def transform_main(source_bytes: bytes, old_jobname: str, new_jobname: str, correction_audit: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:  # 输入父主控、作业身份和修正审计并返回两步位置迁移静力主控。
    base_bytes, audit = base.transform_main(source_bytes, old_jobname, new_jobname)  # 先复用已验证的单层 TYPE72、四项 CNVTOL、LS1 形成态和静力截断变换。
    candidate = base_bytes.decode("utf-8")  # 严格按 UTF-8 解码已通过基础控制流门的候选主控。
    newline = "\r\n" if "\r\n" in candidate else "\n"  # 保持父主控原有 CRLF 或 LF 换行风格。
    candidate = base.replace_once(candidate, "/TITLE,C10 DIRECT MPC STATIC FULL-FORMED-STATE EQUILIBRIUM-PAIR DIAGNOSTIC", "/TITLE,C10 DIRECT MPC CONSTANT-TOTAL-LOAD POSITION-MIGRATION STATIC DIAGNOSTIC", "恒总荷载位置迁移标题")  # 使 OUT 明确区分被证伪的全形成态直配路径。
    ls1_anchor = "! 施加 +Z 参考加速度 9806 mm/s²，使结构承受 -Z 重力。" + newline + "ACEL,0,0,9806" + newline  # 冻结 LS1 唯一重力命令作为 beta=1 插入点。
    ls1_insertion = ls1_anchor + "! 把二值迁移参数设为 1，使修正 include 恢复原 MCT 初态对应的平衡荷载位置。" + newline + "C10_BETA=1" + newline + "! 施加总和小于 1E-6 N 的位置修正向量；总重力大小保持不变。" + newline + f"/INPUT,{Path(CORRECTION_INCLUDE_NAME).stem},inp" + newline  # 在首个 SOLVE 前建立旧位置端点。
    candidate = base.replace_once(candidate, ls1_anchor, ls1_insertion, "LS1 beta=1 旧荷载位置恢复")  # 保证修正 include 只在唯一 LS1 重力锚点后插入一次。
    ls2_anchor = "! 重发同一重力加速度，明确 LS2 没有新增物理外载。" + newline + "ACEL,0,0,9806" + newline  # 冻结 LS2 唯一重力命令作为 beta=0 插入点。
    ls2_insertion = ls2_anchor + "! 把二值迁移参数设为 0，使修正 include 在同一 15,071 节点集显式写入零值并定义最终荷载端点。" + newline + "C10_BETA=0" + newline + "! 用 replacement 重发 LS1 修正节点的零端点；随后 KBC,0 连续插值，ACEL 和总重力保持不变。" + newline + f"/INPUT,{Path(CORRECTION_INCLUDE_NAME).stem},inp" + newline  # 在第二次 SOLVE 前定义固定节点集的零修正终点。
    candidate = base.replace_once(candidate, ls2_anchor, ls2_insertion, "LS2 beta=0 空间质量位置终点")  # 保证修正 include 只在唯一 LS2 重力锚点后再次调用。
    ls2_autots_old = "! 关闭 LS2 自动步长，禁止 cutback 掩盖保持步失稳。" + newline + "AUTOTS,OFF" + newline  # 冻结基础候选中单步保持的自动步长片段。
    ls2_autots_new = "! 启用 LS2 自动步长，允许位置迁移在局部非线性处细分，但不得少于二十个总子步。" + newline + "AUTOTS,ON" + newline  # 允许恒总荷载路径自适应细分而非放宽收敛准则。
    candidate = base.replace_once(candidate, ls2_autots_old, ls2_autots_new, "LS2 位置迁移自动步长")  # 只改变 LS2，LS1 仍保持形成态单步禁止细分。
    ls2_nsubst_old = "! LS2 固定单一子步，不允许细分、放大或缩减。" + newline + "NSUBST,1,1,1" + newline  # 冻结基础候选中 LS2 单子步片段。
    ls2_nsubst_new = f"! LS2 初始 {LS2_INITIAL_SUBSTEPS}、最多 {LS2_MAX_SUBSTEPS}、最少 {LS2_MIN_SUBSTEPS} 个子步；每个起始子步只迁移约 5% 的荷载位置。" + newline + f"NSUBST,{LS2_INITIAL_SUBSTEPS},{LS2_MAX_SUBSTEPS},{LS2_MIN_SUBSTEPS}" + newline  # 建立连续且可 cutback 的位置迁移路径。
    candidate = base.replace_once(candidate, ls2_nsubst_old, ls2_nsubst_new, "LS2 二十至二百子步位置迁移")  # 只替换 LS2 的子步合同。
    candidate = base.replace_once(candidate, "! 重发同一重力加速度，明确 LS2 没有新增物理外载。", "! 重发同一重力加速度；LS2 只改变二期重力空间位置，不改变总荷载或 ACEL。", "LS2 重力语义")  # 更正原零增量保持说明。
    candidate = base.replace_once(candidate, "! 保持斜坡定义；因起终点重力相同，实际外载增量为零。", "! 使用斜坡定义把 beta=1 修正向量连续插值到 beta=0；修正向量总和为零，所以每个子步总荷载恒定。", "LS2 KBC 迁移语义")  # 明确 KBC 只迁移位置。
    candidate = base.replace_once(candidate, "! 执行 LS2 单子步、无稳定化、无新增外载保持求解。", "! 执行 LS2 无稳定化恒总荷载位置迁移，并在 beta=0 空间化 MASS21 端点取得最终平衡。", "LS2 SOLVE 迁移语义")  # 更正第二次求解的物理角色。
    candidate = base.replace_once(candidate, "! LS2 CNVG 不等于 1 时立即拒绝，不允许 cutback。", "! LS2 最终端点 CNVG 不等于 1 时立即拒绝；允许的 cutback 只能增加路径分辨率，不能放宽收敛准则。", "LS2 收敛门语义")  # 区分自适应细分和结果门禁。
    candidate = base.replace_once(candidate, "/COM,STATUS=REJECTED REASON=LS2_HOLD_NOT_CONVERGED", "/COM,STATUS=REJECTED REASON=LS2_LOAD_POSITION_MIGRATION_NOT_CONVERGED", "LS2 失败原因")  # 输出可机器解析的真实失败类型。
    candidate = base.replace_once(candidate, "! 读取 LS2 无稳定化保持步的最后收敛结果。", "! 读取 LS2 无稳定化位置迁移的 beta=0 最后收敛结果。", "LS2 后处理语义")  # 使能量端点说明与新路径一致。
    candidate_lines = candidate.splitlines()  # 建立逐行命令视图，使计数不受说明文字中出现 KBC、AUTOTS 或 NSUBST 名称影响。
    require(candidate.count(f"/INPUT,{Path(CORRECTION_INCLUDE_NAME).stem},inp") == 2, "位置迁移 include 调用数不是两次")  # 固定 beta=1 与 beta=0 两个端点调用。
    require(candidate_lines.count("C10_BETA=1") == 1 and candidate_lines.count("C10_BETA=0") == 1, "二值迁移参数端点不唯一")  # 禁止重复或遗漏端点命令。
    require(candidate_lines.count("KBC,1") == 1 and candidate_lines.count("KBC,0") == 1, "LS1 阶跃与 LS2 迁移 KBC 配置不唯一")  # 确认首步直配、次步线性迁移。
    require(candidate_lines.count("AUTOTS,OFF") == 1 and candidate_lines.count("AUTOTS,ON") == 1, "LS1/LS2 自动步长配置不唯一")  # 固定首步禁止细分、次步允许细分。
    require(candidate_lines.count("NSUBST,1,1,1") == 1 and candidate_lines.count(f"NSUBST,{LS2_INITIAL_SUBSTEPS},{LS2_MAX_SUBSTEPS},{LS2_MIN_SUBSTEPS}") == 1, "LS1/LS2 子步合同不唯一")  # 固定两步各自数值路径。
    require(sum(1 for line in candidate_lines if line.startswith("CNVTOL,")) == 4, "恒总荷载主控未保留四项 CNVTOL")  # 禁止以删除收敛准则换取表面通过。
    require("PERTURB,MODAL" not in candidate and "MODOPT," not in candidate, "恒总荷载诊断仍含模态命令")  # 保持本运行只限静力修复验证。
    audit["schema_version"] = 4  # 将基础变更审计升级为含位置迁移合同的第四版。
    audit["change_families"] = [*audit["change_families"], "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_BETA_1_TO_0"]  # 追加唯一物理路径变更族。
    audit["load_path_physical_basis"] = "MCT_INITIAL_FORCE_STATE_BALANCED_AT_OLD_DEADLOAD_POSITIONS_THEN_CONTINUOUSLY_MIGRATED_TO_SPATIAL_MASS21_AT_CONSTANT_TOTAL_LOAD"  # 冻结修复的工程依据。
    audit["load_path_physical_approval"] = "DIAGNOSTIC_HYPOTHESIS_REQUIRES_FULL_STATIC_CONVERGENCE_BALANCE_AND_SENSITIVITY_CHECK"  # 明确准备完成不等于工程批准。
    audit["ls1"] = {"kbc": 1, "autots": False, "nsubst": [1, 1, 1], "time": 1.0, "beta": 1.0, "physical_role": "RESTORE_OLD_MCT_BALANCED_LOAD_POSITIONS_WITH_FULL_GRAVITY"}  # 记录首步完整形成态端点。
    audit["ls2"] = {"kbc": 0, "autots": True, "nsubst": [LS2_INITIAL_SUBSTEPS, LS2_MAX_SUBSTEPS, LS2_MIN_SUBSTEPS], "time": 1.001, "beta_start": 1.0, "beta_end": 0.0, "total_vertical_load_change_n": correction_audit["rendered_correction_sum_n"], "physical_role": "CONTINUOUS_LOAD_POSITION_MIGRATION_TO_FINAL_SPATIAL_MASS21"}  # 记录第二步连续迁移和守恒量。
    audit["load_position_correction"] = correction_audit  # 嵌入源数量、总和、极值与 include 摘要，闭合主控到物理向量的追溯。
    rendered = candidate.encode("utf-8")  # 将完成语义与数值门的主控重新编码为 UTF-8 字节。
    audit["candidate_sha256"] = base.sha256_bytes(rendered)  # 用最终真实入口覆盖基础候选摘要。
    return rendered, audit  # 返回两步恒总荷载迁移静力主控和完整变更审计。


def main() -> None:  # 无输入参数；验证冻结源并生成一个全新、未启动的恒总荷载位置迁移诊断包。
    require(base.sha256_file(Path(base.__file__).resolve()) == PREPARER_BASE_SHA256, "被复用静力准备模块 SHA-256 漂移")  # 关闭基础变换实现的代码身份门。
    parent_dir = base.RUNS_ROOT / base.PARENT_RUN_NAME  # 定位已修复为单层 TYPE72 的权威父运行。
    micro_dir = base.RUNS_ROOT / base.MICRO_RUN_NAME  # 定位 12/12 通过的单层连接微验证运行。
    parent_manifest, micro_results = base.validate_parent(parent_dir, micro_dir)  # 在创建目录前关闭全部父依赖和微验证门。
    require(base.MAPDL_EXE.is_file(), f"缺少冻结 MAPDL 可执行文件：{base.MAPDL_EXE}")  # 确保后续启动合同指向存在的 2026 R1 求解器。
    source_solver_dir = parent_dir / "solver"  # 定位父运行十二项冻结求解输入目录。
    deadload_path = source_solver_dir / DEADLOAD_INCLUDE_NAME  # 定位旧 MCT 荷载位置权威 include。
    mass_include_path = source_solver_dir / MASS_INCLUDE_NAME  # 定位建立当前 TYPE71 质量并清除旧 FZ 的 include。
    mass_csv_path = base.PROJECT_ROOT / MASS_CSV_NAME  # 定位 33,003 个空间化质量节点的权威 CSV。
    require(base.sha256_file(mass_include_path) == MASS_INCLUDE_SHA256, "空间化 MASS21 include SHA-256 漂移")  # 关闭实际求解质量输入身份门。
    mass_include_text = mass_include_path.read_text(encoding="utf-8")  # 读取质量 include 供幂等删除语义检查。
    require(mass_include_text.count("FDELE,ALL,FZ") == 1, "空间化 MASS21 include 未唯一删除旧 FZ")  # 保证最终装配在修正 include 前没有残留旧节点力。
    old_forces = load_old_fz(deadload_path)  # 读取并验证 23,028 个旧平衡荷载节点。
    masses, mass_source_counts = load_spatial_mass(mass_csv_path)  # 读取并验证 33,003 个新质量节点及来源分类。
    corrections, correction_audit = build_corrections(old_forces, masses)  # 构造恒总荷载位置恢复向量并关闭源精度守恒门。
    include_bytes, correction_audit = render_correction_include(corrections, correction_audit)  # 生成 APDL 文本并关闭渲染后守恒门。
    correction_audit["mass_source_counts"] = mass_source_counts  # 把原始/生成节点记录数并入最终 include 审计。
    correction_audit["old_deadload_include_sha256"] = DEADLOAD_INCLUDE_SHA256  # 记录旧荷载位置源字节身份。
    correction_audit["mass_csv_sha256"] = MASS_CSV_SHA256  # 记录新质量节点与数值源字节身份。
    correction_audit["mass_include_sha256"] = MASS_INCLUDE_SHA256  # 记录实际 TYPE71 求解输入字节身份。
    created_at = datetime.now(timezone.utc)  # 记录本次准备动作的精确 UTC 时间。
    stamp = created_at.strftime("%Y%m%dT%H%M%S%fZ")  # 生成含微秒的运行目录时间戳，防止并发覆盖。
    run_name = f"C10_LOAD_MIGRATION_DIAGNOSTIC_{stamp}"  # 派生只属于恒总荷载位置迁移诊断的唯一运行名。
    run_dir = base.RUNS_ROOT / run_name  # 构造新运行根目录。
    solver_dir = run_dir / "solver"  # 构造 MAPDL 独立工作目录。
    qa_dir = run_dir / "qa"  # 构造守恒、控制流和微验证审计目录。
    input_snapshot_dir = run_dir / "input_snapshot"  # 构造权威 CSV、父主控和准备脚本的输入快照目录。
    require(not run_dir.exists(), f"目标运行目录已存在，禁止覆盖：{run_dir}")  # 强制每次尝试拥有唯一目录和作业身份。
    solver_dir.mkdir(parents=True)  # 一次建立运行根目录和 solver 子目录。
    qa_dir.mkdir()  # 建立 QA 工件目录。
    input_snapshot_dir.mkdir()  # 建立输入快照目录。
    for source_path in sorted(source_solver_dir.iterdir(), key=lambda item: item.name):  # 按文件名稳定顺序复制全部父求解依赖。
        require(source_path.is_file(), f"父 solver 含非文件对象：{source_path.name}")  # 禁止目录或链接混入求解依赖。
        shutil.copy2(source_path, solver_dir / source_path.name)  # 保留原始字节和时间复制到独立工作目录。
    correction_include_path = solver_dir / CORRECTION_INCLUDE_NAME  # 构造本运行唯一位置修正 include 路径。
    correction_include_path.write_bytes(include_bytes)  # 写入已通过源端与文本端守恒门的确定性 APDL 字节。
    old_jobname = str(parent_manifest.get("jobname"))  # 读取父主控冻结的旧作业名前缀。
    new_jobname = f"cw_C10m_{created_at.strftime('%m%dt%H%M%S')}_d1"  # 派生不超过三十二字符的唯一 ASCII 迁移作业名。
    require(len(new_jobname) <= 32, "恒总荷载迁移 MAPDL 作业名超过 32 字符")  # 遵守求解器文件前缀长度限制。
    copied_parent_main = solver_dir / base.PARENT_MAIN_NAME  # 定位刚复制到新 solver 目录的父全模态主控。
    parent_main_bytes = copied_parent_main.read_bytes()  # 读取父主控原始字节供受控变换。
    require(base.sha256_bytes(parent_main_bytes) == str(parent_manifest.get("main_input_sha256")), "父主控摘要与清单不一致")  # 再次闭合入口身份。
    migration_bytes, change_audit = transform_main(parent_main_bytes, old_jobname, new_jobname, correction_audit)  # 生成 LS1 旧位置平衡和 LS2 恒总荷载位置迁移静力主控。
    migration_main_path = solver_dir / MIGRATION_MAIN_NAME  # 构造新运行唯一允许启动的主输入路径。
    migration_main_path.write_bytes(migration_bytes)  # 写入已通过命令计数、守恒和静力截断门的主控字节。
    copied_parent_main.unlink()  # 删除 solver 中未授权启动的父全模态入口，避免误选错误主控。
    shutil.copy2(parent_dir / "solver" / base.PARENT_MAIN_NAME, input_snapshot_dir / base.PARENT_MAIN_NAME)  # 保留未修改父主控供差分审查。
    shutil.copy2(mass_csv_path, input_snapshot_dir / MASS_CSV_NAME)  # 保留生成修正向量所用质量 CSV 的逐字节快照。
    shutil.copy2(Path(__file__).resolve(), input_snapshot_dir / Path(__file__).name)  # 保留本准备实现的逐字节快照。
    shutil.copy2(Path(base.__file__).resolve(), input_snapshot_dir / Path(base.__file__).name)  # 保留被复用基础变换实现的逐字节快照。
    base.write_json(qa_dir / "load_position_migration_audit.json", correction_audit)  # 写出节点数量、质量、力总和、极值和 include 身份的机器审计。
    base.write_json(qa_dir / "migration_control_audit.json", change_audit)  # 写出两载荷步控制流、收敛准则和物理路径审计。
    base.write_json(qa_dir / "micro_validation_reference.json", {"schema_version": 2, "status": micro_results["status"], "run_name": base.MICRO_RUN_NAME, "unit_test_results_sha256": base.sha256_file(micro_dir / "unit_test_results.json"), "constraint_topology": micro_results["constraint_topology"], "planned_case_count": micro_results["planned_case_count"], "passed_case_count": micro_results["passed_case_count"], "failed_case_count": micro_results["failed_case_count"]})  # 冻结本迁移诊断依赖的 12/12 单层 TYPE72 微验证证据。
    launch_argv = [str(base.MAPDL_EXE), "-b", "-smp", "-np", "1", "-j", new_jobname, "-dir", str(solver_dir), "-i", str(migration_main_path), "-o", str(solver_dir / f"{new_jobname}.out")]  # 构造低内存单进程静力诊断启动参数，不含 DMP、MPI 或模态。
    launch_command = "& " + " ".join("'" + part.replace("'", "''") + "'" for part in launch_argv) + "\n"  # 生成可人工复核的 PowerShell 引号命令文本。
    (run_dir / "launch_command_smp1.txt").write_text(launch_command, encoding="utf-8", newline="\n")  # 写出启动合同但本准备脚本本身不调用 MAPDL。
    status = {"schema_version": 1, "run_name": run_name, "jobname": new_jobname, "status": "STATIC_DIAGNOSTIC_PREPARED", "diagnostic_subtype": "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_BETA_1_TO_0", "created_at_utc": created_at.isoformat(), "parent_run": base.PARENT_RUN_NAME, "micro_validation_run": base.MICRO_RUN_NAME, "mapdl_execution_attempted": False, "mapdl_started": False, "execution_mode": "SMP_SERIAL_NP1_DIAGNOSTIC_ONLY", "resource_gate": "FORMAL_8_GIB_FAILED_DIAGNOSTIC_EXCEPTION_REQUIRES_RUNTIME_RECHECK", "launch_allowed_for_diagnostic": True, "launch_allowed_for_production": False, "full_bridge_static_status": "LOAD_POSITION_MIGRATION_PREPARED_NOT_STARTED", "full_bridge_modal_status": "NOT_RUN", "valid_for_production": False, "next_action": "RUNTIME_RESOURCE_RECHECK_THEN_EXECUTE_LOAD_POSITION_MIGRATION_WITH_MONITORING"}  # 冻结准备完成、未启动、非生产且只允许静力诊断的根状态。
    manifest = {"schema_version": 5, "run_name": run_name, "jobname": new_jobname, "status": status["status"], "diagnostic_subtype": status["diagnostic_subtype"], "created_at_utc": created_at.isoformat(), "parent_run": base.PARENT_RUN_NAME, "parent_main_sha256": change_audit["source_sha256"], "preparer_script": f"input_snapshot/{Path(__file__).name}", "preparer_script_sha256": base.sha256_file(Path(__file__).resolve()), "base_preparer_script_sha256": PREPARER_BASE_SHA256, "micro_validation_run": base.MICRO_RUN_NAME, "micro_validation_status": micro_results["status"], "constraint_topology": "SINGLE_TYPE72_NO_AUX_NO_TYPE73", "expected_topology": parent_manifest["expected_topology"], "main_input": f"solver/{MIGRATION_MAIN_NAME}", "main_input_sha256": change_audit["candidate_sha256"], "load_position_correction_include": f"solver/{CORRECTION_INCLUDE_NAME}", "load_position_correction_include_sha256": correction_audit["include_sha256"], "load_position_migration_audit": "qa/load_position_migration_audit.json", "mapdl_executable": str(base.MAPDL_EXE), "mapdl_executable_sha256": base.sha256_file(base.MAPDL_EXE), "execution_mode": status["execution_mode"], "analysis_scope": "FULL_BRIDGE_STATIC_LS1_OLD_LOAD_POSITION_BALANCE_AND_LS2_CONSTANT_TOTAL_LOAD_POSITION_MIGRATION", "load_path_mode": "BETA_1_OLD_MCT_LOAD_POSITION_TO_BETA_0_SPATIAL_MASS21_AT_CONSTANT_TOTAL_LOAD", "initial_state_load_path": "MCT_INISTATE_PLUS_FULL_GRAVITY_AT_OLD_BALANCED_POSITION_THEN_CONTINUOUS_POSITION_MIGRATION", "initial_state_equilibrium_audit": "PENDING_FULL_STATIC_SOLUTION_AND_INDEPENDENT_BALANCE_CHECK", "constraint_imposition": "DIRECT_ELIMINATION", "penalty_n_per_mm": None, "modal_requested": False, "production_claim_allowed": False, "static_result_expected": True, "runtime_equation_count_change_allowed": False, "runtime_small_zero_negative_pivot_allowed": False, "runtime_ignored_or_reset_cnvtol_allowed": False, "launch_argv": launch_argv}  # 汇总求解器、拓扑、守恒向量、两步路径、运行时硬门和禁止生产外推边界。
    base.write_json(run_dir / "C10_static_status.json", status)  # 保存根级准备状态供执行器唯一识别。
    base.write_json(run_dir / "manifest.json", manifest)  # 保存完整迁移诊断运行清单。
    field_dictionary = "# 恒总荷载位置迁移机器字段说明\n\nJSON 不允许注释，因此字段语义集中记录于此。`beta=1` 表示完整 ACEL 与空间化质量均已存在，同时施加 `old_FZ + mass*9806` 的零合力修正向量，使二期重力回到原 MCT 初始内力对应的旧节点位置；`beta=0` 表示在完全相同的 15,071 节点集以 replacement 方式显式写入零值，最终只保留真实 MASS21 重力。迁移 include 不执行 `FDELE`，避免求解器把删除节点力解释为阶跃卸载。LS2 使用 `KBC=0` 从 beta=1 连续插值到 beta=0；因为修正向量总和小于 1E-6 N，所以每个插值子步的全桥总竖向荷载保持不变。力单位 N，长度 mm，质量 tonne，加速度 mm/s²。`STATIC_DIAGNOSTIC_PREPARED` 只表示输入和证据门通过，不表示 MAPDL 已启动或静力已收敛。四项 CNVTOL、方程数恒定和无 small/zero/negative pivot 仍是不可删除硬门；`modal_requested=false` 与 `production_claim_allowed=false` 禁止本包产生模态或生产结论。\n"  # 为无注释 JSON 提供 beta、固定节点更新、单位、守恒和结论边界说明。
    (qa_dir / "field_dictionary.md").write_text(field_dictionary, encoding="utf-8", newline="\n")  # 写出伴随字段字典。
    result_packet = f"# C10 恒总荷载位置迁移诊断准备结果\n\n状态：`STATIC_DIAGNOSTIC_PREPARED`；子类型：`CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_BETA_1_TO_0`。\n\n- 父连接：5,078 个单层 TYPE72；辅助节点=0、TYPE73=0；微验证 12/12 通过。\n- 旧 FZ 节点：{len(old_forces):,}；新 MASS21 节点：{len(masses):,}；非零位置修正节点：{len(corrections):,}。\n- 旧二期节点恒载：{correction_audit['old_fz_sum_n']} N；空间质量重力：{correction_audit['mass_gravity_sum_n']} N。\n- APDL 渲染后修正力合计：{correction_audit['rendered_correction_sum_n']} N，硬门为绝对值不超过 1E-6 N。\n- LS1：完整重力、beta=1、KBC=1、单子步，恢复原 MCT 初态对应的旧荷载位置。\n- LS2：完整重力不变、beta 从 1 迁移到 0、KBC=0、初始/最多/最少子步为 20/200/20，最终回到真实 MASS21 空间位置。\n- 稳定化始终关闭；力、力矩、位移和转角四项 CNVTOL 全部保留；方程数与主元仍是运行时硬门。\n- 当前未启动 MAPDL，没有静力、模态或生产结论。\n"  # 生成便于人工核查的守恒数值和两步路径摘要。
    (run_dir / "result_packet.md").write_text(result_packet, encoding="utf-8", newline="\n")  # 写出准备阶段人读结果包。
    artifact_paths = [path for path in run_dir.rglob("*") if path.is_file() and path.name != "artifact_hashes.sha256"]  # 收集除自引用账本外的全部准备工件。
    artifact_lines = [f"{base.sha256_file(path)}  {path.relative_to(run_dir).as_posix()}" for path in sorted(artifact_paths, key=lambda item: item.relative_to(run_dir).as_posix())]  # 生成稳定排序的当前字节摘要行。
    (run_dir / "artifact_hashes.sha256").write_text("\n".join(artifact_lines) + "\n", encoding="utf-8", newline="\n")  # 写出准备阶段完整工件哈希账本。
    print(json.dumps({"run_dir": str(run_dir), "jobname": new_jobname, "status": status["status"], "correction_node_count": len(corrections), "rendered_correction_sum_n": correction_audit["rendered_correction_sum_n"]}, ensure_ascii=False))  # 向调用者返回可解析的唯一目录、作业名和守恒摘要。


if __name__ == "__main__":  # 仅在直接执行本文件时进入一次准备流程，导入时不创建目录或启动求解器。
    main()  # 执行冻结源验证、修正向量生成、主控变换和准备工件落盘。
