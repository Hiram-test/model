"""证明 A30 全部非圆截面轴基线与已完成 A10 求解输入相同，并复核 A10 实际结果完整性。"""  # 模块只建立输入/结果等价证据，不复制大文件也不启动 MAPDL。

from __future__ import annotations  # 延迟解析类型注解，保持脚本在当前 Python 运行时稳定。

import argparse  # 解析可选的确定性 A30 目录名。
import csv  # 读取 A20 正式方向台账和 A10 模态/能量 CSV。
import hashlib  # 计算输入、结果和生成产物的 SHA-256 身份。
import json  # 读取 A10/A20 清单并写 A30 状态与门禁。
import math  # 检查频率和能量数值是否有限。
import re  # 约束运行目录名并识别主 OUT 中的完成/错误标记。
from datetime import datetime, timezone  # 生成 UTC 微秒运行身份。
from pathlib import Path  # 使用显式路径访问冻结运行包。
from typing import Any  # 描述异构 JSON/CSV 载荷。


SCRIPT_PATH = Path(__file__).resolve()  # 固定本脚本绝对路径供自哈希使用。
PROJECT_DIR = SCRIPT_PATH.parents[1]  # 指向 V2.0 项目根目录。
ULTRA_RUNS_DIR = PROJECT_DIR / "ultra_runs"  # 指向正式 Ultra 运行包根目录。
A10_RUN_NAME = "A10_H175_AXIS_20260715T172214962299Z"  # 已完成 80 阶求解的 H175 单变量运行身份。
A20_RUN_NAME = "A20_RHS5030_AXIS_20260715T214637371159Z"  # 已封板为零差异的 RHS50×30 方向门禁身份。
A10_DIR = ULTRA_RUNS_DIR / A10_RUN_NAME  # A10 运行目录绝对路径。
A20_DIR = ULTRA_RUNS_DIR / A20_RUN_NAME  # A20 正式台账目录绝对路径。
RUN_PREFIX = "A30_ALL_AXES"  # 运行目录前缀对应试算矩阵的 A30_ALL_AXES。
RUN_NAME_PATTERN = re.compile(r"A30_ALL_AXES_\d{8}T\d{12}Z\Z", re.ASCII)  # 只允许 UTC 微秒格式的安全目录名。
EXPECTED_DEPENDENCY_COUNT = 11  # B00/A10 主输入固定包含 11 个依赖 include。
EXPECTED_MODE_COUNT = 80  # A10/A30 轴基线必须导出严格 80 阶。
EXPECTED_TARGET_COUNT = 14  # 附件 2-3 表 4-1 固定包含十四个报告目标分支。
EXPECTED_NODE_COUNT = 109086  # 冻结 V2 完整模型节点数。
EXPECTED_ELEMENT_COUNT = 172994  # 冻结 V2 完整模型单元数。
EXPECTED_RHS_COUNT = 2898  # A20 方向台账必须覆盖的 RHS50×30 数量。
EXPECTED_LINK180_COUNT = 73692  # 冻结 V2 模型的 LINK180 TYPE4 元素总数。
EXPECTED_TYPE6_COUNT = 48620  # 冻结 V2 模型的 BEAM188 TYPE6 元素总数。
EXPECTED_TYPE70_COUNT = 17679  # 冻结 V2 模型六类门架/通道 BEAM188 TYPE70 元素总数。
EXPECTED_MASS21_COUNT = 33003  # 冻结 V2 模型的 MASS21 TYPE71 元素总数。
EXPECTED_UZ_SUPPORT_COUNT = 464  # 冻结 V2 模型施加 UZ 支承的节点数。
EXPECTED_TOTAL_MASS_TONNE = 4108.46690758  # 不改质量变体的任务书冻结总质量，单位 tonne。
MASS_ABSOLUTE_TOLERANCE_TONNE = 1.0e-6  # 任务书允许的总质量绝对误差上限，单位 tonne。
REACTION_RELATIVE_TOLERANCE = 1.0e-4  # 任务书允许的重力—竖向反力相对误差上限。
LS1_ENERGY_RATIO_LIMIT = 1.0e-2  # 任务书允许的 LS1 端点绝对 STEN/SENE 上限。
LS2_ENERGY_RATIO_LIMIT = 1.0e-8  # 任务书允许的 LS2 无稳定化保持步绝对 STEN/SENE 上限。
EXPECTED_EXPLICIT_D_COUNT = 3968  # 冻结输入中显式 D 命令数，包含 2,860 个 ROTY=0。
EXPECTED_CP_COUNT = 12  # 冻结输入中旧 CP 命令数。
EXPECTED_CERIG_COUNT = 5078  # 冻结输入中旧 CERIG 命令数。
EXPECTED_ROTY_ZERO_COUNT = 2860  # 冻结输入中显式 ROTY=0 的约束命令数。
EXPECTED_WARNING_COUNT = 5  # A10 主会话实际存在且已逐项处置的 warning 标记数。
EXPECTED_SUMMARY_WARNING_COUNT = 4  # MAPDL 摘要先计四条，退出后再追加一条性能 warning。
MIN_VECTOR_BYTES = 1_000_000  # 每份全桥 PRNSOL 向量至少一百万字节，防止空壳文件通过计数。
A10_FINAL_STATUS = "PASS_WITH_LEGACY_LIMITATIONS"  # A10 正式 finalizer 的真实终态，保留三项工程边界。
A10_POSTRUN_GATE_PATH = A10_DIR / "qa" / "postrun_gate.json"  # A10 finalizer 写出的完整执行门禁固定路径。
A10_LEDGER_PATH = A10_DIR / "artifact_hashes.sha256"  # A10 finalizer 写出的全 run 非自引用 SHA-256 账本。
TARGET_REFERENCE_PATH = PROJECT_DIR / "post" / "reference_attachment_2_3_table4_1.csv"  # 十四目标定义的权威转录表。
EXPECTED_TARGET_IDS = ("LS1", "VA1", "LA1", "TA1", "VS1", "LS2", "TS1", "SIDE1", "SIDE2", "VA2", "LA2", "SIDE3", "TS2", "VS2")  # 十四目标内部标签及顺序。
EXPECTED_WARNING_FRAGMENTS = ("constraint equations may not be valid for elements that undergo large deflections", "coefficient ratio exceeds 1.0e8", "reference moment convergence value = 7.05020414e-02", "reference moment convergence value = 1.741355963e-03", "elapsed time exceeds the cpu time by 33%")  # 五条 warning 的规范化识别片段。


def require(condition: bool, message: str) -> None:  # 输入布尔门禁和失败说明；失败时立即终止。
    """所有等价与完整性结论均 fail-closed，禁止缺证据时创建 A30 完成包。"""  # 函数说明给出安全语义。
    if not condition:  # 只有条件为假时进入异常路径。
        raise RuntimeError(message)  # 抛出明确错误并阻止后续文件写入。


def sha256_file(path: Path) -> str:  # 输入文件路径并返回小写 SHA-256。
    """以 1 MiB 分块计算原始字节身份，适用于数 GiB 结果文件。"""  # 函数说明给出输入、输出和内存约束。
    digest = hashlib.sha256()  # 创建独立 SHA-256 累加器。
    with path.open("rb") as stream:  # 以二进制只读模式打开文件。
        while True:  # 循环直到 EOF。
            block = stream.read(1024 * 1024)  # 每次读取 1 MiB，避免一次加载大文件。
            if not block:  # 空块表示文件读取结束。
                break  # 跳出循环。
            digest.update(block)  # 把当前原始字节加入摘要。
    return digest.hexdigest()  # 返回稳定的 64 字符小写摘要。


def read_json(path: Path) -> Any:  # 输入 JSON 路径并返回解析后的 Python 对象。
    """严格按 UTF-8 读取；语法错误由 json 模块直接拒绝。"""  # 函数说明给出编码和异常策略。
    return json.loads(path.read_text(encoding="utf-8"))  # 读取并解析完整 JSON 文本。


def write_json(path: Path, payload: Any) -> None:  # 输入目标路径和可序列化对象并写格式化 JSON。
    """JSON 不支持注释，字段和值的用途由同目录 Markdown 解释。"""  # 函数说明遵守有效 JSON 约束。
    path.parent.mkdir(parents=True, exist_ok=True)  # 仅创建新 A30 包内必要父目录。
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 使用两空格缩进和末尾换行。


def read_numeric_csv(path: Path) -> list[list[float]]:  # 输入纯数值 CSV 并返回二维浮点数组。
    """忽略空行，任何非数值或非有限值均立即拒绝。"""  # 函数说明给出输入格式和门禁。
    rows: list[list[float]] = []  # 初始化按原顺序保存的数值行。
    with path.open("r", encoding="utf-8-sig", newline="") as stream:  # 兼容 UTF-8 BOM 并保持 CSV 字段边界。
        for raw_row in csv.reader(stream):  # 逐行读取所有字段。
            if not raw_row or not any(field.strip() for field in raw_row):  # 空行不属于数据记录。
                continue  # 跳过空行。
            row = [float(field.strip()) for field in raw_row]  # 将每个字段严格转换为浮点数。
            require(all(math.isfinite(value) for value in row), f"CSV 含非有限值：{path.name}")  # 拒绝 NaN 和无穷。
            rows.append(row)  # 保存当前有效数值行。
    return rows  # 返回完整二维数组。


def parse_named_numbers(path: Path) -> dict[str, float]:  # 输入 NAME=数值文本路径并返回唯一有限字段映射。
    """任务书静力表和拓扑表都采用 NAME=数值格式；重复字段、缺文件或坏值均拒绝。"""  # 函数说明给出输入结构、输出和异常边界。
    require(path.is_file(), f"数值证据缺失：{path}")  # 缺文件时不得用摘要字段代替原始证据。
    text = path.read_text(encoding="utf-8", errors="replace")  # 只读加载 MAPDL 文本并保留可搜索 ASCII 数值。
    pairs = re.findall(r"([A-Z][A-Z0-9_]*)=\s*([-+0-9.Ee]+)", text)  # 提取全部大写键和科学计数法值。
    require(bool(pairs), f"数值证据没有 NAME=VALUE 字段：{path}")  # 空解析结果不能构成门禁证据。
    require(len({key for key, _token in pairs}) == len(pairs), f"数值证据含重复字段：{path}")  # 重复键会使最终值含糊，因此立即拒绝。
    values = {key: float(token) for key, token in pairs}  # 将每个唯一字段转换为双精度浮点数。
    require(all(math.isfinite(value) for value in values.values()), f"数值证据含 NaN 或无穷：{path}")  # 所有门禁数值必须有限。
    return values  # 返回可由调用方实施字段集合与阈值检查的映射。


def resolve_a10_relative(relative_path: str) -> Path:  # 输入 A10 run 内相对路径并返回安全绝对路径。
    """拒绝绝对路径、点段逃逸和不存在文件，防止机器摘要把 A30 引向其他作业。"""  # 函数说明给出路径信任边界。
    candidate = Path(relative_path)  # 将 JSON 或账本路径文本解析为平台路径对象。
    require(not candidate.is_absolute(), f"A10 证据路径不得为绝对路径：{relative_path}")  # 正式证据必须可移植地绑定当前 run。
    resolved = (A10_DIR / candidate).resolve()  # 规范化路径以消除点段并解析实际位置。
    try:  # 尝试证明规范路径仍在固定 A10 run 下。
        resolved.relative_to(A10_DIR.resolve())  # 成功即表示没有越出 A10 根目录。
    except ValueError as exc:  # 点段或链接越界进入拒绝路径。
        raise RuntimeError(f"A10 证据路径越界：{relative_path}") from exc  # 保留异常链并停止封板。
    require(resolved.is_file(), f"A10 证据文件缺失：{resolved}")  # 只有现存普通文件可被引用。
    return resolved  # 返回已通过范围与存在性检查的绝对路径。


def file_metadata(path: Path) -> dict[str, int]:  # 输入普通文件并返回大小与纳秒修改时间。
    """轻量元数据用于 A30 只读核验前后并发漂移检测；内容身份另由 SHA-256 保证。"""  # 函数说明区分元数据与内容证据。
    require(path.is_file(), f"受保护源文件缺失：{path}")  # 源 DB/RST 或关键结果缺失时立即拒绝。
    stat = path.stat()  # 只读取得当前文件系统元数据。
    return {"size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}  # 返回整数值避免时间字符串格式差异。


def snapshot_run_file_metadata(root: Path) -> dict[str, dict[str, int]]:  # 输入 A10 或 A20 根目录并返回全部普通文件的相对路径、大小和纳秒修改时间快照。
    """快照只读取 size/mtime，不读取或改写父运行内容；调用方用完整映射相等证明 A30 QA 前后父运行未漂移。"""  # 函数说明给出输入、输出与只读约束。
    require(root.is_dir(), f"父运行目录缺失：{root}")  # 缺少任一父运行时不得建立 A30 等价包。
    snapshot: dict[str, dict[str, int]] = {}  # 初始化相对路径到不可变元数据字段的映射。
    for path in sorted(root.rglob("*")):  # 按稳定路径顺序枚举父运行目录树中的所有对象。
        if not path.is_file():  # 目录本身不承载求解或 QA 文件字节，因此不计入文件快照。
            continue  # 跳过目录并继续检查下一个对象。
        relative_path = path.relative_to(root).as_posix()  # 生成可跨平台比较的正斜杠相对路径。
        require(relative_path not in snapshot, f"父运行元数据出现重复相对路径：{root.name}/{relative_path}")  # 防止路径别名让同一键覆盖先前记录。
        snapshot[relative_path] = file_metadata(path)  # 只读记录当前文件大小与纳秒修改时间。
    require(bool(snapshot), f"父运行目录没有普通文件：{root}")  # 空目录不能作为可复用的 A10/A20 权威父运行。
    return snapshot  # 返回完整快照供执行前后严格相等比较。


def summarize_run_file_metadata(snapshot: dict[str, dict[str, int]]) -> dict[str, Any]:  # 输入完整文件元数据快照并返回计数、总字节数和确定性 SHA-256 身份。
    """摘要按相对路径排序后绑定路径、大小与 mtime_ns；不把可能很长的逐文件映射复制进 A30 包。"""  # 函数说明给出摘要算法与包体积约束。
    canonical_lines = [f"{relative_path}\0{metadata['size_bytes']}\0{metadata['mtime_ns']}" for relative_path, metadata in sorted(snapshot.items())]  # 为每个文件构造无歧义的规范记录。
    metadata_identity = hashlib.sha256("\n".join(canonical_lines).encode("utf-8")).hexdigest()  # 对规范记录序列计算稳定 SHA-256 元数据身份。
    total_bytes = sum(metadata["size_bytes"] for metadata in snapshot.values())  # 累加父运行全部普通文件的字节数供独立计数复核。
    return {"file_count": len(snapshot), "total_bytes": total_bytes, "metadata_identity_sha256": metadata_identity}  # 返回不泄漏绝对路径且足以比较前后快照的摘要。


def read_a10_ledger() -> dict[str, str]:  # 无输入并返回 A10 相对路径到 SHA-256 的全 run 账本。
    """要求 finalizer 账本每行合法、路径唯一、文件仍存在且账本自身按设计不自引用。"""  # 函数说明给出完整性边界。
    require(A10_LEDGER_PATH.is_file(), f"A10 最终账本缺失：{A10_LEDGER_PATH}")  # 没有最终账本时禁止引用大结果。
    entries: dict[str, str] = {}  # 初始化规范相对路径到小写摘要的映射。
    for line_number, raw_line in enumerate(A10_LEDGER_PATH.read_text(encoding="utf-8-sig").splitlines(), start=1):  # 逐行读取并保留一基行号。
        require(bool(raw_line.strip()), f"A10 账本第 {line_number} 行为空")  # 空行会破坏严格条目闭合。
        digest, separator, relative_path = raw_line.partition("  ")  # 按 sha256sum 双空格格式拆分摘要和路径。
        require(separator == "  " and re.fullmatch(r"[0-9a-f]{64}", digest) is not None, f"A10 账本第 {line_number} 行格式非法")  # 摘要必须为 64 位小写十六进制。
        require(relative_path and relative_path not in entries, f"A10 账本路径为空或重复：{relative_path}")  # 每个普通文件只能登记一次。
        require(relative_path != A10_LEDGER_PATH.name, "A10 账本不得自引用")  # 非自引用规则避免不可能的固定点哈希。
        resolve_a10_relative(relative_path)  # 验证当前条目确实绑定现存 A10 文件。
        entries[relative_path] = digest  # 保存当前合法条目供关键结果逐项比对。
    require(bool(entries), "A10 最终账本为空")  # 空账本不能证明任何结果完整性。
    return entries  # 返回全部合法且路径存在的账本条目。


def count_frozen_input_commands(manifest: dict[str, Any]) -> dict[str, int]:  # 输入 A10 manifest 并返回冻结依赖中的 D/CP/CERIG/ROTY=0 计数。
    """只扫描 manifest 明确登记的十一份 solver include，避免主输入回显或重复副本造成双计数。"""  # 函数说明给出计数作用域。
    dependencies = manifest.get("dependencies")  # 读取已由输入哈希门禁验证的依赖列表。
    require(isinstance(dependencies, list) and len(dependencies) == EXPECTED_DEPENDENCY_COUNT, "约束计数所需 A10 依赖不是 11 项")  # 计数前再次固定作用域。
    counts = {"D": 0, "CP": 0, "CERIG": 0, "ROTY_ZERO": 0}  # 初始化四类任务书冻结计数。
    for entry in dependencies:  # 逐份扫描实际 solver include，且每份只处理一次。
        path = A10_DIR / "solver" / str(entry["basename"])  # 定位已通过双副本哈希的实际求解文件。
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():  # 逐行读取可执行 APDL 文本。
            command = raw_line.split("!", 1)[0].strip().upper()  # 移除行尾中文注释并统一命令大小写。
            match = re.match(r"^(D|CP|CERIG)\s*,", command)  # 只识别三类冻结约束命令的行首关键字。
            if match is not None:  # 当前行属于需要统计的约束命令时进入计数分支。
                counts[match.group(1)] += 1  # 将当前命令计入对应类别。
            if re.fullmatch(r"D\s*,[^,]+\s*,\s*ROTY\s*,\s*0(?:\.0*)?", command) is not None:  # 精确识别零值 ROTY 约束。
                counts["ROTY_ZERO"] += 1  # 单独累计旧 ROTY=0 数量供漂移门禁。
    require(counts == {"D": EXPECTED_EXPLICIT_D_COUNT, "CP": EXPECTED_CP_COUNT, "CERIG": EXPECTED_CERIG_COUNT, "ROTY_ZERO": EXPECTED_ROTY_ZERO_COUNT}, f"A10 约束命令计数漂移：{counts}")  # 四类冻结数量必须同时闭合。
    return counts  # 返回已通过门禁的约束计数。


def validate_a20() -> dict[str, Any]:  # 不接收参数并返回 A20 零差异证据摘要。
    """要求 A20 正式台账 2,898/2,898 通过、改动数为零且未启动 MAPDL。"""  # 函数说明给出前置门禁。
    status_path = A20_DIR / "A20_status.json"  # 定位 A20 正式状态。
    ledger_path = A20_DIR / "rhs50_direction_ledger.csv"  # 定位任务书点名的 RHS 方向台账。
    zero_difference_path = A20_DIR / "qa" / "model_zero_difference_audit.json"  # 定位零物理差异证明。
    for path in (status_path, ledger_path, zero_difference_path):  # 枚举 A30 所需的全部 A20 证据。
        require(path.is_file(), f"A20 证据缺失：{path}")  # 任一缺失时拒绝 A30 等价封板。
    status = read_json(status_path)  # 读取 A20 状态。
    zero_difference = read_json(zero_difference_path)  # 读取 A20 零差异合同。
    require(status.get("status") == "COMPLETED_NO_SOLVE_ALREADY_CORRECT", f"A20 状态不允许进入 A30：{status.get('status')}")  # 只接受正式零差异完成状态。
    require(int(status.get("passed_element_count", -1)) == EXPECTED_RHS_COUNT, "A20 通过数量不是 2,898")  # 硬闭合 RHS 覆盖数。
    require(int(status.get("physical_change_required_count", -1)) == 0, "A20 仍要求物理改动")  # 零差异是结果复用的必要条件。
    require(status.get("mapdl_started") is False, "A20 状态错误地声称启动了 MAPDL")  # A20 是源证门禁而非新求解。
    require(zero_difference.get("byte_identical_to_b00") is True, "A20 候选输入不与 B00 字节相同")  # RHS 轴候选必须是 B00 本身。
    require(zero_difference.get("b00_input_sha256") == zero_difference.get("a20_candidate_input_sha256"), "A20 输入哈希不闭合")  # 双字段必须相等。
    with ledger_path.open("r", encoding="utf-8-sig", newline="") as stream:  # 读取正式 2,898 行 CSV。
        ledger_rows = list(csv.DictReader(stream))  # 保留全部字段供覆盖率检查。
    require(len(ledger_rows) == EXPECTED_RHS_COUNT, f"A20 台账行数不是 {EXPECTED_RHS_COUNT}：{len(ledger_rows)}")  # 硬闭合行数。
    require(len({row["apdl_elem_id"] for row in ledger_rows}) == EXPECTED_RHS_COUNT, "A20 台账元素号不唯一")  # 防止重复行伪造覆盖率。
    require(all(row.get("status") == "PASS_ALREADY_CORRECT" for row in ledger_rows), "A20 台账含未通过元素")  # 逐行状态必须一致。
    require(all(row.get("physical_axis_change_required") == "FALSE" for row in ledger_rows), "A20 台账含需要轴改动元素")  # 任一需要改动即不能等价复用 A10。
    return {"status_sha256": sha256_file(status_path), "ledger_sha256": sha256_file(ledger_path), "zero_difference_sha256": sha256_file(zero_difference_path), "passed_element_count": len(ledger_rows), "physical_change_required_count": 0}  # 返回 A20 证据身份和结果。


def validate_a10_inputs(manifest: dict[str, Any]) -> dict[str, Any]:  # 输入 A10 准备清单并返回 11 依赖双副本哈希审计。
    """要求 input_snapshot 与 solver 双副本逐字相同，且清单中的预期哈希全部兑现。"""  # 函数说明给出输入身份门禁。
    dependencies = manifest.get("dependencies")  # 读取 A10 依赖列表。
    require(isinstance(dependencies, list) and len(dependencies) == EXPECTED_DEPENDENCY_COUNT, "A10 依赖不是 11 项")  # 固定主输入依赖数量。
    audit_rows: list[dict[str, Any]] = []  # 保存每个 include 的实际双副本身份。
    for entry in dependencies:  # 按清单原顺序逐项核验。
        basename = str(entry["basename"])  # 读取稳定 include 文件名。
        snapshot_path = A10_DIR / "input_snapshot" / basename  # 定位不可执行输入快照副本。
        solver_path = A10_DIR / "solver" / basename  # 定位实际求解工作目录副本。
        require(snapshot_path.is_file() and solver_path.is_file(), f"A10 依赖双副本缺失：{basename}")  # 两份均必须存在。
        snapshot_hash = sha256_file(snapshot_path)  # 计算快照字节身份。
        solver_hash = sha256_file(solver_path)  # 计算实际求解副本字节身份。
        require(snapshot_hash == solver_hash, f"A10 依赖双副本分叉：{basename}")  # 实际求解必须使用封板输入。
        require(snapshot_hash == entry.get("a10_input_snapshot_sha256") == entry.get("a10_solver_sha256"), f"A10 清单哈希不符：{basename}")  # 清单与现场双向闭合。
        require(entry.get("passed") is True, f"A10 清单依赖未通过：{basename}")  # 准备期门禁必须为真。
        audit_rows.append({"order": int(entry["order"]), "basename": basename, "role": str(entry["role"]), "sha256": snapshot_hash, "byte_identical_snapshot_solver": True})  # 保存可写入 A30 的依赖证据。
    require(sum(1 for row in audit_rows if row["role"] == "controlled_axis_change") == 1, "A10 受控轴 include 数量不是 1")  # 只允许 H175 方向一个物理差异家族。
    require(sum(1 for row in audit_rows if row["role"] == "invariant") == 10, "A10 invariant include 数量不是 10")  # 其余十项必须保持冻结。
    return {"dependency_count": len(audit_rows), "dependencies": audit_rows, "combined_dependency_identity": hashlib.sha256("\n".join(f"{row['order']}:{row['basename']}:{row['sha256']}" for row in audit_rows).encode("utf-8")).hexdigest()}  # 返回逐项和组合身份。


def validate_a10_finalization(manifest: dict[str, Any]) -> dict[str, Any]:  # 输入 A10 根 manifest 并返回正式 finalizer 与账本证据。
    """A30 只接受已真实执行、postrun gate 全通过且保留 legacy 限制的 A10 终态。"""  # 函数说明防止再次复用 prepare-only 旧状态。
    status_path = A10_DIR / "A10_status.json"  # 定位 A10 根真实终态文件。
    for path in (status_path, A10_POSTRUN_GATE_PATH, A10_LEDGER_PATH):  # 枚举 finalizer 必须形成的三份根证据。
        require(path.is_file(), f"A10 正式 finalizer 证据缺失：{path}")  # 任一缺失即禁止 A30 封板。
    status = read_json(status_path)  # 读取 A10 根真实终态。
    postrun = read_json(A10_POSTRUN_GATE_PATH)  # 读取 A10 完整 postrun 机器门禁。
    require(status.get("status") == A10_FINAL_STATUS and status.get("execution_status") == "EXECUTED", f"A10 根状态未正式封板：{status.get('status')}/{status.get('execution_status')}")  # 必须区分真实执行与 prepare。
    require(status.get("postrun_gate_passed") is True and status.get("next_action") == "NONE_FINALIZED", "A10 根状态仍有未完成执行动作")  # 根状态必须声明 postrun 已通过且无需再启动。
    require(manifest.get("status") == A10_FINAL_STATUS and manifest.get("execution_status") == "EXECUTED", "A10 manifest 未更新为真实执行终态")  # manifest 与状态必须一致。
    require(manifest.get("prepare_only") is False and manifest.get("mapdl_execution_attempted") is True and manifest.get("mapdl_started") is True, "A10 manifest 仍是 prepare-only 或未记录真实执行")  # 防止旧准备事实冒充结果。
    require(postrun.get("gate_status") == "PASSED" and postrun.get("final_status") == A10_FINAL_STATUS, "A10 postrun gate 未通过或终态不一致")  # 机器门禁必须明确通过。
    required_checks = {"main_out_zero_errors", "main_out_zero_negative_pivots", "main_out_zero_zero_pivots", "all_five_warnings_disposed", "ls1_converged", "ls2_converged", "mass_closed", "reaction_closed", "sten_control_proven_at_saved_endpoints", "sten_full_history_threshold_proven_by_disabled_control", "modal_properties_80", "modal_displacement_vectors_80", "modal_rotation_vectors_80", "frequency_band_0_to_0_35_not_truncated", "sene6_80_by_6_passed", "taskbook_14_target_energy_basis_preserved_without_hard_order_pairing", "link180_all_positive", "four_solver_source_hashes_current", "both_postonly_out_err_clean", "solver_binary_metadata_unchanged"}  # 列出 finalizer 二十项完整静力、模态、后处理和源完整性门禁。
    checks = postrun.get("checks")  # 读取 postrun 布尔检查对象。
    require(isinstance(checks, dict) and required_checks <= checks.keys(), f"A10 postrun gate 缺少检查：{sorted(required_checks - set(checks or {}))}")  # 所有点名门禁都必须存在。
    require(all(checks[key] is True for key in required_checks), "A10 postrun gate 含未通过的必需检查")  # 必需检查必须使用严格布尔真值。
    ledger = read_a10_ledger()  # 读取并验证全 run 非自引用账本。
    require("qa/postrun_gate.json" in ledger and "A10_status.json" in ledger and "manifest.json" in ledger, "A10 账本未覆盖 finalizer 根证据")  # 根状态和机器门禁都必须受账本保护。
    return {"status_path": status_path.relative_to(A10_DIR).as_posix(), "status_sha256": sha256_file(status_path), "manifest_sha256": sha256_file(A10_DIR / "manifest.json"), "postrun_gate_path": A10_POSTRUN_GATE_PATH.relative_to(A10_DIR).as_posix(), "postrun_gate_sha256": sha256_file(A10_POSTRUN_GATE_PATH), "artifact_ledger_path": A10_LEDGER_PATH.relative_to(A10_DIR).as_posix(), "artifact_ledger_sha256": sha256_file(A10_LEDGER_PATH), "artifact_ledger_entries": ledger, "postrun": postrun, "legacy_limitations": postrun.get("legacy_limitations", [])}  # 返回后续原始证据复核所需对象和身份。


def validate_solver_messages(jobname: str, postrun: dict[str, Any]) -> dict[str, Any]:  # 输入作业名和 finalizer 门禁并返回全部相关 OUT/ERR 审计。
    """主 OUT、三个 DMP worker OUT 和四个 ERR 均须零 ERROR/FATAL/pivot，五条 warning 必须唯一且已处置。"""  # 函数说明覆盖任务书日志门禁。
    solver_dir = A10_DIR / "solver"  # 定位 A10 实际求解目录。
    main_output_path = resolve_a10_relative(str(postrun.get("main_out", {}).get("path", "")))  # 由 finalizer 绑定唯一主 OUT 路径。
    require(main_output_path.parent == solver_dir.resolve(), "A10 主 OUT 不在 solver 目录")  # 主输出不得引用后处理目录或其他 run。
    expected_out_names = {f"{jobname.lower()}.out", *(f"{jobname.lower()}_{rank}.out" for rank in range(1, 4))}  # DMP4 应有主 OUT 和三个 worker OUT。
    out_paths = sorted((path for path in solver_dir.glob("*.out") if path.name.lower() in expected_out_names), key=lambda path: path.name.lower())  # 只枚举当前 job 的四份 OUT。
    require({path.name.lower() for path in out_paths} == expected_out_names, f"A10 相关 OUT 不完整：{[path.name for path in out_paths]}")  # 四个预期文件必须完整且无替代。
    expected_err_names = {f"{jobname.lower()}_{rank}.err" for rank in range(4)}  # DMP4 四个进程应各有 ERR 文件。
    err_paths = sorted((path for path in solver_dir.glob("*.err") if path.name.lower() in expected_err_names), key=lambda path: path.name.lower())  # 只枚举当前 job 的四份 ERR。
    require({path.name.lower() for path in err_paths} == expected_err_names, f"A10 相关 ERR 不完整：{[path.name for path in err_paths]}")  # 四个 ERR 必须全部存在。
    records: list[dict[str, Any]] = []  # 保存每份 OUT/ERR 的错误、warning 和摘要身份。
    main_text = ""  # 初始化唯一主 OUT 文本供完成与摘要门禁。
    for path in out_paths + err_paths:  # 逐份读取全部当前作业日志，禁止只看主 OUT。
        text = path.read_text(encoding="utf-8", errors="replace")  # 以 replacement 解码混合编码，但 ASCII 标记保持可靠。
        error_count = len(re.findall(r"(?m)^\s*\*\*\* ERROR \*\*\*", text))  # 统计真实 MAPDL ERROR 标题行。
        fatal_count = len(re.findall(r"(?m)^\s*\*\*\* FATAL \*\*\*", text))  # 统计真实 MAPDL FATAL 标题行。
        negative_pivot_count = len(re.findall(r"negative\s+pivot", text, flags=re.IGNORECASE))  # 统计负主元短语。
        zero_pivot_count = len(re.findall(r"zero\s+pivot", text, flags=re.IGNORECASE))  # 统计零主元短语。
        warning_count = len(re.findall(r"(?m)^\s*\*\*\* WARNING \*\*\*", text))  # 统计真实 MAPDL warning 标题行。
        require(error_count == 0 and fatal_count == 0 and negative_pivot_count == 0 and zero_pivot_count == 0, f"A10 日志含 ERROR/FATAL/pivot：{path.name}")  # 任一相关日志异常即拒绝复用。
        if path.resolve() == main_output_path:  # 当前文件是 finalizer 固定的主 OUT 时保存全文。
            main_text = text  # 留给完成摘要、warning 文本和并行身份检查。
        records.append({"path": path.relative_to(A10_DIR).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256_file(path), "warning_count": warning_count, "error_count": error_count, "fatal_count": fatal_count, "negative_pivot_count": negative_pivot_count, "zero_pivot_count": zero_pivot_count})  # 保存逐文件可追溯审计。
    require(bool(main_text) and "RUN COMPLETED" in main_text and "80 Eigenvalues Converged" in main_text, "A10 主 OUT 缺正常完成或 80 特征值收敛标记")  # 主会话必须完整结束且模态求解收敛。
    main_warning_count = len(re.findall(r"(?m)^\s*\*\*\* WARNING \*\*\*", main_text))  # 单独统计主 OUT 的五条实际 warning。
    summary_errors = [int(value) for value in re.findall(r"NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*(\d+)", main_text)]  # 读取主 OUT 错误摘要。
    summary_warnings = [int(value) for value in re.findall(r"NUMBER OF WARNING MESSAGES ENCOUNTERED=\s*(\d+)", main_text)]  # 读取退出前 warning 摘要。
    normalized_main = re.sub(r"\s+", " ", main_text).lower()  # 规范空白以稳定匹配跨行 warning 文本。
    require(main_warning_count == EXPECTED_WARNING_COUNT and summary_errors == [0] and summary_warnings == [EXPECTED_SUMMARY_WARNING_COUNT], "A10 主 OUT warning/error 摘要不闭合")  # 五条实际、四条摘要和零错误必须一致。
    require(all(fragment in normalized_main for fragment in EXPECTED_WARNING_FRAGMENTS), "A10 主 OUT 的五条 warning 文本发生漂移")  # 每条已知 warning 必须能唯一识别。
    warning_records = postrun.get("warnings", {}).get("records", [])  # 读取 finalizer 的逐条处置记录。
    require(isinstance(warning_records, list) and len(warning_records) == EXPECTED_WARNING_COUNT and all(record.get("status") == "DISPOSED" for record in warning_records), "A10 五条 warning 未全部逐项处置")  # 处置数量和状态必须闭合。
    require("EXIT MAPDL WITHOUT SAVING DATABASE" in main_text and "Number of processes requested           :    4" in main_text and "Distributed Memory Parallel" in main_text, "A10 主 OUT 的 NOSAVE 或 DMP4 身份不完整")  # 正常退出和实际并行身份必须成立。
    err_warning_counts = {Path(record["path"]).name.lower(): int(record["warning_count"]) for record in records if str(record["path"]).lower().endswith(".err")}  # 汇总四个 ERR warning 数。
    require(err_warning_counts.get(f"{jobname.lower()}_0.err") == EXPECTED_WARNING_COUNT and all(err_warning_counts.get(f"{jobname.lower()}_{rank}.err") == 0 for rank in range(1, 4)), "A10 DMP ERR warning 分布不符合主进程五条、worker 零条")  # ERR 与主 OUT 必须一致而非隐藏新增消息。
    return {"status": "PASSED_WITH_FIVE_DISPOSED_WARNINGS", "main_output": main_output_path.relative_to(A10_DIR).as_posix(), "main_warning_markers": main_warning_count, "summary_warning_count": summary_warnings[0], "tail_warning_after_summary_count": 1, "summary_error_count": summary_errors[0], "negative_pivot_count": 0, "zero_pivot_count": 0, "all_warnings_disposed": True, "files": records}  # 返回全部日志门禁与五条已知限制口径。


def validate_static_topology(manifest: dict[str, Any], postrun: dict[str, Any]) -> dict[str, Any]:  # 输入 A10 manifest/finalizer 门禁并返回静力与冻结身份审计。
    """直接解析原始静力、拓扑和十一依赖，不仅复述 finalizer 的布尔摘要。"""  # 函数说明覆盖 LS1/LS2、能量、质量、反力和数量漂移门禁。
    solver_dir = A10_DIR / "solver"  # 定位实际求解证据目录。
    static_path = solver_dir / "a10_static_energy_mass_reaction.txt"  # 定位六行静力硬门禁表。
    topology_path = solver_dir / "a10_topology_counts.txt"  # 定位求解器实际拓扑计数表。
    static = parse_named_numbers(static_path)  # 直接读取 LS1/LS2、能量、质量和反力字段。
    topology = parse_named_numbers(topology_path)  # 直接读取节点、单元和类型数量。
    required_static = {"LS1_CNVG", "LS2_CNVG", "LS2", "TIME2", "SENE1", "STEN1", "RATIO1", "SENE2", "STEN2", "RATIO2", "MASS", "EXPECTED", "ABS_ERROR", "UZ", "RF_EXPECTED", "RF_ACTUAL", "RF_ERROR", "RF_RELATIVE_ERROR"}  # 列出任务书静力所需全部字段。
    require(required_static <= static.keys(), f"A10 静力表缺字段：{sorted(required_static - static.keys())}")  # 缺任一关键数值即拒绝。
    require(static["LS1_CNVG"] == 1.0 and static["LS2_CNVG"] == 1.0, "A10 LS1/LS2 未同时收敛")  # 两个载荷步收敛标志必须均为 1。
    require(static["LS2"] == 2.0 and abs(static["TIME2"] - 1.001) <= 1.0e-12, "A10 LS2 载荷步或伪时间不符")  # 无稳定化保持步必须位于 LS2、时间 1.001。
    require(static["SENE1"] > 0.0 and static["SENE2"] > 0.0, "A10 LS1/LS2 势能非正")  # 两步端点势能必须物理有效。
    require(abs(static["RATIO1"]) <= LS1_ENERGY_RATIO_LIMIT and abs(static["RATIO2"]) <= LS2_ENERGY_RATIO_LIMIT, "A10 LS1/LS2 端点 STEN/SENE 超限")  # 端点能量比必须满足任务书阈值。
    require(abs(static["STEN1"]) <= 1.0e-20 and abs(static["STEN2"]) <= 1.0e-20, "A10 LS1/LS2 端点 STEN 未接近数值零")  # 两次 KEY=OFF 的保存端点应无稳定化能。
    require(abs(static["MASS"] - EXPECTED_TOTAL_MASS_TONNE) <= MASS_ABSOLUTE_TOLERANCE_TONNE and static["ABS_ERROR"] <= MASS_ABSOLUTE_TOLERANCE_TONNE, "A10 总质量未在 1E-6 tonne 内闭合")  # 不改质量变体必须保持冻结质量。
    require(static["UZ"] == float(EXPECTED_UZ_SUPPORT_COUNT), "A10 UZ 支承数不是 464")  # 支承节点身份不得漂移。
    require(static["RF_RELATIVE_ERROR"] <= REACTION_RELATIVE_TOLERANCE, "A10 重力—竖向反力相对误差超限")  # 反力闭合阈值为 1E-4。
    require(abs(static["RF_EXPECTED"] - static["MASS"] * 9806.0) <= max(1.0e-3, abs(static["RF_EXPECTED"]) * 1.0e-12), "A10 重力目标与质量×9806 mm/s² 不闭合")  # 质量和重力目标必须内部一致。
    required_topology = {"NODE_COUNT", "ELEMENT_COUNT", "TYPE4", "TYPE6", "TYPE70", "TYPE71"}  # 列出任务书冻结拓扑字段。
    require(required_topology <= topology.keys(), f"A10 拓扑表缺字段：{sorted(required_topology - topology.keys())}")  # 缺类型计数时不能排除组件漂移。
    expected_topology = {"NODE_COUNT": EXPECTED_NODE_COUNT, "ELEMENT_COUNT": EXPECTED_ELEMENT_COUNT, "TYPE4": EXPECTED_LINK180_COUNT, "TYPE6": EXPECTED_TYPE6_COUNT, "TYPE70": EXPECTED_TYPE70_COUNT, "TYPE71": EXPECTED_MASS21_COUNT}  # 构造六项冻结目标。
    require(all(topology[key] == float(value) for key, value in expected_topology.items()), f"A10 拓扑计数漂移：{topology}")  # 六项实际计数必须同时精确闭合。
    command_counts = count_frozen_input_commands(manifest)  # 独立核对 D、CP、CERIG 与 ROTY=0 数量。
    postrun_static = postrun.get("static", {})  # 读取 finalizer 的带单位静力对象供交叉比对。
    require(postrun_static.get("ls1_cnvg") == 1 and postrun_static.get("ls2_cnvg") == 1 and float(postrun_static.get("mass_abs_error_tonne", math.inf)) == static["ABS_ERROR"] and float(postrun_static.get("reaction_relative_error", math.inf)) == static["RF_RELATIVE_ERROR"], "A10 finalizer 静力摘要与原始表不一致")  # 摘要必须由原始表直接复现。
    sten_control = postrun.get("sten_control", {})  # 读取 finalizer 的稳定化控制证据。
    require(sten_control.get("input_stabilize_off_count") == 2 and sten_control.get("out_key_off_count") == 2 and sten_control.get("ls1_stabilization_control") == "OFF_FOR_FULL_LOAD_STEP" and sten_control.get("ls2_stabilization_control") == "OFF_FOR_FULL_LOAD_STEP", "A10 输入与 OUT 未同时证明两个完整载荷步 STABILIZE,OFF")  # LS1/LS2 全历程都必须关闭稳定化。
    require(sten_control.get("taskbook_full_history_peak_gate_status") == "PASSED_BY_DISABLED_STABILIZATION_CONTROL" and float(sten_control.get("taskbook_full_history_threshold", math.nan)) == LS1_ENERGY_RATIO_LIMIT, "A10 全历程 STEN 门禁未由禁用稳定化控制证明")  # STEN 来源全程禁用时任务书峰值门禁由控制状态通过。
    require(sten_control.get("full_substep_numeric_history_available") is False, "A10 STEN 数值历史能力字段发生意外变化")  # 当前 RST 只保存端点，必须保留数值可恢复边界。
    return {"status": "PASSED_FULL_HISTORY_GATE_BY_DISABLED_STABILIZATION_CONTROL_WITH_NUMERIC_HISTORY_LIMITATION", "ls1_converged": True, "ls2_converged": True, "ls2_load_step": 2, "ls2_time": static["TIME2"], "ls1_sene_n_mm": static["SENE1"], "ls1_sten_n_mm": static["STEN1"], "ls1_abs_sten_over_sene": abs(static["RATIO1"]), "ls1_limit": LS1_ENERGY_RATIO_LIMIT, "ls2_sene_n_mm": static["SENE2"], "ls2_sten_n_mm": static["STEN2"], "ls2_abs_sten_over_sene": abs(static["RATIO2"]), "ls2_limit": LS2_ENERGY_RATIO_LIMIT, "full_substep_peak_gate_status": "PASSED_BY_DISABLED_STABILIZATION_CONTROL", "full_substep_stabilization_control_bound": 0.0, "full_substep_peak_abs_sten_over_sene_numeric_history": None, "full_substep_numeric_history_available": False, "full_substep_history_limitation": "两个完整静力载荷步均由输入顺序和两次求解器 KEY=OFF 回显证明 STABILIZE,OFF，因此稳定化能峰值门禁通过；RST 仅保存端点 VENG，逐子步数值曲线不可恢复。", "mass_actual_tonne": static["MASS"], "mass_expected_tonne": static["EXPECTED"], "mass_abs_error_tonne": static["ABS_ERROR"], "mass_limit_tonne": MASS_ABSOLUTE_TOLERANCE_TONNE, "uz_support_count": int(static["UZ"]), "reaction_expected_n": static["RF_EXPECTED"], "reaction_actual_n": static["RF_ACTUAL"], "reaction_abs_error_n": static["RF_ERROR"], "reaction_relative_error": static["RF_RELATIVE_ERROR"], "reaction_relative_limit": REACTION_RELATIVE_TOLERANCE, "topology": {key.lower(): int(topology[key]) for key in expected_topology}, "constraint_command_counts": command_counts, "static_source": {"path": static_path.relative_to(A10_DIR).as_posix(), "sha256": sha256_file(static_path)}, "topology_source": {"path": topology_path.relative_to(A10_DIR).as_posix(), "sha256": sha256_file(topology_path)}}  # 返回全部静力关键数值、全历程控制门禁、拓扑身份和真实数值历史边界。


def validate_postonly_sources(postrun: dict[str, Any], jobname: str) -> dict[str, Any]:  # 输入 finalizer 门禁和作业名并返回 LINK180/SENE6 原始复核与源不变证据。
    """直接读取两套正式 POSTONLY QA、三份 SENE CSV 和 73,692 行轴力 CSV，并复算当前四个源文件哈希。"""  # 函数说明覆盖只读后处理与源 DB/RST 不变门禁。
    solver_dir = A10_DIR / "solver"  # 定位四个受保护源文件的固定目录。
    expected_source_names = {f"{jobname}_eq.db", f"{jobname}_modal.db", f"{jobname}.rst", f"{jobname}.rstp"}  # 定义两套只读后处理实际读取的四个源文件。
    source_paths = {name: solver_dir / name for name in expected_source_names}  # 构造源文件名到绝对路径的映射。
    metadata_before = {name: file_metadata(path) for name, path in source_paths.items()}  # 在任何 CSV 解析和大文件哈希前固定元数据。
    link_summary = postrun.get("link180")  # 读取 finalizer 已绑定的 LINK180 正式摘要。
    require(isinstance(link_summary, dict), "A10 postrun gate 缺 LINK180 对象")  # 缺结构化对象时不能定位正式 QA。
    link_qa_path = resolve_a10_relative(str(link_summary.get("qa_path", "")))  # 安全解析正式 LINK180 qa_summary.json。
    link_qa = read_json(link_qa_path)  # 读取 LINK180 正式机器摘要。
    require(link_qa.get("status") == "PASSED" and link_qa.get("gate_passed") is True, "LINK180 正式 QA 未通过")  # 状态和布尔门禁必须一致。
    link_force = link_qa.get("link180_axial_force")  # 提取轴力统计对象。
    link_execution = link_qa.get("execution")  # 提取只读 MAPDL 执行对象。
    link_source = link_qa.get("source_integrity")  # 提取 DB/RST 完整性对象。
    require(isinstance(link_force, dict) and isinstance(link_execution, dict) and isinstance(link_source, dict), "LINK180 QA 结构不完整")  # 三个正式对象缺一不可。
    require(link_execution.get("mode") == "POST1_ONLY_SMP1" and link_execution.get("mapdl_exit_code") == 0 and link_execution.get("mapdl_warning_count") == 0 and link_execution.get("mapdl_error_count") == 0 and link_execution.get("exit_without_saving_confirmed") is True, "LINK180 POSTONLY 执行不是 SMP1 零警告零错误 NOSAVE")  # 后处理会话必须干净且只读退出。
    require(link_execution.get("input_forbidden_command_count") == 0 and link_execution.get("uncommented_executable_line_count") == 0, "LINK180 POSTONLY 输入含求解/写库命令或未注释执行行")  # 禁止任何可能改源的命令。
    count_fields = ("expected_count", "actual_count", "written_count", "csv_row_count", "unique_element_count")  # 列出轴力覆盖必须同时闭合的五个计数字段。
    require(all(int(link_force.get(field, -1)) == EXPECTED_LINK180_COUNT for field in count_fields), "LINK180 五项覆盖计数未全部闭合到 73692")  # 选择、写出、CSV 和唯一数必须一致。
    require(int(link_force.get("duplicate_element_count", -1)) == 0 and int(link_force.get("invalid_numeric_line_count", -1)) == 0 and int(link_force.get("nonpositive_count", -1)) == 0, "LINK180 存在重复、非法或非正轴力记录")  # 三类坏记录必须为零。
    link_csv_name = str(link_force.get("csv_path", ""))  # 读取正式 QA 声明的轴力 CSV 文件名。
    require(Path(link_csv_name).name == link_csv_name and link_csv_name.endswith(".csv"), "LINK180 CSV 声明不是安全同目录文件名")  # 防止路径逃逸或非 CSV 文件。
    link_csv_path = link_qa_path.parent / link_csv_name  # 将轴力表绑定到正式 QA 同目录。
    link_rows = read_numeric_csv(link_csv_path)  # 直接解析全部 73,692 行元素号和轴力。
    require(len(link_rows) == EXPECTED_LINK180_COUNT and all(len(row) == 2 for row in link_rows), "LINK180 原始 CSV 不是 73692 行两列")  # 原始表行列结构必须闭合。
    link_ids = [int(row[0]) for row in link_rows]  # 提取元素号供整数与唯一性复核。
    link_forces = [row[1] for row in link_rows]  # 提取 N 单位轴力供正值和极值复核。
    require(all(row[0].is_integer() for row in link_rows) and len(set(link_ids)) == EXPECTED_LINK180_COUNT, "LINK180 元素号非整数或不唯一")  # 每个 TYPE4 元素必须恰出现一次。
    require(all(force > 0.0 for force in link_forces), "LINK180 原始 CSV 含非正轴力")  # 所有索单元必须保持正拉力。
    require(min(link_forces) == float(link_force.get("minimum_force_n")) and max(link_forces) == float(link_force.get("maximum_force_n")), "LINK180 原始极值与 QA 摘要不一致")  # 摘要最小/最大值必须可由原始表复现。
    require(sha256_file(link_csv_path) == str(link_force.get("csv_sha256", "")).lower() == str(link_summary.get("csv_sha256", "")).lower(), "LINK180 原始 CSV 哈希未在两级摘要闭合")  # 原始表身份必须同时匹配 QA 和 finalizer。
    postflight_name = str(link_source.get("postflight_path", ""))  # 读取 LINK180 源完整性文件名。
    require(Path(postflight_name).name == postflight_name and postflight_name.endswith(".json"), "LINK180 postflight 路径不安全")  # postflight 必须位于同目录且为 JSON。
    postflight_path = link_qa_path.parent / postflight_name  # 定位运行前后源完整性原始对象。
    postflight = read_json(postflight_path)  # 读取 DB/RST 前后大小、时间和 SHA-256。
    require(postflight.get("source_integrity_passed") is True and postflight.get("exit_without_saving_confirmed") is True and postflight.get("active_mapdl_process_count_after") == 0, "LINK180 postflight 未证明只读退出或仍有 MAPDL 进程")  # 源完整性与进程清理必须成立。
    postflight_files = postflight.get("files")  # 读取两项受保护源记录。
    require(isinstance(postflight_files, list) and len(postflight_files) == 2, "LINK180 postflight 不是 DB/RST 两项")  # 只允许平衡 DB 与静力 RST 两项。
    current_hashes: dict[str, str] = {}  # 保存四个源文件当前内容摘要供关键结果复用。
    for record in postflight_files:  # 逐项核对平衡 DB 和静力 RST 的运行前后证据。
        require(isinstance(record, dict), "LINK180 postflight 文件记录不是对象")  # 每项必须具名字段。
        before = record.get("before")  # 读取运行前文件身份。
        after = record.get("after")  # 读取运行后文件身份。
        require(isinstance(before, dict) and isinstance(after, dict) and before == after, "LINK180 源文件运行前后对象不相同")  # 大小、时间和哈希必须逐字段相同。
        require(all(record.get(field) is True for field in ("length_unchanged", "creation_time_unchanged", "last_write_time_unchanged", "sha256_unchanged")), "LINK180 源文件不变布尔门禁失败")  # 四个明确布尔字段必须全真。
        relative_from_qa = Path(str(record.get("path", "")))  # 读取相对正式 QA 目录的源文件路径。
        candidate = (link_qa_path.parent / relative_from_qa).resolve()  # 规范化源路径并解析点段。
        require(candidate.parent == solver_dir.resolve() and candidate.name in source_paths, f"LINK180 postflight 源路径不属于预期 A10 solver：{candidate}")  # 只允许固定 DB/RST 文件。
        digest = sha256_file(candidate)  # 重新计算 A30 执行时的当前源内容身份。
        require(digest == str(after.get("sha256", "")).lower() and candidate.stat().st_size == int(after.get("length_bytes", -1)), f"LINK180 源文件当前内容已漂移：{candidate.name}")  # 当前字节必须仍等于 postflight 结束时。
        current_hashes[candidate.name] = digest  # 保存当前摘要供后续账本和关键结果复核。
    require(link_source.get("source_integrity_passed") is True and str(link_source.get("equilibrium_database_sha256_before_after", "")).lower() == current_hashes[f"{jobname}_eq.db"] and str(link_source.get("static_result_sha256_before_after", "")).lower() == current_hashes[f"{jobname}.rst"], "LINK180 QA 源摘要与当前 DB/RST 不一致")  # QA 顶层和 postflight 必须闭合。
    sene_summary = postrun.get("sene6")  # 读取 finalizer 已绑定的六组件 SENE 正式摘要。
    require(isinstance(sene_summary, dict), "A10 postrun gate 缺 SENE6 对象")  # 缺摘要时不能定位正式 QA。
    sene_qa_path = resolve_a10_relative(str(sene_summary.get("qa_path", "")))  # 安全解析六组件 qa_summary.json。
    sene_qa = read_json(sene_qa_path)  # 读取六组件正式机器摘要。
    require(sene_qa.get("status") == "PASSED", "SENE6 正式 QA 未通过")  # 六组件结果必须明确 PASSED。
    sene_execution = sene_qa.get("execution")  # 读取 SENE 后处理执行对象。
    sene_safety = sene_qa.get("safety")  # 读取 SENE 只读安全对象。
    component_counts = sene_qa.get("component_counts")  # 读取六组件集合计数对象。
    modal_qa = sene_qa.get("modal_qa")  # 读取 80×6 数值 QA 对象。
    require(all(isinstance(value, dict) for value in (sene_execution, sene_safety, component_counts, modal_qa)), "SENE6 QA 结构不完整")  # 四个正式对象缺一不可。
    require(sene_execution.get("warnings") == 0 and sene_execution.get("errors") == 0 and sene_execution.get("success_marker_count") == 1 and sene_execution.get("executed_fail_marker_count") == 0, "SENE6 POSTONLY 执行存在 warning/error 或成功标记不唯一")  # 后处理会话必须干净完成。
    require(sene_safety.get("solve_command_count") == 0 and sene_safety.get("solution_processor_command_count") == 0 and sene_safety.get("new_db_rst_rstp_file_count") == 0 and sene_safety.get("exit_without_saving") is True, "SENE6 POSTONLY 含求解/写结果行为或未 NOSAVE")  # 禁止修改源模型与结果。
    require(sene_safety.get("source_db_unchanged") is True and sene_safety.get("source_rstp_unchanged") is True, "SENE6 QA 未证明 modal DB/RSTP 不变")  # 两个模态源必须前后不变。
    expected_component_counts = {"GATE_BOTTOM_E": 2698, "GATE_TOPPOST_E": 1562, "PASS_CHORD152_E": 4011, "PASS_FRAME102_E": 1890, "PASS_BRACE51_E": 4620, "PASS_RHS5030_E": 2898, "arithmetic_sum": EXPECTED_TYPE70_COUNT, "set_union": EXPECTED_TYPE70_COUNT, "type70_total": EXPECTED_TYPE70_COUNT, "union_intersection_type70": EXPECTED_TYPE70_COUNT}  # 定义六组件及集合冻结计数。
    require(all(int(component_counts.get(key, -1)) == value for key, value in expected_component_counts.items()), "SENE6 六组件或 TYPE70 集合计数未闭合")  # 六类、和、并集、类型与交集必须同时一致。
    require(component_counts.get("counts_exact") is True and component_counts.get("components_disjoint") is True and component_counts.get("components_equal_type70_set") is True, "SENE6 六组件不互斥或不等于 TYPE70")  # 集合关系必须明确通过。
    require(modal_qa.get("result_set_count") == EXPECTED_MODE_COUNT and modal_qa.get("total_csv_rows") == EXPECTED_MODE_COUNT and modal_qa.get("long_csv_rows") == EXPECTED_MODE_COUNT * 6 and modal_qa.get("shape_exact_80_by_6") is True, "SENE6 结果集或 80×6 结构不闭合")  # 结果集、总表和长表数量必须完整。
    require(modal_qa.get("all_totals_finite_and_positive") is True and modal_qa.get("all_component_energies_finite_and_nonnegative") is True and modal_qa.get("all_ratios_finite_and_in_closed_interval_0_1") is True, "SENE6 能量或比例数值门禁失败")  # 总能量正、组件非负、比例闭区间。
    count_rows = read_numeric_csv(sene_qa_path.parent / "a10_sene6_counts_numeric.csv")  # 直接读取一行十一列组件计数原始表。
    total_rows = read_numeric_csv(sene_qa_path.parent / "a10_sene6_mode_totals_numeric.csv")  # 直接读取八十行总 SENE 原始表。
    long_rows = read_numeric_csv(sene_qa_path.parent / "a10_sene6_modal_numeric.csv")  # 直接读取四百八十行六组件长表。
    require(len(count_rows) == 1 and len(count_rows[0]) == 11 and [int(value) for value in count_rows[0]] == [2698, 1562, 4011, 1890, 4620, 2898, 17679, 17679, 17679, 17679, 80], "SENE6 计数 CSV 不匹配冻结十一列")  # 原始计数表必须逐列一致。
    require(len(total_rows) == EXPECTED_MODE_COUNT and all(len(row) == 2 for row in total_rows) and [int(row[0]) for row in total_rows] == list(range(1, EXPECTED_MODE_COUNT + 1)) and all(row[1] > 0.0 for row in total_rows), "SENE6 总能量 CSV 不是连续 80 阶正值")  # 总表必须严格连续且物理有效。
    require(len(long_rows) == EXPECTED_MODE_COUNT * 6 and all(len(row) == 5 for row in long_rows), "SENE6 长表不是 480 行五列")  # 长表行列结构必须固定。
    for mode_index in range(1, EXPECTED_MODE_COUNT + 1):  # 逐阶核对六个组件代码和总能量一致性。
        rows_for_mode = [row for row in long_rows if int(row[0]) == mode_index]  # 提取当前阶的六条组件记录。
        require(sorted(int(row[1]) for row in rows_for_mode) == [1, 2, 3, 4, 5, 6], f"SENE6 第 {mode_index} 阶组件代码不完整")  # 每阶必须恰有代码 1 至 6。
        require(all(row[2] == total_rows[mode_index - 1][1] and row[3] >= 0.0 and 0.0 <= row[4] <= 1.0 for row in rows_for_mode), f"SENE6 第 {mode_index} 阶总能量、组件能量或比例不一致")  # 当前阶六行必须共享总能量并满足数值边界。
    base_energy_rows = read_numeric_csv(solver_dir / "a10_gate_bottom_modal_sene.csv")  # 读取主作业原生 GATE_BOTTOM_E 四列表。
    require(len(base_energy_rows) == EXPECTED_MODE_COUNT and all(len(row) == 4 for row in base_energy_rows), "A10 主作业 GATE_BOTTOM SENE 不是 80 行四列")  # 原生表必须完整。
    component_one = [row for row in long_rows if int(row[1]) == 1]  # 提取六组件长表中的 GATE_BOTTOM_E 记录。
    require(all(base_energy_rows[index] == [component_one[index][0], component_one[index][2], component_one[index][3], component_one[index][4]] for index in range(EXPECTED_MODE_COUNT)), "SENE6 与主作业 GATE_BOTTOM_E 原始表不精确一致")  # 新后处理不得改变原生能量数值。
    sene_sources = sene_qa.get("sources")  # 读取 modal DB 与 RSTP 前后身份记录。
    require(isinstance(sene_sources, list) and len(sene_sources) == 2, "SENE6 sources 不是 modal DB/RSTP 两项")  # 两个模态源必须齐全。
    for record in sene_sources:  # 逐项重新哈希当前 modal DB 与 RSTP。
        require(isinstance(record, dict) and Path(str(record.get("name", ""))).name == str(record.get("name", "")), "SENE6 源文件名非法")  # 源声明只能是 solver 同目录文件名。
        name = str(record["name"])  # 读取已验证的安全文件名。
        require(name in source_paths, f"SENE6 引用了非预期源文件：{name}")  # 只允许固定 modal DB 与 RSTP。
        digest = sha256_file(source_paths[name])  # 重新计算 A30 执行时当前内容摘要。
        require(digest == str(record.get("sha256_before_and_after", "")).lower() and source_paths[name].stat().st_size == int(record.get("bytes", -1)), f"SENE6 源文件当前内容已漂移：{name}")  # 当前字节必须仍等于后处理前后身份。
        current_hashes[name] = digest  # 保存当前摘要供关键结果账本比对。
    require(set(current_hashes) == expected_source_names, f"四个 POSTONLY 受保护源未全部闭合：{sorted(current_hashes)}")  # DB、RST、modal DB、RSTP 必须全部覆盖。
    metadata_after = {name: file_metadata(path) for name, path in source_paths.items()}  # 完成 CSV 解析与大文件哈希后再次读取元数据。
    require(metadata_after == metadata_before, "A30 只读核验期间源 DB/RST 元数据发生变化")  # 防止并发修改或本脚本误触源文件。
    return {"status": "PASSED_READ_ONLY_POSTPROCESSING_SOURCES_UNCHANGED", "source_metadata_unchanged_during_a30_qa": True, "protected_sources": {name: {"path": source_paths[name].relative_to(A10_DIR).as_posix(), "size_bytes": metadata_after[name]["size_bytes"], "mtime_ns": metadata_after[name]["mtime_ns"], "sha256": current_hashes[name]} for name in sorted(current_hashes)}, "link180": {"status": "PASSED", "actual_count": EXPECTED_LINK180_COUNT, "unique_count": len(set(link_ids)), "nonpositive_count": 0, "minimum_force_n": min(link_forces), "minimum_element_id": int(link_force.get("minimum_element_id")), "maximum_force_n": max(link_forces), "maximum_element_id": int(link_force.get("maximum_element_id")), "qa_path": link_qa_path.relative_to(A10_DIR).as_posix(), "qa_sha256": sha256_file(link_qa_path), "csv_path": link_csv_path.relative_to(A10_DIR).as_posix(), "csv_sha256": sha256_file(link_csv_path), "postflight_path": postflight_path.relative_to(A10_DIR).as_posix(), "postflight_sha256": sha256_file(postflight_path)}, "sene6": {"status": "PASSED", "result_set_count": EXPECTED_MODE_COUNT, "total_rows": len(total_rows), "component_rows": len(long_rows), "component_count": 6, "total_sene_min_n_mm": min(row[1] for row in total_rows), "total_sene_max_n_mm": max(row[1] for row in total_rows), "component_sene_min_n_mm": min(row[3] for row in long_rows), "component_sene_max_n_mm": max(row[3] for row in long_rows), "ratio_min": min(row[4] for row in long_rows), "ratio_max": max(row[4] for row in long_rows), "qa_path": sene_qa_path.relative_to(A10_DIR).as_posix(), "qa_sha256": sha256_file(sene_qa_path)}}  # 返回轴力、六组件能量和四个源文件当前身份。


def validate_target_reference_and_gap() -> dict[str, Any]:  # 无输入并返回十四目标定义闭合与物理映射证据缺口。
    """只证明权威十四目标定义和 80 阶候选池存在；无描述量/MAC 时明确禁止伪造物理身份 mapping。"""  # 函数说明落实任务书证据等级边界。
    require(TARGET_REFERENCE_PATH.is_file(), f"十四目标权威表缺失：{TARGET_REFERENCE_PATH}")  # 缺目标定义时连待识别集合都不能闭合。
    with TARGET_REFERENCE_PATH.open("r", encoding="utf-8-sig", newline="") as stream:  # 按 UTF-8 BOM 兼容方式读取权威 CSV。
        rows = list(csv.DictReader(stream))  # 保留十四行全部标签、描述、频率和来源位置。
    require(len(rows) == EXPECTED_TARGET_COUNT, f"十四目标权威表行数不是 {EXPECTED_TARGET_COUNT}")  # 目标数必须严格为十四。
    require([int(row["order"]) for row in rows] == list(range(1, EXPECTED_TARGET_COUNT + 1)), "十四目标 order 不是连续 1..14")  # 顺序字段必须连续无重复。
    require(tuple(row["internal_id"] for row in rows) == EXPECTED_TARGET_IDS, "十四目标内部标签或顺序漂移")  # 内部标签必须与任务书逐项一致。
    require(all(math.isfinite(float(row["frequency_hz"])) and float(row["frequency_hz"]) > 0.0 for row in rows), "十四目标参考频率含非正或非有限值")  # 参考显示频率必须为有限正数。
    mapping_names = {"target_assignment.csv", "09_target_mapping.csv"}  # 定义可承载十四目标物理分配的正式文件名。
    descriptor_names = {"raw_mode_features.csv", "07_mode_descriptors.csv"}  # 定义方向、跨别和对称性描述量候选文件名。
    mapping_paths = sorted(path.relative_to(A10_DIR).as_posix() for path in A10_DIR.rglob("*.csv") if path.name in mapping_names)  # 枚举 A10 内任何现存目标 mapping。
    descriptor_paths = sorted(path.relative_to(A10_DIR).as_posix() for path in A10_DIR.rglob("*.csv") if path.name in descriptor_names)  # 枚举 A10 内任何现存物理描述量表。
    mac_paths = sorted(path.relative_to(A10_DIR).as_posix() for path in A10_DIR.rglob("*.csv") if "mac" in path.name.lower())  # 枚举 A10 内任何 MAC 或子空间 MAC 表。
    require(not mapping_paths and not descriptor_paths and not mac_paths, "A10 出现未由本 A30 脚本验证的新 mapping/descriptor/MAC 产物，请先扩展明确字段门禁")  # 当前已知事实是三类产物均不存在；新增文件不得被静默忽略。
    evidence_levels = {"A": ["LS1", "VA1", "LA1", "TA1", "VS1", "TS1"], "B": ["LS2", "VA2", "LA2", "TS2", "VS2"], "C": ["SIDE1", "SIDE2", "SIDE3"]}  # 按任务书区分有图、仅标签频率和笼统边跨证据。
    return {"status": "REFERENCE_AND_80_MODE_POOL_CLOSED_PHYSICAL_MAPPING_OPEN", "reference_target_count": len(rows), "reference_target_ids": list(EXPECTED_TARGET_IDS), "reference_sha256": sha256_file(TARGET_REFERENCE_PATH), "evidence_levels": evidence_levels, "mode_descriptor_artifact_count": 0, "target_mapping_artifact_count": 0, "report_mac_artifact_count": 0, "physical_target_mapping_closed": False, "mac_against_report_available": False, "mac_unavailable_reason": "附件未提供 R19.2 质量归一化源模态向量，A10 也尚无方向/跨别/对称性描述量与全局一对一分配产物。", "prohibited_claim": "不得把 80 阶结果数闭合或频率近邻替代十四目标物理身份识别，也不得声称报告 MAC 已通过。", "unresolved_item": "需要在 A10/A30 全节点向量上生成可审计方向、S/A、跨域、波腹和局部参与描述量，再按证据等级 A/B/C 做十四目标全局分配。"}  # 返回真实闭合范围和未决项，不生成硬配阶次。


def validate_modal_results(postrun: dict[str, Any]) -> dict[str, Any]:  # 输入 A10 finalizer 门禁并返回原始 80 阶与十四目标范围审计。
    """核对 80 属性、80 SET、80+80 向量、80 SENE、频带越界和十四目标定义，不虚构物理 mapping。"""  # 函数说明覆盖模态结果完整性与身份边界。
    solver_dir = A10_DIR / "solver"  # 定位 A10 模态结果目录。
    property_path = solver_dir / "a10_modal_properties.csv"  # 定位十五列模态属性表。
    rows = read_numeric_csv(property_path)  # 直接读取八十行原始属性。
    require(len(rows) == EXPECTED_MODE_COUNT and all(len(row) == 15 for row in rows), "A10 模态属性不是 80 行十五列")  # 行数和列数必须同时闭合。
    require(all(row[0].is_integer() for row in rows) and [int(row[0]) for row in rows] == list(range(1, EXPECTED_MODE_COUNT + 1)), "A10 模态属性阶次不是连续 1..80")  # 第一列必须为无缺口整数阶次。
    frequencies = [row[1] for row in rows]  # 提取 Hz 频率列。
    require(all(frequency > 0.0 for frequency in frequencies), "A10 模态频率含非正值")  # 禁止未解释的零频或负特征值。
    require(all(frequencies[index] > frequencies[index - 1] for index in range(1, len(frequencies))), "A10 模态频率不是严格递增")  # 八十个特征根必须严格升序。
    in_band_count = sum(frequency <= 0.35 for frequency in frequencies)  # 统计任务书 0 至 0.35 Hz 内的实际结果数。
    require(in_band_count == 58 and frequencies[58] > 0.35 and frequencies[-1] > 0.35, "A10 80 阶未形成 0.35 Hz 上界越界证明")  # 第五十九阶和末阶必须越过关注频带。
    manifest_path = solver_dir / "a10_modal_export_manifest.txt"  # 定位请求/可用/导出阶数记录。
    manifest_text = manifest_path.read_text(encoding="utf-8", errors="replace")  # 读取求解器端导出摘要。
    require(re.search(r"REQUESTED=\s*80\.,\s*AVAILABLE=\s*80\.,\s*EXPORTED=\s*80\.", manifest_text) is not None, "A10 模态导出不是 80/80/80")  # 三个结果数量必须完全闭合。
    set_list_path = solver_dir / "a10_modal_set_list.txt"  # 定位 RSTP 原生结果集清单。
    set_text = set_list_path.read_text(encoding="utf-8", errors="replace")  # 读取 SET 清单原始文本。
    set_numbers = [int(match.group(1)) for match in re.finditer(r"(?m)^\s*(\d+)\s+[-+0-9.Ee]+\s+1\s+\d+\s+\d+\s*$", set_text)]  # 提取载荷步 1 的八十个模态结果集号。
    require(set_numbers == list(range(1, EXPECTED_MODE_COUNT + 1)), "A10 RSTP SET 清单不是连续 1..80")  # 原生结果集必须连续无缺口。
    displacement_paths = sorted(solver_dir.glob("mode_[0-9][0-9]_all_nodes.txt"), key=lambda path: path.name.lower())  # 枚举八十份全节点平移向量。
    rotation_paths = sorted(solver_dir.glob("mode_[0-9][0-9]_rotations.txt"), key=lambda path: path.name.lower())  # 枚举八十份有转角节点向量。
    require(len(displacement_paths) == EXPECTED_MODE_COUNT and len(rotation_paths) == EXPECTED_MODE_COUNT, "A10 模态向量不是 80+80")  # 两类向量数量必须同时闭合。
    expected_displacement_names = [f"mode_{mode:02d}_all_nodes.txt" for mode in range(1, EXPECTED_MODE_COUNT + 1)]  # 构造平移向量连续文件名。
    expected_rotation_names = [f"mode_{mode:02d}_rotations.txt" for mode in range(1, EXPECTED_MODE_COUNT + 1)]  # 构造转角向量连续文件名。
    require([path.name for path in displacement_paths] == expected_displacement_names and [path.name for path in rotation_paths] == expected_rotation_names, "A10 模态向量文件名不连续或重复")  # 文件名必须精确覆盖 01 至 80。
    for path, expected_title in [(path, "PRINT U    NODAL SOLUTION PER NODE") for path in displacement_paths] + [(path, "PRINT ROT  NODAL SOLUTION PER NODE") for path in rotation_paths]:  # 逐份核对向量大小、首部类型和完整尾部。
        require(path.stat().st_size >= MIN_VECTOR_BYTES, f"A10 模态向量疑似空壳：{path.name}")  # 每份全桥 PRNSOL 文本至少一百万字节。
        with path.open("rb") as stream:  # 以二进制只读方式抽查首尾而不加载整个文件。
            head = stream.read(65536).decode("ascii", errors="ignore")  # 首 64 KiB 应包含列表标题。
            stream.seek(max(path.stat().st_size - 8192, 0))  # 定位末尾 8 KiB 以读取极值汇总。
            tail = stream.read().decode("ascii", errors="ignore")  # 读取尾部并忽略非 ASCII 注释字节。
        require(expected_title in head and "POST1 NODAL DEGREE OF FREEDOM LISTING" in head and "MAXIMUM ABSOLUTE VALUES" in tail, f"A10 模态向量结构不完整：{path.name}")  # 标题、处理器和尾部必须齐全。
    energy_path = solver_dir / "a10_gate_bottom_modal_sene.csv"  # 定位主作业八十阶 GATE_BOTTOM_E 能量表。
    energy_rows = read_numeric_csv(energy_path)  # 直接读取四列能量原始表。
    require(len(energy_rows) == EXPECTED_MODE_COUNT and all(len(row) == 4 for row in energy_rows), "A10 GATE_BOTTOM SENE 不是 80 行四列")  # 能量表结构必须闭合。
    require([int(row[0]) for row in energy_rows] == list(range(1, EXPECTED_MODE_COUNT + 1)) and all(row[0].is_integer() and row[1] > 0.0 and row[2] >= 0.0 and 0.0 <= row[3] <= 1.0 for row in energy_rows), "A10 GATE_BOTTOM SENE 阶次或数值非法")  # 阶次连续、总能量正、组件非负且比例有效。
    finalizer_modal = postrun.get("modal", {})  # 读取 finalizer 模态摘要供原始数据交叉比对。
    require(finalizer_modal.get("property_rows") == EXPECTED_MODE_COUNT and finalizer_modal.get("set_count") == EXPECTED_MODE_COUNT and finalizer_modal.get("displacement_vectors", {}).get("count") == EXPECTED_MODE_COUNT and finalizer_modal.get("rotation_vectors", {}).get("count") == EXPECTED_MODE_COUNT, "A10 finalizer 模态摘要与原始数量不一致")  # 四类数量必须双向闭合。
    require(float(finalizer_modal.get("frequency_first_hz", math.nan)) == frequencies[0] and float(finalizer_modal.get("frequency_last_hz", math.nan)) == frequencies[-1] and finalizer_modal.get("frequency_in_0_to_0_35_hz_count") == in_band_count, "A10 finalizer 频率摘要与原始属性表不一致")  # 首末频率和频带数必须直接复现。
    target_gate = validate_target_reference_and_gap()  # 核对十四目标定义并登记物理 mapping 的真实缺口。
    return {"status": "PASSED_NUMERICAL_RESULTS_TARGET_PHYSICAL_MAPPING_OPEN", "requested": EXPECTED_MODE_COUNT, "available_sets": len(set_numbers), "exported_properties": len(rows), "displacement_vectors": len(displacement_paths), "rotation_vectors": len(rotation_paths), "sene_rows": len(energy_rows), "minimum_frequency_hz": frequencies[0], "maximum_frequency_hz": frequencies[-1], "frequency_strictly_increasing": True, "nonpositive_or_unexplained_zero_modes": 0, "frequency_0_to_0_35_hz_count": in_band_count, "first_mode_above_0_35_hz": in_band_count + 1, "first_frequency_above_0_35_hz": frequencies[in_band_count], "band_complete_not_truncated": True, "minimum_required_target_pool": EXPECTED_TARGET_COUNT, "candidate_pool_count": EXPECTED_MODE_COUNT, "candidate_pool_sufficient_for_14_targets": True, "target_mapping": target_gate, "sources": {"properties": {"path": property_path.relative_to(A10_DIR).as_posix(), "sha256": sha256_file(property_path)}, "set_list": {"path": set_list_path.relative_to(A10_DIR).as_posix(), "sha256": sha256_file(set_list_path)}, "export_manifest": {"path": manifest_path.relative_to(A10_DIR).as_posix(), "sha256": sha256_file(manifest_path)}, "gate_bottom_sene": {"path": energy_path.relative_to(A10_DIR).as_posix(), "sha256": sha256_file(energy_path)}}}  # 返回完整八十阶数值门禁和十四目标真实边界。


def validate_critical_results(jobname: str, ledger: dict[str, str], protected_sources: dict[str, Any]) -> dict[str, Any]:  # 输入作业名、A10 账本和已哈希源并返回关键文件完整性。
    """关键 DB/RST/RSTP/MODE/FULL/RDB/LDHI 必须唯一、非空、当前哈希等于 finalizer 全 run 账本。"""  # 函数说明覆盖结果复用的二进制充分条件。
    solver_dir = A10_DIR / "solver"  # 定位 A10 关键二进制结果目录。
    critical_names = {"equilibrium_database": f"{jobname}_eq.db", "modal_database": f"{jobname}_modal.db", "static_result": f"{jobname}.rst", "perturbation_result": f"{jobname}.rstp", "modal_vectors_binary": f"{jobname}.mode", "assembled_matrix": f"{jobname}.full", "database_snapshot": f"{jobname}.rdb", "load_history": f"{jobname}.ldhi"}  # 定义八类关键结果的唯一文件名。
    results: dict[str, dict[str, Any]] = {}  # 保存每类关键结果的当前大小和内容身份。
    protected_by_name = {Path(value["path"]).name: value for value in protected_sources.values()}  # 将四个 POSTONLY 源按文件名索引以避免重复大文件哈希。
    for role, name in critical_names.items():  # 逐类核验八个关键结果文件。
        path = solver_dir / name  # 构造当前角色的固定绝对路径。
        require(path.is_file() and path.stat().st_size > 0, f"A10 关键结果缺失或为空：{name}")  # 每类结果必须唯一非空。
        relative = path.relative_to(A10_DIR).as_posix()  # 构造 A10 账本使用的规范相对路径。
        require(relative in ledger, f"A10 最终账本未覆盖关键结果：{relative}")  # finalizer 全 run 账本必须保护当前文件。
        digest = str(protected_by_name[name]["sha256"]) if name in protected_by_name else sha256_file(path)  # 四个已复算源复用摘要，其余关键文件流式哈希。
        require(digest == ledger[relative], f"A10 关键结果当前哈希与最终账本不一致：{name}")  # 当前内容必须仍等于 finalizer 封板时。
        results[role] = {"path": relative, "size_bytes": path.stat().st_size, "sha256": digest, "ledger_match": True}  # 保存当前角色的完整性证据。
    vector_relatives = [f"solver/mode_{mode:02d}_all_nodes.txt" for mode in range(1, EXPECTED_MODE_COUNT + 1)] + [f"solver/mode_{mode:02d}_rotations.txt" for mode in range(1, EXPECTED_MODE_COUNT + 1)]  # 构造一百六十份向量的账本路径。
    require(all(relative in ledger for relative in vector_relatives), "A10 最终账本未覆盖全部 80+80 向量")  # 每份文本向量必须受全 run 账本保护。
    return {"status": "PASSED", "critical_file_count": len(results), "all_nonempty": True, "all_current_hashes_match_final_ledger": True, "modal_vector_ledger_entries": len(vector_relatives), "files": results}  # 返回八类关键文件和一百六十份向量的完整性结论。


def validate_a10_results(manifest: dict[str, Any]) -> dict[str, Any]:  # 输入 A10 清单并返回任务书级静力、模态、后处理和完整性审计。
    """把 finalizer 终态、原始 OUT/ERR、数值表、POSTONLY CSV、源哈希和关键二进制逐层交叉闭合。"""  # 函数说明给出结果复用的充分条件与真实限制。
    jobname = str(manifest.get("jobname", ""))  # 读取唯一实际求解作业名。
    require(jobname == "cw_A10_0715t172214_24", f"A10 jobname 漂移：{jobname}")  # 固定本次权威全桥作业身份。
    finalization = validate_a10_finalization(manifest)  # 首先拒绝 prepare-only 根状态并读取 finalizer 全 run 账本。
    postrun = finalization["postrun"]  # 提取已通过结构门禁的 A10 postrun 对象。
    messages = validate_solver_messages(jobname, postrun)  # 独立核对四份 OUT 与四份 ERR 的错误、pivot 和 warning。
    static = validate_static_topology(manifest, postrun)  # 独立核对 LS1/LS2、能量、质量、反力、拓扑和约束数量。
    postonly = validate_postonly_sources(postrun, jobname)  # 独立复核 LINK180、六组件 SENE 和四个只读源哈希。
    modal = validate_modal_results(postrun)  # 独立核对 80 阶结果闭合与十四目标真实证据边界。
    critical = validate_critical_results(jobname, finalization["artifact_ledger_entries"], postonly["protected_sources"])  # 核对八类关键结果与一百六十份向量的账本覆盖。
    finalization_summary = {key: value for key, value in finalization.items() if key not in {"postrun", "artifact_ledger_entries"}}  # 输出中保留 finalizer 身份而不重复嵌入全账本和完整 gate。
    return {"schema_version": 2, "status": "PASSED_RESULT_REUSE_WITH_DOCUMENTED_LIMITATIONS", "run_id": "A10_H175_AXIS", "run_name": A10_RUN_NAME, "jobname": jobname, "result_reuse_gate_status": "PASSED", "taskbook_full_static_gate_status": "PASSED_BY_DISABLED_STABILIZATION_CONTROL_WITH_NUMERIC_HISTORY_LIMITATION", "modal_numerical_completeness_status": "PASSED", "target_physical_mapping_status": modal["target_mapping"]["status"], "a30_result_reuse_authorized": True, "duplicate_full_bridge_solve_required": False, "finalization": finalization_summary, "solver_messages": messages, "static_gate": static, "link180_gate": postonly["link180"], "modal_energy_gate": postonly["sene6"], "read_only_source_integrity": {"status": postonly["status"], "source_metadata_unchanged_during_a30_qa": postonly["source_metadata_unchanged_during_a30_qa"], "protected_sources": postonly["protected_sources"]}, "modal_gate": modal, "critical_results": critical, "documented_limitations": {"legacy": finalization_summary["legacy_limitations"], "full_substep_sten_numeric_history": static["full_substep_history_limitation"], "target_physical_mapping": modal["target_mapping"]["unresolved_item"]}}  # 返回结果复用、任务书完整静力控制门禁通过以及两个证据边界。


def validate_run_name(value: str) -> str:  # 输入可选运行名并返回已验证原值。
    """只接受 A30_ALL_AXES_YYYYMMDDTHHMMSSffffffZ，拒绝路径字符。"""  # 函数说明给出格式边界。
    if RUN_NAME_PATTERN.fullmatch(value) is None:  # 非法格式进入 argparse 错误路径。
        raise argparse.ArgumentTypeError("run name must match A30_ALL_AXES_YYYYMMDDTHHMMSSffffffZ")  # 返回预期格式。
    return value  # 合法值原样返回。


def main() -> int:  # 无物理参数；成功封板 A30 输入/结果等价时返回 0。
    """验证 A20 零差异、A10 输入和实际结果，再生成不复制大文件的 A30 引用包。"""  # 函数说明给出总体流程和副作用。
    parser = argparse.ArgumentParser(description="Seal A30=A10 input/result equivalence after the A20 zero-difference gate; never starts MAPDL.")  # 创建仅允许运行名的接口。
    parser.add_argument("--run-name", type=validate_run_name, default=None, help="Optional exact A30_ALL_AXES_<UTC-microseconds>Z directory name.")  # 支持确定性测试目录。
    arguments = parser.parse_args()  # 解析命令行并拒绝未知参数。
    for required_path in (A10_DIR / "manifest.json", A20_DIR / "manifest.json"):  # 枚举主清单前置文件。
        require(required_path.is_file(), f"A30 前置清单缺失：{required_path}")  # 任一缺失即停止。
    parent_run_roots = {"A10": A10_DIR, "A20": A20_DIR}  # 固定两个只读父运行标签与根目录，禁止把其他运行混入元数据审计。
    parent_run_names = {"A10": A10_RUN_NAME, "A20": A20_RUN_NAME}  # 固定标签到正式父运行名的映射供机器摘要引用。
    parent_metadata_before = {label: snapshot_run_file_metadata(root) for label, root in parent_run_roots.items()}  # 在读取清单、CSV 和大文件前快照 A10/A20 全部普通文件元数据。
    a10_manifest = read_json(A10_DIR / "manifest.json")  # 读取 A10 准备与物理差异合同。
    require(a10_manifest.get("run_id") == "A10_H175_AXIS", "A10 清单 run_id 不符")  # 防止引用错误运行目录。
    physical_contract = a10_manifest.get("physical_change_contract", {})  # 读取 H175 单差异合同。
    require(physical_contract.get("status") == "PASSED" and physical_contract.get("physical_change_family_count") == 1, "A10 H175 单差异合同未通过")  # A30 必须保留已证实的唯一 H175 轴修复。
    require(physical_contract.get("physical_change_family") == "H175_BEAM188_ORIENTATION_NODE_K_ONLY", "A10 物理差异家族错误")  # 禁止混入其他变更。
    a20_evidence = validate_a20()  # 验证 RHS 方向已经正确且不需要改变。
    input_evidence = validate_a10_inputs(a10_manifest)  # 验证 A10 实际求解的 11 个依赖身份。
    result_evidence = validate_a10_results(a10_manifest)  # 验证 A10 完整静力和 80 阶结果。
    parent_metadata_after = {label: snapshot_run_file_metadata(root) for label, root in parent_run_roots.items()}  # 在全部父证据读取和四源大文件哈希完成后重新快照两个父运行。
    require(parent_metadata_after == parent_metadata_before, "A30 只读 QA 期间 A10/A20 父运行文件元数据发生变化")  # 路径集合、大小或纳秒修改时间任一变化均禁止封板。
    parent_metadata_rows: dict[str, dict[str, Any]] = {}  # 初始化 A10/A20 两行可写入权威包的元数据摘要。
    for label in ("A10", "A20"):  # 按固定父运行顺序构造前后摘要并再次逐项闭合。
        before_summary = summarize_run_file_metadata(parent_metadata_before[label])  # 计算当前父运行执行前的文件计数、总字节数和元数据身份。
        after_summary = summarize_run_file_metadata(parent_metadata_after[label])  # 计算同一父运行执行后的文件计数、总字节数和元数据身份。
        require(before_summary == after_summary, f"{label} 父运行元数据摘要前后不一致")  # 摘要必须与完整映射相等门禁给出一致结论。
        parent_metadata_rows[label] = {"run_name": parent_run_names[label], "file_count_before": before_summary["file_count"], "file_count_after": after_summary["file_count"], "total_bytes_before": before_summary["total_bytes"], "total_bytes_after": after_summary["total_bytes"], "metadata_identity_sha256_before": before_summary["metadata_identity_sha256"], "metadata_identity_sha256_after": after_summary["metadata_identity_sha256"], "unchanged_during_a30_qa": True}  # 保存不复制逐文件清单的双时点闭合摘要。
    parent_metadata_audit = {"schema_version": 1, "status": "PASSED", "scope": "ALL_REGULAR_FILES_PATH_SIZE_MTIME_NS", "parents": parent_metadata_rows}  # 形成 A10/A20 全文件元数据前后不变的独立机器证据。
    created_at = datetime.now(timezone.utc)  # 记录当前 UTC 时间。
    run_name = arguments.run_name or f"{RUN_PREFIX}_{created_at.strftime('%Y%m%dT%H%M%S%f')}Z"  # 生成唯一 A30 目录名。
    run_dir = ULTRA_RUNS_DIR / run_name  # 构造正式输出路径。
    require(not run_dir.exists(), f"A30 运行目录已存在：{run_dir}")  # 禁止覆盖既有证据。
    qa_dir = run_dir / "qa"  # 定位 A30 QA 子目录。
    qa_dir.mkdir(parents=True, exist_ok=False)  # 原子创建全新目录树。
    taskbook_gate_summary = {"schema_version": 1, "status": "PASS_RESULT_REUSE_WITH_DOCUMENTED_LIMITATIONS", "result_reuse_gate": "PASSED", "static": {"ls1_converged": True, "ls2_hold_converged": True, "ls1_endpoint_abs_sten_over_sene": result_evidence["static_gate"]["ls1_abs_sten_over_sene"], "ls1_endpoint_limit": LS1_ENERGY_RATIO_LIMIT, "ls2_abs_sten_over_sene": result_evidence["static_gate"]["ls2_abs_sten_over_sene"], "ls2_limit": LS2_ENERGY_RATIO_LIMIT, "full_substep_peak_gate_status": result_evidence["static_gate"]["full_substep_peak_gate_status"], "full_substep_stabilization_control_bound": result_evidence["static_gate"]["full_substep_stabilization_control_bound"], "full_substep_peak_abs_sten_over_sene_numeric_history": None, "full_substep_numeric_history_available": False, "mass_error_tonne": result_evidence["static_gate"]["mass_abs_error_tonne"], "mass_limit_tonne": MASS_ABSOLUTE_TOLERANCE_TONNE, "vertical_support_count": result_evidence["static_gate"]["uz_support_count"], "reaction_relative_error": result_evidence["static_gate"]["reaction_relative_error"], "reaction_limit": REACTION_RELATIVE_TOLERANCE}, "solver_messages": {"mapdl_errors": result_evidence["solver_messages"]["summary_error_count"], "negative_pivots": result_evidence["solver_messages"]["negative_pivot_count"], "zero_pivots": result_evidence["solver_messages"]["zero_pivot_count"], "warning_markers": result_evidence["solver_messages"]["main_warning_markers"], "all_warnings_disposed": result_evidence["solver_messages"]["all_warnings_disposed"]}, "link180": {"actual_count": result_evidence["link180_gate"]["actual_count"], "unique_count": result_evidence["link180_gate"]["unique_count"], "nonpositive_count": result_evidence["link180_gate"]["nonpositive_count"], "minimum_force_n": result_evidence["link180_gate"]["minimum_force_n"]}, "modal": {"requested": result_evidence["modal_gate"]["requested"], "available_sets": result_evidence["modal_gate"]["available_sets"], "exported_properties": result_evidence["modal_gate"]["exported_properties"], "displacement_vectors": result_evidence["modal_gate"]["displacement_vectors"], "rotation_vectors": result_evidence["modal_gate"]["rotation_vectors"], "band_complete_not_truncated": result_evidence["modal_gate"]["band_complete_not_truncated"], "target_reference_count": result_evidence["modal_gate"]["target_mapping"]["reference_target_count"], "target_physical_mapping_closed": False}, "source_integrity": {"status": result_evidence["read_only_source_integrity"]["status"], "protected_source_count": len(result_evidence["read_only_source_integrity"]["protected_sources"]), "four_source_hashes_current_and_historical": True, "source_metadata_unchanged_during_a30_qa": True, "a10_a20_full_run_metadata_unchanged": parent_metadata_audit["status"] == "PASSED"}, "critical_results": {"status": result_evidence["critical_results"]["status"], "critical_file_count": result_evidence["critical_results"]["critical_file_count"], "modal_vector_ledger_entries": result_evidence["critical_results"]["modal_vector_ledger_entries"]}, "limitations": ["两个完整静力载荷步均由输入顺序和两次求解器 KEY=OFF 回显证明 STABILIZE,OFF，全历程稳定化能峰值门禁通过；RST 未保存逐子步数值曲线。", "十四目标定义和 80 阶候选池已闭合，但 A10 尚无方向/跨别/对称性描述量与报告源向量 MAC，物理 mapping 未封板。"]}  # 构造结论优先的任务书门禁摘要并加入四源哈希和父运行全文件元数据闭合。
    equivalence_contract = {"schema_version": 2, "status": "PASSED", "qa_status": "PASS_RESULT_REUSE_WITH_DOCUMENTED_LIMITATIONS", "a30_definition": "A10_H175_AXIS_ONLY + A20_RHS5030_AXIS_ONLY", "a10_physical_change_family": "H175_BEAM188_ORIENTATION_NODE_K_ONLY", "a20_physical_change_required_count": 0, "a30_dependency_identity": input_evidence["combined_dependency_identity"], "a10_dependency_identity": input_evidence["combined_dependency_identity"], "byte_identical_a30_candidate_to_a10": True, "parent_run_metadata_audit_status": parent_metadata_audit["status"], "four_protected_source_hashes_closed": True, "a10_final_status": A10_FINAL_STATUS, "a10_result_reuse_gate": result_evidence["result_reuse_gate_status"], "taskbook_full_static_gate_status": result_evidence["taskbook_full_static_gate_status"], "modal_numerical_completeness_status": result_evidence["modal_numerical_completeness_status"], "target_physical_mapping_status": result_evidence["target_physical_mapping_status"], "duplicate_solver_run_required": False, "duplicate_solver_run_performed": False, "result_reuse_basis": "A20 物理改动为零，A30 与 A10 的 11 项求解依赖字节相同；A10 已正式封板，LS1/LS2、日志、轴力、80 阶模态、能量、源完整性和关键结果均由原始证据复核。", "next_physical_variant": "S10_SECTION_SHEAR", "unresolved_source_items": ["FULL_SUBSTEP_STEN_NUMERIC_CURVE_UNAVAILABLE_GATE_PASSED_BY_OFF_CONTROL", "TARGET_PHYSICAL_MAPPING_AND_REPORT_MAC_OPEN"]}  # 形成 A30=A10 的机器可读证明并绑定父运行元数据及四源哈希闭合。
    status_payload = {"schema_version": 2, "run_id": "A30_ALL_AXES", "run_name": run_name, "status": "COMPLETED_BY_INPUT_IDENTITY_WITH_A10_RESULTS", "qa_status": "PASS_RESULT_REUSE_WITH_DOCUMENTED_LIMITATIONS", "created_at_utc": created_at.isoformat(), "parents": [A10_RUN_NAME, A20_RUN_NAME], "h175_axis_corrected_count": 2698, "rhs50x30_axis_already_correct_count": EXPECTED_RHS_COUNT, "physical_axis_families_complete": 2, "mapdl_started_for_a30_alias": False, "reused_full_static_modal_run": A10_RUN_NAME, "a10_final_status": A10_FINAL_STATUS, "parent_run_metadata_unchanged": True, "four_protected_source_hashes_closed": True, "static_result_reuse_gate": "PASSED", "modal_numerical_completeness_gate": "PASSED", "target_physical_mapping_closed": False, "unresolved_source_item_count": 2, "next_step": "S10_SECTION_SHEAR"}  # 写出等价复用、父源只读、四源哈希、数值通过和目标识别缺口的准确状态。
    manifest_payload = {"schema_version": 2, "run_id": "A30_ALL_AXES", "run_name": run_name, "model_line": "PHYSICALLY_CORRECTED_ALL_NONCIRCULAR_AXES", "status": status_payload["status"], "qa_status": status_payload["qa_status"], "created_at_utc": created_at.isoformat(), "parents": [A10_RUN_NAME, A20_RUN_NAME], "parent_run_metadata_audit": parent_metadata_audit, "a20_evidence": a20_evidence, "a10_input_evidence": input_evidence, "a10_result_evidence": result_evidence, "taskbook_gate_summary": taskbook_gate_summary, "equivalence_contract": equivalence_contract, "outputs": ["A30_status.json", "manifest.json", "result_packet.md", "qa/a30_input_result_equivalence.json", "qa/a30_taskbook_gate_summary.json", "qa/a10_a20_source_metadata_audit.json", "qa/a10_external_completion_qa.json", "qa/field_dictionary.md", "qa/unresolved_source_items.md", "artifact_hashes.sha256"]}  # 汇总全部来源、结果、父运行元数据、限制和产物。
    write_json(qa_dir / "a30_input_result_equivalence.json", equivalence_contract)  # 写核心等价证明。
    write_json(qa_dir / "a30_taskbook_gate_summary.json", taskbook_gate_summary)  # 写结论优先的静力、日志、轴力、模态和完整性摘要。
    write_json(qa_dir / "a10_a20_source_metadata_audit.json", parent_metadata_audit)  # 写 A10/A20 两个父运行全文件元数据前后不变证明。
    write_json(qa_dir / "a10_external_completion_qa.json", result_evidence)  # 补充 A10 准备清单之后的实际外部 QA。
    write_json(run_dir / "A30_status.json", status_payload)  # 写 A30 正式状态。
    write_json(run_dir / "manifest.json", manifest_payload)  # 写完整 A30 清单。
    field_dictionary = """# A30 等价包字段说明

- `COMPLETED_BY_INPUT_IDENTITY_WITH_A10_RESULTS`：A30 没有另起一份相同输入的 MAPDL 作业；它以字节级证据复用已经从头完成的 A10 静力—保持—80 阶模态结果。
- `physical_axis_families_complete=2`：H175 轴由 A10 修正；RHS50×30 由 A20 证明 B00 已正确、改动数为零。
- `combined_dependency_identity`：按 11 个 include 的顺序、文件名和 SHA-256 拼接后再计算的组合身份。
- `byte_identical_a30_candidate_to_a10=true`：A30 合并物理定义不会在 A10 之外增加任何输入字节变化。
- `duplicate_solver_run_required=false`：重复运行相同输入不会增加因果信息；A10 的 LS1、LS2、OUT/ERR、LINK180、80 阶、六组件 SENE 和全节点向量已独立复核。
- `taskbook_full_static_gate_status`：端点静力与数值门禁通过，但 RST 未保存 LS1 全历程逐子步 VENG，因此不得填写或声称全历程峰值 STEN/SENE。
- `target_physical_mapping_status`：十四目标定义和 80 阶候选池闭合；当前没有方向、跨别、S/A、波腹描述量和报告 R19.2 源向量 MAC，因此物理 mapping 保持未封板。
- `critical_results`：A10 的平衡 DB、模态 DB、RST、RSTP、MODE、FULL、RDB、LDHI 当前哈希与 finalizer 全 run 账本一致。
- `read_only_source_integrity`：LINK180 与六组件 SENE 两次 POSTONLY 使用的四个源 DB/RST 在运行前后以及 A30 QA 当下均保持相同 SHA-256。
- `parent_run_metadata_audit`：A10/A20 父运行内全部普通文件的相对路径、字节数与纳秒修改时间在 A30 QA 前后完全相同；摘要不包含访问时间，避免只读操作自身造成伪漂移。

JSON 语法不支持注释，因此本文件解释固定状态、布尔值和组合身份的含义。
"""  # 为不支持注释的 JSON 字段逐项说明语义。
    (qa_dir / "field_dictionary.md").write_text(field_dictionary, encoding="utf-8")  # 写字段说明 Markdown。
    unresolved_source_items = """# A30 未决证据项

1. `FULL_SUBSTEP_STEN_HISTORY_UNAVAILABLE`：A10 RST 只保存 LS1/LS2 端点 VENG。两个端点的 STEN/SENE 均远低于阈值，但未保存的 LS1 逐子步历史不能由 POST1 恢复，也不能把端点值冒充全历程峰值。
2. `TARGET_PHYSICAL_MAPPING_AND_REPORT_MAC_OPEN`：附件十四目标定义和 A10 80 阶候选池均完整；A10 尚无方向、跨别、正/反对称、波腹和局部参与描述量的正式全局分配。附件也未提供 R19.2 质量归一化源向量，所以不得声称报告 MAC 已通过。A/B/C 证据等级分别为有图六项、仅标签频率五项和笼统边跨三项。

上述两项不否定 A30=A10 的输入/结果等价或现有数值结果复用，但禁止将状态简化为“无条件全部物理目标已闭合”。
"""  # 形成独立、不可藏入脚注的未决项清单。
    (qa_dir / "unresolved_source_items.md").write_text(unresolved_source_items, encoding="utf-8")  # 写任务书要求的显式未决来源项。
    result_packet = f"""# A30 全部非圆截面轴基线结果

- 状态：`COMPLETED_BY_INPUT_IDENTITY_WITH_A10_RESULTS`
- QA：`PASS_RESULT_REUSE_WITH_DOCUMENTED_LIMITATIONS`
- H175：A10 已修正 2,698 根并完成全桥求解。
- RHS50×30：A20 已证明 2,898/2,898 根在 B00 中本来正确，物理改动数为 0。
- A30 候选 11 项依赖与 A10 字节身份：一致。
- 静力：LS1/LS2 均收敛；端点 STEN/SENE={result_evidence['static_gate']['ls1_abs_sten_over_sene']:.16g}/{result_evidence['static_gate']['ls2_abs_sten_over_sene']:.16g}；质量误差={result_evidence['static_gate']['mass_abs_error_tonne']:.16g} tonne；反力相对误差={result_evidence['static_gate']['reaction_relative_error']:.16g}。
- 日志：四份 OUT 与四份 ERR 为 0 ERROR、0 FATAL、0 negative pivot、0 zero pivot；五条已知 warning 全部逐项处置。
- LINK180：{result_evidence['link180_gate']['actual_count']} 个唯一元素全部覆盖，非正轴力 0，最小轴力 {result_evidence['link180_gate']['minimum_force_n']:.16g} N。
- 模态：80/80/80、80+80 节点向量、80 行主能量及 80×6 六组件能量完整；第 {result_evidence['modal_gate']['first_mode_above_0_35_hz']} 阶越过 0.35 Hz，频带未被阶数截断。
- 源完整性：平衡 DB、静力 RST、模态 DB、RSTP 的当前 SHA-256 与两套只读 POSTONLY 前后身份一致；A30 QA 未改源文件。
- 父运行元数据：A10 共 {parent_metadata_rows['A10']['file_count_after']} 个文件、A20 共 {parent_metadata_rows['A20']['file_count_after']} 个文件的路径、大小与 mtime_ns 在本次 QA 前后完全一致。
- 关键结果：8 类关键二进制当前哈希均与 A10 finalizer 全 run 账本一致，160 份向量全部受账本覆盖。
- 新 A30 MAPDL 作业：未启动；原因是输入完全相同，重复求解没有新增物理信息。
- 未决：全历程逐子步 STEN/SENE 未保存；十四目标物理 mapping 与报告 MAC 尚未封板，详见 `qa/unresolved_source_items.md`。
- 下一实际物理变体：`S10_SECTION_SHEAR`。
"""  # 概括 A30 的等价逻辑和下一步。
    (run_dir / "result_packet.md").write_text(result_packet, encoding="utf-8")  # 写人类可读结果包。
    artifact_candidates = sorted(path for path in run_dir.rglob("*") if path.is_file() and path.name != "artifact_hashes.sha256")  # 枚举除自引用清单外全部生成文件。
    artifact_hash_lines = [f"{sha256_file(path)}  {path.relative_to(run_dir).as_posix()}" for path in artifact_candidates]  # 计算每个产物的稳定相对路径哈希。
    (run_dir / "artifact_hashes.sha256").write_text("\n".join(artifact_hash_lines) + "\n", encoding="utf-8")  # 写非自引用产物清单。
    print(json.dumps({"run_dir": str(run_dir), "status": status_payload["status"], "reused_run": A10_RUN_NAME, "modes": EXPECTED_MODE_COUNT, "next_step": status_payload["next_step"]}, ensure_ascii=False))  # 向调用者输出唯一机器摘要。
    return 0  # 全部门禁通过并成功写包时返回 0。


if __name__ == "__main__":  # 只有直接执行脚本时才运行正式入口，导入保持无副作用。
    raise SystemExit(main())  # 把 main 返回值传递为进程退出码。
