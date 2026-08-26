"""独立复核 C10 单层 TYPE72 全桥静力诊断并发布不可覆盖的最终工件。"""  # 本模块不启动 MAPDL，不修改求解原件，也不把诊断例外冒充生产结果。

from __future__ import annotations  # 延迟解析类型标注，保持运行时依赖最小且便于静态检查。

import argparse  # 解析唯一允许的 C10_STATIC_DIAGNOSTIC 运行目录参数。
import csv  # 读取 MAPDL 写出的六列 LS1 能量历程 CSV。
import hashlib  # 复算准备输入、原始结果和最终发布工件的 SHA-256。
import json  # 读取运行清单并写出合法机器结论文件。
import math  # 拒绝非有限数并执行独立质量、反力和能量复算。
import os  # 使用硬链接的原子“目标不存在才创建”语义发布最终文本，禁止竞态覆盖。
import re  # 从 MAPDL OUT、拓扑表和静力摘要中提取稳定字段。
import time  # 在最终哈希前执行两秒文件稳定性检查，避免读取仍在增长的 OUT。
from datetime import datetime  # 解析启动时刻并检查二进制结果工件不是运行前遗留文件。
from pathlib import Path  # 安全处理包含中文的项目与运行绝对路径。
from typing import Any  # 标注异构 JSON 对象、解析字段和值数组。

import psutil  # 检查启动器登记的原 PID 是否仍存在，防止求解中途封板。

SCRIPT_PATH = Path(__file__).resolve()  # 固定当前 finalizer 绝对路径供源码哈希与项目定位使用。
PROJECT_ROOT = SCRIPT_PATH.parents[1]  # 取 ultra_tools 的父目录作为本分析包根目录。
RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # 限定所有可验收运行必须位于统一证据目录。
EXPECTED_EQUATION_COUNT = 1234834  # 单层 TYPE72 全桥在直接消元后的批准独立方程总数。
EXPECTED_NODE_COUNT = 109086  # 删除 3,124 个串联辅助节点后的全桥节点总数。
EXPECTED_ELEMENT_COUNT = 178072  # 删除 3,124 个 TYPE73 后的全桥元素总数。
EXPECTED_TYPE_COUNTS = {4: 73692, 6: 48620, 70: 17679, 71: 33003, 72: 5078}  # 冻结 LINK180、梁、质量和单层 MPC184 的运行时类型计数。
EXPECTED_MPC_FIRST_ID = 2017680  # 单层 TYPE72 连接元素的连续编号起点。
EXPECTED_MPC_LAST_ID = 2022757  # 单层 TYPE72 连接元素的连续编号终点。
EXPECTED_MASS_TONNE = 4108.46690758  # 从父 S10 质量台账冻结的全桥总质量，单位 tonne。
GRAVITY_MM_PER_S2 = 9806.0  # 主输入 ACEL 使用的重力加速度绝对值，单位 mm/s²。
MASS_ABSOLUTE_TOLERANCE_TONNE = 1.0e-6  # 静力摘要质量相对冻结台账的绝对误差上限。
VERTICAL_REACTION_RELATIVE_TOLERANCE = 1.0e-4  # 仅对 UZ 支承竖向重力反力闭合的相对误差上限。
LS1_ENERGY_RATIO_LIMIT = 1.0e-2  # LS1 端点和全历程峰值允许的 |STEN/SENE| 上限。
LS2_ENERGY_RATIO_LIMIT = 1.0e-8  # 无物理荷载增量 LS2 允许的 |STEN/SENE| 上限。
LS1_MIN_ACCEPTED_SUBSTEPS = 20  # AUTOTS 合同规定的最少接受子步数。
LS1_MAX_ACCEPTED_SUBSTEPS = 200  # AUTOTS 合同规定的最多接受子步数。
FORMED_STATE_LOAD_PATH_MODE = "FULL_FORMED_STATE_STEP_PAIRED_WITH_INISTATE"  # 标识完整恒载与完整 INISTATE 在 LS1 单一步形成态平衡点直接配对的新诊断路径。
S10_FORCE_SEED_LOAD_PATH_MODE = "FULL_FORMED_STATE_STEP_PAIRED_WITH_S10_LS2_FORCE_SEED"  # 标识把历史 S10 LS2 LINK180 索力作为 corrected-MPC 重平衡诊断种子并采用形成态单步数值合同的路径。
INHERITED_LOAD_PATH_MODE = "INHERITED_FROM_EXECUTED_S10_WITHOUT_PHYSICAL_APPROVAL_CHANGE"  # 标识沿用旧 S10 斜坡加载并允许 AUTOTS 接受 20 至 200 个 LS1 子步的兼容路径。
MIGRATION_LOAD_PATH_MODE = "BETA_1_OLD_MCT_LOAD_POSITION_TO_BETA_0_SPATIAL_MASS21_AT_CONSTANT_TOTAL_LOAD"  # 标识 LS1 恢复旧平衡位置并在 LS2 恒总荷载迁移到空间 MASS21 的路径。
SUPPORTED_LOAD_PATH_MODES = {FORMED_STATE_LOAD_PATH_MODE, S10_FORCE_SEED_LOAD_PATH_MODE, INHERITED_LOAD_PATH_MODE, MIGRATION_LOAD_PATH_MODE}  # 冻结 finalizer 唯一允许的四类载荷路径，禁止未知模式借用任一路径门禁。
FORMED_STATE_INITIAL_AUDIT = "DIAGNOSTIC_PAIRING_TEST_PENDING_FULL_PHYSICAL_RECONCILIATION"  # 标识形成态配对仅完成诊断试验且仍待 MCT 初力与 APDL 初始状态完整物理对账。
S10_FORCE_SEED_INITIAL_AUDIT = "S10_FORCE_SEED_TRANSFER_PENDING_CORRECTED_MPC_REEQUILIBRATION"  # 标识历史 S10 索力种子迁移仍须在 corrected-MPC 拓扑上完成重平衡且没有生产初始状态签认。
INHERITED_INITIAL_AUDIT = "PENDING_MCT_INIFORCE_EQUILIBRIUM_FORCE_RECONCILIATION"  # 标识旧继承路径仍待 MCT INIFORCE/EQUI-MFORCE 与 APDL INISTATE 平衡复核。
MIGRATION_INITIAL_AUDIT = "PENDING_FULL_STATIC_SOLUTION_AND_INDEPENDENT_BALANCE_CHECK"  # 标识恒总荷载位置迁移仍须以完整静力端点和独立平衡复核闭合。
S10_FORCE_SEED_INITIAL_STATE_LOAD_PATH = "S10_LS2_LINK180_FORCE_SEED_PLUS_FULL_PERMANENT_LOAD_SINGLE_STEP"  # 冻结 seed manifest 对初始状态与完整恒载单步配对关系的独立语义字段。
MIGRATION_INITIAL_STATE_LOAD_PATH = "MCT_INISTATE_PLUS_FULL_GRAVITY_AT_OLD_BALANCED_POSITION_THEN_CONTINUOUS_POSITION_MIGRATION"  # 冻结迁移清单对初始状态、完整重力和位置变化顺序的唯一语义。
EXPECTED_INITIAL_STATE_LOAD_PATH_BY_MODE = {FORMED_STATE_LOAD_PATH_MODE: FORMED_STATE_LOAD_PATH_MODE, S10_FORCE_SEED_LOAD_PATH_MODE: S10_FORCE_SEED_INITIAL_STATE_LOAD_PATH, INHERITED_LOAD_PATH_MODE: INHERITED_LOAD_PATH_MODE, MIGRATION_LOAD_PATH_MODE: MIGRATION_INITIAL_STATE_LOAD_PATH}  # 为四类 load_path_mode 指定唯一允许的 initial_state_load_path，防止两个身份字段分叉。
EXPECTED_INITIAL_STATE_AUDIT_BY_MODE = {FORMED_STATE_LOAD_PATH_MODE: FORMED_STATE_INITIAL_AUDIT, S10_FORCE_SEED_LOAD_PATH_MODE: S10_FORCE_SEED_INITIAL_AUDIT, INHERITED_LOAD_PATH_MODE: INHERITED_INITIAL_AUDIT, MIGRATION_LOAD_PATH_MODE: MIGRATION_INITIAL_AUDIT}  # 为四类路径指定唯一未闭合物理审计状态，禁止互相借用审计措辞。
ADAPTIVE_MIGRATION_DIAGNOSTIC_SUBTYPE = "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_ADAPTIVE_CUTBACK_TO_0_05_PERCENT"  # 冻结本 finalizer 允许验收的唯一恒总荷载迁移子类型。
S10_FORCE_SEED_DIAGNOSTIC_SUBTYPE = "S10_LS2_FORCE_SEED_CORRECTED_MPC_REEQUILIBRATION"  # 冻结 seed 运行必须声明的 corrected-MPC 重平衡诊断子类型。
S10_FORCE_SEED_INCLUDE_RELATIVE = "solver/apply_s10_ls2_force_seed_override_link180.inp"  # 冻结历史 S10 索力种子覆盖 include 在运行目录内的唯一相对路径。
S10_FORCE_SEED_AUDIT_RELATIVE = "qa/s10_force_seed_audit.json"  # 冻结 seed 元素覆盖、正索力和来源摘要预检工件的唯一相对路径。
NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"  # 覆盖 MAPDL 整数、小数和科学计数法的有限数词法。
ERROR_COUNT_PATTERN = re.compile(r"NUMBER OF ERROR\s+MESSAGES ENCOUNTERED\s*=\s*(\d+)", re.IGNORECASE)  # 提取 MAPDL 页尾累计错误数。
WARNING_COUNT_PATTERN = re.compile(r"NUMBER OF WARNING\s+MESSAGES ENCOUNTERED\s*=\s*(\d+)", re.IGNORECASE)  # 提取 MAPDL 页尾累计警告数。
EQUATION_COUNT_PATTERN = re.compile(r"NUMBER OF EQUATIONS\s*=\s*(\d+)", re.IGNORECASE)  # 提取每次直接求解器组装报告的方程数。
MINIMUM_PIVOT_PATTERN = re.compile(rf"Sparse solver minimum pivot\s*=\s*({NUMBER_PATTERN})", re.IGNORECASE)  # 提取每次分解的有符号最小主元。
ERR_WARNING_PATTERN = re.compile(r"\*\*\* WARNING \*\*\*", re.IGNORECASE)  # 统计独立 ERR 文件中的原生警告块数量。
COEFFICIENT_RATIO_WARNING = "COEFFICIENT RATIO EXCEEDS 1.0E8 - CHECK RESULTS."  # 标识刚度尺度跨越八个数量级的求解器病态性警告。
MOMENT_REFERENCE_WARNING = "A REFERENCE MOMENT VALUE TIMES THE TOLERANCE IS USED"  # 标识力矩收敛参考值被内部阈值接管的诊断限定警告。
CNVTOL_F_DEFAULT_WARNING = "DEFAULT VALUE OF 1.0 FOR CONVERGENCE ON F"  # 标识 F 收敛 MINREF 使用 MAPDL 默认 1 N 的警告。
CNVTOL_M_DEFAULT_WARNING = "DEFAULT VALUE OF 1.0 FOR CONVERGENCE ON M"  # 标识 M 收敛 MINREF 使用 MAPDL 默认 1 N·mm 的警告。


def require(condition: bool, message: str) -> None:  # 接收必须成立的条件和失败说明；失败时终止且无返回值。
    if not condition:  # 仅在谱系、完成性、数值或工件门禁失败时进入拒绝路径。
        raise RuntimeError(message)  # 抛出明确原因，防止发布虚假的静力通过结论。


def resolve_load_path_contract(manifest: dict[str, Any]) -> dict[str, Any]:  # 接收 manifest 并返回已通过精确身份、初态路径和审计措辞门禁的载荷路径合同。
    declared_load_path_mode = manifest.get("load_path_mode")  # 读取新版清单显式冻结的模式；旧清单缺字段时仅允许由历史 initial_state_load_path 恢复兼容模式。
    load_path_mode = str(declared_load_path_mode if declared_load_path_mode is not None else manifest.get("initial_state_load_path", ""))  # 形成待核对的唯一模式字符串且不对未知值做模糊归类。
    require(load_path_mode in SUPPORTED_LOAD_PATH_MODES, f"运行清单载荷路径模式不受支持：{load_path_mode}")  # 未知模式不得套用形成态单步、seed 单步或继承 AUTOTS 的任何验收条件。
    expected_initial_state_load_path = EXPECTED_INITIAL_STATE_LOAD_PATH_BY_MODE[load_path_mode]  # 从冻结映射取得当前模式唯一允许的初始状态路径语义。
    require(manifest.get("initial_state_load_path") == expected_initial_state_load_path, "运行清单的 initial_state_load_path 与 load_path_mode 精确合同不一致")  # seed 模式允许独立语义值但禁止任意别名，旧模式仍保持原字段兼容。
    expected_initial_state_audit = EXPECTED_INITIAL_STATE_AUDIT_BY_MODE[load_path_mode]  # 从冻结映射取得当前模式唯一允许的未闭合物理审计状态。
    require(manifest.get("initial_state_equilibrium_audit") == expected_initial_state_audit, "运行清单的初始状态审计字段与载荷路径模式不一致")  # 禁止普通 INISTATE、历史 seed 与继承路径互相借用审计措辞。
    s10_force_seed_mode = load_path_mode == S10_FORCE_SEED_LOAD_PATH_MODE  # 标识是否必须执行历史 S10 legacy-CERIG 索力种子的专用谱系和生产禁用门。
    single_step_load_path_mode = load_path_mode in {FORMED_STATE_LOAD_PATH_MODE, S10_FORCE_SEED_LOAD_PATH_MODE, MIGRATION_LOAD_PATH_MODE}  # 普通形成态、seed 和迁移路径共享 LS1 单子步及最终两结果集合同。
    migration_load_path_mode = load_path_mode == MIGRATION_LOAD_PATH_MODE  # 标识是否需要执行输入基准、授权证据、NSBMX 和 beta 端点专用门禁。
    ls1_accepted_substep_minimum = 1 if single_step_load_path_mode else LS1_MIN_ACCEPTED_SUBSTEPS  # 两类形成态固定最少一个接受子步，旧继承模式保留最少二十个。
    ls1_accepted_substep_maximum = 1 if single_step_load_path_mode else LS1_MAX_ACCEPTED_SUBSTEPS  # 两类形成态固定最多一个接受子步，旧继承模式保留最多二百个。
    fixed_static_result_set_count = 2 if single_step_load_path_mode else None  # 两类形成态固定 LS1+LS2 恰两结果集，旧继承模式由实际 LS1 历程数动态确定。
    return {"mode": load_path_mode, "expected_initial_state_load_path": expected_initial_state_load_path, "expected_initial_state_audit": expected_initial_state_audit, "s10_force_seed_mode": s10_force_seed_mode, "migration_load_path_mode": migration_load_path_mode, "single_step_load_path_mode": single_step_load_path_mode, "ls1_accepted_substep_minimum": ls1_accepted_substep_minimum, "ls1_accepted_substep_maximum": ls1_accepted_substep_maximum, "fixed_static_result_set_count": fixed_static_result_set_count}  # 返回后续数值门与报告门共同使用的不可歧义合同对象。


def sha256_file(path: Path) -> str:  # 接收普通文件路径并返回完整二进制内容的六十四位小写 SHA-256。
    digest = hashlib.sha256()  # 为当前文件创建独立摘要累加器。
    with path.open("rb") as handle:  # 使用二进制只读模式避免编码和换行变换。
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):  # 以一 MiB 数据块读取直到文件末尾。
            digest.update(chunk)  # 把当前原始字节块加入摘要计算。
    return digest.hexdigest()  # 返回固定长度的最终摘要字符串。


def read_json(path: Path) -> dict[str, Any]:  # 接收 UTF-8 JSON 路径并返回已验证为对象的顶层字典。
    require(path.is_file(), f"缺少 JSON 工件：{path}")  # 在解析前拒绝缺失路径。
    payload = json.loads(path.read_text(encoding="utf-8"))  # 按 UTF-8 解析完整 JSON 文档。
    require(isinstance(payload, dict), f"JSON 顶层不是对象：{path}")  # 禁止数组或标量冒充清单。
    return payload  # 返回已通过结构门的异构字典。


def write_new_text(path: Path, value: str) -> None:  # 接收目标路径和文本并执行 UTF-8、LF、不可覆盖写入。
    require(not path.exists(), f"拒绝覆盖既有最终工件：{path}")  # 一次封板后必须创建新运行，禁止静默改写。
    with path.open("x", encoding="utf-8", newline="\n") as handle:  # 使用 x 模式获得操作系统级不可覆盖保证。
        handle.write(value)  # 写入已经在内存完成验证的最终文本。


def write_new_json(path: Path, payload: dict[str, Any]) -> None:  # 接收目标路径和对象字典并写出合法稳定 JSON。
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 保留中文、两空格缩进、禁止 NaN/Infinity 并固定末尾换行。
    write_new_text(path, rendered)  # 复用不可覆盖的 UTF-8 写入路径。


def write_new_batch(payloads: dict[Path, str]) -> None:  # 接收多个最终路径与已渲染文本并通过预检、暂存和原子替换发布。
    require(bool(payloads), "批量发布列表为空")  # 禁止空发布被误认为最终化成功。
    staging_paths = {path: path.with_name(f"{path.name}.codex_staging") for path in payloads}  # 为每个目标构造同目录暂存名以保证替换发生在同一文件系统。
    published_identities: dict[Path, tuple[int, int, int]] = {}  # 记录本调用已创建目标的卷号、文件 ID 和大小，异常回滚前防止误删竞态替换文件。
    for target_path, staging_path in staging_paths.items():  # 在产生任何新文件前统一关闭全部路径门。
        require(target_path.parent.is_dir(), f"最终工件父目录不存在：{target_path.parent}")  # 禁止隐式创建错误目录层级。
        require(not target_path.exists(), f"拒绝覆盖既有最终工件：{target_path}")  # 保持每次 run 的不可覆盖发布合同。
        require(not staging_path.exists(), f"发现遗留暂存工件，拒绝继续：{staging_path}")  # 防止上次异常内容混入本次发布。
    try:  # 暂存或发布异常时仅清理本调用创建且仍位于暂存命名空间的文件。
        for target_path, value in payloads.items():  # 先把全部已完成序列化的内容写入同目录暂存文件。
            staging_path = staging_paths[target_path]  # 读取当前目标对应的唯一暂存路径。
            with staging_path.open("x", encoding="utf-8", newline="\n") as handle:  # 使用不可覆盖模式写 UTF-8/LF 暂存字节。
                handle.write(value)  # 写入内存中已完成验证和渲染的完整工件。
        for target_path, staging_path in staging_paths.items():  # 全部暂存成功后按调用顺序发布，最终状态由调用者安排在最后。
            os.link(staging_path, target_path)  # 在同卷以硬链接原子创建目标；目标若竞态出现则失败且绝不覆盖。
            published_stat = target_path.stat()  # 在删除暂存名之前取得本调用新建目标的数据对象身份。
            published_identities[target_path] = (int(published_stat.st_dev), int(published_stat.st_ino), int(published_stat.st_size))  # 保存精确卷、文件 ID 和大小供异常回滚安全核验。
            staging_path.unlink()  # 目标创建成功后删除仅属于本调用的暂存名称，保留同一数据对象的最终名称。
    except Exception:  # 捕获任意 I/O 异常，清理未发布暂存并回滚本调用已发布且身份未变化的目标。
        for staging_path in staging_paths.values():  # 仅枚举本批次命名规则下尚未发布的暂存路径。
            if staging_path.exists():  # 已原子发布的暂存路径自然不存在，不触碰最终文件。
                staging_path.unlink()  # 删除本次未发布暂存碎片，使失败状态清晰且可人工审计。
        for target_path, expected_identity in reversed(list(published_identities.items())):  # 按发布逆序回滚本调用已创建目标，尽量恢复调用前无最终工件状态。
            if target_path.is_file():  # 只有目标仍为普通文件时才读取并比较数据对象身份。
                current_stat = target_path.stat()  # 取得当前卷、文件 ID 和大小以防其他进程已替换同名路径。
                current_identity = (int(current_stat.st_dev), int(current_stat.st_ino), int(current_stat.st_size))  # 构造与发布时相同格式的身份三元组。
                if current_identity == expected_identity:  # 仅当同名路径仍指向本调用创建的同一数据对象时允许回滚删除。
                    target_path.unlink()  # 删除本调用的部分发布目标，避免异常后留下可被误读的半套结果。
        raise  # 重新抛出原异常，禁止把部分发布冒充成功。


def parse_hash_ledger(path: Path, root: Path) -> dict[str, str]:  # 接收 SHA-256 账本及其路径根并返回相对路径到摘要的唯一映射。
    require(path.is_file(), f"缺少哈希账本：{path}")  # 在解析前拒绝缺失的准备态或父运行账本。
    entries: dict[str, str] = {}  # 初始化去重后的相对路径摘要映射。
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():  # 逐行读取固定为 UTF-8 的六十四位摘要账本。
        stripped = line.strip()  # 去除行首尾空白并保留路径内部空格。
        require(bool(stripped), f"哈希账本含空行：{path}")  # 空行会破坏条目数和路径追溯，故直接拒绝。
        parts = stripped.split(maxsplit=1)  # 仅在首段空白处分离摘要与相对路径。
        require(len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]) is not None, f"哈希账本行格式无效：{line}")  # 固定摘要词法并要求路径存在。
        relative_text = parts[1].strip()  # 先提取 sha256sum 文本或二进制模式下的原始路径字段。
        if relative_text.startswith("*"):  # GNU sha256sum 用前导星号标识二进制读取模式而非文件名字符。
            relative_text = relative_text[1:]  # 去掉模式标记以恢复真实相对路径。
        relative_text = relative_text.replace("\\", "/")  # 把账本路径统一为正斜杠形式便于跨平台比较。
        require(relative_text not in entries, f"哈希账本重复路径：{relative_text}")  # 禁止同一工件由不同摘要歧义覆盖。
        resolved_path = (root / Path(relative_text)).resolve()  # 将相对路径投影到指定运行根的规范绝对路径。
        require(resolved_path.is_relative_to(root.resolve()), f"哈希账本路径越界：{relative_text}")  # 防止父段或绝对路径越出运行证据范围。
        entries[relative_text] = parts[0]  # 保存当前唯一相对路径与批准摘要。
    return entries  # 返回可供逐项复算的完整账本映射。


def verify_hash_ledger(path: Path, root: Path) -> dict[str, str]:  # 接收准备态账本与运行根并返回全部通过复算的条目。
    entries = parse_hash_ledger(path, root)  # 先解析格式、唯一性和路径边界。
    for relative_text, expected_hash in entries.items():  # 逐项核对准备时冻结的每个文件原始字节。
        artifact_path = (root / Path(relative_text)).resolve()  # 恢复当前条目的规范绝对文件路径。
        require(artifact_path.is_file(), f"准备态账本工件缺失：{artifact_path}")  # 任何输入或准备 QA 丢失都中断谱系。
        require(sha256_file(artifact_path) == expected_hash, f"准备态账本工件哈希漂移：{artifact_path}")  # 禁止求解期间或之后修改被冻结输入。
    return entries  # 返回已逐项通过哈希复算的准备态映射。


def argument_value(arguments: list[str], flag: str) -> str:  # 接收启动参数数组和标志并返回其唯一后继值。
    indices = [index for index, value in enumerate(arguments) if value.lower() == flag.lower()]  # 查找忽略大小写后的全部标志位置。
    require(len(indices) == 1, f"启动参数 {flag} 出现 {len(indices)} 次，预期 1")  # 重复或缺失标志都可能造成实际路径歧义。
    index = indices[0]  # 读取已经确认唯一的标志下标。
    require(index + 1 < len(arguments), f"启动参数 {flag} 缺少后继值")  # 防止越界或空值配置。
    return arguments[index + 1]  # 返回求解器实际采用的相邻参数值。


def process_identity_is_alive(identity: dict[str, Any]) -> bool:  # 接收冻结 PID、创建时刻、二进制和命令行对象并返回同一进程是否仍存活。
    try:  # 目标进程可能已自然退出、拒绝访问或 PID 已被系统回收给其他程序。
        process = psutil.Process(int(identity["pid"]))  # 按冻结 PID 获取当前进程对象，但不单凭 PID 作结论。
        if abs(float(process.create_time()) - float(identity["create_time_epoch_seconds"])) > 0.001:  # 创建时刻变化证明 PID 已被复用。
            return False  # 不把无关复用进程误判为仍在求解。
        if str(Path(process.exe()).resolve()).casefold() != str(Path(str(identity["executable"])).resolve()).casefold():  # 二进制路径变化证明不是原包装器。
            return False  # 返回原求解进程已不存活语义，同时后续仍独立扫描本 job 子进程。
        if [str(value) for value in process.cmdline()] != [str(value) for value in identity["command_line"]]:  # 命令行数组变化表示身份不闭合或 PID复用。
            return False  # 拒绝仅凭相同 PID/名称阻断封板。
        return True  # 四项身份均一致时确认原启动根仍存活。
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, KeyError, TypeError, ValueError, OSError, RuntimeError):  # 进程消失、字段破损或路径异常均无法证明同一根存活。
        return False  # 返回未确认存活；启动链字段完整性由调用处另行强制验证。


def resolve_run(run_dir: Path) -> Path:  # 接收用户给定运行目录并返回位于 ultra_runs 下的规范绝对路径。
    resolved = run_dir.resolve()  # 消除相对段并获得稳定绝对路径。
    require(resolved.is_dir(), f"静力诊断运行目录不存在：{resolved}")  # 拒绝缺失或普通文件路径。
    require(resolved.parent == RUNS_ROOT.resolve(), f"运行目录越出 ultra_runs：{resolved}")  # 限定唯一允许的证据根目录。
    require(resolved.name.startswith(("C10_STATIC_DIAGNOSTIC_", "C10_LOAD_MIGRATION_DIAGNOSTIC_")), f"运行目录不属于批准的 C10 静力或迁移诊断族：{resolved.name}")  # 阻断其他模型线且允许专用迁移验收。
    return resolved  # 返回已通过边界与运行族检查的目录。


def scalar(text_value: str, label: str) -> float:  # 接收机器摘要文本和唯一标签并返回有限浮点数。
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(label)}\s*=\s*({NUMBER_PATTERN})", re.IGNORECASE)  # 以标识符左边界限定标签，避免 EXPECTED 误命中 RF_EXPECTED 等较长字段。
    matches = pattern.findall(text_value)  # 收集全部匹配以拒绝缺失或歧义字段。
    require(len(matches) == 1, f"字段 {label} 匹配数为 {len(matches)}，预期 1")  # 每个摘要字段只能出现一次。
    value = float(matches[0])  # 把 MAPDL 数词转换为 Python 双精度浮点数。
    require(math.isfinite(value), f"字段 {label} 不是有限数")  # 禁止 NaN 或无穷进入验收。
    return value  # 返回已验证的有限标量。


def parse_topology(text_value: str) -> dict[str, int]:  # 接收拓扑输出文本并返回节点、元素和五类元素整数计数。
    values = {"nodes": int(round(scalar(text_value, "NODE_COUNT"))), "elements": int(round(scalar(text_value, "ELEMENT_COUNT")))}  # 提取并四舍五入 MAPDL 以浮点格式输出的总计数。
    for type_id in EXPECTED_TYPE_COUNTS:  # 按冻结类型集合逐项提取运行时数量。
        values[f"TYPE{type_id}"] = int(round(scalar(text_value, f"TYPE{type_id}")))  # 保存当前类型的整数计数。
    return values  # 返回可直接写入 JSON 的运行时拓扑对象。


def parse_mpc_rows(path: Path) -> list[tuple[int, int, int, int]]:  # 接收 ELLIST 文本并返回元素 ID、类型 ID、I 节点和 J 节点四元组列表。
    rows: list[tuple[int, int, int, int]] = []  # 初始化仅包含真实两节点 MPC184 数据行的解析列表。
    line_pattern = re.compile(r"^\s*(\d+)\s+\d+\s+(\d+)\s+\d+\s+\d+\s+\d+\s+(\d+)\s+(\d+)\s*$")  # 匹配 ELEM、TYP 及末两列节点号并排除标题与截断行。
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():  # 逐行读取 MAPDL 列表并容忍本地标题字符替换。
        match = line_pattern.match(line)  # 尝试把当前行识别为数值元素记录。
        if match is not None:  # 只有真实数据行进入结果列表。
            rows.append((int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))))  # 保存元素号、TYPE 和有向主从节点供逐条映射门禁。
    return rows  # 返回已过滤标题、空行和选择说明的两节点元素记录。


def parse_expected_mpc_mapping(path: Path) -> tuple[list[tuple[int, int, int]], dict[str, int]]:  # 接收父运行连接映射 CSV 并返回刚臂三元组及两类批准语义计数。
    rows: list[tuple[int, int, int]] = []  # 初始化保持父工程连接顺序的期望映射。
    implementation_counts = {"MPC184_TYPE72_DIRECT_ELIMINATION_RIGID_BEAM": 0, "MPC184_TYPE72_DIRECT_ELIMINATION_PROJECTED_TO_TRANSLATION_ONLY_SLAVE": 0}  # 冻结 ALL 与 UXYZ 投影两类唯一合法实现名称及初始计数。
    with path.open("r", encoding="utf-8-sig", newline="") as handle:  # 以 UTF-8/BOM 兼容方式只读父连接证据表。
        reader = csv.DictReader(handle)  # 根据表头按工程字段名解析，避免依赖列位置。
        required_columns = {"rigid_element", "master_node", "slave_node", "implementation"}  # 冻结逐条连接验证所需的最小字段集合。
        require(reader.fieldnames is not None and required_columns.issubset(set(reader.fieldnames)), f"父连接映射缺少字段：{path}")  # 拒绝旧版或破损表结构。
        for raw_row in reader:  # 按父映射记录顺序遍历全部工程连接。
            implementation = str(raw_row["implementation"]).strip()  # 读取本条连接的批准实现类型。
            require(implementation in implementation_counts, f"父连接实现不是两类精确批准的 TYPE72 直接消元：{implementation}")  # 禁止未知后缀、TYPE73、罚函数或其他实现伪装混入。
            implementation_counts[implementation] += 1  # 累计当前精确实现类别供 1,954/3,124 语义计数闭合。
            rows.append((int(str(raw_row["rigid_element"]).strip()), int(str(raw_row["master_node"]).strip()), int(str(raw_row["slave_node"]).strip())))  # 保存可与运行时 ELLIST 一一比较的整数三元组。
    require(implementation_counts == {"MPC184_TYPE72_DIRECT_ELIMINATION_RIGID_BEAM": 1954, "MPC184_TYPE72_DIRECT_ELIMINATION_PROJECTED_TO_TRANSLATION_ONLY_SLAVE": 3124}, f"父连接语义计数不等于批准的 1954/3124：{implementation_counts}")  # 关闭 ALL 与 UXYZ 投影数量门。
    return rows, implementation_counts  # 返回完整、有序且实现类型与计数已验证的父连接映射证据。


def parse_expected_mpc_input(path: Path) -> list[tuple[int, int, int]]:  # 接收子运行哈希冻结的 TYPE72 include 并返回 EN 元素、I 节点、J 节点三元组。
    rows: list[tuple[int, int, int]] = []  # 初始化保持实际 APDL 建模顺序的有向连接列表。
    pattern = re.compile(r"^\s*EN\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:!.*)?$", re.IGNORECASE)  # 识别本 include 中显式编号的两节点 EN 命令。
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():  # 逐行读取已受子准备账本保护的实际执行输入。
        match = pattern.match(line)  # 尝试把当前行识别为 TYPE72 连接元素生成命令。
        if match is not None:  # 只有完整 EN 三整数记录进入期望运行时映射。
            rows.append((int(match.group(1)), int(match.group(2)), int(match.group(3))))  # 保存元素 ID 及有向主从节点。
    return rows  # 返回可直接与 ELLIST 和父工程映射双重交叉核对的子输入记录。


def parse_expected_cp_input(path: Path) -> list[tuple[int, str, tuple[int, ...]]]:  # 接收冻结 APDL include 并返回 CP 集号、方向和有序节点元组。
    rows: list[tuple[int, str, tuple[int, ...]]] = []  # 初始化保持 APDL 命令顺序的期望 CP 列表。
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():  # 逐行读取已通过准备账本哈希门的源输入。
        if re.match(r"^\s*CP\s*,", line, re.IGNORECASE) is None:  # 只处理真实 CP 命令并忽略注释与其他 APDL 行。
            continue  # 非 CP 行不影响运行时耦合自由度合同。
        fields = [field.strip() for field in line.split(",")]  # 按 APDL 逗号字段拆分集合号、方向和节点序列。
        require(len(fields) >= 5, f"冻结 CP 命令字段不足：{line}")  # 每组至少需要命令、集合号、方向和两个节点。
        rows.append((int(fields[1]), fields[2].upper(), tuple(int(value) for value in fields[3:])))  # 保存可与 CPLIST 输出逐项比较的规范整数记录。
    return rows  # 返回冻结输入定义的全部 CP 集合。


def parse_runtime_cp(path: Path) -> list[tuple[int, str, tuple[int, ...]]]:  # 接收 CPLIST 文本并返回已执行 CP 集号、方向和有序节点元组。
    rows: list[tuple[int, str, tuple[int, ...]]] = []  # 初始化运行时 CP 记录列表。
    current_set: int | None = None  # 保存当前标题声明的 CP 集合号；尚未进入集合时为 None。
    current_direction = ""  # 保存当前 CP 自由度方向；尚未进入集合时为空。
    expected_node_count = 0  # 保存当前标题声明的节点数，用于截断分页标题中的其他数字。
    collected_nodes: list[int] = []  # 累积当前集合跨多行输出的节点号。
    collecting_nodes = False  # 标识是否已经读到当前集合的 NODES= 起始行。
    header_pattern = re.compile(r"COUPLED SET=\s*(\d+)\s+DIRECTION=\s*([A-Z]+)\s+TOTAL NODES=\s*(\d+)", re.IGNORECASE)  # 识别每组 CPLIST 标题。
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():  # 按原始页序遍历 CPLIST 输出。
        header = header_pattern.search(line)  # 尝试识别新 CP 集合标题。
        if header is not None:  # 新标题出现时初始化对应集合的解析状态。
            require(current_set is None or len(collected_nodes) == expected_node_count, f"CP 集 {current_set} 节点列表不完整")  # 前一集合必须在分页前已收齐声明节点数。
            current_set = int(header.group(1))  # 读取运行时集合号。
            current_direction = header.group(2).upper()  # 读取并规范化运行时自由度方向。
            expected_node_count = int(header.group(3))  # 读取标题声明的节点总数。
            collected_nodes = []  # 为新集合清空节点累积器。
            collecting_nodes = False  # 等待后续 NODES= 行后再采集数字。
            continue  # 当前标题行不含成员节点，转入下一行。
        if current_set is None:  # 尚未遇到任何集合标题时忽略页眉和空行。
            continue  # 页眉不属于运行时 CP 数据。
        if "NODES=" in line.upper():  # NODES= 标志开启当前集合成员采集。
            collecting_nodes = True  # 后续续行也继续提取节点号直至达到声明数量。
            line = line.split("=", maxsplit=1)[1]  # 去掉 NODES= 标签，避免标签文本干扰整数解析。
        if collecting_nodes and len(collected_nodes) < expected_node_count:  # 仅在成员区且尚未收齐时读取当前行整数。
            collected_nodes.extend(int(value) for value in re.findall(r"\d+", line))  # 追加本行所有非负节点号。
            require(len(collected_nodes) <= expected_node_count, f"CP 集 {current_set} 实际节点超过标题数量")  # 防止分页或格式漂移污染节点序列。
            if len(collected_nodes) == expected_node_count:  # 收齐当前集合全部成员时立即封装记录。
                rows.append((current_set, current_direction, tuple(collected_nodes)))  # 保存有序集合供冻结输入逐项比较。
                collecting_nodes = False  # 停止采集以忽略后续页眉数字。
    require(current_set is None or len(collected_nodes) == expected_node_count, f"最后 CP 集 {current_set} 节点列表不完整")  # 文件结束时关闭最后集合完整性门。
    return rows  # 返回已剔除页眉且节点数闭合的运行时 CP 列表。


def parse_expected_d_inputs(paths: list[Path]) -> list[tuple[int, str, float]]:  # 接收冻结边界 include 列表并返回唯一节点、方向和值记录。
    rows: list[tuple[int, str, float]] = []  # 初始化保持 include 和命令顺序的期望 D 记录。
    pattern = re.compile(rf"^\s*D\s*,\s*(\d+)\s*,\s*([A-Z]+)\s*,\s*({NUMBER_PATTERN})\s*(?:!.*)?$", re.IGNORECASE)  # 识别本项目显式单节点单自由度 D 命令。
    for path in paths:  # 按主输入实际 include 顺序遍历三个边界来源。
        for line in path.read_text(encoding="utf-8", errors="strict").splitlines():  # 逐行解析准备账本已冻结的 APDL 源字节。
            match = pattern.match(line)  # 尝试把当前行识别为受支持的显式 D 记录。
            if match is not None:  # 只有真实 D 命令进入期望边界集合。
                rows.append((int(match.group(1)), match.group(2).upper(), float(match.group(3))))  # 保存节点、方向和值供运行时逐项比对。
    require(len(rows) == len(set(rows)), "冻结边界输入含重复的节点、方向和值 D 命令")  # 禁止重复输入被 DLIST 去重后掩盖。
    return rows  # 返回冻结输入定义的全部显式位移约束。


def parse_runtime_d(path: Path) -> list[tuple[int, str, float]]:  # 接收 DLIST 文本并返回已执行节点、方向和实部值记录。
    rows: list[tuple[int, str, float]] = []  # 初始化运行时位移约束列表。
    pattern = re.compile(rf"^\s*(\d+)\s+([A-Z]+)\s+({NUMBER_PATTERN})\s+({NUMBER_PATTERN})\s*$", re.IGNORECASE)  # 识别 NODE、LABEL、REAL、IMAG 四列数据行。
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():  # 逐行读取 DLIST 并忽略标题与空行。
        match = pattern.match(line)  # 尝试解析当前数据行。
        if match is not None:  # 只有完整四列记录进入边界结果。
            imaginary_value = float(match.group(4))  # 读取复数约束的虚部以阻断意外谐响应数据。
            require(math.isclose(imaginary_value, 0.0, rel_tol=0.0, abs_tol=0.0), f"运行时 D 约束含非零虚部：{line}")  # 本静力模型只允许实值约束。
            rows.append((int(match.group(1)), match.group(2).upper(), float(match.group(3))))  # 保存运行时节点、方向和实部值。
    return rows  # 返回已过滤页眉的完整运行时 D 列表。


def parse_history(path: Path) -> list[list[float]]:  # 接收六列无表头 CSV 并返回有限浮点行数组。
    rows: list[list[float]] = []  # 初始化 LS1 已接受结果集列表。
    with path.open("r", encoding="utf-8", newline="") as handle:  # 使用标准 CSV 只读模式避免手工逗号解析歧义。
        for raw_row in csv.reader(handle):  # 按文件顺序遍历每个 MAPDL *VWRITE 数据行。
            require(len(raw_row) == 6, f"LS1 能量历程列数不是 6：{raw_row}")  # 固定 LSTP、SBST、TIME、SENE、STEN、RATIO 六列合同。
            values = [float(cell.strip()) for cell in raw_row]  # 去除对齐空格并转换六个数值。
            require(all(math.isfinite(value) for value in values), f"LS1 能量历程含非有限数：{raw_row}")  # 禁止异常值进入峰值与单调性计算。
            rows.append(values)  # 保存当前已接受静力结果集。
    return rows  # 返回保持求解结果顺序的六列数组。


def parse_mntr_rows(path: Path) -> list[dict[str, float | int]]:  # 接收 MAPDL MNTR 路径并返回每个已接受子步的载荷步、子步、尝试、迭代、增量和累计时间。
    rows: list[dict[str, float | int]] = []  # 初始化保持原生监控文件顺序的已接受子步记录。
    row_pattern = re.compile(rf"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+({NUMBER_PATTERN})\s+({NUMBER_PATTERN})(?:\s+|$)", re.IGNORECASE)  # 匹配五个整数控制列和 INCREMENT/TOTAL 两个浮点列，忽略后续用户监控变量。
    for line in path.read_text(encoding="latin-1", errors="strict").splitlines():  # Latin-1 一一映射全部原始字节并逐行扫描，避免本地页眉解码失败。
        match = row_pattern.match(line)  # 尝试把当前行识别为 MNTR 数值数据行而非标题或空白。
        if match is not None:  # 只有完整七字段前缀的真实已接受子步进入结果。
            row = {"load_step": int(match.group(1)), "substep": int(match.group(2)), "attempt": int(match.group(3)), "iterations": int(match.group(4)), "total_iterations": int(match.group(5)), "increment": float(match.group(6)), "total_time": float(match.group(7))}  # 转换控制列为整数、时间列为双精度数。
            require(all(math.isfinite(float(value)) for value in row.values()), f"MNTR 数据行含非有限数：{line}")  # 禁止 NaN/无穷或破损数词进入步长门。
            rows.append(row)  # 保存当前已接受子步及其尝试和时间路径。
    return rows  # 返回可与 OUT 完成子步和 NSUBST 边界交叉核对的有序记录。


def classify_warning_blocks(text_value: str) -> list[dict[str, str]]:  # 接收完整 ERR 文本并返回逐警告块的唯一类别、摘要和规范文本摘录。
    raw_blocks = re.split(r"\*\*\* WARNING \*\*\*", text_value, flags=re.IGNORECASE)[1:]  # 按每个原生警告标题切分并丢弃标题前的版本说明。
    classifications: list[dict[str, str]] = []  # 初始化保持 ERR 顺序的警告分类证据。
    category_phrases = {"COEFFICIENT_RATIO_GT_1E8": COEFFICIENT_RATIO_WARNING, "MOMENT_REFERENCE_INTERNAL_THRESHOLD": MOMENT_REFERENCE_WARNING, "CNVTOL_F_DEFAULT_MINREF_1": CNVTOL_F_DEFAULT_WARNING, "CNVTOL_M_DEFAULT_MINREF_1": CNVTOL_M_DEFAULT_WARNING}  # 定义本诊断允许披露但禁止生产签认的四类唯一短语。
    for raw_block in raw_blocks:  # 逐块独立分类以防一个块双命中同时掩盖另一个未知块。
        normalized_block = " ".join(raw_block.upper().split())  # 把 MAPDL 自动换行和多空格压缩为单空格后再匹配。
        matches = [category for category, phrase in category_phrases.items() if phrase in normalized_block]  # 收集当前块命中的全部批准类别。
        category = matches[0] if len(matches) == 1 else ("UNCLASSIFIED" if len(matches) == 0 else "AMBIGUOUS")  # 仅唯一命中获得批准类别，缺失或多重命中均保留拒绝标签。
        block_hash = hashlib.sha256(raw_block.encode("utf-8", errors="replace")).hexdigest()  # 为完整原始警告块生成不可混淆摘要而不在 JSON 复制冗长文本。
        classifications.append({"category": category, "sha256": block_hash, "normalized_excerpt": normalized_block[:320]})  # 保存类别、原文摘要及最多 320 字符的审阅摘录。
    return classifications  # 返回与 ERR 原始顺序一一对应的警告分类列表。


def file_is_stable(path: Path) -> bool:  # 接收原始 OUT 路径并返回两秒内大小与修改时刻是否均不变。
    first = path.stat()  # 记录第一次文件大小和纳秒级修改时刻。
    time.sleep(2.0)  # 等待两秒以排除求解器退出阶段仍在追加页尾统计。
    second = path.stat()  # 记录第二次文件状态快照。
    return first.st_size == second.st_size and first.st_mtime_ns == second.st_mtime_ns  # 只有两个关键属性均稳定时允许最终哈希。


def finalize(run_dir_value: Path) -> Path:  # 接收静力诊断目录并返回新建的最终状态 JSON 路径。
    run_dir = resolve_run(run_dir_value)  # 规范化并关闭运行目录边界门。
    manifest = read_json(run_dir / "manifest.json")  # 读取准备阶段冻结的求解身份与拓扑合同。
    launch = read_json(run_dir / "runtime_launch.json")  # 读取异步启动器登记的 PID、资源和参数。
    launch_claim_path = run_dir / "runtime_launch_claim.json"  # 定位进程创建前由新版执行器排他写出的唯一启动权声明。
    launch_claim = read_json(launch_claim_path) if launch_claim_path.is_file() else None  # 兼容历史静力诊断无认领文件，但后续对新版自适应迁移强制要求该对象。
    require(manifest.get("run_name") == run_dir.name and launch.get("run_name") == run_dir.name, "清单或启动记录运行名不一致")  # 防止目录复制错配。
    require(manifest.get("jobname") == launch.get("jobname"), "清单与启动记录 jobname 不一致")  # 防止结果文件族被另一作业身份替换。
    require(manifest.get("execution_mode") == launch.get("execution_mode"), "清单与启动记录执行模式不一致")  # 防止准备态 SMP1 被运行时其他模式替换。
    require(manifest.get("launch_argv") == launch.get("launch_argv"), "清单与启动记录的完整启动参数不一致")  # 要求启动器逐项采用冻结命令。
    require(manifest.get("constraint_topology") == "SINGLE_TYPE72_NO_AUX_NO_TYPE73", "运行清单不是单层 TYPE72 拓扑")  # 阻断旧串联约束运行。
    require(manifest.get("execution_mode") == "SMP_SERIAL_NP1_DIAGNOSTIC_ONLY", "运行模式不是批准的 SMP1 静力诊断")  # 禁止把其他并行模式混入本结论。
    require(manifest.get("modal_requested") is False, "运行清单仍请求模态")  # 当前 finalizer 只允许静力范围。
    require(manifest.get("production_claim_allowed") is False, "运行清单意外允许生产声明")  # 保持资源例外和物理审计边界。
    load_path_identity = resolve_load_path_contract(manifest)  # 通过纯函数一次性关闭模式、初始状态路径和物理审计措辞的精确一致性门。
    load_path_mode = str(load_path_identity["mode"])  # 取得已经列入白名单且完成双字段核对的载荷路径模式。
    expected_initial_state_audit = str(load_path_identity["expected_initial_state_audit"])  # 取得已经按模式精确匹配的未闭合初始状态审计状态。
    s10_force_seed_mode = bool(load_path_identity["s10_force_seed_mode"])  # 标识是否需要核验历史 S10 legacy-CERIG 索力种子的专用谱系。
    migration_load_path_mode = bool(load_path_identity["migration_load_path_mode"])  # 标识是否需要核验恒总荷载位置迁移的输入基准、授权证据和自适应路径。
    single_step_load_path_mode = bool(load_path_identity["single_step_load_path_mode"])  # 标识是否采用 LS1 恰一接受子步且 LS1+LS2 恰两结果集的形成态数值合同。
    require(not migration_load_path_mode or isinstance(launch_claim, dict), "自适应迁移缺少 Popen 前排他启动认领")  # 新迁移运行只有同时存在认领与真实 PID 记录才允许最终验收。
    solver_dir = (run_dir / "solver").resolve()  # 定位并规范化本次运行唯一 MAPDL 工作目录。
    require(solver_dir.is_dir(), f"缺少 solver 工作目录：{solver_dir}")  # 在检查参数路径前关闭工作目录存在性门。
    launch_argv = [str(value) for value in manifest["launch_argv"]]  # 从已核对一致的清单恢复完整启动参数数组。
    require(launch_argv.count("-b") == 1 and launch_argv.count("-smp") == 1, "启动参数必须唯一包含批处理和 SMP 标志")  # 固定非交互 SMP 诊断执行模式。
    require(argument_value(launch_argv, "-np") == "1", "启动参数 -np 不是批准的单进程值 1")  # 禁止未资格验证的并行模式混入。
    require(argument_value(launch_argv, "-j") == str(manifest["jobname"]), "启动参数 -j 与清单 jobname 不一致")  # 固定结果文件族身份。
    require(Path(argument_value(launch_argv, "-dir")).resolve() == solver_dir, "启动参数 -dir 未指向本运行 solver 目录")  # 阻断跨运行工作目录污染。
    input_path = Path(argument_value(launch_argv, "-i")).resolve()  # 按唯一 -i 值定位实际主输入。
    output_path = Path(argument_value(launch_argv, "-o")).resolve()  # 按唯一 -o 值定位权威 MAPDL OUT。
    manifest_input_path = (run_dir / str(manifest["main_input"])).resolve()  # 把清单相对主输入解析为规范绝对路径。
    require(input_path == manifest_input_path and input_path.parent == solver_dir, "启动主输入与清单或 solver 目录不一致")  # 防止运行另一输入后借用本目录验收。
    require(output_path.parent == solver_dir and output_path.name.lower() == f"{manifest['jobname']}.out".lower(), "启动主 OUT 路径或文件名不属于本 job")  # 固定唯一权威输出。
    mapdl_path = Path(launch_argv[0]).resolve()  # 以 argv 首项定位实际 MAPDL 可执行文件。
    require(mapdl_path == Path(str(manifest["mapdl_executable"])).resolve() and mapdl_path.is_file(), "MAPDL 可执行文件路径与清单不一致或缺失")  # 固定已批准求解器二进制路径。
    require(sha256_file(mapdl_path) == str(manifest["mapdl_executable_sha256"]), "MAPDL 可执行文件 SHA-256 与清单不一致")  # 禁止版本或二进制静默漂移。
    prepared_entries = verify_hash_ledger(run_dir / "artifact_hashes.sha256", run_dir)  # 复算准备态账本中的全部输入、清单与预检工件。
    prepared_ledger_sha256 = sha256_file(run_dir / "artifact_hashes.sha256")  # 计算已经逐项复算通过的准备账本自身摘要供认领和运行记录交叉核对。
    manifest_sha256 = sha256_file(run_dir / "manifest.json")  # 计算受准备账本保护的清单摘要以关闭启动链三方身份。
    process_identity_path: Path | None = None  # 为历史无认领运行初始化不适用增强进程身份路径，新版启动链将在分支内赋值。
    process_identity: dict[str, Any] | None = None  # 为历史运行初始化不适用增强进程身份对象，迁移模式后续强制存在。
    if isinstance(launch_claim, dict):  # 新版启动器存在排他认领时执行无条件完整一致性核验，历史运行则由前述模式门决定是否允许缺省。
        require(launch_claim.get("schema_version") == 1 and launch_claim.get("status") == "LAUNCH_CLAIMED_NOT_YET_STARTED", "启动认领模式或状态不符合冻结合同")  # 只接受 Popen 前写出的第一版不可覆盖认领语义。
        require(launch_claim.get("run_name") == run_dir.name and launch_claim.get("jobname") == manifest.get("jobname"), "启动认领运行名或 jobname 不一致")  # 防止另一目录或作业的认领文件被复制借用。
        require(launch_claim.get("execution_mode") == manifest.get("execution_mode") and launch_claim.get("launch_argv") == manifest.get("launch_argv"), "启动认领执行模式或完整参数与清单不一致")  # 固定认领时批准的 SMP1 参数数组。
        require(launch_claim.get("diagnostic_subtype") == manifest.get("diagnostic_subtype") and launch_claim.get("single_variable_change") == manifest.get("single_variable_change"), "启动认领诊断子类型或唯一变量与清单不一致")  # 防止认领后切换诊断逻辑或多变量候选。
        require(launch_claim.get("manifest_sha256") == manifest_sha256 and launch_claim.get("prepared_ledger_sha256") == prepared_ledger_sha256 and launch_claim.get("prepared_ledger_entry_count") == len(prepared_entries), "启动认领的清单或准备账本身份不一致")  # 关闭认领前后全部输入字节谱系。
        require(launch.get("manifest_sha256") == manifest_sha256 and launch.get("prepared_ledger_sha256") == prepared_ledger_sha256 and launch.get("prepared_ledger_entry_count") == len(prepared_entries), "真实启动记录的清单或准备账本身份不一致")  # 要求取得 PID 后记录继续引用同一准备谱系。
        require(launch.get("launch_claim_sha256") == sha256_file(launch_claim_path), "真实启动记录引用的排他认领摘要不一致")  # 证明 Popen 后记录对应当前不可覆盖认领原件。
        require(launch_claim.get("prelaunch_resources") == launch.get("prelaunch_resources"), "启动认领与真实启动记录的资源快照不一致")  # 防止资源门在两个启动工件之间被改写。
        require(launch_claim.get("production_claim_allowed") is False and launch.get("production_claim_allowed") is False, "启动链意外允许生产声明")  # 保持低内存诊断例外不能升级为生产结论。
        require(launch.get("status") == "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURE_PENDING", "新版最小 PID 启动记录状态不符合冻结合同")  # 最小记录在 Popen 后立即落盘且不可改写，增强身份由独立工件完成。
        process_identity_relative = str(launch.get("process_identity_path", ""))  # 读取最小启动记录声明的增强身份相对路径。
        require(process_identity_relative == "runtime_process_identity.json", "增强进程身份路径不符合固定运行根文件名")  # 阻断路径逃逸、匿名或失败身份借用。
        process_identity_path = (run_dir / process_identity_relative).resolve()  # 构造当前运行根下增强身份规范绝对路径。
        require(process_identity_path.parent == run_dir and process_identity_path.is_file(), "增强进程身份工件缺失或越出运行根")  # 只有成功捕获身份的运行可继续封板。
        process_identity = read_json(process_identity_path)  # 读取 PID、创建时刻、二进制和真实命令行身份。
        require(process_identity.get("status") == "MAIN_PROCESS_IDENTITY_CAPTURED" and process_identity.get("run_name") == run_dir.name and process_identity.get("jobname") == manifest.get("jobname"), "增强进程身份状态或运行/job身份不一致")  # 关闭跨运行复制和失败工件冒充。
        require(int(process_identity.get("pid", 0)) == int(launch.get("main_pid", 0)) and process_identity.get("runtime_launch_sha256") == sha256_file(run_dir / "runtime_launch.json"), "增强进程身份 PID 或最小启动记录摘要不一致")  # 证明增强身份对应当前不可覆盖 PID 记录。
        require(str(Path(str(process_identity.get("executable", ""))).resolve()).casefold() == str(mapdl_path).casefold() and [str(value) for value in process_identity.get("command_line", [])] == launch_argv, "增强进程二进制或真实命令行与批准启动参数不一致")  # 固定操作系统实际执行身份。
    require(not migration_load_path_mode or isinstance(process_identity, dict), "自适应迁移缺少成功捕获的防 PID 回收进程身份")  # 新迁移运行必须使用完整三段启动链，不能回退历史仅 PID 语义。
    input_relative = input_path.relative_to(run_dir).as_posix()  # 生成主输入在准备态账本中的规范相对路径。
    require(input_relative in prepared_entries, "准备态账本未冻结实际主输入")  # 防止只在清单声明但未纳入哈希谱系。
    require(prepared_entries[input_relative] == str(manifest["main_input_sha256"]), "准备账本与清单的主输入 SHA-256 不一致")  # 关闭双重身份字段的一致性门。
    require(sha256_file(input_path) == str(manifest["main_input_sha256"]), "实际主输入 SHA-256 与清单不一致")  # 独立复算实际传入求解器的文件字节。
    if migration_load_path_mode:  # 恒总荷载迁移模式执行默认 K5 输入基准、K5 证伪授权和 NSBMX 单差异专用门。
        require(manifest.get("diagnostic_subtype") == ADAPTIVE_MIGRATION_DIAGNOSTIC_SUBTYPE, "迁移运行子类型不是批准的 0.05% 自适应诊断")  # 禁止旧固定步或 K5 运行借用成功验收路径。
        require(manifest.get("single_variable_change") == "LS2_NSBMX_200_TO_2000_ONLY", "迁移运行唯一变量不是 NSBMX 200→2000")  # 固定相对默认 0.5% 输入的唯一命令变化。
        require(manifest.get("mpc184_keyopt5_static") == 0 and manifest.get("prestressed_modal_requires_keyopt5_restore_to_zero") is False, "自适应迁移未保持默认 TYPE72 KEYOPT(5)=0")  # 防止已证伪 K5 设置混入候选。
        increment_change = manifest.get("migration_increment_change")  # 读取 NSUBST 三参数、初始和最小迁移增量审计对象。
        require(isinstance(increment_change, dict), "迁移清单缺少 migration_increment_change 对象")  # 后续字段门只接受对象结构。
        require(increment_change.get("nsbstp") == 200 and increment_change.get("nsbmx") == 2000 and increment_change.get("nsbmn") == 200, "迁移清单 NSUBST 三参数不是 200/2000/200")  # 固定初始、最大和最小子步数。
        require(math.isclose(float(increment_change.get("new_initial_fraction", -1.0)), 0.005, rel_tol=0.0, abs_tol=0.0) and math.isclose(float(increment_change.get("new_minimum_fraction", -1.0)), 0.0005, rel_tol=0.0, abs_tol=0.0), "迁移清单初始或最小增量不是 0.5%/0.05%")  # 防止百分比说明与命令分叉。
        migration_main_commands = [line.split("!", maxsplit=1)[0].strip().upper().replace(" ", "") for line in input_path.read_text(encoding="utf-8", errors="strict").splitlines()]  # 规范化实际主控可执行命令供唯一计数。
        require(migration_main_commands.count("NSUBST,200,2000,200") == 1 and migration_main_commands.count("NSUBST,200,200,200") == 0, "实际主控自适应 NSUBST 命令不唯一或仍含固定步命令")  # 固定唯一新值并排除旧值。
        require(migration_main_commands.count("KEYOPT,72,5,1") == 0 and migration_main_commands.count("KBC,1") == 1 and migration_main_commands.count("KBC,0") == 1, "实际主控 K5 或两步 KBC 合同漂移")  # 保持默认 K5、LS1 阶跃和 LS2 线性迁移。
        require(migration_main_commands.count("/INPUT,APPLY_CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_V1,INP") == 2 and sum(1 for command in migration_main_commands if command.startswith("CNVTOL,")) == 4, "迁移 include 调用或四项 CNVTOL 数量漂移")  # 固定 beta 两端和不可放宽收敛门。
        baseline_reference_relative = str(manifest.get("previous_migration_reference", "")).replace("\\", "/")  # 规范化输入基准引用在本运行内的相对路径。
        authorization_reference_relative = str(manifest.get("adaptive_authorization_reference", "")).replace("\\", "/")  # 规范化 K5 证伪授权引用相对路径。
        require(baseline_reference_relative == "qa/previous_migration_reference.json" and authorization_reference_relative == "qa/adaptive_authorization_reference.json", "迁移输入基准或授权引用路径不符合冻结合同")  # 禁止跨路径或匿名证据。
        require(baseline_reference_relative in prepared_entries and authorization_reference_relative in prepared_entries, "准备账本未冻结迁移输入基准或授权引用")  # 两份谱系 JSON 必须进入启动前字节账本。
        baseline_reference = read_json(run_dir / Path(baseline_reference_relative))  # 读取默认 K5=0 的固定 0.5% 输入基准证据。
        authorization_reference = read_json(run_dir / Path(authorization_reference_relative))  # 读取 K5=1 同轨失败后的后续授权证据。
        require(baseline_reference.get("role") == "SINGLE_DIFFERENCE_INPUT_BASELINE" and authorization_reference.get("role") == "FOLLOWUP_AUTHORIZATION_EVIDENCE_NOT_INPUT_BASELINE", "迁移基准与授权证据角色混淆")  # 防止从 K5 输入错误派生多变量候选。
        require(baseline_reference.get("run_name") == manifest.get("single_difference_input_baseline_run") and authorization_reference.get("run_name") == manifest.get("authorization_evidence_run"), "迁移清单与引用运行名不一致")  # 关闭清单和 QA 的运行身份双字段。
        baseline_run = (RUNS_ROOT / str(baseline_reference["run_name"])).resolve()  # 定位默认 K5=0 的固定 0.5% 输入基准运行。
        authorization_run = (RUNS_ROOT / str(authorization_reference["run_name"])).resolve()  # 定位 K5=1 同轨发散授权运行。
        require(baseline_run.parent == RUNS_ROOT.resolve() and baseline_run.is_dir() and authorization_run.parent == RUNS_ROOT.resolve() and authorization_run.is_dir(), "迁移输入基准或授权运行路径越界/缺失")  # 限定两个源运行都位于同一证据根。
        baseline_source_paths = {"root_status_sha256": baseline_run / "C10_static_status.json", "manifest_sha256": baseline_run / "manifest.json", "final_artifact_ledger_sha256": baseline_run / "artifact_hashes.sha256", "main_input_sha256": baseline_run / "solver" / "c10_load_migration_static_main.inp", "runtime_abort_audit_sha256": baseline_run / "qa" / "runtime_abort_audit.json"}  # 构造输入基准五项关键原件映射。
        authorization_source_paths = {"root_status_sha256": authorization_run / "C10_static_status.json", "manifest_sha256": authorization_run / "manifest.json", "final_artifact_ledger_sha256": authorization_run / "artifact_hashes.sha256", "main_input_sha256": authorization_run / "solver" / "c10_load_migration_static_main.inp", "runtime_abort_audit_sha256": authorization_run / "qa" / "runtime_abort_audit.json"}  # 构造授权运行五项关键原件映射。
        require(all(path.is_file() and sha256_file(path) == str(baseline_reference.get(field)) for field, path in baseline_source_paths.items()), "迁移输入基准关键原件缺失或摘要漂移")  # 逐项复算默认 K5 基准状态、清单、账本、主控和发散审计。
        require(all(path.is_file() and sha256_file(path) == str(authorization_reference.get(field)) for field, path in authorization_source_paths.items()), "迁移授权运行关键原件缺失或摘要漂移")  # 逐项复算 K5 授权运行五项关键原件。
        require(len(verify_hash_ledger(baseline_source_paths["final_artifact_ledger_sha256"], baseline_run)) == 59 and len(verify_hash_ledger(authorization_source_paths["final_artifact_ledger_sha256"], authorization_run)) == 59, "迁移输入基准或授权运行最终账本未通过五十九项复算")  # 关闭两条源谱系全部工件的当前字节门。
        require(authorization_reference.get("single_difference_observed_effect") == "NO_CHANGE_IN_LS2_FIRST_TWO_NR_STATES_AT_PRINTED_PRECISION" and authorization_reference.get("authorized_next_diagnostic") == "LS2_ADAPTIVE_SUBSTEPS_200_2000_200_ALLOW_0_05_PERCENT_MINIMUM_INCREMENT", "K5 授权证据未证明无效或未批准自适应下一步")  # 固定 K5 证伪和后续许可语义。
    s10_force_seed_source_run = "NOT_APPLICABLE"  # 为非 seed 模式初始化机器报告的历史源运行字段，避免残留其他分支值。
    s10_force_seed_source_audit = "NOT_APPLICABLE"  # 为非 seed 模式初始化机器报告的历史后处理审计字段。
    s10_force_seed_include_sha256 = "NOT_APPLICABLE"  # 为非 seed 模式初始化种子 include 摘要字段。
    s10_force_seed_source_csv_sha256 = "NOT_APPLICABLE"  # 为非 seed 模式初始化历史索力 CSV 摘要字段。
    s10_force_seed_define_count = 0  # 非 seed 模式没有 seed override 定义，使用零作为不适用计数而非伪造成功数。
    if s10_force_seed_mode:  # 仅 seed 模式进入历史 S10 索力来源、覆盖顺序和生产禁用的专用 fail-closed 门。
        require(manifest.get("diagnostic_subtype") == S10_FORCE_SEED_DIAGNOSTIC_SUBTYPE, "S10 索力种子运行的 diagnostic_subtype 不符合冻结合同")  # 禁止其他诊断借用 seed 载荷路径身份。
        seed_include_relative = str(manifest.get("initial_state_seed_include", "")).replace("\\", "/")  # 规范化清单中的 seed include 相对路径供严格路径比较。
        require(seed_include_relative == S10_FORCE_SEED_INCLUDE_RELATIVE, "S10 索力种子 include 相对路径不符合冻结合同")  # seed 模式只允许批准的 LINK180 覆盖 include。
        seed_include_path = (run_dir / seed_include_relative).resolve()  # 把已通过精确文本门的 seed 相对路径解析为绝对路径。
        require(seed_include_path.parent == solver_dir and seed_include_path.is_file(), "S10 索力种子 include 缺失或越出本运行 solver 目录")  # 阻断跨运行或缺失种子文件。
        require(seed_include_relative in prepared_entries, "准备态账本未冻结 S10 索力种子 include")  # 要求种子字节已经进入准备态哈希谱系。
        s10_force_seed_include_sha256 = sha256_file(seed_include_path)  # 独立复算实际 seed include 的 SHA-256 供清单、QA 和报告三方闭合。
        require(str(manifest.get("initial_state_seed_include_sha256", "")) == s10_force_seed_include_sha256, "S10 索力种子 include SHA-256 与 manifest 不一致")  # 禁止清单引用另一版本种子。
        require(prepared_entries[seed_include_relative] == s10_force_seed_include_sha256, "S10 索力种子 include SHA-256 与准备态账本不一致")  # 禁止账本与实际文件分叉。
        s10_force_seed_source_csv_sha256 = str(manifest.get("initial_state_seed_source_csv_sha256", ""))  # 读取历史 S10 LS2 LINK180 索力 CSV 的冻结来源摘要。
        require(re.fullmatch(r"[0-9a-f]{64}", s10_force_seed_source_csv_sha256) is not None, "S10 索力种子来源 CSV SHA-256 格式非法")  # 来源摘要必须为完整六十四位小写十六进制。
        seed_input_text = seed_include_path.read_text(encoding="utf-8", errors="strict")  # 以严格 UTF-8 读取实际种子命令，拒绝编码替换掩盖命令损坏。
        seed_delete_matches = list(re.finditer(r"^\s*INISTATE\s*,\s*DELE\s*$", seed_input_text, flags=re.IGNORECASE | re.MULTILINE))  # 定位全部旧初始状态删除命令并排除注释文本误计数。
        seed_define_matches = list(re.finditer(r"^\s*INISTATE\s*,\s*DEFINE\s*,\s*(\d+)\s*,", seed_input_text, flags=re.IGNORECASE | re.MULTILINE))  # 定位每条 seed DEFINE 并提取目标 LINK180 元素号。
        seed_stress_type_matches = list(re.finditer(r"^\s*INISTATE\s*,\s*SET\s*,\s*DTYP\s*,\s*STRE\s*$", seed_input_text, flags=re.IGNORECASE | re.MULTILINE))  # 定位轴向应力数据类型声明，防止把力值误解释为其他初始状态量。
        s10_force_seed_define_count = len(seed_define_matches)  # 保存实际 seed DEFINE 数量供硬门和最终机器报告共同使用。
        seed_defined_element_ids = [int(match.group(1)) for match in seed_define_matches]  # 按文件顺序恢复全部被覆盖的 LINK180 元素号。
        expected_seed_element_ids = set(range(1, 73689)) | {400000, 400001, 400002, 400003}  # 冻结 TYPE4 元素集合为连续 1..73688 加四个 400000 系列构件，共 73692 个。
        require(len(seed_delete_matches) == 1, "S10 索力种子 include 的 INISTATE,DELE 不是恰好一次")  # 防止未删除旧 MCT 状态或重复删除破坏覆盖语义。
        require(s10_force_seed_define_count == 73692 and len(set(seed_defined_element_ids)) == 73692, "S10 索力种子 DEFINE 数量或元素唯一性不满足 73692 合同")  # 要求每个目标 LINK180 恰定义一次。
        require(set(seed_defined_element_ids) == expected_seed_element_ids, "S10 索力种子 DEFINE 元素集合与冻结 TYPE4 集合不一致")  # 禁止漏项、串号或向非目标元素施加种子。
        require(len(seed_stress_type_matches) == 1, "S10 索力种子 include 的 INISTATE STRE 数据类型声明不是恰好一次")  # 确保 73692 个数值按应力解释。
        require(seed_delete_matches[0].start() < seed_define_matches[0].start(), "S10 索力种子在删除旧初始状态前已经开始 DEFINE")  # 删除必须先于第一条重定义以形成确定覆盖顺序。
        main_input_text = input_path.read_text(encoding="utf-8", errors="strict")  # 读取已完成 SHA 门的主输入以验证原始初态与 seed 覆盖的真实调用顺序。
        main_input_include_names = [match.group(1).strip().lower() for match in re.finditer(r"^\s*/INPUT\s*,\s*([^,\s]+)\s*,\s*inp\s*$", main_input_text, flags=re.IGNORECASE | re.MULTILINE)]  # 提取可执行 /INPUT 名称且忽略注释中的描述文本。
        original_initial_state_name = "apply_mct_authoritative_initial_state_link180"  # 冻结必须先读取的原始 MCT LINK180 初始状态 include 名称。
        seed_override_name = Path(S10_FORCE_SEED_INCLUDE_RELATIVE).stem.lower()  # 从冻结 seed 相对路径派生主输入中应出现的无扩展名调用名称。
        original_initial_state_indices = [index for index, name in enumerate(main_input_include_names) if name == original_initial_state_name]  # 收集原始初态 include 的全部可执行调用位置。
        seed_override_indices = [index for index, name in enumerate(main_input_include_names) if name == seed_override_name]  # 收集 seed override include 的全部可执行调用位置。
        require(len(original_initial_state_indices) == 1 and len(seed_override_indices) == 1, "主输入中的原始 initial-state 或 seed override 调用不是恰好一次")  # 防止重复、遗漏或多路径覆盖。
        require(seed_override_indices[0] == original_initial_state_indices[0] + 1, "主输入未在原始 initial-state include 后立即调用 seed override")  # 确保旧状态读入后立即删除并完整重定义，期间不得插入其他模型变更。
        seed_audit_relative = S10_FORCE_SEED_AUDIT_RELATIVE  # 使用冻结相对路径定位 seed 准备期逐元素审计工件。
        seed_audit_path = (run_dir / seed_audit_relative).resolve()  # 把 seed 审计相对路径解析到本运行目录。
        require(seed_audit_relative in prepared_entries and seed_audit_path.is_file(), "准备态账本未冻结 S10 索力种子审计工件")  # 审计 JSON 必须存在且进入哈希谱系。
        seed_audit = read_json(seed_audit_path)  # 读取已由准备态账本保护的 seed 来源与覆盖审计对象。
        require(seed_audit.get("schema_version") == 1 and seed_audit.get("status") == "PASSED", "S10 索力种子审计 schema 或状态不符合批准合同")  # 只接受已通过的第一版冻结审计结构。
        require(seed_audit.get("element_count") == 73692 and seed_audit.get("all_forces_positive") is True, "S10 索力种子审计未证明 73692 个正索力")  # 种子必须覆盖全部 LINK180 且保持拉力物理。
        require(seed_audit.get("old_initial_state_deleted_before_redefinition") is True, "S10 索力种子审计未证明旧初始状态先删除")  # QA 声明必须与本次命令级复核一致。
        require(seed_audit.get("include_sha256") == s10_force_seed_include_sha256, "S10 索力种子审计与实际 include SHA-256 不一致")  # 关闭 QA 到实际命令文件的字节谱系。
        require(seed_audit.get("source_csv_sha256") == s10_force_seed_source_csv_sha256, "S10 索力种子审计与 manifest 的来源 CSV SHA-256 不一致")  # 关闭 QA 到历史 S10 轴力来源摘要的谱系。
        require(seed_audit.get("source_csv") == "s10_link180_axial_force_n.csv", "S10 索力种子审计的来源 CSV 文件名不符合冻结合同")  # 禁止其他未说明数据集冒充历史 S10 LINK180 轴力。
        require(seed_audit.get("valid_for_production") is False, "S10 索力种子审计意外允许生产使用")  # 种子准备审计本身必须明确拒绝生产签认。
        s10_force_seed_source_run = str(seed_audit.get("source_run", ""))  # 读取历史 S10 求解运行 ID 供最终 JSON 与报告披露。
        s10_force_seed_source_audit = str(seed_audit.get("source_audit", ""))  # 读取历史 LINK180 后处理审计 ID 供来源追踪。
        require(s10_force_seed_source_run.startswith("S10_") and s10_force_seed_source_audit.startswith("S10_"), "S10 索力种子的历史源运行或审计 ID 非法")  # 来源身份必须明确属于 S10 链而不是匿名或其他算例。
    main_pid = int(launch["main_pid"])  # 读取异步启动器登记的 MAPDL 包装进程 PID。
    if isinstance(process_identity, dict):  # 新版启动链使用 PID、创建时刻、二进制和命令行四重身份判断包装器是否仍存活。
        require(not process_identity_is_alive(process_identity), f"启动器原始进程身份仍存活，拒绝在求解中封板：{main_pid}")  # 防止长运行后 PID 被无关进程复用而误拒，同时真实原进程存在时继续阻断。
    else:  # 历史无增强身份的已存在运行保留旧 PID 门以维持向后兼容，但不用于本次迁移。
        require(not psutil.pid_exists(main_pid), f"历史启动器 PID {main_pid} 仍存在，拒绝在求解中封板")  # 只有旧运行缺少防复用证据时才回退单 PID 检查。
    active_job_processes: list[int] = []  # 初始化仍携带本 jobname 命令行的求解器进程 PID 列表。
    for process in psutil.process_iter(["pid", "name", "cmdline"]):  # 遍历本机进程以弥补包装 PID 早于真实 ANSYS 子进程退出的问题。
        try:  # 进程可能在枚举期间退出或拒绝访问，需按瞬时状态安全处理。
            command_line = " ".join(process.info.get("cmdline") or [])  # 合并当前进程参数供 jobname 文本筛选。
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):  # 捕获进程消失、权限与僵尸三类只读枚举异常。
            continue  # 无法稳定读取的瞬时进程不作为仍运行证据。
        process_name = str(process.info.get("name") or "").lower()  # 读取可执行映像名以排除含 jobname 文本的监控 PowerShell 或编辑器。
        if process_name.startswith("ansys") and str(manifest["jobname"]).lower() in command_line.lower() and str(solver_dir).lower() in command_line.lower():  # 仅筛选本 solver 目录中携带本 jobname 的 ANSYS worker。
            active_job_processes.append(int(process.info["pid"]))  # 保存仍活动的本作业 PID 供门禁失败说明。
    require(not active_job_processes, f"仍有本 job 求解器进程活动：{active_job_processes}")  # 包装和真实求解进程均结束后才允许封板。
    require(not any(solver_dir.glob("*.lock")), "solver 目录仍存在 MAPDL lock 文件")  # 用运行专属锁消失证明数据库已关闭。
    require(output_path.is_file(), f"缺少主 OUT：{output_path}")  # 拒绝未启动或输出丢失的运行。
    require(file_is_stable(output_path), "主 OUT 在两秒检查窗口内仍发生变化")  # 防止封板时求解器仍在追加内容。
    output_text = output_path.read_text(encoding="utf-8", errors="replace")  # 读取完整 OUT 并仅替换不可解码的本地字符。
    output_upper = output_text.upper()  # 统一大写用于固定异常短语和完成标志检查。
    error_path = solver_dir / f"{manifest['jobname']}.err"  # 定位与冻结 jobname 完全一致的独立 MAPDL 警告错误文件。
    require(error_path.is_file() and error_path.stat().st_size > 0, f"缺少或为空的独立 ERR：{error_path}")  # 本次已知含诊断告警，空 ERR 视为谱系或文件丢失。
    require(file_is_stable(error_path), "独立 ERR 在两秒检查窗口内仍发生变化")  # 防止警告仍在追加时提前分类。
    error_text = error_path.read_text(encoding="utf-8", errors="replace")  # 读取完整 ERR 并保留所有可解析原生警告文本。
    error_upper = error_text.upper()  # 统一大写供固定告警分类和异常短语检查。
    runtime_monitor_claim_path: Path | None = None  # 为非迁移历史运行初始化不适用的监控认领路径。
    runtime_monitor_samples_path: Path | None = None  # 为非迁移历史运行初始化不适用的监控样本路径。
    runtime_monitor_final_path: Path | None = None  # 为非迁移历史运行初始化不适用的监控终态路径。
    runtime_monitor_audit: dict[str, Any] = {"applicable": False, "status": "NOT_APPLICABLE"}  # 为非迁移运行初始化明确不适用的运行硬停审计对象。
    if migration_load_path_mode:  # 自适应迁移成功验收必须闭合准备账本内监控代码、排他认领、完整流水与自然退出终态。
        runtime_monitor_claim_path = run_dir / "qa" / "runtime_hard_stop_monitor_claim.json"  # 定位监控器在任何样本或中止动作前写出的唯一权声明。
        runtime_monitor_samples_path = run_dir / "qa" / "runtime_hard_stop_monitor_samples.jsonl"  # 定位每十秒刷盘的资源、进程和日志增量流水。
        runtime_monitor_final_path = run_dir / "qa" / "runtime_hard_stop_monitor_final.json"  # 定位进程树退出后排他提交的监控终态。
        require(runtime_monitor_claim_path.is_file() and runtime_monitor_samples_path.is_file() and runtime_monitor_final_path.is_file(), "自适应迁移缺少监控认领、样本或终态工件")  # 任一运行监控原件缺失即拒绝成功封板。
        require(runtime_monitor_samples_path.stat().st_size > 0, "自适应迁移监控样本流水为空")  # 至少需要一次附着后的真实资源和进程样本。
        runtime_monitor_claim = read_json(runtime_monitor_claim_path)  # 读取监控代码身份、启动链摘要和初始绑定进程证据。
        runtime_monitor_final = read_json(runtime_monitor_final_path)  # 读取退出稳定性、资源极值、方程数和控制器动作终态。
        runtime_monitor_sample_lines = [line for line in runtime_monitor_samples_path.read_text(encoding="utf-8").splitlines() if line.strip()]  # 读取并剔除空白行，保留每次十秒采样的原始 JSON 对象边界。
        runtime_monitor_samples = [json.loads(line) for line in runtime_monitor_sample_lines]  # 逐行解析监控流水，任何破损 JSON 都会失败关闭而不能只信终态摘要。
        require(all(isinstance(sample, dict) for sample in runtime_monitor_samples), "监控样本流水存在非对象记录")  # 每个 JSONL 记录都必须是具名字段对象。
        require(all(sample.get("schema_version") == 1 for sample in runtime_monitor_samples), "监控样本流水 schema 不全为冻结第一版")  # 禁止混入未知字段语义版本的样本。
        runtime_monitor_sample_indexes = [int(sample.get("sample_index", -1)) for sample in runtime_monitor_samples]  # 提取样本序号供连续性和总数复算。
        runtime_monitor_sample_available_ram = [int(sample.get("physical_memory_available_bytes", -1)) for sample in runtime_monitor_samples]  # 提取各样本可用物理内存供最小值复算。
        runtime_monitor_sample_disk_free = [int(sample.get("disk_free_bytes", -1)) for sample in runtime_monitor_samples]  # 提取各样本工作盘余量供最小值复算。
        runtime_monitor_sample_related_rss = [int(sample.get("related_rss_bytes", -1)) for sample in runtime_monitor_samples]  # 提取各样本本 job 工作集供峰值复算。
        runtime_monitor_sample_low_ram_seconds = [float(sample.get("low_ram_continuous_seconds", -1.0)) for sample in runtime_monitor_samples]  # 提取连续低内存计时供六十秒硬停合同复算。
        runtime_monitor_sample_equation_counts = [int(value) for sample in runtime_monitor_samples for value in sample.get("new_equation_counts", [])]  # 按样本和日志出现顺序重建监控器观察到的方程数序列。
        runtime_monitor_sample_hard_events = [event for sample in runtime_monitor_samples for event in sample.get("new_hard_events", [])]  # 按样本顺序重建全部新硬事件并与终态动作摘要闭合。
        require(runtime_monitor_claim.get("status") == "MONITOR_CLAIMED" and runtime_monitor_claim.get("run_name") == run_dir.name and runtime_monitor_claim.get("jobname") == manifest.get("jobname"), "监控认领状态或运行/job身份不一致")  # 关闭跨运行监控工件复制。
        require(runtime_monitor_claim.get("runtime_launch_sha256") == sha256_file(run_dir / "runtime_launch.json") and runtime_monitor_claim.get("runtime_launch_claim_sha256") == sha256_file(launch_claim_path), "监控认领引用的两段启动工件摘要不一致")  # 证明监控附着当前不可覆盖启动链。
        require(isinstance(process_identity_path, Path) and runtime_monitor_claim.get("runtime_process_identity_sha256") == sha256_file(process_identity_path), "监控认领引用的增强进程身份摘要不一致")  # 证明监控使用当前防 PID 回收身份。
        runtime_monitor_relative = str(manifest.get("runtime_monitor_script", "")).replace("\\", "/")  # 读取清单冻结的监控器快照相对路径。
        require(runtime_monitor_relative == "input_snapshot/ultra_c10_adaptive_monitor.py" and runtime_monitor_relative in prepared_entries, "清单或准备账本未冻结自适应监控器快照")  # 固定监控代码必须属于准备态账本。
        require(runtime_monitor_claim.get("monitor_script_sha256") == str(manifest.get("runtime_monitor_script_sha256")) == prepared_entries[runtime_monitor_relative], "监控认领、清单和准备账本的监控代码摘要不一致")  # 三方证明实际附着脚本字节身份。
        require(runtime_monitor_final.get("status") == "NATURAL_PROCESS_TREE_EXITED_STABLE_WITHOUT_MONITOR_HARD_STOP" and runtime_monitor_final.get("run_name") == run_dir.name and runtime_monitor_final.get("jobname") == manifest.get("jobname"), "监控终态不是本 job 自然稳定退出且无硬停")  # 控制器硬停或退出证据阻断不得进入成功分支。
        require(runtime_monitor_final.get("monitor_claim_sha256") == sha256_file(runtime_monitor_claim_path) and runtime_monitor_final.get("samples_sha256") == sha256_file(runtime_monitor_samples_path), "监控终态引用的认领或样本流水摘要不一致")  # 关闭监控执行期间工件替换。
        require(runtime_monitor_final.get("hard_events") == [] and runtime_monitor_final.get("controller_abort", {}).get("requested") is False and runtime_monitor_final.get("final_related_processes") == [], "监控终态仍含硬事件、控制器中止或存活本 job 进程")  # 成功分支只接受未抢停且进程树清空。
        require(runtime_monitor_final.get("final_lock_file", {}).get("exists") is False and runtime_monitor_final.get("monitor_block_reason") is None, "监控终态仍有 MAPDL lock 或完整性阻断")  # 与当前无锁门双向闭合。
        require(runtime_monitor_sample_indexes == list(range(1, len(runtime_monitor_samples) + 1)) and int(runtime_monitor_final.get("sample_count", -1)) == len(runtime_monitor_samples), "监控样本序号不连续或终态样本总数不能由 JSONL 复算")  # 防止删行、重排或伪造 sample_count。
        require(all(value > 0 for value in runtime_monitor_sample_available_ram) and min(runtime_monitor_sample_available_ram) == int(runtime_monitor_final.get("minimum_physical_memory_available_bytes", -1)), "监控终态最小可用内存不能由样本流水复算")  # 用完整流水复核内存极值而非只信摘要布尔值。
        require(all(value > 0 for value in runtime_monitor_sample_disk_free) and min(runtime_monitor_sample_disk_free) == int(runtime_monitor_final.get("minimum_disk_free_bytes", -1)), "监控终态最小磁盘余量不能由样本流水复算")  # 用完整流水复核磁盘极值而非只信摘要布尔值。
        require(all(value >= 0 for value in runtime_monitor_sample_related_rss) and max(runtime_monitor_sample_related_rss) == int(runtime_monitor_final.get("maximum_related_rss_bytes", -1)), "监控终态最大本 job 工作集不能由样本流水复算")  # 用完整流水复核进程资源峰值。
        require(all(value >= 0.0 for value in runtime_monitor_sample_low_ram_seconds) and max(runtime_monitor_sample_low_ram_seconds) < 60.0, "监控样本出现达到六十秒的连续低内存区间却进入成功分支")  # 成功路径必须由逐样本计时证明未触发持续低内存硬停。
        require(runtime_monitor_sample_equation_counts == runtime_monitor_final.get("observed_equation_counts"), "监控终态方程数序列不能由样本流水逐项复算")  # 关闭摘要遗漏或重排方程观察值的失效开放路径。
        require(runtime_monitor_sample_hard_events == runtime_monitor_final.get("hard_events"), "监控终态硬事件序列不能由样本流水逐项复算")  # 关闭样本已记录事件但终态摘要清空的失效开放路径。
        require(int(runtime_monitor_final.get("minimum_physical_memory_available_bytes", 0)) >= 512 * 1024**2 and int(runtime_monitor_final.get("minimum_disk_free_bytes", 0)) >= 32 * 1024**3, "监控终态资源极值越过硬停线却未形成事件")  # 独立核对监控动作与资源极值一致性。
        require(runtime_monitor_final.get("unique_equation_counts") == [EXPECTED_EQUATION_COUNT], "监控流水观察方程数缺失或发生漂移")  # 成功运行至少一次组装且全部保持冻结方程数。
        require(int(runtime_monitor_final.get("final_out_file", {}).get("size_bytes", -1)) == output_path.stat().st_size and int(runtime_monitor_final.get("final_err_file", {}).get("size_bytes", -1)) == error_path.stat().st_size, "监控终态 OUT/ERR 大小与最终原件不一致")  # 证明监控提交后原生日志没有继续变化。
        runtime_monitor_audit = {"applicable": True, "status": runtime_monitor_final["status"], "claim_sha256": sha256_file(runtime_monitor_claim_path), "samples_sha256": sha256_file(runtime_monitor_samples_path), "final_sha256": sha256_file(runtime_monitor_final_path), "sample_count": int(runtime_monitor_final["sample_count"]), "sample_indexes_recomputed_sequential": True, "minimum_physical_memory_available_bytes": int(runtime_monitor_final["minimum_physical_memory_available_bytes"]), "minimum_disk_free_bytes": int(runtime_monitor_final["minimum_disk_free_bytes"]), "maximum_related_rss_bytes": int(runtime_monitor_final["maximum_related_rss_bytes"]), "maximum_low_ram_continuous_seconds": max(runtime_monitor_sample_low_ram_seconds), "resource_extrema_recomputed_from_samples": True, "hard_event_count": len(runtime_monitor_final["hard_events"]), "hard_events_recomputed_from_samples": True, "controller_abort_requested": bool(runtime_monitor_final["controller_abort"]["requested"]), "observed_equation_counts_recomputed": runtime_monitor_sample_equation_counts, "unique_equation_counts": runtime_monitor_final["unique_equation_counts"]}  # 保存可纳入最终验证包且已由 JSONL 独立复算的监控代码、资源、秩和动作摘要。
    error_counts = [int(value) for value in ERROR_COUNT_PATTERN.findall(output_text)]  # 提取所有页尾错误累计值。
    warning_counts = [int(value) for value in WARNING_COUNT_PATTERN.findall(output_text)]  # 提取所有页尾警告累计值。
    equation_counts = [int(value) for value in EQUATION_COUNT_PATTERN.findall(output_text)]  # 按出现顺序提取全部方程数。
    unique_equation_counts = sorted(set(equation_counts))  # 去重后检查二分与迭代重组是否改变依赖自由度集合。
    minimum_pivots = [float(value) for value in MINIMUM_PIVOT_PATTERN.findall(output_text)]  # 提取每次直接分解的有符号最小主元。
    bisection_count = output_upper.count("BEGIN BISECTION")  # 统计 AUTOTS 实际触发的二分次数并作为路径事实报告。
    incomplete_attempt_count = len(re.findall(r"SUBSTEP\s+\d+\s+NOT COMPLETED", output_text, re.IGNORECASE))  # 统计未接受尝试次数，不把允许的 AUTOTS 回退冒充已接受子步。
    ls2_completed_substep_numbers = [int(value) for value in re.findall(r"\*\*\* LOAD STEP\s+2\s+SUBSTEP\s+(\d+)\s+COMPLETED", output_text, re.IGNORECASE)]  # 提取 LS2 全部已接受子步编号，排除未完成尝试和 LS1。
    ls2_completed_substep_sequence_valid = (not migration_load_path_mode) or (200 <= len(ls2_completed_substep_numbers) <= 2000 and ls2_completed_substep_numbers == list(range(1, len(ls2_completed_substep_numbers) + 1)))  # 迁移路径要求接受子步连续且数量落在 NSBMX/NSBMN 边界内。
    native_monitor_path = solver_dir / f"{manifest['jobname']}.mntr"  # 定位 MAPDL 已接受子步、尝试次数、迭代数和真实增量路径的原生 MNTR。
    require(native_monitor_path.is_file() and native_monitor_path.stat().st_size > 0, "缺少或为空的 MAPDL MNTR 监控文件")  # 成功分支必须保留独立于 OUT 完成标志的原生收敛路径证据。
    require(file_is_stable(native_monitor_path), "MAPDL MNTR 在两秒检查窗口内仍发生变化")  # 防止求解器退出交接或缓冲刷新期间提前解析。
    mntr_rows = parse_mntr_rows(native_monitor_path)  # 解析全部已接受子步的控制列和时间列。
    mntr_ls1_rows = [row for row in mntr_rows if int(row["load_step"]) == 1]  # 提取 LS1 已接受形成态记录供单步合同核对。
    mntr_ls2_rows = [row for row in mntr_rows if int(row["load_step"]) == 2]  # 提取 LS2 已接受迁移记录供增量上下界和端点核对。
    mntr_ls2_increments = [float(row["increment"]) for row in mntr_ls2_rows]  # 提取实际接受增量，二分失败尝试不会作为已接受行混入。
    mntr_ls2_total_times = [float(row["total_time"]) for row in mntr_ls2_rows]  # 提取原生打印累计时间供非降与终点检查。
    reconstructed_ls2_times: list[float] = []  # 初始化由每个实际增量独立累加的高分辨率迁移时间路径。
    reconstructed_time = 1.0  # LS2 从已平衡 beta=1 的 time=1.0 起步。
    for increment in mntr_ls2_increments:  # 按原生已接受顺序累加每个迁移增量。
        reconstructed_time += increment  # 形成不受 MNTR 累计时间显示位数限制的严格递增路径。
        reconstructed_ls2_times.append(reconstructed_time)  # 保存当前接受子步的独立累计时间。
    mntr_ls2_total_iterations = [int(row["total_iterations"]) for row in mntr_ls2_rows]  # 提取 LS2 内累计牛顿迭代数供严格递增检查。
    mntr_checks = {"at_least_one_accepted_row": len(mntr_rows) >= 1, "only_load_steps_one_and_two": all(int(row["load_step"]) in {1, 2} for row in mntr_rows), "positive_attempt_and_iteration_fields": all(int(row["attempt"]) >= 1 and int(row["iterations"]) >= 1 and int(row["total_iterations"]) >= 1 for row in mntr_rows), "ls1_single_formed_state_row": len(mntr_ls1_rows) == 1 and int(mntr_ls1_rows[0]["substep"]) == 1 and math.isclose(float(mntr_ls1_rows[0]["increment"]), 1.0, rel_tol=0.0, abs_tol=1.0e-12) and math.isclose(float(mntr_ls1_rows[0]["total_time"]), 1.0, rel_tol=0.0, abs_tol=1.0e-12)}  # 建立所有当前形成态路径共享的 MNTR 基础合同。
    if migration_load_path_mode:  # 自适应恒总荷载迁移追加 0.5% 初始/最大与 0.05% 最小真实增量专项门。
        migration_duration = 0.001  # 冻结 LS2 从 time=1.0 到 1.001 的总伪时间长度，对应 beta 从一连续迁移到零。
        maximum_migration_increment = migration_duration / 200.0  # NSBMN=200 规定任何接受增量不得大于 5E-6，即 beta 0.5%。
        minimum_migration_increment = migration_duration / 2000.0  # NSBMX=2000 规定自动二分允许的最小接受增量为 5E-7，即 beta 0.05%。
        increment_tolerance = 1.0e-12  # 给单个 MNTR 增量的上下界比较保留一皮秒伪时间绝对容差，避免浮点转换噪声越界。
        increment_sum_tolerance = 5.1e-8  # 按 MAPDL 五位尾数科学计数法最坏约五万分之一相对舍入累计总时长 0.001 的上界取 5.1E-8，同时仍小于最小 5E-7 增量的十一分之一。
        mntr_checks.update({"ls2_row_count_matches_out_completed_substeps": len(mntr_ls2_rows) == len(ls2_completed_substep_numbers), "ls2_substeps_sequential": [int(row["substep"]) for row in mntr_ls2_rows] == list(range(1, len(mntr_ls2_rows) + 1)), "ls2_accepted_row_count_within_200_to_2000": 200 <= len(mntr_ls2_rows) <= 2000, "ls2_each_increment_within_5e_minus_7_to_5e_minus_6": all(minimum_migration_increment - increment_tolerance <= value <= maximum_migration_increment + increment_tolerance for value in mntr_ls2_increments), "ls2_increment_sum_equals_0_001": math.isclose(sum(mntr_ls2_increments), migration_duration, rel_tol=0.0, abs_tol=increment_sum_tolerance), "ls2_reconstructed_times_strictly_increasing": all(reconstructed_ls2_times[index] > (1.0 if index == 0 else reconstructed_ls2_times[index - 1]) for index in range(len(reconstructed_ls2_times))), "ls2_reconstructed_final_time_1_001": len(reconstructed_ls2_times) > 0 and math.isclose(reconstructed_ls2_times[-1], 1.001, rel_tol=0.0, abs_tol=increment_sum_tolerance), "ls2_printed_total_times_nondecreasing": all(mntr_ls2_total_times[index] >= mntr_ls2_total_times[index - 1] for index in range(1, len(mntr_ls2_total_times))), "ls2_printed_final_time_1_001": len(mntr_ls2_total_times) > 0 and math.isclose(mntr_ls2_total_times[-1], 1.001, rel_tol=0.0, abs_tol=5.0e-7), "ls2_printed_times_match_reconstruction_within_display_resolution": len(mntr_ls2_total_times) == len(reconstructed_ls2_times) and all(math.isclose(printed, rebuilt, rel_tol=0.0, abs_tol=5.0e-5) for printed, rebuilt in zip(mntr_ls2_total_times, reconstructed_ls2_times, strict=True)), "ls2_total_iterations_strictly_increasing": all(mntr_ls2_total_iterations[index] > mntr_ls2_total_iterations[index - 1] for index in range(1, len(mntr_ls2_total_iterations)))})  # 以原生接受行证明实际步长、连续编号、累计路径和迭代闭合，并按原生打印精度控制累计误差而非误拒真成功路径。
    mntr_checks["passed"] = all(mntr_checks.values())  # 形成适用于当前载荷路径的原生 MNTR 总门。
    warning_classifications = classify_warning_blocks(error_text)  # 对每个 ERR 警告块规范空白后执行唯一类别判定。
    err_warning_count = len(warning_classifications)  # 以实际切分出的警告块数量闭合 OUT 页尾摘要。
    warning_categories = [entry["category"] for entry in warning_classifications]  # 提取保持原始顺序的类别序列供计数和未知项门禁。
    coefficient_ratio_warning_count = warning_categories.count("COEFFICIENT_RATIO_GT_1E8")  # 统计病态尺度告警并在诊断结果中显式披露。
    moment_reference_warning_count = warning_categories.count("MOMENT_REFERENCE_INTERNAL_THRESHOLD")  # 统计力矩收敛参考阈值由程序接管的次数。
    cnvtol_f_default_warning_count = warning_categories.count("CNVTOL_F_DEFAULT_MINREF_1")  # 统计 F 的默认 MINREF 警告次数。
    cnvtol_m_default_warning_count = warning_categories.count("CNVTOL_M_DEFAULT_MINREF_1")  # 统计 M 的默认 MINREF 警告次数。
    classified_warning_count = sum(1 for category in warning_categories if category not in {"UNCLASSIFIED", "AMBIGUOUS"})  # 合计唯一命中批准类别的警告块。
    err_checks = {"fatal_marker_absent": "*** FATAL ***" not in error_upper and "PROBLEM TERMINATED" not in error_upper, "error_marker_absent": "*** ERROR ***" not in error_upper, "warning_summary_matches_err_blocks": len(warning_counts) == 1 and warning_counts[0] == err_warning_count, "cnvtol_f_default_warning_exactly_one": cnvtol_f_default_warning_count == 1, "cnvtol_m_default_warning_exactly_one": cnvtol_m_default_warning_count == 1, "all_warning_blocks_classified": classified_warning_count == err_warning_count and "UNCLASSIFIED" not in warning_categories and "AMBIGUOUS" not in warning_categories}  # 要求 ERR 无错误且每个警告块恰属于一个已知诊断限定类别。
    err_checks["passed"] = all(err_checks.values())  # 形成独立 ERR 分类与摘要闭合总门。
    log_checks = {"run_completed_marker": "RUN COMPLETED" in output_upper, "normal_nosave_exit_marker": "EXIT MAPDL WITHOUT SAVING DATABASE" in output_upper, "unique_zero_error_summary": len(error_counts) == 1 and error_counts[0] == 0, "fatal_marker_absent": "*** FATAL ***" not in output_upper and "PROBLEM TERMINATED" not in output_upper, "error_marker_absent": "*** ERROR ***" not in output_upper, "ignored_cnvtol_absent": "CNVTOL COMMAND IS IGNORED" not in output_upper, "automatic_cnvtol_reset_absent": "INTERNALLY RESET TO CNVTOL" not in output_upper, "small_pivot_absent": "SMALL EQUATION SOLVER PIVOT" not in output_upper and re.search(r"\bSMALL PIVOT\b", output_upper) is None, "zero_pivot_absent": "ZERO PIVOT" not in output_upper, "negative_pivot_absent": "NEGATIVE PIVOT" not in output_upper, "unclassified_extreme_pivot_phrase_absent": "EXTREMELY LARGE PIVOT RATIO" not in output_upper, "equation_count_reported": len(equation_counts) >= 1, "equation_count_constant_and_expected": unique_equation_counts == [EXPECTED_EQUATION_COUNT], "minimum_pivots_reported": len(minimum_pivots) >= 1, "all_minimum_pivots_positive_finite": all(math.isfinite(value) and value > 0.0 for value in minimum_pivots), "ls2_completed_substeps_within_adaptive_contract": ls2_completed_substep_sequence_valid}  # 汇总求解器原生日志、主元、方程和迁移接受子步硬门。
    log_checks["passed"] = all(log_checks.values())  # 日志总门要求以上每项均为真。
    gate_path = solver_dir / "c10_gate_status.txt"  # 定位 APDL 静力内部 QA 的唯一状态文件。
    topology_path = solver_dir / "c10_topology_counts.txt"  # 定位运行时节点和元素类型计数文件。
    mpc_path = solver_dir / "c10_mpc184_elements.txt"  # 定位全部 5,078 个 MPC184 的 ELLIST 原始表。
    ce_path = solver_dir / "c10_constraint_equations.txt"  # 定位运行时 CE 列表以证明没有残留约束方程。
    cp_path = solver_dir / "c10_coupled_dof.txt"  # 定位运行时 CP 集合及成员节点清单。
    d_path = solver_dir / "c10_displacement_constraints.txt"  # 定位运行时显式位移约束清单。
    static_path = solver_dir / "c10_static_energy_mass_reaction.txt"  # 定位 LS1/LS2、能量、质量和竖向反力摘要。
    history_path = solver_dir / "c10_ls1_energy_history.csv"  # 定位全部已接受 LS1 结果集能量历程。
    result_path = solver_dir / f"{manifest['jobname']}.rst"  # 定位静力求解结果文件。
    equilibrium_db_path = solver_dir / f"{manifest['jobname']}_eq.db"  # 定位 APDL 内部门禁通过后保存的平衡数据库。
    restart_database_path = solver_dir / f"{manifest['jobname']}.rdb"  # 定位线性扰动续算所需的多帧重启动数据库。
    load_history_path = solver_dir / f"{manifest['jobname']}.ldhi"  # 定位线性扰动续算所需的载荷历史索引。
    restart_state_paths = sorted((path for path in solver_dir.iterdir() if re.fullmatch(rf"{re.escape(str(manifest['jobname']))}\.r\d{{3}}", path.name, re.IGNORECASE) is not None), key=lambda path: path.name.lower())  # 收集并稳定排序本 job 的多帧重启动状态文件族。
    require(len(restart_state_paths) >= 1, "未生成任何 .rNNN 多帧重启动状态，后续线性扰动模态不可续算")  # 静力诊断虽可独立完成，但本修复目标要求保留可验证的扰动入口。
    required_restart_name = f"{manifest['jobname']}.r002".lower()  # 按计划的 RESTART,2,1,PERTURB 固定 LS2 重启动文件名。
    require(any(path.name.lower() == required_restart_name for path in restart_state_paths), f"缺少线性扰动所需 LS2 重启动点：{required_restart_name}")  # 单有 R001 不能证明载荷步二子步一可重启动。
    required_files = [gate_path, topology_path, mpc_path, ce_path, cp_path, d_path, static_path, history_path, result_path, equilibrium_db_path, restart_database_path, load_history_path, *restart_state_paths]  # 汇总静力、约束与后续扰动续算必须存在的权威工件。
    for required_path in required_files:  # 逐项关闭存在性和非空门禁。
        require(required_path.is_file() and required_path.stat().st_size > 0, f"缺少或为空的静力工件：{required_path}")  # 任一原始工件缺失即拒绝发布通过。
    started_at = datetime.fromisoformat(str(launch["started_at_utc"]))  # 解析带时区的启动时刻供结果新鲜度检查。
    for result_artifact in [result_path, equilibrium_db_path, restart_database_path, load_history_path, *restart_state_paths]:  # 对二进制求解和重启动工件逐项检查生成时刻与稳定性。
        require(result_artifact.stat().st_mtime >= started_at.timestamp(), f"二进制工件早于本次启动时刻：{result_artifact}")  # 阻断旧文件被复制进新运行冒充本次结果。
        require(file_is_stable(result_artifact), f"二进制工件仍在变化：{result_artifact}")  # 锁消失后再次确认每个大文件已停止写入。
    gate_text = gate_path.read_text(encoding="utf-8", errors="strict").strip()  # 严格读取并去除 MAPDL 对齐空格和末尾换行。
    gate_check = gate_text == "STATUS=STATIC_DIAGNOSTIC_GATES_PASSED PHASE=STATIC_ONLY_COMPLETE"  # 只接受静力专用终态，拒绝 RUNNING 或任一 REJECTED 原因。
    topology = parse_topology(topology_path.read_text(encoding="utf-8", errors="strict"))  # 解析运行时模型规模和类型数量。
    expected_topology = {"nodes": EXPECTED_NODE_COUNT, "elements": EXPECTED_ELEMENT_COUNT, **{f"TYPE{type_id}": count for type_id, count in EXPECTED_TYPE_COUNTS.items()}}  # 构造冻结拓扑目标对象。
    topology_checks = {"exact_counts": topology == expected_topology, "type_sum_equals_elements": sum(topology[f"TYPE{type_id}"] for type_id in EXPECTED_TYPE_COUNTS) == topology["elements"]}  # 同时要求逐项相等和类型合计闭合。
    topology_checks["passed"] = all(topology_checks.values())  # 形成运行时拓扑总门。
    mpc_rows = parse_mpc_rows(mpc_path)  # 解析全部 MPC184 数值数据行。
    mpc_ids = [row[0] for row in mpc_rows]  # 提取元素 ID 有序列表。
    mpc_types = [row[1] for row in mpc_rows]  # 提取对应 TYPE 列有序列表。
    parent_run = (RUNS_ROOT / str(manifest["parent_run"])).resolve()  # 定位清单冻结的 C10 单层连接父运行。
    require(parent_run.parent == RUNS_ROOT.resolve() and parent_run.is_dir(), "父运行路径越界或不存在")  # 限定父谱系只能来自相邻唯一运行目录。
    parent_entries = parse_hash_ledger(parent_run / "artifact_hashes.sha256", parent_run)  # 读取父运行不可变工件账本供连接映射身份复核。
    parent_mapping_relative = "qa/connection_mapping.csv"  # 固定逐条工程连接映射在父运行中的相对位置。
    require(parent_mapping_relative in parent_entries, "父运行账本未包含连接映射 CSV")  # 禁止使用未受哈希保护的映射表。
    parent_mapping_path = parent_run / Path(parent_mapping_relative)  # 定位父工程连接映射原件。
    require(parent_mapping_path.is_file() and sha256_file(parent_mapping_path) == parent_entries[parent_mapping_relative], "父连接映射缺失或哈希漂移")  # 复算映射原始字节并关闭父谱系门。
    parent_main_relative = "input_snapshot/c10_mpc_only_main.inp"  # 固定父 C10 主输入快照的账本相对路径。
    require(parent_main_relative in parent_entries and parent_entries[parent_main_relative] == str(manifest["parent_main_sha256"]), "父主输入清单摘要与父账本不一致")  # 核对本静力运行声明的直接父输入身份。
    require(sha256_file(parent_run / Path(parent_main_relative)) == str(manifest["parent_main_sha256"]), "父主输入当前字节与清单摘要不一致")  # 独立复算父输入防止父运行事后漂移。
    expected_mpc_mapping, parent_implementation_counts = parse_expected_mpc_mapping(parent_mapping_path)  # 从受父账本保护的工程映射提取主从关系和精确语义计数。
    runtime_mpc_mapping = [(row[0], row[2], row[3]) for row in mpc_rows]  # 从运行时 ELLIST 提取元素 ID、I 节点和 J 节点有向映射。
    finite_input_path = solver_dir / "apply_finite_gates_and_passages_v2.inp"  # 定位实际定义 TYPE72 与 5,078 个刚臂的冻结 include。
    child_input_mpc_mapping = parse_expected_mpc_input(finite_input_path)  # 从子准备账本直接锚定的实际 EN 命令提取第一来源主从映射。
    finite_input_commands = [line.split("!", maxsplit=1)[0].strip().upper().replace(" ", "") for line in finite_input_path.read_text(encoding="utf-8", errors="strict").splitlines()]  # 规范化非注释 APDL 命令供 KEYOPT 唯一性检查。
    mpc_checks = {"row_count_5078": len(mpc_rows) == EXPECTED_TYPE_COUNTS[72], "continuous_expected_ids": mpc_ids == list(range(EXPECTED_MPC_FIRST_ID, EXPECTED_MPC_LAST_ID + 1)), "all_type72": all(type_id == 72 for type_id in mpc_types), "runtime_pairs_match_child_hashed_input": runtime_mpc_mapping == child_input_mpc_mapping, "runtime_pairs_match_parent_engineering_mapping": runtime_mpc_mapping == expected_mpc_mapping, "parent_semantics_1954_all_3124_uxyz": parent_implementation_counts == {"MPC184_TYPE72_DIRECT_ELIMINATION_RIGID_BEAM": 1954, "MPC184_TYPE72_DIRECT_ELIMINATION_PROJECTED_TO_TRANSLATION_ONLY_SLAVE": 3124}, "type72_definition_unique": finite_input_commands.count("ET,72,MPC184") == 1, "rigid_beam_keyopt_unique": finite_input_commands.count("KEYOPT,72,1,1") == 1, "direct_elimination_keyopt_unique": finite_input_commands.count("KEYOPT,72,2,0") == 1, "geometric_stiffness_keyopt_unique": finite_input_commands.count("KEYOPT,72,5,0") == 1, "forbidden_type73_definition_absent": all(not command.startswith("ET,73,") for command in finite_input_commands)}  # 验证数量、ID、子输入与父工程双重映射及直接消元刚臂定义。
    mpc_checks["passed"] = all(mpc_checks.values())  # 形成单层连接运行时总门。
    ce_text = ce_path.read_text(encoding="utf-8", errors="replace")  # 读取运行时约束方程列表以检查零 CE 合同。
    ce_checks = {"no_constraint_equations_message_unique": ce_text.upper().count("NO CONSTRAINT EQUATIONS TO LIST.") == 1, "constraint_equation_rows_absent": re.search(r"CONSTRAINT EQUATION\s*=\s*\d+", ce_text, re.IGNORECASE) is None}  # 要求明确零 CE 消息且不存在任何方程记录。
    ce_checks["passed"] = all(ce_checks.values())  # 形成运行时 CE 总门。
    downpull_input_path = solver_dir / "apply_mct_downpull_equivalent_xlong.inp"  # 定位定义全部 12 个 CP 集的冻结 include。
    expected_cp_rows = parse_expected_cp_input(downpull_input_path)  # 从受准备账本保护的输入提取批准 CP 集合。
    runtime_cp_rows = parse_runtime_cp(cp_path)  # 从运行时 CPLIST 解析实际 CP 集合及成员。
    cp_nodes = {node for _, _, nodes in runtime_cp_rows for node in nodes}  # 汇总全部运行时 CP 成员节点供连接端点重叠检查。
    mpc_endpoint_nodes = {node for row in mpc_rows for node in (row[2], row[3])}  # 汇总全部 TYPE72 主从端点节点。
    cp_checks = {"exact_frozen_cp_mapping": runtime_cp_rows == expected_cp_rows, "set_count_12": len(runtime_cp_rows) == 12, "set_ids_60000_to_60011": [row[0] for row in runtime_cp_rows] == list(range(60000, 60012)), "each_set_has_17_nodes": all(len(row[2]) == 17 for row in runtime_cp_rows), "mpc_endpoint_cp_overlap_absent": len(mpc_endpoint_nodes & cp_nodes) == 0}  # 验证 CP 数量、方向、成员和与连接端点的禁止重叠。
    cp_checks["passed"] = all(cp_checks.values())  # 形成运行时 CP 总门。
    d_input_paths = [solver_dir / "apply_mct_constraints_xlong.inp", solver_dir / "apply_modal_roty_stabilization_xlong.inp", downpull_input_path]  # 按三类边界来源收集准备账本已冻结的显式 D 命令。
    expected_d_rows = parse_expected_d_inputs(d_input_paths)  # 提取全部批准节点、方向和值约束。
    runtime_d_rows = parse_runtime_d(d_path)  # 解析 MAPDL 实际 DLIST 约束。
    d_label_counts = {label: sum(1 for _, row_label, _ in runtime_d_rows if row_label == label) for label in ("UX", "UY", "UZ", "ROTY")}  # 统计四个批准自由度方向的运行时约束数量。
    d_checks = {"exact_frozen_d_mapping": sorted(runtime_d_rows) == sorted(expected_d_rows), "row_count_3968": len(runtime_d_rows) == 3968, "exact_label_counts": d_label_counts == {"UX": 180, "UY": 464, "UZ": 464, "ROTY": 2860}, "all_values_zero": all(math.isclose(value, 0.0, rel_tol=0.0, abs_tol=0.0) for _, _, value in runtime_d_rows)}  # 验证运行时边界与冻结输入逐条相同且计数闭合。
    d_checks["passed"] = all(d_checks.values())  # 形成运行时显式位移约束总门。
    static_text = static_path.read_text(encoding="utf-8", errors="strict")  # 严格读取静力机器摘要。
    values = {label: scalar(static_text, label) for label in ("LS1_CNVG", "LS2_CNVG", "LS2", "TIME2", "SENE1", "STEN1", "RATIO1", "STATIC_NSET", "LS1_HISTORY_COUNT", "PEAK_SUBSTEP", "PEAK_TIME", "LS1_HISTORY_PEAK_ABS_STEN_OVER_SENE", "SENE2", "STEN2", "RATIO2", "MASS", "EXPECTED", "ABS_ERROR", "UZ", "RF_EXPECTED", "RF_ACTUAL", "RF_ERROR", "RF_RELATIVE_ERROR")}  # 一次提取全部唯一静力 QA 标量。
    history_rows = parse_history(history_path)  # 读取全部已接受 LS1 结果集。
    history_count = len(history_rows)  # 统计 AUTOTS 实际接受的 LS1 子步数。
    history_times = [row[2] for row in history_rows]  # 提取伪时间序列用于严格递增和终点检查。
    history_reported_ratios = [abs(row[5]) for row in history_rows]  # 提取 MAPDL CSV 报告的每个结果集 |STEN/SENE| 供一致性核对。
    history_recomputed_ratios = [abs(row[4]) / max(abs(row[3]), 1.0e-30) for row in history_rows]  # 仅由 SENE 与 STEN 独立复算每行无量纲能量比。
    history_peak_index = max(range(history_count), key=lambda index: history_recomputed_ratios[index]) if history_count > 0 else -1  # 按独立复算值定位全历程峰值行；空历史使用拒绝哨兵。
    load_step_values_are_exact_integers = all(math.isclose(row[0], 1.0, rel_tol=0.0, abs_tol=1.0e-12) for row in history_rows)  # 禁止四舍五入把非整数载荷步误判为 1。
    substep_values_are_exact_integers = all(math.isclose(row[1], float(index), rel_tol=0.0, abs_tol=1.0e-12) for index, row in enumerate(history_rows, start=1))  # 要求 CSV 子步号逐行精确为一开始的整数序列。
    reported_history_ratios_match_recomputation = all(math.isclose(reported, recomputed, rel_tol=1.0e-10, abs_tol=1.0e-30) for reported, recomputed in zip(history_reported_ratios, history_recomputed_ratios, strict=True))  # 防止错误 RATIO 列与错误峰值自洽地伪造通过。
    history_endpoint_matches_summary = history_count > 0 and math.isclose(values["SENE1"], history_rows[-1][3], rel_tol=1.0e-10, abs_tol=1.0e-6) and math.isclose(values["STEN1"], history_rows[-1][4], rel_tol=1.0e-10, abs_tol=1.0e-12) and math.isclose(abs(values["RATIO1"]), history_recomputed_ratios[-1], rel_tol=1.0e-10, abs_tol=1.0e-30)  # 要求 LS1 摘要端点与历程末行由原始能量到比值全部闭合。
    expected_ls1_substep_minimum = int(load_path_identity["ls1_accepted_substep_minimum"])  # 从已自检的模式合同取得 LS1 最少接受子步数，避免报告与门禁重复分支。
    expected_ls1_substep_maximum = int(load_path_identity["ls1_accepted_substep_maximum"])  # 从已自检的模式合同取得 LS1 最多接受子步数。
    fixed_static_result_set_count = load_path_identity["fixed_static_result_set_count"]  # 读取形成态固定结果集数；旧继承路径以 None 表示动态合同。
    expected_static_result_set_count = int(fixed_static_result_set_count) if fixed_static_result_set_count is not None else history_count + 1  # 两类形成态均固定两结果集，旧路径要求全部 LS1 结果集再加一个 LS2 结果集。
    single_step_point_exact = (not single_step_load_path_mode) or (history_count == 1 and math.isclose(history_rows[0][0], 1.0, rel_tol=0.0, abs_tol=1.0e-12) and math.isclose(history_rows[0][1], 1.0, rel_tol=0.0, abs_tol=1.0e-12) and math.isclose(history_rows[0][2], 1.0, rel_tol=0.0, abs_tol=1.0e-12))  # 普通形成态与 seed 形成态都必须唯一保存 LS1/子步1/time1，继承路径把该专用门标记为不适用通过。
    history_checks = {"accepted_substep_count_matches_load_path_contract": expected_ls1_substep_minimum <= history_count <= expected_ls1_substep_maximum, "formed_state_single_ls1_substep_at_time_one": single_step_point_exact, "s10_force_seed_uses_formed_state_numeric_contract": (not s10_force_seed_mode) or single_step_point_exact, "all_load_step_one_exact": load_step_values_are_exact_integers, "substep_numbers_sequential_exact": substep_values_are_exact_integers, "times_strictly_increasing": all(history_times[index] > history_times[index - 1] for index in range(1, history_count)), "final_time_one": history_count > 0 and math.isclose(history_times[-1], 1.0, rel_tol=0.0, abs_tol=1.0e-12), "positive_strain_energy": all(row[3] > 0.0 for row in history_rows), "reported_ratios_match_recomputed": reported_history_ratios_match_recomputation, "history_peak_within_limit": history_count > 0 and max(history_recomputed_ratios) <= LS1_ENERGY_RATIO_LIMIT, "reported_count_matches": math.isclose(values["LS1_HISTORY_COUNT"], float(history_count), rel_tol=0.0, abs_tol=1.0e-12), "reported_static_nset_matches_load_path": math.isclose(values["STATIC_NSET"], float(expected_static_result_set_count), rel_tol=0.0, abs_tol=1.0e-12), "formed_state_total_nset_two_exact": (not single_step_load_path_mode) or math.isclose(values["STATIC_NSET"], 2.0, rel_tol=0.0, abs_tol=1.0e-12), "endpoint_matches_summary": history_endpoint_matches_summary, "reported_peak_matches": history_count > 0 and math.isclose(values["PEAK_SUBSTEP"], history_rows[history_peak_index][1], rel_tol=0.0, abs_tol=1.0e-12) and math.isclose(values["PEAK_TIME"], history_rows[history_peak_index][2], rel_tol=0.0, abs_tol=1.0e-12) and math.isclose(values["LS1_HISTORY_PEAK_ABS_STEN_OVER_SENE"], history_recomputed_ratios[history_peak_index], rel_tol=1.0e-10, abs_tol=1.0e-30)}  # 按模式验证两类形成态单步或继承 AUTOTS 路径，同时显式证明 seed 没有绕过独立能量、端点和峰值门。
    history_checks["passed"] = all(history_checks.values())  # 形成 LS1 全历程总门。
    recomputed_ratio1 = abs(values["STEN1"]) / max(abs(values["SENE1"]), 1.0e-30)  # 由 LS1 原始能量独立复算端点稳定化比。
    recomputed_ratio2 = abs(values["STEN2"]) / max(abs(values["SENE2"]), 1.0e-30)  # 由 LS2 原始能量独立复算保持步稳定化比。
    recomputed_mass_absolute_error = abs(values["MASS"] - values["EXPECTED"])  # 由摘要质量与期望值独立复算非负绝对误差，单位 tonne。
    recomputed_expected_reaction = values["MASS"] * GRAVITY_MM_PER_S2  # 独立按求解质量和 ACEL 复算竖向重力，单位 N。
    recomputed_reaction_error = values["RF_ACTUAL"] - values["RF_EXPECTED"]  # 独立复算摘要使用的有符号竖向反力差，单位 N。
    recomputed_relative_error = abs(recomputed_reaction_error) / max(abs(values["RF_EXPECTED"]), 1.0)  # 独立复算相对误差并用 1 N 防止零分母。
    mass_input_path = solver_dir / "apply_dynamic_mass21_spatialized_v2.inp"  # 定位定义附加离散质量的冻结 include。
    mass_input_commands = [line.split("!", maxsplit=1)[0].strip().upper().replace(" ", "") for line in mass_input_path.read_text(encoding="utf-8", errors="strict").splitlines()]  # 规范化质量输入命令供方向等向性证据检查。
    static_checks = {"ls1_converged_exact": math.isclose(values["LS1_CNVG"], 1.0, rel_tol=0.0, abs_tol=1.0e-12), "ls2_converged_exact": math.isclose(values["LS2_CNVG"], 1.0, rel_tol=0.0, abs_tol=1.0e-12), "last_load_step_two_exact": math.isclose(values["LS2"], 2.0, rel_tol=0.0, abs_tol=1.0e-12), "time2_exact": math.isclose(values["TIME2"], 1.001, rel_tol=0.0, abs_tol=1.0e-12), "ls1_positive_sene": values["SENE1"] > 0.0, "ls1_ratio_matches_recomputed": math.isclose(abs(values["RATIO1"]), recomputed_ratio1, rel_tol=1.0e-10, abs_tol=1.0e-30), "ls1_energy_ratio_within_limit": recomputed_ratio1 <= LS1_ENERGY_RATIO_LIMIT, "ls2_positive_sene": values["SENE2"] > 0.0, "ls2_ratio_matches_recomputed": math.isclose(abs(values["RATIO2"]), recomputed_ratio2, rel_tol=1.0e-10, abs_tol=1.0e-30), "ls2_energy_ratio_within_limit": recomputed_ratio2 <= LS2_ENERGY_RATIO_LIMIT, "mass21_single_isotropic_mass_definition": mass_input_commands.count("ET,71,MASS21") == 1 and mass_input_commands.count("KEYOPT,71,3,2") == 1, "mass_matches_frozen_ledger": abs(values["MASS"] - EXPECTED_MASS_TONNE) <= MASS_ABSOLUTE_TOLERANCE_TONNE and recomputed_mass_absolute_error <= MASS_ABSOLUTE_TOLERANCE_TONNE, "mass_abs_error_nonnegative_and_recomputed": values["ABS_ERROR"] >= 0.0 and math.isclose(values["ABS_ERROR"], recomputed_mass_absolute_error, rel_tol=1.0e-9, abs_tol=1.0e-12), "mass_expected_field_matches": math.isclose(values["EXPECTED"], EXPECTED_MASS_TONNE, rel_tol=0.0, abs_tol=1.0e-9), "uz_support_count_464_exact": math.isclose(values["UZ"], 464.0, rel_tol=0.0, abs_tol=1.0e-12), "rf_expected_recomputed": math.isclose(values["RF_EXPECTED"], recomputed_expected_reaction, rel_tol=1.0e-12, abs_tol=1.0e-6), "rf_error_recomputed": math.isclose(values["RF_ERROR"], recomputed_reaction_error, rel_tol=1.0e-9, abs_tol=1.0e-6), "rf_relative_error_recomputed": math.isclose(values["RF_RELATIVE_ERROR"], recomputed_relative_error, rel_tol=1.0e-9, abs_tol=1.0e-15), "vertical_gravity_reaction_closure": values["RF_RELATIVE_ERROR"] <= VERTICAL_REACTION_RELATIVE_TOLERANCE}  # 验证 LS1/LS2、独立能量复算、等向质量证据和仅竖向重力反力闭合。
    static_checks["passed"] = all(static_checks.values())  # 形成静力机器摘要总门。
    check_groups = {"log": log_checks, "err": err_checks, "mntr": mntr_checks, "topology": topology_checks, "mpc184": mpc_checks, "ce": ce_checks, "cp": cp_checks, "d": d_checks, "history": history_checks, "static": static_checks}  # 汇总日志、原生实际增量路径及全部带 passed 字段的独立检查组供统一失败定位。
    failed_checks = [f"{group_name}.{check_name}" for group_name, checks in check_groups.items() for check_name, passed in checks.items() if check_name != "passed" and passed is not True]  # 收集每个实际失败的精确组名与键名。
    if not gate_check:  # APDL 内部门禁文本不通过时补充唯一可读失败键。
        failed_checks.append("gate.exact_static_terminal_status")  # 把 RUNNING 或 REJECTED 状态显式纳入异常原因。
    overall_passed = len(failed_checks) == 0 and all(bool(checks["passed"]) for checks in check_groups.values())  # 只有无失败键且每组总门为真时才允许发布。
    require(overall_passed, f"静力诊断未通过硬门：{json.dumps(failed_checks, ensure_ascii=False)}")  # 失败时返回具体键，禁止再出现只有‘运行失败’而无原因的空报告。
    native_status_path = solver_dir / f"{manifest['jobname']}.stat"  # 定位 MAPDL 原生作业阶段状态文件。
    require(not native_status_path.exists(), "正常完成后仍残留 MAPDL STAT 临时状态文件，退出阶段未闭合")  # 实证正常 RUN COMPLETED 会移除 STAT；该文件残留只作为强停或异常退出证据，不能被成功分支要求存在。
    preparation_ledger_path = run_dir / "artifact_hashes.sha256"  # 定位已经逐项复算通过的准备态账本原件。
    raw_paths = [output_path, error_path, native_monitor_path, gate_path, topology_path, mpc_path, ce_path, cp_path, d_path, static_path, history_path, result_path, equilibrium_db_path, restart_database_path, load_history_path, *restart_state_paths, preparation_ledger_path]  # 汇总静力、约束、原生实际增量路径、结果、扰动续算和准备谱系原件；正常退出后不存在的 STAT 不进入成功账本。
    raw_hash_cache = {path.resolve(): sha256_file(path) for path in raw_paths}  # 对每项原始发布工件只计算一次最终 SHA-256，供 raw manifest 与最终账本共同复用。
    output_hash = raw_hash_cache[output_path.resolve()]  # 从单次原始哈希缓存取得主 OUT 摘要，保证 verification、raw manifest 与 ledger 完全同值。
    raw_manifest = {"schema_version": 2, "run_name": run_dir.name, "file_count": len(raw_paths), "files": [{"path": str(path), "sha256": raw_hash_cache[path.resolve()], "size_bytes": path.stat().st_size} for path in raw_paths]}  # 记录每项发布原件的一致摘要和字节数。
    restart_inventory = {"status": "PRESERVED_AND_HASHED_NOT_YET_RESUME_TESTED", "rdb": str(restart_database_path), "ldhi": str(load_history_path), "rnnn_count": len(restart_state_paths), "rnnn_files": [str(path) for path in restart_state_paths], "ordinary_eq_db_not_a_restart_substitute": True}  # 明确线性扰动所需文件已封存但尚未做只读重启动资格试验。
    warning_disposition = {"status": "REVIEWED_DIAGNOSTIC_WARNINGS_PRODUCTION_BLOCKED", "total": err_warning_count, "coefficient_ratio_gt_1e8": coefficient_ratio_warning_count, "moment_reference_internal_threshold": moment_reference_warning_count, "cnvtol_f_default_minref_1": cnvtol_f_default_warning_count, "cnvtol_m_default_minref_1": cnvtol_m_default_warning_count, "unclassified": warning_categories.count("UNCLASSIFIED"), "ambiguous": warning_categories.count("AMBIGUOUS"), "classification": warning_classifications, "production_implication": "CONDITIONING_SCALING_AND_EXPLICIT_MINREF_REVIEW_REQUIRED"}  # 逐类披露条件数与收敛参考值警告并阻断无条件通过语义。
    reaction_scope = "VERTICAL_GRAVITY_REACTION_CLOSURE_ONLY_NOT_FULL_GLOBAL_FORCE_MOMENT_BALANCE"  # 冻结本诊断只核对 UZ 重力反力而非六分量全局平衡的边界。
    initial_state_audit = expected_initial_state_audit  # 使用已经与 manifest 和载荷路径双向核对的初始状态审计状态，避免报告回退到旧路径固定措辞。
    load_path_contract = {"mode": load_path_mode, "ls1_accepted_substep_minimum": expected_ls1_substep_minimum, "ls1_accepted_substep_maximum": expected_ls1_substep_maximum, "ls1_final_time": 1.0, "static_result_set_count_expected": expected_static_result_set_count, "single_step_formed_state_numeric_contract": single_step_load_path_mode, "s10_force_seed_mode": s10_force_seed_mode}  # 保存机器可读的模式化 LS1 子步、终点、结果集和 seed 数值合同身份。
    bisection_disposition = "LS2_ADAPTIVE_200_TO_2000_SUBSTEPS_RECORDED_NOT_HIDDEN" if migration_load_path_mode else ("FIXED_SINGLE_FORMED_STATE_STEP_ATTEMPTS_RECORDED_NOT_HIDDEN" if single_step_load_path_mode else "ALLOWED_BY_FROZEN_LS1_AUTOTS_20_TO_200_RECORDED_NOT_HIDDEN")  # 迁移路径允许 LS2 切回至 0.05%，其他路径保持各自既有二分合同。
    if s10_force_seed_mode:  # seed 模式必须采用专用人读措辞，禁止与普通 INISTATE 配对或生产初态签认混淆。
        load_path_summary = "LS1 以 KBC=1、AUTOTS=false、NSUBST=1 将完整恒载与历史 S10 LS2 LINK180 索力诊断种子在 time=1 的单一形成态平衡点配对；LS2 为零物理增量保持，LS1+LS2 总结果集必须为 2"  # 说明 seed 与普通形成态共享数值合同但来源不同。
        initial_state_limit_summary = "历史 S10 索力来自受 legacy CERIG 约束拓扑限制的旧模型，本次迁移仅是 corrected-MPC 重平衡诊断种子；它尚未证明 corrected-MPC 初始平衡，也绝不是生产初始状态签认，production_claim_allowed=false"  # 明确 legacy CERIG 来源限制和禁止生产使用。
        seed_provenance_summary = f"诊断种子来自历史运行 `{s10_force_seed_source_run}` 的审计 `{s10_force_seed_source_audit}`；legacy CERIG 源拓扑不能直接代表当前 corrected-MPC 物理状态，迁移状态为 `{initial_state_audit}`，production_claim_allowed=false"  # 在人读包中绑定历史来源与未闭合迁移状态。
    elif migration_load_path_mode:  # 恒总荷载迁移模式使用默认 K5=0 和 200/2000/200 自适应 LS2 专用语义。
        load_path_summary = f"LS1 以 KBC=1、beta=1、NSUBST=1 恢复旧 MCT 平衡荷载位置；LS2 以 KBC=0、AUTOTS=true、NSUBST=200/2000/200 在总竖向荷载变化不超过 1E-6 N 的条件下把 beta 从 1 迁移到 0，实际接受 {len(ls2_completed_substep_numbers)} 个连续子步并到达 time=1.001"  # 说明形成态起点、恒总荷载位置迁移、自适应边界和最终端点。
        initial_state_limit_summary = "本次若通过，只证明既有 MCT 初始内力可沿已审计恒总荷载位置路径数值迁移到空间 MASS21 重力平衡；生产使用仍需独立平衡、步长敏感性和规范复核"  # 防止把单一路径数值通过冒充完整物理签认。
        seed_provenance_summary = "本模式未使用历史 S10 LS2 索力诊断种子；输入基准为默认 K5=0 固定 0.5% 运行，K5=1 运行仅作为证伪和自适应授权证据；production_claim_allowed=false"  # 明确两条源谱系角色和禁止生产声明。
    elif single_step_load_path_mode:  # 普通形成态模式继续保留既有完整 INISTATE 单步诊断语义。
        load_path_summary = "LS1 以 KBC=1、AUTOTS=false、NSUBST=1 将完整恒载与完整 INISTATE 在 time=1 的单一形成态平衡点直接配对；LS2 为零物理增量保持，LS1+LS2 总结果集必须为 2"  # 保留普通形成态的既有报告合同。
        initial_state_limit_summary = "本次形成态单步配对仅检验完整恒载与既有完整 INISTATE 的数值配对行为，不代表 MCT 初力到 APDL 初始状态的完整物理对账已经闭合"  # 保留普通形成态尚未完成物理对账的限制。
        seed_provenance_summary = "本模式未使用历史 S10 LS2 索力诊断种子；production_claim_allowed=false"  # 明确普通形成态没有借用 legacy seed 且仍不允许生产声明。
    else:  # 仅剩白名单中的旧继承 AUTOTS 模式，保持原数值和物理审计措辞。
        load_path_summary = "LS1 沿用旧 S10 斜坡加载并允许 AUTOTS 接受 20 至 200 个子步；LS2 为零物理增量保持，总结果集必须等于 LS1 接受数加 1"  # 保留旧路径的二十至二百接受子步合同。
        initial_state_limit_summary = "MCT INIFORCE/EQUI-MFORCE 与 APDL INISTATE 的物理平衡审计仍待完成"  # 保留旧继承路径的未闭合初态审计边界。
        seed_provenance_summary = "本模式未使用历史 S10 LS2 索力诊断种子；production_claim_allowed=false"  # 明确旧继承路径没有被重新包装为 seed 模式。
    load_path_convergence_summary = f"LS1 严格保存并复算 1 个形成态子步，LS2 接受 {len(ls2_completed_substep_numbers)} 个连续迁移子步，实际总结果集为 {int(round(values['STATIC_NSET']))}" if migration_load_path_mode else (f"LS1 严格保存并复算 1 个形成态子步，实际总结果集为 {int(round(values['STATIC_NSET']))}" if single_step_load_path_mode else f"LS1 保存并复算 {history_count} 个 AUTOTS 接受子步")  # 生成与迁移、其他单步或旧 AUTOTS 合同一致的收敛措辞。
    s10_force_seed_disposition = {"applicable": s10_force_seed_mode, "role": "HISTORICAL_S10_LS2_LINK180_FORCE_DIAGNOSTIC_SEED_ONLY" if s10_force_seed_mode else "NOT_APPLICABLE", "source_run": s10_force_seed_source_run, "source_audit": s10_force_seed_source_audit, "source_constraint_limitation": "HISTORICAL_S10_LEGACY_CERIG_TOPOLOGY_NOT_CURRENT_CORRECTED_MPC_PHYSICAL_APPROVAL" if s10_force_seed_mode else "NOT_APPLICABLE", "target_constraint_topology": "SINGLE_TYPE72_NO_AUX_NO_TYPE73", "seed_include_sha256": s10_force_seed_include_sha256, "source_csv_sha256": s10_force_seed_source_csv_sha256, "seed_define_count": s10_force_seed_define_count, "migration_status": initial_state_audit if s10_force_seed_mode else "NOT_APPLICABLE", "diagnostic_seed_only": s10_force_seed_mode, "production_initial_state_approved": False, "production_claim_allowed": False}  # 保存 seed 历史来源、legacy CERIG 限制、corrected-MPC 目标、迁移状态和双重生产禁用声明。
    resource_gate_exception = str(launch.get("resource_gate_exception"))  # 从实际启动记录读取资源例外而不硬编码未来运行状态。
    prelaunch_resources = launch.get("prelaunch_resources", {})  # 读取启动前内存、磁盘和冲突进程的机器门禁记录。
    gibibyte_bytes = 1024 ** 3  # 采用二进制 GiB 定义统一启动器和终结器的资源阈值换算基准。
    formal_memory_threshold_bytes = 8 * gibibyte_bytes  # 正式运行内存门固定为八 GiB 可用物理内存。
    diagnostic_memory_threshold_bytes = 4 * gibibyte_bytes  # 非生产诊断绝对下限固定为四 GiB 可用物理内存。
    disk_threshold_bytes = 50 * gibibyte_bytes  # 启动时工作盘可用空间门固定为五十 GiB。
    physical_memory_total_raw = prelaunch_resources.get("physical_memory_total_bytes")  # 读取启动器记录的物理内存总字节数原值供类型和值域复算。
    physical_memory_available_raw = prelaunch_resources.get("physical_memory_available_bytes")  # 读取启动器记录的可用物理内存字节数原值供阈值复算。
    disk_free_raw = prelaunch_resources.get("disk_free_bytes")  # 读取启动器记录的工作盘可用字节数原值供阈值复算。
    conflicting_solver_process_count_raw = prelaunch_resources.get("conflicting_solver_process_count")  # 读取启动瞬间冲突求解器进程计数原值供独占性复算。
    resource_byte_values_are_integers = all(isinstance(value, int) and not isinstance(value, bool) for value in (physical_memory_total_raw, physical_memory_available_raw, disk_free_raw))  # 要求三个资源字节值均为真正整数，拒绝布尔值或字符串伪装。
    physical_memory_total_bytes = int(physical_memory_total_raw) if resource_byte_values_are_integers else -1  # 仅在全部资源值类型有效时转换总内存，否则置负一触发失败关闭。
    physical_memory_available_bytes = int(physical_memory_available_raw) if resource_byte_values_are_integers else -1  # 仅在全部资源值类型有效时转换可用内存，否则置负一触发失败关闭。
    disk_free_bytes = int(disk_free_raw) if resource_byte_values_are_integers else -1  # 仅在全部资源值类型有效时转换磁盘余量，否则置负一触发失败关闭。
    formal_8_gib_gate_raw = prelaunch_resources.get("formal_8_gib_gate_passed")  # 读取正式八 GiB 门布尔原值供与字节数双向核对。
    diagnostic_4_gib_gate_raw = prelaunch_resources.get("diagnostic_4_gib_exception_gate_passed")  # 读取诊断四 GiB 门布尔原值供与字节数双向核对。
    disk_50_gib_gate_raw = prelaunch_resources.get("disk_50_gib_gate_passed")  # 读取五十 GiB 磁盘门布尔原值供与字节数双向核对。
    recorded_gate_booleans_are_valid = all(isinstance(value, bool) for value in (formal_8_gib_gate_raw, diagnostic_4_gib_gate_raw, disk_50_gib_gate_raw))  # 要求三个门禁标志均为 JSON 布尔而非可真值化替代类型。
    formal_8_gib_passed = formal_8_gib_gate_raw is True  # 仅把明确真布尔解释为正式八 GiB 门通过。
    expected_resource_disposition = "FORMAL_8_GIB_PASSED_DIAGNOSTIC_SCOPE_STILL_NONPRODUCTION" if formal_8_gib_passed else "FORMAL_8_GIB_FAILED_DIAGNOSTIC_ONLY"  # 按经字节复核的真实门结果派生执行器应记录的唯一处置标签。
    resource_checks = {"resource_byte_values_are_integers": resource_byte_values_are_integers, "physical_memory_values_positive_and_ordered": physical_memory_total_bytes >= physical_memory_available_bytes > 0, "recorded_gate_booleans_are_valid": recorded_gate_booleans_are_valid, "formal_8_gib_gate_matches_available_bytes": recorded_gate_booleans_are_valid and formal_8_gib_gate_raw == (physical_memory_available_bytes >= formal_memory_threshold_bytes), "diagnostic_4_gib_gate_matches_available_bytes_and_passed": recorded_gate_booleans_are_valid and diagnostic_4_gib_gate_raw == (physical_memory_available_bytes >= diagnostic_memory_threshold_bytes) and diagnostic_4_gib_gate_raw is True, "disk_50_gib_gate_matches_free_bytes_and_passed": recorded_gate_booleans_are_valid and disk_50_gib_gate_raw == (disk_free_bytes >= disk_threshold_bytes) and disk_50_gib_gate_raw is True, "conflicting_solver_process_count_is_nonnegative_integer": isinstance(conflicting_solver_process_count_raw, int) and not isinstance(conflicting_solver_process_count_raw, bool) and conflicting_solver_process_count_raw >= 0, "no_conflicting_solver_process": conflicting_solver_process_count_raw == 0, "resource_disposition_matches_actual_gate": resource_gate_exception == expected_resource_disposition}  # 由原始字节值复算四、八、五十 GiB 门，并要求类型、顺序、独占性和动态处置标签全部闭合。
    resource_checks["passed"] = all(resource_checks.values())  # 形成不依赖启动瞬间内存恰好高低的资源总门。
    require(resource_checks["passed"], f"资源记录与 SMP1 诊断门不一致：{json.dumps(resource_checks, ensure_ascii=False)}")  # 8 GiB通过或登记例外均保持诊断范围，且4 GiB、50 GiB和独占性必须通过。
    verification = {"schema_version": 2, "status": "STATIC_NUMERIC_GATES_PASSED_WITH_REVIEWED_WARNINGS_DIAGNOSTIC_ONLY", "run_name": run_dir.name, "load_path_mode": load_path_mode, "load_path_contract": load_path_contract, "solver_native_completion": {"os_exit_code_available": False, "wrapper_pid_gone": True, "matching_ansys_job_processes_gone": True, "run_lock_absent": True, "out_and_binary_artifacts_stable": True, "run_completed_marker": True, "normal_nosave_exit_marker": True, "error_summary": error_counts, "warning_summary": warning_counts}, "input_lineage": {"prepared_ledger_entry_count": len(prepared_entries), "prepared_ledger_sha256": sha256_file(preparation_ledger_path), "main_input_sha256": str(manifest["main_input_sha256"]), "mapdl_executable_sha256": str(manifest["mapdl_executable_sha256"]), "parent_ledger_sha256": sha256_file(parent_run / "artifact_hashes.sha256"), "parent_connection_mapping_sha256": sha256_file(parent_mapping_path), "child_finite_connection_input_sha256": sha256_file(finite_input_path), "finalizer_sha256": sha256_file(SCRIPT_PATH)}, "log_checks": log_checks, "err_checks": err_checks, "warning_disposition": warning_disposition, "equation_counts": equation_counts, "unique_equation_counts": unique_equation_counts, "minimum_pivots": minimum_pivots, "minimum_reported_pivot": min(minimum_pivots), "bisection_count": bisection_count, "incomplete_attempt_count": incomplete_attempt_count, "bisection_disposition": bisection_disposition, "gate_status": gate_text, "gate_status_passed": gate_check, "runtime_topology": topology, "topology_checks": topology_checks, "mpc184_checks": mpc_checks, "constraint_equation_checks": ce_checks, "coupled_dof_checks": cp_checks, "displacement_constraint_counts": d_label_counts, "displacement_constraint_checks": d_checks, "history_row_count": history_count, "history_recomputed_ratios": history_recomputed_ratios, "history_checks": history_checks, "static_values": values, "static_recomputed": {"ratio1": recomputed_ratio1, "ratio2": recomputed_ratio2, "mass_absolute_error_tonne": recomputed_mass_absolute_error, "expected_vertical_reaction_n": recomputed_expected_reaction, "vertical_reaction_error_n": recomputed_reaction_error, "vertical_reaction_relative_error": recomputed_relative_error}, "static_checks": static_checks, "mass_direction_basis": "APDL_SUMMARY_USED_MTOT_X; FROZEN_MASS21_KEYOPT_3_2_AND_STRUCTURAL_DENSITIES_SUPPORT_ISOTROPIC_X_EQUALS_Z; MTOT_Z_NOT_INDEPENDENTLY_EXPORTED", "reaction_scope": reaction_scope, "restart_inventory": restart_inventory, "main_out_sha256": output_hash, "full_bridge_modal_status": "NOT_RUN", "initial_state_equilibrium_audit": initial_state_audit, "resource_gate_exception": resource_gate_exception, "resource_checks": resource_checks, "valid_for_production": False}  # 保存可复算的载荷路径、谱系、警告、秩、主元、约束、能量和静力 QA 证据及严格使用边界。
    verification["solver_native_completion"]["native_stat_absent_after_normal_exit"] = not native_status_path.exists()  # 明确记录正常退出已移除临时 STAT，而不是把强停残留误作成功必需工件。
    verification["runtime_hard_stop_monitor"] = runtime_monitor_audit  # 纳入冻结监控代码、资源极值、方程数和无控制器抢停证据。
    verification["mntr_path_audit"] = {"checks": mntr_checks, "row_count": len(mntr_rows), "ls1_row_count": len(mntr_ls1_rows), "ls2_row_count": len(mntr_ls2_rows), "ls2_minimum_accepted_increment": min(mntr_ls2_increments) if mntr_ls2_increments else None, "ls2_maximum_accepted_increment": max(mntr_ls2_increments) if mntr_ls2_increments else None, "ls2_increment_sum": sum(mntr_ls2_increments), "ls2_maximum_attempt_number": max((int(row["attempt"]) for row in mntr_ls2_rows), default=0), "ls2_final_total_iterations": mntr_ls2_total_iterations[-1] if mntr_ls2_total_iterations else None, "mntr_sha256": raw_hash_cache[native_monitor_path.resolve()]}  # 保存原生已接受步的实际增量范围、总和、尝试、迭代和检查矩阵，完整逐行证据由已哈希 MNTR 原件承担。
    final_status = {"schema_version": 2, "run_name": run_dir.name, "status": "STATIC_DIAGNOSTIC_COMPLETED_WITH_REVIEWED_WARNINGS", "static_numeric_gates": "PASSED", "warning_status": warning_disposition["status"], "modal_status": "NOT_RUN", "load_path_mode": load_path_mode, "constraint_topology": "SINGLE_TYPE72_NO_AUX_NO_TYPE73", "equation_count": EXPECTED_EQUATION_COUNT, "minimum_pivot": min(minimum_pivots), "accepted_ls1_substep_count": history_count, "static_result_set_count": int(round(values["STATIC_NSET"])), "bisection_count": bisection_count, "vertical_gravity_reaction_relative_error": values["RF_RELATIVE_ERROR"], "reaction_scope": reaction_scope, "restart_status": restart_inventory["status"], "resource_gate_exception": resource_gate_exception, "initial_state_equilibrium_audit": initial_state_audit, "valid_for_production": False, "next_action": "MODAL_DIAGNOSTIC_ONLY_AFTER_RESTART_READABILITY_AND_RESOURCE_GATES; PHYSICAL_APPROVAL_REQUIRES_INITIAL_STATE_AND_CONDITIONING_MINREF_AUDITS"}  # 发布含载荷路径身份的条件性静力状态，并明确模态、初始状态和生产签认前置条件。
    verification["migration_path_disposition"] = {"applicable": migration_load_path_mode, "single_difference": "LS2_NSBMX_200_TO_2000_ONLY" if migration_load_path_mode else "NOT_APPLICABLE", "mpc184_keyopt5_static": int(manifest.get("mpc184_keyopt5_static", 0)) if migration_load_path_mode else None, "ls2_nsubst": [200, 2000, 200] if migration_load_path_mode else None, "accepted_ls2_substep_count": len(ls2_completed_substep_numbers) if migration_load_path_mode else None, "accepted_ls2_substep_numbers": ls2_completed_substep_numbers if migration_load_path_mode else [], "bisection_count": bisection_count if migration_load_path_mode else None, "incomplete_attempt_count": incomplete_attempt_count if migration_load_path_mode else None, "beta_start": 1.0 if migration_load_path_mode else None, "beta_end": 0.0 if migration_load_path_mode else None, "time_end": values["TIME2"] if migration_load_path_mode else None, "constant_total_vertical_correction_sum_n": "2.08526E-10" if migration_load_path_mode else None}  # 保存迁移唯一变量、接受路径、二分尝试、beta 端点和恒总荷载守恒量。
    if migration_load_path_mode:  # 恒总荷载迁移通过全部硬门时升级为专用但仍非生产的静力终态。
        verification["status"] = "STATIC_ADAPTIVE_LOAD_POSITION_MIGRATION_NUMERIC_GATES_PASSED_DIAGNOSTIC_ONLY"  # 区分 beta=0 空间质量端点通过与旧零增量保持通过。
        final_status["status"] = "STATIC_ADAPTIVE_LOAD_POSITION_MIGRATION_COMPLETED_WITH_REVIEWED_WARNINGS"  # 发布专用根状态且继续保留警告限定。
        final_status["accepted_ls2_substep_count"] = len(ls2_completed_substep_numbers)  # 记录二百至二千范围内实际接受的连续迁移子步数量。
        final_status["ls2_final_time"] = values["TIME2"]  # 记录由 APDL 摘要独立验证的 1.001 终点。
        final_status["load_position_beta_endpoint"] = 0.0  # 记录 correction include 已迁移到真实空间 MASS21 的零修正端点。
        final_status["next_action"] = "INDEPENDENT_STATIC_BALANCE_AND_STEP_SENSITIVITY_REVIEW_THEN_RESTART_READABILITY_AND_PRESTRESSED_MODAL_DIAGNOSTIC"  # 静力通过后先做独立保证，再进入重启动与预应力模态。
    verification["s10_force_seed_disposition"] = s10_force_seed_disposition  # 在完整机器验证包中披露历史 S10 seed 来源、legacy CERIG 限制和迁移未签认状态。
    verification["production_claim_allowed"] = False  # 机器验证包显式冻结生产声明为禁止，不能只依赖 valid_for_production 的间接含义。
    final_status["s10_force_seed_disposition"] = s10_force_seed_disposition  # 在根级终态中重复关键 seed 限制，避免下游只读 status 时遗漏物理边界。
    final_status["production_claim_allowed"] = False  # 根级最终状态显式声明本诊断绝不允许生产初始状态或生产分析结论。
    qa_dir = run_dir / "qa"  # 使用准备阶段已建立的 QA 目录保存最终机器复核。
    raw_manifest_path = qa_dir / "static_raw_result_manifest.json"  # 定位原始结果哈希清单输出。
    verification_path = qa_dir / "static_solution_verification.json"  # 定位完整静力硬门输出。
    status_path = run_dir / "C10_static_final_status.json"  # 定位根级最终静力状态。
    packet_path = run_dir / "result_packet_final.md"  # 定位人读最终结果包且不覆盖准备阶段说明。
    packet = f"# C10 单层 TYPE72 全桥静力诊断结果\n\n状态：`{final_status['status']}`；数值硬门通过，但不是生产签认。\n\n- 载荷路径：`{load_path_mode}`。{load_path_summary}。\n- 连接与边界：5,078 个单层 TYPE72，辅助节点=0、TYPE73=0、CE=0、CP=12 组、D=3,968 条；运行时主从节点和冻结工程映射逐条一致。\n- 方程数：全部 {len(equation_counts)} 次组装均为 {EXPECTED_EQUATION_COUNT}，未发生旧模型的 +7,128 跳变。\n- 主元：最小报告值 {min(minimum_pivots):.9g}，small/zero/negative pivot 均为零。\n- 收敛：LS1、LS2 和 APDL 静力内部 QA 均通过；{load_path_convergence_summary}；求解日志记录 {bisection_count} 次二分尝试并已如实披露。\n- 已审阅警告：coefficient-ratio>{1.0e8:.0e} 共 {coefficient_ratio_warning_count} 次，力矩参考阈值内部接管 {moment_reference_warning_count} 次，F/M 默认 MINREF 各 {cnvtol_f_default_warning_count}/{cnvtol_m_default_warning_count} 次；未知警告为 0。这些警告阻断生产签认。\n- 质量：{values['MASS']:.12g} tonne；独立复算绝对误差 {recomputed_mass_absolute_error:.6e} tonne。摘要使用 MTOT,X，本运行由冻结的等向 MASS21 和结构密度支持 X=Z，但未独立输出 MTOT,Z。\n- 竖向重力反力相对误差：{values['RF_RELATIVE_ERROR']:.6e}。该工件只证明 UZ 支承竖向反力闭合，不包含完整 Fx/Fy/Mx/My/Mz 平衡。\n- 重启动：`.rdb/.ldhi/{len(restart_state_paths)} 个 .rNNN` 已封存哈希但尚未做只读 RESUME/PERTURB 可用性试验；`_eq.db` 不能替代多帧重启动文件。\n- 资源边界：{resource_gate_exception}，`valid_for_production=false`。\n- 未完成：预应力模态未运行；{initial_state_limit_summary}；条件尺度与显式 MINREF 处置仍待完成。\n\n机器硬门见 `qa/static_solution_verification.json`，原始结果哈希见 `qa/static_raw_result_manifest.json`。\n"  # 从已完成迁移专用分支的最终状态动态生成报告，保证人读状态与最终 JSON 精确一致且不越过物理审计边界。
    packet = packet.replace("数值硬门通过，但不是生产签认。", "数值硬门通过，但不是生产签认；`production_claim_allowed=false`。", 1)  # 在人读包首段显式冻结生产声明为禁止且只替换唯一状态短语。
    packet = packet.replace("- 载荷路径：", f"- 初始状态种子边界：{seed_provenance_summary}。\n- 载荷路径：", 1)  # 在载荷路径前插入历史 seed 来源或不适用声明，确保 legacy CERIG 限制可见。
    rendered_raw_manifest = json.dumps(raw_manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 在产生文件前完成原始结果清单序列化。
    rendered_verification = json.dumps(verification, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 在产生文件前完成机器验证包序列化。
    rendered_status = json.dumps(final_status, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 在产生文件前完成最终状态提交标志序列化。
    release_existing_paths = {path.resolve() for path in raw_paths} | {(run_dir / Path(relative_text)).resolve() for relative_text in prepared_entries} | {(run_dir / "runtime_launch.json").resolve(), (run_dir / "launch_command_smp1.txt").resolve()}  # 以显式白名单收集准备态、运行身份和批准原始结果，排除 EMAT/ESAV/OSAV/DSP 等临时垃圾。
    if launch_claim_path.is_file():  # 新版执行链存在 Popen 前认领原件时把它纳入最终发布账本，历史无认领运行不伪造条目。
        release_existing_paths.add(launch_claim_path.resolve())  # 冻结已经通过三方核对的不可覆盖启动权声明摘要。
    if isinstance(process_identity_path, Path):  # 新版执行链存在成功增强身份工件时把它纳入最终发布账本。
        release_existing_paths.add(process_identity_path.resolve())  # 冻结已经通过 PID、创建时刻、二进制和命令行四重核对的身份原件。
    if migration_load_path_mode:  # 自适应迁移把监控认领、完整样本流水和自然退出终态全部列入最终发布白名单。
        require(isinstance(runtime_monitor_claim_path, Path) and isinstance(runtime_monitor_samples_path, Path) and isinstance(runtime_monitor_final_path, Path), "迁移监控发布路径对象未完成初始化")  # 关闭类型与分支初始化门。
        release_existing_paths.update({runtime_monitor_claim_path.resolve(), runtime_monitor_samples_path.resolve(), runtime_monitor_final_path.resolve()})  # 冻结控制器未抢停、资源硬线和方程秩全过程证据。
    for release_path in release_existing_paths:  # 在计算最终账本前逐项验证白名单工件仍存在。
        require(release_path.is_file(), f"最终发布白名单工件缺失：{release_path}")  # 防止集合并入不存在路径后生成虚假账本。
    release_hash_cache = dict(raw_hash_cache)  # 从原始结果单次哈希缓存开始构造全部既有发布工件摘要。
    for release_path in release_existing_paths:  # 仅对不属于 raw manifest 的准备态和启动工件补算一次摘要。
        if release_path not in release_hash_cache:  # 已在 raw 缓存中的大文件禁止二次哈希造成时间窗不一致。
            release_hash_cache[release_path] = sha256_file(release_path)  # 为当前较小谱系工件补充最终摘要。
    for relative_text, expected_hash in prepared_entries.items():  # 使用最终发布阶段已经取得的摘要再次关闭准备态文件的时间窗一致性门。
        prepared_path = (run_dir / Path(relative_text)).resolve()  # 恢复当前准备态账本条目的规范绝对路径。
        require(release_hash_cache[prepared_path] == expected_hash, f"准备态工件在早期复核与最终发布之间发生漂移：{prepared_path}")  # 禁止最终 ledger 接受与准备账本不同的新字节。
    ledger_entries = {path.relative_to(run_dir).as_posix(): release_hash_cache[path] for path in release_existing_paths}  # 从统一缓存生成既有白名单账本条目。
    rendered_final_artifacts = {raw_manifest_path: rendered_raw_manifest, verification_path: rendered_verification, packet_path: packet, status_path: rendered_status}  # 汇总四项尚未落盘的最终文本供摘要计算。
    for target_path, rendered_text in rendered_final_artifacts.items():  # 对最终文本直接按待写 UTF-8 字节计算摘要。
        ledger_entries[target_path.relative_to(run_dir).as_posix()] = hashlib.sha256(rendered_text.encode("utf-8")).hexdigest()  # 使最终账本可与批量暂存字节逐项闭合。
    final_ledger_path = run_dir / "artifact_hashes.final.sha256"  # 定位不包含自身摘要的最终发布账本。
    final_ledger_text = "\n".join(f"{digest}  {relative_text}" for relative_text, digest in sorted(ledger_entries.items())) + "\n"  # 按相对路径稳定排序渲染最终白名单账本。
    rendered_outputs = {raw_manifest_path: rendered_raw_manifest, verification_path: rendered_verification, packet_path: packet, final_ledger_path: final_ledger_text, status_path: rendered_status}  # 按原始清单、验证包、人读包、账本、最终状态顺序构造事务；状态最后作为提交标志。
    write_new_batch(rendered_outputs)  # 统一预检、暂存、原子替换并在异常时回滚全部本次文件。
    return status_path  # 返回已发布的根级最终静力状态路径。


def parse_arguments() -> argparse.Namespace:  # 无输入并返回必需的静力诊断目录参数。
    parser = argparse.ArgumentParser(description="Finalize one completed C10 single-TYPE72 full-bridge static diagnostic without starting MAPDL.")  # 创建只读验收接口。
    parser.add_argument("--run-dir", required=True, type=Path, help="C10_STATIC_DIAGNOSTIC run directory to verify and finalize.")  # 要求调用者显式指定唯一运行，禁止选择 latest。
    return parser.parse_args()  # 解析并返回命令行命名空间。


def main() -> None:  # 无输入和返回值；执行独立验收并向标准输出写机器摘要。
    arguments = parse_arguments()  # 读取受控静力运行目录参数。
    status_path = finalize(arguments.run_dir)  # 执行全部谱系、日志、拓扑、能量、质量和竖向反力门禁。
    status = read_json(status_path)  # 重新读取落盘 JSON 以确认最终工件可解析。
    print(json.dumps({"status_path": str(status_path), "status": status["status"], "modal_status": status["modal_status"], "valid_for_production": status["valid_for_production"]}, ensure_ascii=False))  # 输出精简机器摘要供调用者确认。


if __name__ == "__main__":  # 仅直接执行本文件时进入静力最终化流程，导入时不产生文件写入。
    main()  # 执行一次 fail-closed 的 C10 静力诊断最终化。
