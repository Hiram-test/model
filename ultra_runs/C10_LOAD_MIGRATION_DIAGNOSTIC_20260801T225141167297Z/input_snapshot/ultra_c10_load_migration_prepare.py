from __future__ import annotations  # 启用延迟类型注解，避免运行期解析复杂容器注解增加依赖。

import argparse  # 解析是否仅排除 TYPE72 静力几何应力刚度的显式单变量诊断开关。
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
PREPARER_BASE_SHA256 = "c7c14705c7635b7513bde90369aa25f59962c36411975dd72704eb14f5d2c2ba"  # 冻结已增加官方 KEYOPT(5) 诊断能力的静力准备模块六十四位小写 SHA-256 字节身份。
MASS_CSV_NAME = "mass21_spatialized_v2_nodes.csv"  # 指定 33,003 个动态质量节点的唯一权威源文件名。
MASS_CSV_SHA256 = "067997d002caa3d41337ecf2ffc28d5c2f17f9abe4db7f27fbd875abbaa39db0"  # 冻结二期空间化质量 CSV 的完整字节身份。
DEADLOAD_INCLUDE_NAME = "apply_authoritative_mct_deadload_v1.inp"  # 指定原 MCT 平衡荷载位置所在的权威恒载 include。
DEADLOAD_INCLUDE_SHA256 = "3feb7eec692762d8324865611ae600a39e4b13cd777d8d5bb29896b2e1a1223e"  # 冻结 23,028 个原始 FZ 节点荷载的 include 字节身份。
MASS_INCLUDE_NAME = "apply_dynamic_mass21_spatialized_v2.inp"  # 指定建立 33,003 个 TYPE71 MASS21 并删除旧 FZ 的动态质量 include。
MASS_INCLUDE_SHA256 = "4f9cf3cac4d1b032abccf0c3dcca208f3a9e5c7d064b25fb47ebcdd3e6bcbc9f"  # 冻结当前空间化 MASS21 求解输入字节身份。
CORRECTION_INCLUDE_NAME = "apply_constant_total_load_position_migration_v1.inp"  # 指定 LS1 恢复旧荷载位置、LS2 在同一节点集写零并由 KBC 线性迁移的 include 名称。
MIGRATION_MAIN_NAME = "c10_load_migration_static_main.inp"  # 指定新运行唯一允许启动的静力主控文件名。
PREVIOUS_MIGRATION_RUN_NAME = "C10_LOAD_MIGRATION_DIAGNOSTIC_20260801T213043973535Z"  # 指定已证明 beta=1 收敛但首个 5% 迁移过粗的直接前序运行。
K5_REFERENCE_MIGRATION_RUN_NAME = "C10_LOAD_MIGRATION_DIAGNOSTIC_20260801T215406049179Z"  # 指定已证明 0.5% 插值正确但首轮牛顿更新爆炸的直接单变量比较运行。
ADAPTIVE_INPUT_BASELINE_LEDGER_SHA256 = "5dd245c8aed37f1d50b38c0e21397899879e928cf772661529aaed8e4004cc7d"  # 冻结默认 KEYOPT(5)=0、固定 0.5% 输入基准的五十九项最终账本身份。
ADAPTIVE_INPUT_BASELINE_STATUS_SHA256 = "5d04ba688917716dba04607017e62f2d9477cfc3aadb17c5cbbf9b67725271cb"  # 冻结默认 K5 输入基准的根级终止状态身份。
ADAPTIVE_INPUT_BASELINE_MANIFEST_SHA256 = "4121dbd9e141ce0aa5339ede9f32bbccde4f9288e3ae08c1dc176de38d8429fb"  # 冻结默认 K5 输入基准的最终清单身份。
ADAPTIVE_INPUT_BASELINE_ABORT_SHA256 = "6364eec5ce4baa22071763759d6f22a22494896349334251eb11f0412542f2dc"  # 冻结默认 K5 输入基准的终止审计身份。
ADAPTIVE_INPUT_BASELINE_MAIN_SHA256 = "95692772a129acc9d37dab52df88472a9e3ebc4898b3aad83991c6a057bbaece"  # 冻结默认 K5 输入基准实际主控的字节身份。
ADAPTIVE_REFERENCE_MIGRATION_RUN_NAME = "C10_LOAD_MIGRATION_DIAGNOSTIC_20260801T222546216597Z"  # 指定 KEYOPT(5)=1 后仍逐项复现 0.5% 发散的直接前序运行。
ADAPTIVE_REFERENCE_LEDGER_SHA256 = "3138f483b3129884f5315802bc690606529e57ee3c0d7a3c85b3fe465630d5e3"  # 冻结前序 K5 运行五十九项最终工件账本的字节身份。
ADAPTIVE_REFERENCE_STATUS_SHA256 = "1504877e74e4eb8cd55be06777b70b0ef912599874526db989a785eef7c15459"  # 冻结前序 K5 运行根级终止状态的字节身份。
ADAPTIVE_REFERENCE_MANIFEST_SHA256 = "3c9b45e12fd3b8e173501fe7be7be23610cac0823be418d80f2ee9dc51a2ecce"  # 冻结前序 K5 运行最终清单的字节身份。
ADAPTIVE_REFERENCE_ABORT_SHA256 = "aeda52bd378ad3f8e4e5d1d0979931adc5a038f931c26823350f6dccb33acbb2"  # 冻结前序 K5 运行第二版终止审计的字节身份。
ADAPTIVE_REFERENCE_MAIN_SHA256 = "e9fe212fa3ff2b3c9f98b628786d5a94b6b3a5b796d728c5e8791035ce81b9e8"  # 冻结前序 K5 运行实际 APDL 主控的字节身份。
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
LS2_INITIAL_SUBSTEPS = 200  # 已证伪 5% 首步后，LS2 固定二百个荷载位置迁移子步，使每步只迁移 0.5% 的二期重力位置。
LS2_MAX_SUBSTEPS = 200  # LS2 最多二百个子步；与初始值相同，冻结 0.5% 增量并禁止求解器放大步长。
LS2_MIN_SUBSTEPS = 200  # LS2 最少二百个子步；与初始值相同，保证整个 beta 路径均保持 0.5% 分辨率。
LS2_ADAPTIVE_MAX_SUBSTEPS = 2000  # 自适应诊断最多允许二千个子步，对应失败切回时最小迁移增量为 0.05%。
EXPECTED_MASS_HEADER = ["apdl_node_id", "x_mm", "y_mm", "z_mm", "mass_tonne", "is_generated_node", "system", "assembly_name", "role", "component_ids", "component_masses_tonne"]  # 冻结质量 CSV 十一列名称和顺序，任一证据字段漂移即拒绝。
OLD_FZ_PATTERN = re.compile(r"^F,(\d+),FZ,([+\-0-9.Ee]+)$")  # 只接受无空字段、全局 FZ 和科学计数值的权威 APDL 荷载行。
LEDGER_PATTERN = re.compile(r"^([0-9a-f]{64})  (.+)$")  # 只接受标准小写 SHA-256、双空格和运行内相对路径的最终工件账本行。


def parse_args() -> argparse.Namespace:  # 无业务输入并返回命令行命名空间；两个诊断开关互斥且默认复现既有 0.5% 路径。
    parser = argparse.ArgumentParser(description="准备恒总荷载位置迁移静力诊断包。")  # 创建仅负责准备新运行且不会启动 MAPDL 的参数解析器。
    mode_group = parser.add_mutually_exclusive_group()  # 建立互斥模式组，禁止一次运行同时宣称 K5 与自适应步长为唯一变化。
    mode_group.add_argument("--exclude-mpc-stress-stiffness", action="store_true", help="仅在静力阶段设置 TYPE72 KEYOPT(5)=1，并保持固定 0.5% 迁移路径。")  # 显式选择已执行的官方 K5 单差异模式。
    mode_group.add_argument("--adaptive-migration-cutback", action="store_true", help="继承 TYPE72 KEYOPT(5)=1，仅把 LS2 改为 200/2000/200，允许切回至 0.05%。")  # 显式选择 K5 失败后的唯一数值细化诊断。
    return parser.parse_args()  # 返回已验证参数；未知参数由 argparse 以非零状态拒绝。


def require(condition: bool, message: str) -> None:  # 输入布尔条件和失败原因；条件不满足时终止准备且不返回业务值。
    if not condition:  # 仅在身份、数量、单位、守恒或控制流门禁失败时进入拒绝分支。
        raise RuntimeError(message)  # 抛出明确异常，禁止生成可被误启动的半成品运行目录。


def validate_final_artifact_ledger(run_dir: Path, expected_ledger_sha256: str) -> int:  # 输入前序运行目录和冻结账本摘要并返回逐项验证通过数量。
    ledger_path = run_dir / "artifact_hashes.sha256"  # 定位前序运行覆盖全部原件和 QA 工件的最终账本。
    require(ledger_path.is_file(), f"前序运行缺少最终账本：{run_dir.name}")  # 没有最终字节身份时禁止作为单变量基准。
    require(base.sha256_file(ledger_path) == expected_ledger_sha256, f"前序运行最终账本摘要漂移：{run_dir.name}")  # 先固定账本本身的完整字节身份。
    lines = ledger_path.read_text(encoding="utf-8").splitlines()  # 按冻结 UTF-8 格式读取全部标准摘要行。
    require(len(lines) >= 50, f"前序运行最终账本条目异常不足：{run_dir.name}")  # 阻断只覆盖准备输入而遗漏运行原件的旧账本。
    for line_number, line in enumerate(lines, start=1):  # 按真实行号逐项复算路径和当前文件内容。
        match = LEDGER_PATTERN.fullmatch(line)  # 对当前整行执行严格格式匹配。
        require(match is not None, f"前序账本第 {line_number} 行格式错误")  # 拒绝畸形摘要、分隔符或空路径。
        relative_path = Path(match.group(2))  # 把 POSIX 相对路径转换为当前平台路径对象。
        require(not relative_path.is_absolute() and ".." not in relative_path.parts, f"前序账本第 {line_number} 行路径越界")  # 禁止绝对路径和父目录逃逸。
        artifact_path = run_dir / relative_path  # 构造前序运行根内的真实工件路径。
        require(artifact_path.is_file(), f"前序账本工件缺失：{relative_path.as_posix()}")  # 拒绝被删除、移动或替换为目录的工件。
        require(base.sha256_file(artifact_path) == match.group(1), f"前序账本工件漂移：{relative_path.as_posix()}")  # 逐项复算并拒绝归档后的任何字节变化。
    return len(lines)  # 返回完整通过格式、边界、存在性和摘要门的最终工件数量。


def executable_apdl_lines(text: str) -> list[str]:  # 输入完整 APDL 文本并返回排除空行、说明注释和标题后的可执行命令序列。
    commands: list[str] = []  # 初始化保持原顺序的可执行命令列表，供单变量逐项比较。
    for line in text.splitlines():  # 按真实 APDL 行顺序扫描完整主控文本。
        stripped = line.strip()  # 去除仅影响显示的首尾空白，保留命令字段内容。
        if not stripped or stripped.startswith("!") or stripped.startswith("/TITLE,"):  # 空行、感叹号说明和运行身份标题不属于工程数值变量。
            continue  # 跳过非执行说明或已单独登记的运行标题并继续扫描。
        commands.append(stripped)  # 保存当前真实可执行命令供顺序和唯一差异核验。
    return commands  # 返回不改变命令大小写、字段或先后关系的稳定序列。


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


def transform_main(source_bytes: bytes, old_jobname: str, new_jobname: str, correction_audit: dict[str, Any], exclude_mpc_stress_stiffness: bool = False, adaptive_migration_cutback: bool = False) -> tuple[bytes, dict[str, Any]]:  # 输入父主控、作业身份、修正审计和两个互斥模式开关并返回两步位置迁移静力主控。
    require(not (exclude_mpc_stress_stiffness and adaptive_migration_cutback), "K5 单差异与自适应迁移模式不能同时显式选择")  # 防止一个新运行登记两个互斥的因果起点。
    static_k5_excluded = bool(exclude_mpc_stress_stiffness)  # 自适应模式回到默认 K5=0 输入基准，仅显式 K5 诊断设置 KEYOPT(5)=1。
    ls2_max_substeps = LS2_ADAPTIVE_MAX_SUBSTEPS if adaptive_migration_cutback else LS2_MAX_SUBSTEPS  # 仅自适应模式把允许的最大子步数从二百增加到二千。
    base_bytes, audit = base.transform_main(source_bytes, old_jobname, new_jobname)  # 先复用已验证的单层 TYPE72、四项 CNVTOL、LS1 形成态和静力截断变换。
    candidate = base_bytes.decode("utf-8")  # 严格按 UTF-8 解码已通过基础控制流门的候选主控。
    newline = "\r\n" if "\r\n" in candidate else "\n"  # 保持父主控原有 CRLF 或 LF 换行风格。
    migration_title = "/TITLE,C10 DIRECT MPC CONSTANT-LOAD MIGRATION ADAPTIVE-CUTBACK STATIC DIAGNOSTIC" if adaptive_migration_cutback else ("/TITLE,C10 DIRECT MPC CONSTANT-LOAD MIGRATION K5-EXCLUDED STATIC DIAGNOSTIC" if exclude_mpc_stress_stiffness else "/TITLE,C10 DIRECT MPC CONSTANT-TOTAL-LOAD POSITION-MIGRATION STATIC DIAGNOSTIC")  # 用标题区分默认 K5 自适应、K5 排除和固定 0.5% 三种互斥运行身份。
    candidate = base.replace_once(candidate, "/TITLE,C10 DIRECT MPC STATIC FULL-FORMED-STATE EQUILIBRIUM-PAIR DIAGNOSTIC", migration_title, "恒总荷载位置迁移标题")  # 使 OUT 明确区分被证伪的全形成态直配路径及本次唯一数值变量。
    if static_k5_excluded:  # 只有显式 K5 单差异诊断设置 TYPE72 KEYOPT(5)=1，自适应模式保持权威默认值零。
        prep7_anchor = "! 进入前处理器读取完整装配后的节点和单元身份。" + newline + "/PREP7" + newline  # 冻结全部 include 装配完成后且首个 SOLVE 前的合法前处理器锚点。
        prep7_block = prep7_anchor + "! 按 MPC184 单元文档建议，仅在本静力诊断中排除 rigid-beam 几何应力刚度对切线矩阵的贡献。" + newline + "KEYOPT,72,5,1" + newline  # 保留 TYPE72 直接消元刚体运动学、荷载和连接，仅切换可能造成罕见收敛困难的 KEYOPT(5)。
        candidate = base.replace_once(candidate, prep7_anchor, prep7_block, "TYPE72 静力几何应力刚度排除")  # 在节点单元计数和两次静力求解前唯一设置 TYPE72 KEYOPT(5)=1。
    ls1_anchor = "! 施加 +Z 参考加速度 9806 mm/s²，使结构承受 -Z 重力。" + newline + "ACEL,0,0,9806" + newline  # 冻结 LS1 唯一重力命令作为 beta=1 插入点。
    ls1_insertion = ls1_anchor + "! 把二值迁移参数设为 1，使修正 include 恢复原 MCT 初态对应的平衡荷载位置。" + newline + "C10_BETA=1" + newline + "! 施加总和小于 1E-6 N 的位置修正向量；总重力大小保持不变。" + newline + f"/INPUT,{Path(CORRECTION_INCLUDE_NAME).stem},inp" + newline  # 在首个 SOLVE 前建立旧位置端点。
    candidate = base.replace_once(candidate, ls1_anchor, ls1_insertion, "LS1 beta=1 旧荷载位置恢复")  # 保证修正 include 只在唯一 LS1 重力锚点后插入一次。
    ls2_anchor = "! 重发同一重力加速度，明确 LS2 没有新增物理外载。" + newline + "ACEL,0,0,9806" + newline  # 冻结 LS2 唯一重力命令作为 beta=0 插入点。
    ls2_insertion = ls2_anchor + "! 把二值迁移参数设为 0，使修正 include 在同一 15,071 节点集显式写入零值并定义最终荷载端点。" + newline + "C10_BETA=0" + newline + "! 用 replacement 重发 LS1 修正节点的零端点；随后 KBC,0 连续插值，ACEL 和总重力保持不变。" + newline + f"/INPUT,{Path(CORRECTION_INCLUDE_NAME).stem},inp" + newline  # 在第二次 SOLVE 前定义固定节点集的零修正终点。
    candidate = base.replace_once(candidate, ls2_anchor, ls2_insertion, "LS2 beta=0 空间质量位置终点")  # 保证修正 include 只在唯一 LS2 重力锚点后再次调用。
    ls2_autots_old = "! 关闭 LS2 自动步长，禁止 cutback 掩盖保持步失稳。" + newline + "AUTOTS,OFF" + newline  # 冻结基础候选中单步保持的自动步长片段。
    ls2_autots_new = ("! 启用 LS2 自动时间步；初始和最少子步数保持二百，禁止增量大于 0.5%，失败时最多细分到二千子步即 0.05%。" if adaptive_migration_cutback else "! 保留 LS2 自动时间步框架，但 NSUBST 的初始、最大和最小值均为二百，因此实际增量固定为 0.5%。") + newline + "AUTOTS,ON" + newline  # 自适应模式只允许缩小增量，固定模式继续禁止放大或缩小。
    candidate = base.replace_once(candidate, ls2_autots_old, ls2_autots_new, "LS2 位置迁移自动步长")  # 只改变 LS2，LS1 仍保持形成态单步禁止细分。
    ls2_nsubst_old = "! LS2 固定单一子步，不允许细分、放大或缩减。" + newline + "NSUBST,1,1,1" + newline  # 冻结基础候选中 LS2 单子步片段。
    ls2_nsubst_description = f"! LS2 初始 {LS2_INITIAL_SUBSTEPS}、最多 {ls2_max_substeps}、最少 {LS2_MIN_SUBSTEPS} 个子步；初始与最大迁移增量为 0.5%" + ("，失败时允许切回至最小 0.05%。" if adaptive_migration_cutback else "，三项相等所以禁止切回或放大。")  # 准确解释 NSUBST 的初始、最大和最小子步数对增量上下界的控制。
    ls2_nsubst_new = ls2_nsubst_description + newline + f"NSUBST,{LS2_INITIAL_SUBSTEPS},{ls2_max_substeps},{LS2_MIN_SUBSTEPS}" + newline  # 建立连续且永不大于 0.5% 的固定或自适应位置迁移路径。
    candidate = base.replace_once(candidate, ls2_nsubst_old, ls2_nsubst_new, "LS2 位置迁移子步合同")  # 只替换 LS2 子步上限，其他非线性和物理控制不变。
    candidate = base.replace_once(candidate, "! 重发同一重力加速度，明确 LS2 没有新增物理外载。", "! 重发同一重力加速度；LS2 只改变二期重力空间位置，不改变总荷载或 ACEL。", "LS2 重力语义")  # 更正原零增量保持说明。
    candidate = base.replace_once(candidate, "! 保持斜坡定义；因起终点重力相同，实际外载增量为零。", "! 使用斜坡定义把 beta=1 修正向量连续插值到 beta=0；修正向量总和为零，所以每个子步总荷载恒定。", "LS2 KBC 迁移语义")  # 明确 KBC 只迁移位置。
    candidate = base.replace_once(candidate, "! 执行 LS2 单子步、无稳定化、无新增外载保持求解。", "! 执行 LS2 无稳定化恒总荷载位置迁移，并在 beta=0 空间化 MASS21 端点取得最终平衡。", "LS2 SOLVE 迁移语义")  # 更正第二次求解的物理角色。
    ls2_convergence_semantics = "! LS2 最终端点 CNVG 不等于 1 时立即拒绝；允许的 cutback 只能增加路径分辨率，不能放宽收敛准则。" if adaptive_migration_cutback else "! LS2 最终端点 CNVG 不等于 1 时立即拒绝；本固定 200/200/200 合同不允许 cutback。"  # 根据实际 NSUBST 合同准确声明是否允许求解器细分。
    candidate = base.replace_once(candidate, "! LS2 CNVG 不等于 1 时立即拒绝，不允许 cutback。", ls2_convergence_semantics, "LS2 收敛门语义")  # 更正结果门和数值细分边界，禁止审计文字与命令矛盾。
    candidate = base.replace_once(candidate, "/COM,STATUS=REJECTED REASON=LS2_HOLD_NOT_CONVERGED", "/COM,STATUS=REJECTED REASON=LS2_LOAD_POSITION_MIGRATION_NOT_CONVERGED", "LS2 失败原因")  # 输出可机器解析的真实失败类型。
    candidate = base.replace_once(candidate, "! 读取 LS2 无稳定化保持步的最后收敛结果。", "! 读取 LS2 无稳定化位置迁移的 beta=0 最后收敛结果。", "LS2 后处理语义")  # 使能量端点说明与新路径一致。
    candidate_lines = candidate.splitlines()  # 建立逐行命令视图，使计数不受说明文字中出现 KBC、AUTOTS 或 NSUBST 名称影响。
    require(candidate.count(f"/INPUT,{Path(CORRECTION_INCLUDE_NAME).stem},inp") == 2, "位置迁移 include 调用数不是两次")  # 固定 beta=1 与 beta=0 两个端点调用。
    require(candidate_lines.count("C10_BETA=1") == 1 and candidate_lines.count("C10_BETA=0") == 1, "二值迁移参数端点不唯一")  # 禁止重复或遗漏端点命令。
    require(candidate_lines.count("KBC,1") == 1 and candidate_lines.count("KBC,0") == 1, "LS1 阶跃与 LS2 迁移 KBC 配置不唯一")  # 确认首步直配、次步线性迁移。
    require(candidate_lines.count("AUTOTS,OFF") == 1 and candidate_lines.count("AUTOTS,ON") == 1, "LS1/LS2 自动步长配置不唯一")  # 固定 LS1 禁止细分，并由 LS2 的 NSUBST 上下界决定是否允许切回。
    require(candidate_lines.count("NSUBST,1,1,1") == 1 and candidate_lines.count(f"NSUBST,{LS2_INITIAL_SUBSTEPS},{ls2_max_substeps},{LS2_MIN_SUBSTEPS}") == 1, "LS1/LS2 子步合同不唯一")  # 固定 LS1 单步和当前模式唯一的 LS2 数值路径。
    require(sum(1 for line in candidate_lines if line.startswith("CNVTOL,")) == 4, "恒总荷载主控未保留四项 CNVTOL")  # 禁止以删除收敛准则换取表面通过。
    require("PERTURB,MODAL" not in candidate and "MODOPT," not in candidate, "恒总荷载诊断仍含模态命令")  # 保持本运行只限静力修复验证。
    require(candidate_lines.count("KEYOPT,72,5,1") == (1 if static_k5_excluded else 0), "TYPE72 KEYOPT(5)=1 命令数量与诊断模式不一致")  # 确认仅 K5 模式恰一次，自适应和默认模式完全不存在该命令。
    audit["schema_version"] = 6 if adaptive_migration_cutback else (5 if exclude_mpc_stress_stiffness else 4)  # 自适应、K5 单差异和默认路径分别采用第六、第五和第四版审计结构。
    audit["change_families"] = [*audit["change_families"], "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_BETA_1_TO_0", *( ["MPC184_STATIC_GEOMETRIC_STRESS_STIFFNESS_EXCLUSION"] if static_k5_excluded else [] ), *( ["LS2_ADAPTIVE_CUTBACK_0_5_TO_0_05_PERCENT"] if adaptive_migration_cutback else [] )]  # 记录共同迁移，并分别追加互斥的 K5 或自适应步长变更族。
    audit["load_path_physical_basis"] = "MCT_INITIAL_FORCE_STATE_BALANCED_AT_OLD_DEADLOAD_POSITIONS_THEN_CONTINUOUSLY_MIGRATED_TO_SPATIAL_MASS21_AT_CONSTANT_TOTAL_LOAD"  # 冻结修复的工程依据。
    audit["load_path_physical_approval"] = "DIAGNOSTIC_HYPOTHESIS_REQUIRES_FULL_STATIC_CONVERGENCE_BALANCE_AND_SENSITIVITY_CHECK"  # 明确准备完成不等于工程批准。
    audit["ls1"] = {"kbc": 1, "autots": False, "nsubst": [1, 1, 1], "time": 1.0, "beta": 1.0, "physical_role": "RESTORE_OLD_MCT_BALANCED_LOAD_POSITIONS_WITH_FULL_GRAVITY"}  # 记录首步完整形成态端点。
    audit["ls2"] = {"kbc": 0, "autots": True, "nsubst": [LS2_INITIAL_SUBSTEPS, ls2_max_substeps, LS2_MIN_SUBSTEPS], "initial_migration_fraction": 1.0 / LS2_INITIAL_SUBSTEPS, "minimum_migration_fraction": 1.0 / ls2_max_substeps, "maximum_migration_fraction": 1.0 / LS2_MIN_SUBSTEPS, "cutback_allowed": adaptive_migration_cutback, "time": 1.001, "beta_start": 1.0, "beta_end": 0.0, "total_vertical_load_change_n": correction_audit["rendered_correction_sum_n"], "physical_role": "CONTINUOUS_LOAD_POSITION_MIGRATION_TO_FINAL_SPATIAL_MASS21"}  # 记录第二步连续迁移、增量上下界、切回许可和守恒量。
    audit["mpc184_keyopt5_static"] = 1 if static_k5_excluded else 0  # 机器记录两次静力求解实际采用的 TYPE72 KEYOPT(5) 值。
    audit["prestressed_modal_requires_keyopt5_restore_to_zero"] = bool(static_k5_excluded)  # 仅 K5 排除模式声明模态前恢复；自适应模式从始至终保持默认零。
    audit["load_position_correction"] = correction_audit  # 嵌入源数量、总和、极值与 include 摘要，闭合主控到物理向量的追溯。
    rendered = candidate.encode("utf-8")  # 将完成语义与数值门的主控重新编码为 UTF-8 字节。
    audit["candidate_sha256"] = base.sha256_bytes(rendered)  # 用最终真实入口覆盖基础候选摘要。
    return rendered, audit  # 返回两步恒总荷载迁移静力主控和完整变更审计。


def main() -> None:  # 读取单变量开关、验证冻结源并生成一个全新且未启动的恒总荷载位置迁移诊断包。
    args = parse_args()  # 解析互斥的 K5 排除或自适应切回模式，未知参数直接拒绝。
    exclude_mpc_stress_stiffness = bool(args.exclude_mpc_stress_stiffness)  # 规范化为输入变换、谱系门、清单和说明共用的唯一模式标志。
    adaptive_migration_cutback = bool(args.adaptive_migration_cutback)  # 规范化为 NSBMX、授权证据、清单和结果说明共用的唯一模式标志。
    static_k5_excluded = bool(exclude_mpc_stress_stiffness)  # 自适应模式保持默认 K5=0，仅显式 K5 诊断排除刚臂几何应力刚度。
    ls2_max_substeps = LS2_ADAPTIVE_MAX_SUBSTEPS if adaptive_migration_cutback else LS2_MAX_SUBSTEPS  # 当前模式的 LS2 最大子步数决定最小允许迁移增量。
    require(base.sha256_file(Path(base.__file__).resolve()) == PREPARER_BASE_SHA256, "被复用静力准备模块 SHA-256 漂移")  # 关闭基础变换实现的代码身份门。
    parent_dir = base.RUNS_ROOT / base.PARENT_RUN_NAME  # 定位已修复为单层 TYPE72 的权威父运行。
    micro_dir = base.RUNS_ROOT / base.MICRO_RUN_NAME  # 定位 12/12 通过的单层连接微验证运行。
    parent_manifest, micro_results = base.validate_parent(parent_dir, micro_dir)  # 在创建目录前关闭全部父依赖和微验证门。
    previous_migration_run_name = K5_REFERENCE_MIGRATION_RUN_NAME if (exclude_mpc_stress_stiffness or adaptive_migration_cutback) else PREVIOUS_MIGRATION_RUN_NAME  # K5 与自适应模式都从默认 K5=0 的固定 0.5% 输入基准派生。
    expected_previous_status = "ABORTED_BY_CONTROLLER_AFTER_LS2_FIRST_0_5_PERCENT_MIGRATION_DIVERGED" if (exclude_mpc_stress_stiffness or adaptive_migration_cutback) else "ABORTED_BY_CONTROLLER_AFTER_LS2_FIRST_5_PERCENT_MIGRATION_DIVERGED"  # 冻结当前模式允许引用的唯一输入基准终态。
    previous_increment_fraction = 0.005 if (exclude_mpc_stress_stiffness or adaptive_migration_cutback) else 0.05  # 两种单差异模式保持 0.5% 初始步，兼容模式从 5% 缩小到 0.5%。
    new_increment_fraction = 0.005  # 所有新 LS2 的首个尝试和最大允许增量都为完整迁移路径的 0.5%。
    new_minimum_increment_fraction = 0.0005 if adaptive_migration_cutback else 0.005  # 仅自适应模式允许失败时最小切回至完整路径的 0.05%。
    step_refinement_factor = 1 if (exclude_mpc_stress_stiffness or adaptive_migration_cutback) else 10  # 记录初始增量相对输入基准是否变化，避免把最小 cutback 误称新首步。
    single_variable_change = "LS2_NSBMX_200_TO_2000_ONLY" if adaptive_migration_cutback else ("TYPE72_KEYOPT5_0_TO_1_ONLY" if exclude_mpc_stress_stiffness else "LS2_INCREMENT_5_PERCENT_TO_0_5_PERCENT_ONLY")  # 明确候选相对输入基准唯一获准的可执行命令变化。
    diagnostic_subtype = "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_ADAPTIVE_CUTBACK_TO_0_05_PERCENT" if adaptive_migration_cutback else ("CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_WITH_MPC184_STATIC_STRESS_STIFFNESS_EXCLUDED" if exclude_mpc_stress_stiffness else "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_BETA_1_TO_0")  # 为根状态和清单生成三种互斥诊断子类型。
    previous_migration_dir = base.RUNS_ROOT / previous_migration_run_name  # 定位当前模式指定的直接前序迁移运行。
    previous_migration_status = base.load_json(previous_migration_dir / "C10_static_status.json")  # 读取前序根状态供单变量因果门禁。
    require(previous_migration_status.get("status") == expected_previous_status, "前序迁移运行状态不符合当前单变量诊断合同")  # 禁止在失败证据未闭合时改变数值变量。
    require(previous_migration_status.get("ls1_beta_1_converged") is True, "前序迁移运行未证明 beta=1 基态收敛")  # 新运行必须继承已证实的物理起点而非另一条假设。
    require(float(previous_migration_status.get("ls2_attempted_migration_fraction", -1.0)) == previous_increment_fraction, "前序迁移首步比例不符合当前比较基准")  # 固定 5% 细化基准或 0.5% 单差异基准。
    if exclude_mpc_stress_stiffness or adaptive_migration_cutback:  # 两种从默认 0.5% 输入派生的模式都必须复算其五十九项最终归档。
        baseline_entry_count = validate_final_artifact_ledger(previous_migration_dir, ADAPTIVE_INPUT_BASELINE_LEDGER_SHA256)  # 复算默认 K5=0 基准的完整最终账本。
        require(baseline_entry_count == 59, "默认 0.5% 输入基准最终账本条目不是五十九项")  # 固定已发布归档覆盖规模。
        require(base.sha256_file(previous_migration_dir / "C10_static_status.json") == ADAPTIVE_INPUT_BASELINE_STATUS_SHA256, "默认 0.5% 输入基准状态摘要漂移")  # 固定根状态字节身份。
        require(base.sha256_file(previous_migration_dir / "manifest.json") == ADAPTIVE_INPUT_BASELINE_MANIFEST_SHA256, "默认 0.5% 输入基准清单摘要漂移")  # 固定最终清单字节身份。
        require(base.sha256_file(previous_migration_dir / "qa" / "runtime_abort_audit.json") == ADAPTIVE_INPUT_BASELINE_ABORT_SHA256, "默认 0.5% 输入基准终止审计摘要漂移")  # 固定发散数值证据身份。
        require(base.sha256_file(previous_migration_dir / "solver" / MIGRATION_MAIN_NAME) == ADAPTIVE_INPUT_BASELINE_MAIN_SHA256, "默认 0.5% 输入基准主控摘要漂移")  # 固定可执行输入身份。
    if adaptive_migration_cutback:  # 只有自适应模式需要额外证明 K5 单差异已无效并明确授权步长细化。
        authorization_dir = base.RUNS_ROOT / ADAPTIVE_REFERENCE_MIGRATION_RUN_NAME  # 定位已正式封板的 K5=1 同轨发散授权运行。
        authorization_entry_count = validate_final_artifact_ledger(authorization_dir, ADAPTIVE_REFERENCE_LEDGER_SHA256)  # 复算授权运行五十九项最终工件。
        require(authorization_entry_count == 59, "K5 授权运行最终账本条目不是五十九项")  # 固定授权归档覆盖规模。
        require(base.sha256_file(authorization_dir / "C10_static_status.json") == ADAPTIVE_REFERENCE_STATUS_SHA256, "K5 授权运行根状态摘要漂移")  # 固定 K5 无效根结论。
        require(base.sha256_file(authorization_dir / "manifest.json") == ADAPTIVE_REFERENCE_MANIFEST_SHA256, "K5 授权运行清单摘要漂移")  # 固定 K5 运行完整谱系。
        require(base.sha256_file(authorization_dir / "qa" / "runtime_abort_audit.json") == ADAPTIVE_REFERENCE_ABORT_SHA256, "K5 授权运行终止审计摘要漂移")  # 固定同轨残差证据。
        require(base.sha256_file(authorization_dir / "solver" / MIGRATION_MAIN_NAME) == ADAPTIVE_REFERENCE_MAIN_SHA256, "K5 授权运行主控摘要漂移")  # 固定 K5=1 实际可执行输入。
        authorization_status = base.load_json(authorization_dir / "C10_static_status.json")  # 读取授权根状态供关键语义门禁。
        authorization_abort = base.load_json(authorization_dir / "qa" / "runtime_abort_audit.json")  # 读取授权终止审计供 K5 无效与后续许可门禁。
        require(authorization_status.get("status") == "ABORTED_BY_CONTROLLER_AFTER_LS2_FIRST_0_5_PERCENT_MIGRATION_DIVERGED_WITH_MPC184_STATIC_STRESS_STIFFNESS_EXCLUDED", "K5 授权运行终态不符合冻结失败类型")  # 只接受已正式封板的 K5 无效运行。
        require(authorization_abort.get("single_difference_observed_effect") == "NO_CHANGE_IN_LS2_FIRST_TWO_NR_STATES_AT_PRINTED_PRECISION" and authorization_abort.get("ls1_converged") is True and int(authorization_abort.get("ls2_completed_substeps", -1)) == 0, "K5 授权运行未证明同轨发散或 LS1 基态闭合")  # 固定 K5 证伪核心事实。
        require(authorization_abort.get("next_diagnostic_single_difference") == "LS2_ADAPTIVE_SUBSTEPS_200_2000_200_ALLOW_0_05_PERCENT_MINIMUM_INCREMENT", "K5 授权运行未明确批准 200/2000/200 下一步")  # 防止未经批准扩大数值路径。
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
    job_family = "cw_C10madp" if adaptive_migration_cutback else ("cw_C10mk5" if exclude_mpc_stress_stiffness else "cw_C10m")  # 用短 ASCII 前缀区分自适应、K5 单差异和普通迁移运行。
    new_jobname = f"{job_family}_{created_at.strftime('%m%dt%H%M%S')}_d1"  # 派生不超过三十二字符且不复用历史结果的唯一迁移作业名。
    require(len(new_jobname) <= 32, "恒总荷载迁移 MAPDL 作业名超过 32 字符")  # 遵守求解器文件前缀长度限制。
    copied_parent_main = solver_dir / base.PARENT_MAIN_NAME  # 定位刚复制到新 solver 目录的父全模态主控。
    parent_main_bytes = copied_parent_main.read_bytes()  # 读取父主控原始字节供受控变换。
    require(base.sha256_bytes(parent_main_bytes) == str(parent_manifest.get("main_input_sha256")), "父主控摘要与清单不一致")  # 再次闭合入口身份。
    migration_bytes, change_audit = transform_main(parent_main_bytes, old_jobname, new_jobname, correction_audit, exclude_mpc_stress_stiffness, adaptive_migration_cutback)  # 生成 LS1 旧位置平衡、LS2 恒总荷载迁移及当前唯一数值分支的静力主控。
    if adaptive_migration_cutback:  # 自适应运行必须在创建可启动入口前证明相对默认 0.5% 输入只有 NSBMX 一项变化。
        baseline_manifest = base.load_json(previous_migration_dir / "manifest.json")  # 读取默认 K5=0 输入基准的实际作业身份。
        baseline_jobname = str(baseline_manifest.get("jobname"))  # 提取基准作业名，使比较候选消除运行身份差异。
        require(baseline_jobname and baseline_jobname != "None", "默认 0.5% 输入基准缺少作业名")  # 拒绝畸形清单造成虚假归一化。
        comparison_bytes, comparison_audit = transform_main(parent_main_bytes, old_jobname, baseline_jobname, correction_audit, False, True)  # 用基准作业名在内存重建自适应候选，不写入额外文件。
        baseline_main_text = (previous_migration_dir / "solver" / MIGRATION_MAIN_NAME).read_text(encoding="utf-8")  # 读取已由最终账本验证的默认 0.5% 主控。
        baseline_commands = executable_apdl_lines(baseline_main_text)  # 生成排除标题和说明后的基准可执行序列。
        adaptive_commands = executable_apdl_lines(comparison_bytes.decode("utf-8"))  # 生成同作业名自适应候选的可执行序列。
        require(baseline_commands.count("NSUBST,200,200,200") == 1 and baseline_commands.count("NSUBST,200,2000,200") == 0, "输入基准 NSUBST 合同不是固定 200/200/200")  # 固定唯一差异的旧值。
        require(adaptive_commands.count("NSUBST,200,200,200") == 0 and adaptive_commands.count("NSUBST,200,2000,200") == 1, "自适应候选 NSUBST 合同不是 200/2000/200")  # 固定唯一差异的新值。
        normalized_adaptive_commands = ["NSUBST,200,200,200" if command == "NSUBST,200,2000,200" else command for command in adaptive_commands]  # 仅把获准的新 NSBMX 值归一回基准值供全序列比较。
        require(normalized_adaptive_commands == baseline_commands, "自适应候选除 NSBMX 200→2000 外仍含其他可执行命令变化")  # 逐项关闭隐藏 K5、荷载、连接、收敛或控制流变化。
        change_audit["single_difference_input_baseline"] = {"run_name": previous_migration_dir.name, "main_sha256": ADAPTIVE_INPUT_BASELINE_MAIN_SHA256, "baseline_command_count": len(baseline_commands), "candidate_command_count": len(adaptive_commands), "only_executable_change": "NSUBST,200,200,200_TO_NSUBST,200,2000,200", "comparison_candidate_sha256": comparison_audit["candidate_sha256"]}  # 记录同作业名命令级单差异证明和摘要。
    migration_main_path = solver_dir / MIGRATION_MAIN_NAME  # 构造新运行唯一允许启动的主输入路径。
    migration_main_path.write_bytes(migration_bytes)  # 写入已通过命令计数、守恒和静力截断门的主控字节。
    copied_parent_main.unlink()  # 删除 solver 中未授权启动的父全模态入口，避免误选错误主控。
    shutil.copy2(parent_dir / "solver" / base.PARENT_MAIN_NAME, input_snapshot_dir / base.PARENT_MAIN_NAME)  # 保留未修改父主控供差分审查。
    shutil.copy2(mass_csv_path, input_snapshot_dir / MASS_CSV_NAME)  # 保留生成修正向量所用质量 CSV 的逐字节快照。
    shutil.copy2(Path(__file__).resolve(), input_snapshot_dir / Path(__file__).name)  # 保留本准备实现的逐字节快照。
    shutil.copy2(Path(base.__file__).resolve(), input_snapshot_dir / Path(base.__file__).name)  # 保留被复用基础变换实现的逐字节快照。
    base.write_json(qa_dir / "load_position_migration_audit.json", correction_audit)  # 写出节点数量、质量、力总和、极值和 include 身份的机器审计。
    base.write_json(qa_dir / "migration_control_audit.json", change_audit)  # 写出两载荷步控制流、收敛准则和物理路径审计。
    base.write_json(qa_dir / "previous_migration_reference.json", {"schema_version": 3 if adaptive_migration_cutback else (2 if exclude_mpc_stress_stiffness else 1), "role": "SINGLE_DIFFERENCE_INPUT_BASELINE", "status": previous_migration_status["status"], "run_name": previous_migration_run_name, "root_status_sha256": base.sha256_file(previous_migration_dir / "C10_static_status.json"), "manifest_sha256": base.sha256_file(previous_migration_dir / "manifest.json"), "final_artifact_ledger_sha256": base.sha256_file(previous_migration_dir / "artifact_hashes.sha256") if (exclude_mpc_stress_stiffness or adaptive_migration_cutback) else None, "main_input_sha256": base.sha256_file(previous_migration_dir / "solver" / MIGRATION_MAIN_NAME), "runtime_abort_audit_sha256": base.sha256_file(previous_migration_dir / "qa" / "runtime_abort_audit.json"), "ls1_beta_1_converged": True, "previous_first_increment_fraction": previous_increment_fraction, "new_initial_increment_fraction": new_increment_fraction, "new_minimum_increment_fraction": new_minimum_increment_fraction, "initial_step_refinement_factor": step_refinement_factor, "single_variable_change": single_variable_change})  # 冻结输入基准完整身份、首步不变关系、最小切回和唯一可执行变化。
    if adaptive_migration_cutback:  # 自适应包单独记录 K5=1 证伪运行，避免把授权证据误当输入派生基准。
        base.write_json(qa_dir / "adaptive_authorization_reference.json", {"schema_version": 1, "role": "FOLLOWUP_AUTHORIZATION_EVIDENCE_NOT_INPUT_BASELINE", "run_name": authorization_dir.name, "status": authorization_status["status"], "root_status_sha256": ADAPTIVE_REFERENCE_STATUS_SHA256, "manifest_sha256": ADAPTIVE_REFERENCE_MANIFEST_SHA256, "runtime_abort_audit_sha256": ADAPTIVE_REFERENCE_ABORT_SHA256, "main_input_sha256": ADAPTIVE_REFERENCE_MAIN_SHA256, "final_artifact_ledger_sha256": ADAPTIVE_REFERENCE_LEDGER_SHA256, "final_artifact_ledger_entry_count": authorization_entry_count, "single_difference_observed_effect": authorization_abort["single_difference_observed_effect"], "ls1_converged": authorization_abort["ls1_converged"], "ls2_completed_substeps": authorization_abort["ls2_completed_substeps"], "authorized_next_diagnostic": authorization_abort["next_diagnostic_single_difference"]})  # 冻结 K5 无效、LS1 闭合、LS2 零完成子步和 200/2000/200 授权链。
    base.write_json(qa_dir / "micro_validation_reference.json", {"schema_version": 2, "status": micro_results["status"], "run_name": base.MICRO_RUN_NAME, "unit_test_results_sha256": base.sha256_file(micro_dir / "unit_test_results.json"), "constraint_topology": micro_results["constraint_topology"], "planned_case_count": micro_results["planned_case_count"], "passed_case_count": micro_results["passed_case_count"], "failed_case_count": micro_results["failed_case_count"]})  # 冻结本迁移诊断依赖的 12/12 单层 TYPE72 微验证证据。
    launch_argv = [str(base.MAPDL_EXE), "-b", "-smp", "-np", "1", "-j", new_jobname, "-dir", str(solver_dir), "-i", str(migration_main_path), "-o", str(solver_dir / f"{new_jobname}.out")]  # 构造低内存单进程静力诊断启动参数，不含 DMP、MPI 或模态。
    launch_command = "& " + " ".join("'" + part.replace("'", "''") + "'" for part in launch_argv) + "\n"  # 生成可人工复核的 PowerShell 引号命令文本。
    (run_dir / "launch_command_smp1.txt").write_text(launch_command, encoding="utf-8", newline="\n")  # 写出启动合同但本准备脚本本身不调用 MAPDL。
    next_action = "RUNTIME_RESOURCE_RECHECK_THEN_EXECUTE_ADAPTIVE_MIGRATION_ALLOW_BISECTION_TO_0_05_PERCENT" if adaptive_migration_cutback else ("RUNTIME_RESOURCE_RECHECK_THEN_EXECUTE_SINGLE_VARIABLE_K5_LOAD_MIGRATION_WITH_MONITORING" if exclude_mpc_stress_stiffness else "RUNTIME_RESOURCE_RECHECK_THEN_EXECUTE_LOAD_POSITION_MIGRATION_WITH_MONITORING")  # 冻结当前模式唯一允许的启动和监控行为。
    status = {"schema_version": 3 if adaptive_migration_cutback else (2 if exclude_mpc_stress_stiffness else 1), "run_name": run_name, "jobname": new_jobname, "status": "STATIC_DIAGNOSTIC_PREPARED", "diagnostic_subtype": diagnostic_subtype, "created_at_utc": created_at.isoformat(), "parent_run": base.PARENT_RUN_NAME, "previous_migration_run": previous_migration_run_name, "authorization_evidence_run": ADAPTIVE_REFERENCE_MIGRATION_RUN_NAME if adaptive_migration_cutback else None, "single_variable_change": single_variable_change, "ls2_nsubst": [LS2_INITIAL_SUBSTEPS, ls2_max_substeps, LS2_MIN_SUBSTEPS], "ls2_initial_migration_fraction": new_increment_fraction, "ls2_minimum_migration_fraction": new_minimum_increment_fraction, "mpc184_keyopt5_static": 1 if static_k5_excluded else 0, "prestressed_modal_requires_keyopt5_restore_to_zero": bool(static_k5_excluded), "micro_validation_run": base.MICRO_RUN_NAME, "mapdl_execution_attempted": False, "mapdl_started": False, "execution_mode": "SMP_SERIAL_NP1_DIAGNOSTIC_ONLY", "resource_gate": "FORMAL_8_GIB_FAILED_DIAGNOSTIC_EXCEPTION_REQUIRES_RUNTIME_RECHECK", "launch_allowed_for_diagnostic": True, "launch_allowed_for_production": False, "full_bridge_static_status": "LOAD_POSITION_MIGRATION_PREPARED_NOT_STARTED", "full_bridge_modal_status": "NOT_RUN", "valid_for_production": False, "next_action": next_action}  # 冻结准备完成、输入基准、授权证据、唯一数值变量、步长边界和只允许静力诊断的根状态。
    manifest = {"schema_version": 7 if adaptive_migration_cutback else (6 if exclude_mpc_stress_stiffness else 5), "run_name": run_name, "jobname": new_jobname, "status": status["status"], "diagnostic_subtype": status["diagnostic_subtype"], "created_at_utc": created_at.isoformat(), "parent_run": base.PARENT_RUN_NAME, "parent_main_sha256": change_audit["source_sha256"], "single_difference_input_baseline_run": previous_migration_run_name, "previous_migration_run": previous_migration_run_name, "previous_migration_reference": "qa/previous_migration_reference.json", "authorization_evidence_run": ADAPTIVE_REFERENCE_MIGRATION_RUN_NAME if adaptive_migration_cutback else None, "adaptive_authorization_reference": "qa/adaptive_authorization_reference.json" if adaptive_migration_cutback else None, "migration_increment_change": {"previous_initial_fraction": previous_increment_fraction, "new_initial_fraction": new_increment_fraction, "new_minimum_fraction": new_minimum_increment_fraction, "initial_refinement_factor": step_refinement_factor, "nsbstp": LS2_INITIAL_SUBSTEPS, "nsbmx": ls2_max_substeps, "nsbmn": LS2_MIN_SUBSTEPS}, "single_variable_change": single_variable_change, "mpc184_keyopt5_static": 1 if static_k5_excluded else 0, "prestressed_modal_requires_keyopt5_restore_to_zero": bool(static_k5_excluded), "preparer_script": f"input_snapshot/{Path(__file__).name}", "preparer_script_sha256": base.sha256_file(Path(__file__).resolve()), "base_preparer_script_sha256": PREPARER_BASE_SHA256, "micro_validation_run": base.MICRO_RUN_NAME, "micro_validation_status": micro_results["status"], "constraint_topology": "SINGLE_TYPE72_NO_AUX_NO_TYPE73", "expected_topology": parent_manifest["expected_topology"], "main_input": f"solver/{MIGRATION_MAIN_NAME}", "main_input_sha256": change_audit["candidate_sha256"], "load_position_correction_include": f"solver/{CORRECTION_INCLUDE_NAME}", "load_position_correction_include_sha256": correction_audit["include_sha256"], "load_position_migration_audit": "qa/load_position_migration_audit.json", "mapdl_executable": str(base.MAPDL_EXE), "mapdl_executable_sha256": base.sha256_file(base.MAPDL_EXE), "execution_mode": status["execution_mode"], "analysis_scope": "FULL_BRIDGE_STATIC_LS1_OLD_LOAD_POSITION_BALANCE_AND_LS2_CONSTANT_TOTAL_LOAD_POSITION_MIGRATION", "load_path_mode": "BETA_1_OLD_MCT_LOAD_POSITION_TO_BETA_0_SPATIAL_MASS21_AT_CONSTANT_TOTAL_LOAD", "initial_state_load_path": "MCT_INISTATE_PLUS_FULL_GRAVITY_AT_OLD_BALANCED_POSITION_THEN_CONTINUOUS_POSITION_MIGRATION", "initial_state_equilibrium_audit": "PENDING_FULL_STATIC_SOLUTION_AND_INDEPENDENT_BALANCE_CHECK", "constraint_imposition": "DIRECT_ELIMINATION", "penalty_n_per_mm": None, "adaptive_bisection_must_not_be_stopped_on_first_divergence": bool(adaptive_migration_cutback), "modal_requested": False, "production_claim_allowed": False, "static_result_expected": True, "runtime_equation_count_change_allowed": False, "runtime_small_zero_negative_pivot_allowed": False, "runtime_ignored_or_reset_cnvtol_allowed": False, "launch_argv": launch_argv}  # 汇总输入基准、授权证据、唯一 NSBMX 变化、步长边界、求解器、拓扑、守恒和禁止生产外推边界。
    base.write_json(run_dir / "C10_static_status.json", status)  # 保存根级准备状态供执行器唯一识别。
    base.write_json(run_dir / "manifest.json", manifest)  # 保存完整迁移诊断运行清单。
    k5_field_note = "`mpc184_keyopt5_static=1` 表示只在本次非线性静力诊断中排除 TYPE72 rigid-beam 几何应力刚度；连接运动学、直接消元、初始内力、荷载、0.5% 子步和四项收敛标准均未改变。`prestressed_modal_requires_keyopt5_restore_to_zero=true` 表示即使静力通过也不得直接做模态，必须先在隔离副本中恢复 KEYOPT(5)=0 并通过重启微验证。" if exclude_mpc_stress_stiffness else "`mpc184_keyopt5_static=0` 表示保留 TYPE72 默认几何应力刚度。"  # 解释 JSON 中无注释的静力切线选择及其模态使用边界。
    adaptive_field_note = "`ls2_nsubst=[200,2000,200]` 表示初始和最大迁移增量均为 0.5%，失败时允许自动二分至最小 0.05%；首个 85 MN 残差或 divergence 提示是触发二分的证据，不是控制器停机条件。只有资源硬门、FATAL/ERROR、方程数漂移、small/zero/negative pivot，或 0.05% 最小增量仍失败时才终止。" if adaptive_migration_cutback else "`ls2_nsubst=[200,200,200]` 表示固定 0.5% 且不允许 cutback。"  # 解释自适应步长上下界和控制器不得提前停止的行为合同。
    field_dictionary = f"# 恒总荷载位置迁移机器字段说明\n\nJSON 不允许注释，因此字段语义集中记录于此。`beta=1` 表示完整 ACEL 与空间化质量均已存在，同时施加 `old_FZ + mass*9806` 的零合力修正向量，使二期重力回到原 MCT 初始内力对应的旧节点位置；`beta=0` 表示在完全相同的 15,071 节点集以 replacement 方式显式写入零值，最终只保留真实 MASS21 重力。迁移 include 不执行 `FDELE`，避免求解器把删除节点力解释为阶跃卸载。LS2 使用 `KBC=0` 从 beta=1 连续插值到 beta=0；因为修正向量总和小于 1E-6 N，所以每个插值子步的全桥总竖向荷载保持不变。{k5_field_note} {adaptive_field_note} 力单位 N，长度 mm，质量 tonne，加速度 mm/s²。`STATIC_DIAGNOSTIC_PREPARED` 只表示输入和证据门通过，不表示 MAPDL 已启动或静力已收敛。方程数恒定和无 small/zero/negative pivot 仍是不可删除硬门；`modal_requested=false` 与 `production_claim_allowed=false` 禁止本包产生模态或生产结论。\n"  # 为无注释 JSON 提供 beta、固定节点更新、单位、守恒、K5、步长和停机边界说明。
    (qa_dir / "field_dictionary.md").write_text(field_dictionary, encoding="utf-8", newline="\n")  # 写出伴随字段字典。
    mode_result_line = "- 输入相对默认 K5=0 的固定 0.5% 基准，唯一可执行变化为 `NSUBST,200,200,200 → NSUBST,200,2000,200`；K5=1 同轨失败运行只作为授权证据。\n" if adaptive_migration_cutback else ("- 与默认 K5=0 的 0.5% 发散基准相比，唯一变化是静力阶段 TYPE72 `KEYOPT(5): 0→1`；预应力模态前必须恢复为 0。\n" if exclude_mpc_stress_stiffness else "- TYPE72 保持默认 `KEYOPT(5)=0`。\n")  # 生成人读结果中的输入基准、授权证据和唯一变量说明。
    ls2_result_line = f"- LS2：完整重力不变、beta 从 1 迁移到 0、KBC=0、NSUBST={LS2_INITIAL_SUBSTEPS}/{ls2_max_substeps}/{LS2_MIN_SUBSTEPS}；初始与最大增量 0.5%，最小允许增量 {new_minimum_increment_fraction * 100:.2f}%，最终目标为真实 MASS21 空间位置。\n"  # 生成人读步长三参数、百分比上下界和物理终点说明。
    result_packet = f"# C10 恒总荷载位置迁移诊断准备结果\n\n状态：`STATIC_DIAGNOSTIC_PREPARED`；子类型：`{diagnostic_subtype}`。\n\n- 父连接：5,078 个单层 TYPE72；辅助节点=0、TYPE73=0；微验证 12/12 通过。\n{mode_result_line}- 旧 FZ 节点：{len(old_forces):,}；新 MASS21 节点：{len(masses):,}；非零位置修正节点：{len(corrections):,}。\n- 旧二期节点恒载：{correction_audit['old_fz_sum_n']} N；空间质量重力：{correction_audit['mass_gravity_sum_n']} N。\n- APDL 渲染后修正力合计：{correction_audit['rendered_correction_sum_n']} N，硬门为绝对值不超过 1E-6 N。\n- LS1：完整重力、beta=1、KBC=1、单子步，恢复原 MCT 初态对应的旧荷载位置。\n{ls2_result_line}- 稳定化始终关闭；力、力矩、位移和转角四项 CNVTOL 全部保留；方程数与主元仍是运行时硬门。\n- 当前未启动 MAPDL，没有静力、模态或生产结论。\n"  # 生成便于人工核查的守恒数值、唯一变量、步长边界和两步路径摘要。
    (run_dir / "result_packet.md").write_text(result_packet, encoding="utf-8", newline="\n")  # 写出准备阶段人读结果包。
    artifact_paths = [path for path in run_dir.rglob("*") if path.is_file() and path.name != "artifact_hashes.sha256"]  # 收集除自引用账本外的全部准备工件。
    artifact_lines = [f"{base.sha256_file(path)}  {path.relative_to(run_dir).as_posix()}" for path in sorted(artifact_paths, key=lambda item: item.relative_to(run_dir).as_posix())]  # 生成稳定排序的当前字节摘要行。
    (run_dir / "artifact_hashes.sha256").write_text("\n".join(artifact_lines) + "\n", encoding="utf-8", newline="\n")  # 写出准备阶段完整工件哈希账本。
    print(json.dumps({"run_dir": str(run_dir), "jobname": new_jobname, "status": status["status"], "diagnostic_subtype": diagnostic_subtype, "single_variable_change": single_variable_change, "ls2_nsubst": [LS2_INITIAL_SUBSTEPS, ls2_max_substeps, LS2_MIN_SUBSTEPS], "mpc184_keyopt5_static": 1 if static_k5_excluded else 0, "correction_node_count": len(corrections), "rendered_correction_sum_n": correction_audit["rendered_correction_sum_n"]}, ensure_ascii=False))  # 向调用者返回可解析的唯一目录、作业名、单变量、步长、K5 和守恒摘要。


if __name__ == "__main__":  # 仅在直接执行本文件时进入一次准备流程，导入时不创建目录或启动求解器。
    main()  # 执行冻结源验证、修正向量生成、主控变换和准备工件落盘。
