"""对已外部执行完成的 A10 运行包实施只读证据门禁，并在全部通过后一次性封板真实终态。"""  # 模块只读取 solver 与正式后处理证据，写入范围严格限制为根状态、lineage、qa、结果包、编排器快照和哈希账本。

from __future__ import annotations  # 启用延迟类型注解，避免复杂容器类型在导入阶段产生兼容性副作用。

import argparse  # 解析仅用于测试或明确指定正式 LINK180 QA 的可选路径参数。
import copy  # 深复制 prepare 期 manifest，保留全部历史字段后再更新真实执行终态。
import csv  # 严格读取无标题纯数值 CSV，并核对列数、行数和有限数值。
import hashlib  # 流式计算源证据、正式 QA、编排器与全 run 产物的 SHA-256。
import json  # 读取机器 QA，并生成合法的根状态、manifest 与 postrun gate JSON。
import math  # 拒绝 CSV 中的 NaN 和无穷值，并执行数值容差门禁。
import os  # 提供 fsync 与原子 os.replace，避免半写状态成为正式证据。
import re  # 严格提取 MAPDL 警告、错误、收敛摘要、静力键值和结果集清单。
from datetime import datetime, timezone  # 生成采用 UTC 的唯一最终化时间戳。
from pathlib import Path  # 统一处理 run 内绝对路径、相对账本路径和越界写入门禁。
from typing import Any  # 描述 JSON 动态对象、数值表和证据汇总字典。


SCRIPT_PATH = Path(__file__).resolve()  # 固定当前 finalizer 源码绝对路径，供自身哈希和 run 内快照使用。
TOOLS_DIR = SCRIPT_PATH.parent  # ultra_tools 是 finalizer 所在且唯一允许新增源码的位置。
PROJECT_ROOT = TOOLS_DIR.parent  # V2.0 项目根目录承载 ultra_runs 与全部冻结证据。
RUN_NAME = "A10_H175_AXIS_20260715T172214962299Z"  # 本脚本只允许封板这一已明确指定的 A10 正式 run。
RUN_DIR = PROJECT_ROOT / "ultra_runs" / RUN_NAME  # 指向待最终化 A10 run 的唯一绝对目录。
SOLVER_DIR = RUN_DIR / "solver"  # solver 目录在本脚本中永久只读，任何写目标均不得位于其下。
QA_DIR = RUN_DIR / "qa"  # 最终 postrun 机器门禁与警告处置文档写入既有 qa 目录。
LINEAGE_DIR = RUN_DIR / "lineage"  # prepare 期根状态与 manifest 原始字节归档到既有 lineage 目录。
ORCHESTRATOR_DIR = RUN_DIR / "orchestrator_snapshot"  # finalizer 源码快照与 prepare 编排器快照并列保存。
STATUS_PATH = RUN_DIR / "A10_status.json"  # 根状态将从 prepare 事实更新为真实执行终态。
MANIFEST_PATH = RUN_DIR / "manifest.json"  # 根 manifest 将保留准备字段并补入真实执行与 postrun 字段。
RESULT_PACKET_PATH = RUN_DIR / "result_packet.md"  # 原 prepare 说明将更新为可读的最终结果包。
LEDGER_PATH = RUN_DIR / "artifact_hashes.sha256"  # 全 run 账本覆盖旧 prepare 账本且按设计排除自身。
PREPARE_STATUS_ARCHIVE = LINEAGE_DIR / "A10_status.prepare_original.json"  # 固定保存 prepare 根状态原始字节且禁止覆盖。
PREPARE_MANIFEST_ARCHIVE = LINEAGE_DIR / "manifest.prepare_original.json"  # 固定保存 prepare manifest 原始字节且禁止覆盖。
POSTRUN_GATE_PATH = QA_DIR / "postrun_gate.json"  # 机器可读最终门禁的固定路径。
EXTERNAL_COMPLETION_QA_PATH = QA_DIR / "a10_external_completion_qa.json"  # 提供 A30 与后续任务复用的统一外部完成证据入口；内容与 postrun gate 逐字节一致。
WARNING_DISPOSITION_PATH = QA_DIR / "warning_disposition.md"  # 五条 warning 的逐项工程处置固定路径。
EXECUTION_FIELDS_PATH = QA_DIR / "execution_field_dictionary.md"  # 最终 JSON 与状态字段的相邻中文说明路径。
FINALIZER_SNAPSHOT_PATH = ORCHESTRATOR_DIR / "ultra_a10_finalize.py"  # run 内保存本次最终化源码的逐字节快照。
MAIN_OUT_PATH = SOLVER_DIR / "cw_a10_0715t172214_24.out"  # 37 MB 主 OUT 是执行、警告、错误与模态收敛的权威证据。
MAIN_INPUT_PATH = SOLVER_DIR / "a10_h175_axis_main.inp"  # 主输入用于核对无频带上限和两次 STABILIZE,OFF 控制状态。
EQUILIBRIUM_DB_PATH = SOLVER_DIR / "cw_A10_0715t172214_24_eq.db"  # LS2 平衡数据库必须继续匹配 LINK180 POSTONLY 记录的当前 SHA-256。
STATIC_RST_PATH = SOLVER_DIR / "cw_A10_0715t172214_24.rst"  # LS1/LS2 静力结果文件必须继续匹配 LINK180 POSTONLY 记录的当前 SHA-256。
MODAL_DB_PATH = SOLVER_DIR / "cw_A10_0715t172214_24_modal.db"  # 线性摄动模态数据库必须继续匹配六组件 SENE POSTONLY 记录的当前 SHA-256。
MODAL_RSTP_PATH = SOLVER_DIR / "cw_A10_0715t172214_24.rstp"  # 合并后的 80 阶模态结果文件必须继续匹配六组件 SENE POSTONLY 记录的当前 SHA-256。
STATIC_TABLE_PATH = SOLVER_DIR / "a10_static_energy_mass_reaction.txt"  # 静力收敛、能量、质量和反力表的固定路径。
MODAL_TABLE_PATH = SOLVER_DIR / "a10_modal_properties.csv"  # 80 行十五列模态属性表的固定路径。
MODAL_MANIFEST_PATH = SOLVER_DIR / "a10_modal_export_manifest.txt"  # requested/available/exported 三个 80 的固定证据。
MODAL_SET_LIST_PATH = SOLVER_DIR / "a10_modal_set_list.txt"  # RSTP 原生 80 结果集索引的固定证据。
GATE_STATUS_PATH = SOLVER_DIR / "a10_gate_status.txt"  # solver 导出完成且等待外部 QA 的固定状态文件。
EXPECTED_PREPARE_STATUS = "PREPARED_NOT_STARTED_USER_OVERRIDE"  # 仅允许从用户覆盖后的 prepare 状态执行一次最终化。
FINAL_STATUS = "PASS_WITH_LEGACY_LIMITATIONS"  # 工程数值门禁通过但保留 legacy CERIG、病态尺度和 STEN 历史边界。
EXECUTION_STATUS = "EXECUTED"  # 明确 MAPDL 已由外部命令真实执行完成，而非仍处于准备阶段。
EXPECTED_MODES = 80  # 模态属性、结果集、位移向量和转角向量均必须覆盖 1 至 80 阶。
TASKBOOK_TARGET_MODES = 14  # 任务书给出 14 个目标物理模态，但禁止按阶号硬配；A10 必须保留覆盖它们所需的全部 80 阶原始能量。
EXPECTED_VECTOR_FILES = 80  # 每类模态向量文件的冻结目标数量。
MIN_VECTOR_BYTES = 1_000_000  # 每个全桥 PRNSOL 文本至少 1,000,000 字节，防止空壳文件通过计数。
EXPECTED_COMPONENT_COUNTS = [2698, 1562, 4011, 1890, 4620, 2898, 17679, 17679, 17679, 17679, 80]  # 六组件、和、并集、TYPE70、交集和结果集的冻结数列。
EXPECTED_LINK180_COUNT = 73692  # LINK180 TYPE4 元素总数必须与拓扑统计完全一致。
FREQUENCY_BAND_HZ = 0.35  # 旧交付关注频带上限为 0.35 Hz，本次第 59 阶必须越过该值以证明未截断。
EXPECTED_IN_BAND_MODES = 58  # 当前权威结果在不大于 0.35 Hz 内恰有 58 阶，第 59 阶首次越界。
EXPECTED_WARNINGS = 5  # 主 OUT 中实际 warning 标记为四条求解期警告加一条退出后性能警告。
EXPECTED_SUMMARY_WARNINGS = 4  # MAPDL 退出摘要先报告四条，随后才追加第五条 elapsed/CPU 性能警告。
EXPECTED_CLEAN_ERR_BYTES = 80  # 两个正式 POSTONLY 会话的 ERR 仅含 MAPDL 版本标识，冻结大小为 80 字节且不含警告或错误。
BINARY_SUFFIXES = {".db", ".rst", ".rstp", ".rdb", ".full", ".emat", ".esav", ".mode", ".mlv", ".r001", ".r002", ".dsp"}  # 这些 solver 后缀按二进制元数据实施前后不变门禁。
WARNING_FRAGMENTS = ["constraint equations may not be valid for elements that undergo large deflections", "coefficient ratio exceeds 1.0e8", "reference moment convergence value = 7.05020414e-02", "reference moment convergence value = 1.741355963e-03", "elapsed time exceeds the cpu time by 33%"]  # 五条实际 warning 的规范化唯一识别片段。


def require(condition: bool, message: str) -> None:  # 输入布尔门禁与失败说明，成功无返回，失败立即抛出异常。
    """所有最终化条件均 fail-closed；本函数自身不写文件。"""  # 函数契约强调任何不确定性不得进入真实终态写入阶段。
    if not condition:  # 仅当硬门禁为假时进入拒绝路径。
        raise RuntimeError(message)  # 抛出含上下文的异常并由顶层返回非零退出码。


def sha256_bytes(payload: bytes) -> str:  # 输入任意字节串并返回 64 位小写十六进制 SHA-256。
    """内存字节摘要用于 prepare 原件、生成 JSON 与 finalizer 快照的身份闭合。"""  # 函数说明固定输入输出且无文件副作用。
    return hashlib.sha256(payload).hexdigest()  # 一次性计算并返回规范小写摘要。


def sha256_file(path: Path) -> str:  # 输入现存普通文件并流式返回 SHA-256。
    """采用 8 MiB 块读取大结果文件，兼顾 20 GB 全 run 账本吞吐和有限内存。"""  # 函数说明给出块大小、用途和内存约束。
    require(path.is_file(), f"待哈希文件不存在：{path}")  # 哈希前确认目标是普通文件而非目录或缺失路径。
    digest = hashlib.sha256()  # 为当前文件创建独立 SHA-256 累加器。
    with path.open("rb") as stream:  # 以二进制只读方式打开，禁止换行和编码转换。
        while True:  # 循环读取直至明确遇到 EOF。
            block = stream.read(8 * 1024 * 1024)  # 每次读取 8 MiB 原始字节以提高大文件吞吐。
            if not block:  # 空字节串仅表示正常到达文件末尾。
                break  # 结束读取循环并保留累计摘要。
            digest.update(block)  # 把当前原始字节块加入摘要状态。
    return digest.hexdigest()  # 返回当前完整文件的 64 位小写摘要。


def json_bytes(value: dict[str, Any]) -> bytes:  # 输入 JSON 顶层对象并返回无 BOM UTF-8 字节。
    """采用两空格缩进、中文直写和末尾 LF；JSON 不插入非法注释。"""  # 函数说明固定机器格式并由相邻 Markdown 解释字段。
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")  # 渲染确定性可读 JSON 并编码为 UTF-8。


def read_json(path: Path) -> dict[str, Any]:  # 输入 JSON 文件并返回已验证为对象的字典。
    """按 UTF-8-sig 严格解析；缺失、语法错误或非对象顶层均拒绝。"""  # 函数说明给出编码兼容和 fail-closed 结构约束。
    require(path.is_file(), f"缺少 JSON 证据：{path}")  # 读取前确认普通文件存在。
    value = json.loads(path.read_text(encoding="utf-8-sig"))  # 兼容可选 BOM 并严格解析合法 JSON。
    require(isinstance(value, dict), f"JSON 顶层不是对象：{path}")  # 顶层必须具名字段便于门禁。
    return value  # 返回结构已验证的 JSON 对象。


def read_mixed_text(path: Path) -> str:  # 输入 MAPDL 或历史文本并返回可搜索 Unicode 字符串。
    """MAPDL OUT 混合编码时以 UTF-8 replacement 解码；全部门禁片段均为不受替换影响的 ASCII。"""  # 函数说明明确替换策略仅服务 ASCII 证据。
    require(path.is_file(), f"缺少文本证据：{path}")  # 读取前确认目标是普通文件。
    return path.read_text(encoding="utf-8", errors="replace")  # 一次读取文本并以替换字符承载非 UTF-8 注释字节。


def parse_numeric_csv(path: Path, columns: int) -> list[list[float]]:  # 输入无标题 CSV 与期望列数并返回有限浮点矩阵。
    """拒绝空行、列数漂移、非数值、NaN 和无穷；原文件保持只读。"""  # 函数说明给出输入约束、输出结构和异常条件。
    require(path.is_file(), f"缺少纯数值 CSV：{path}")  # 解析前确认目标存在。
    rows: list[list[float]] = []  # 初始化保持原始行顺序的数值矩阵。
    with path.open("r", encoding="utf-8-sig", newline="") as stream:  # 按 UTF-8 读取并让 csv 模块保持字段边界。
        for row_number, raw_row in enumerate(csv.reader(stream), start=1):  # 逐行解析并保留一基行号供错误定位。
            require(len(raw_row) == columns, f"CSV 第 {row_number} 行列数不是 {columns}：{path}")  # 每行必须命中固定列契约。
            values = [float(token.strip()) for token in raw_row]  # 将允许科学计数法的字段转换为双精度浮点。
            require(all(math.isfinite(value) for value in values), f"CSV 第 {row_number} 行含非有限数：{path}")  # 拒绝 NaN 和正负无穷。
            rows.append(values)  # 保存当前已验证数值行。
    require(bool(rows), f"纯数值 CSV 为空：{path}")  # 空文件不能作为正式证据。
    return rows  # 返回完整有限数值矩阵。


def validate_current_source_file(path: Path, expected_size: int, expected_sha256: str, evidence_role: str) -> dict[str, Any]:  # 输入 solver 源文件、POSTONLY 记录的字节数/摘要和证据角色，并返回当前身份对象。
    """直接重算当前源文件 SHA-256，拒绝仅凭后处理完成时的历史不变声明封板。"""  # 函数说明覆盖 DB、RST、模态 DB 与 RSTP 四个大文件的当前时点完整性。
    require(path.is_file(), f"缺少 {evidence_role} 源文件：{path}")  # 四个权威源必须仍是现存普通文件。
    require(isinstance(expected_size, int) and expected_size > 0, f"{evidence_role} 的预期字节数非法：{expected_size}")  # POSTONLY 记录的大小必须是正整数。
    normalized_expected_sha256 = expected_sha256.strip().lower()  # 统一历史摘要大小写以便与本脚本小写摘要精确比较。
    require(re.fullmatch(r"[0-9a-f]{64}", normalized_expected_sha256) is not None, f"{evidence_role} 的预期 SHA-256 非法。")  # 摘要必须是 64 位十六进制字符串。
    current_stat = path.stat()  # 读取当前字节数与纳秒修改时间供身份对象和大小门禁使用。
    require(current_stat.st_size == expected_size, f"{evidence_role} 当前字节数与 POSTONLY 记录不一致。")  # 内容重算前先拒绝明显截断或替换。
    current_sha256 = sha256_file(path)  # 对当前大文件流式重算完整 SHA-256，绝不打开写句柄。
    after_stat = path.stat()  # 在摘要读取后再次取得元数据以排除哈希期间并发写入。
    require((current_stat.st_size, current_stat.st_mtime_ns) == (after_stat.st_size, after_stat.st_mtime_ns), f"{evidence_role} 在当前哈希期间发生变化。")  # 大文件读取窗口内大小或纳秒修改时间漂移即拒绝。
    require(current_sha256 == normalized_expected_sha256, f"{evidence_role} 当前 SHA-256 与 POSTONLY 记录不一致。")  # 当前字节内容必须与后处理前后共同摘要一致。
    return {"role": evidence_role, "path": path.relative_to(RUN_DIR).as_posix(), "length_bytes": current_stat.st_size, "last_write_time_ns": current_stat.st_mtime_ns, "sha256": current_sha256, "matches_postonly_record": True}  # 返回可直接写入统一 QA 的当前源身份。


def validate_clean_postonly_out_err(directory: Path, out_name: str, err_name: str) -> dict[str, Any]:  # 输入正式 POSTONLY 目录及安全文件名，并返回 OUT/ERR 零警告零错误证据。
    """直接读取正式 OUT/ERR，要求 0 warning、0 error、NOSAVE 正常退出和 80 字节版本 ERR。"""  # 函数说明避免统一 QA 仅转述子 QA 声明。
    require(Path(out_name).name == out_name and Path(err_name).name == err_name, "POSTONLY OUT/ERR 名称不得包含路径段。")  # 禁止调用方借文件名越出正式目录。
    out_path = directory / out_name  # 将已验证 OUT 文件名绑定到正式 POSTONLY 目录。
    err_path = directory / err_name  # 将已验证 ERR 文件名绑定到正式 POSTONLY 目录。
    out_text = read_mixed_text(out_path)  # 读取正式 OUT 供标题标记、退出摘要和 NOSAVE 门禁。
    err_text = read_mixed_text(err_path)  # 读取正式 ERR 供独立警告与错误标题门禁。
    out_warning_markers = len(re.findall(r"(?m)^\s*\*\*\* WARNING \*\*\*", out_text))  # 统计 OUT 的实际 MAPDL warning 标题行。
    out_error_markers = len(re.findall(r"(?m)^\s*\*\*\* ERROR \*\*\*", out_text))  # 统计 OUT 的实际 MAPDL error 标题行。
    summary_warnings = [int(value) for value in re.findall(r"NUMBER OF WARNING MESSAGES ENCOUNTERED=\s*(\d+)", out_text)]  # 读取正式会话退出摘要的 warning 数。
    summary_errors = [int(value) for value in re.findall(r"NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*(\d+)", out_text)]  # 读取正式会话退出摘要的 error 数。
    err_warning_markers = len(re.findall(r"(?m)^\s*\*\*\* WARNING \*\*\*", err_text))  # 统计 ERR 的 warning 标题行以防 OUT 与 ERR 口径分叉。
    err_error_markers = len(re.findall(r"(?m)^\s*\*\*\* ERROR \*\*\*", err_text))  # 统计 ERR 的 error 标题行以防 OUT 与 ERR 口径分叉。
    require(out_warning_markers == 0 and out_error_markers == 0 and summary_warnings == [0] and summary_errors == [0], f"POSTONLY OUT 不是零警告零错误：{out_path}")  # OUT 标题与退出摘要必须同时为零。
    require(err_warning_markers == 0 and err_error_markers == 0 and err_path.stat().st_size == EXPECTED_CLEAN_ERR_BYTES, f"POSTONLY ERR 不是干净的 {EXPECTED_CLEAN_ERR_BYTES} 字节版本标识：{err_path}")  # ERR 必须无标题且大小命中冻结值。
    require("EXIT MAPDL WITHOUT SAVING DATABASE" in out_text, f"POSTONLY OUT 未确认 NOSAVE 退出：{out_path}")  # 后处理不得保存或覆盖任何源数据库。
    return {"out_path": out_path.relative_to(RUN_DIR).as_posix(), "out_length_bytes": out_path.stat().st_size, "out_sha256": sha256_file(out_path), "out_warning_count": 0, "out_error_count": 0, "err_path": err_path.relative_to(RUN_DIR).as_posix(), "err_length_bytes": err_path.stat().st_size, "err_sha256": sha256_file(err_path), "err_warning_count": 0, "err_error_count": 0, "exit_without_saving_confirmed": True}  # 返回带路径、大小、摘要和零计数的直接证据。


def apdl_commands(text: str) -> list[str]:  # 输入 APDL 全文并返回去注释、去空白且大写的可执行命令序列。
    """仅忽略整行中文注释与行尾感叹号注释，保留命令字段和逗号结构。"""  # 函数说明固定解析边界用于控制流门禁。
    commands: list[str] = []  # 初始化保持源顺序的命令列表。
    for raw_line in text.splitlines():  # 逐行扫描 APDL 源文本。
        stripped = raw_line.strip()  # 移除不影响语义的行首尾空白。
        if not stripped or stripped.startswith("!"):  # 空行和整行注释不属于可执行命令。
            continue  # 跳到下一源行且不登记命令。
        command = stripped.split("!", 1)[0].strip().upper()  # 移除允许的行尾注释并统一大小写。
        if command:  # 仅保留移除注释后仍非空的命令。
            commands.append(command)  # 按源顺序登记当前可执行命令。
    return commands  # 返回供 STABILIZE、MODOPT 和输出控制门禁使用的命令序列。


def validate_prepare_roots() -> dict[str, Any]:  # 无输入并返回 prepare 原件字节、对象和摘要。
    """只允许从唯一 prepare 状态执行一次；任何已有最终输出或 lineage 原件均拒绝重复封板。"""  # 函数说明给出一次性事务前提。
    require(RUN_DIR.is_dir(), f"A10 run 不存在：{RUN_DIR}")  # 固定 run 必须已存在。
    require(SOLVER_DIR.is_dir() and QA_DIR.is_dir() and LINEAGE_DIR.is_dir() and ORCHESTRATOR_DIR.is_dir(), "A10 run 结构不完整。")  # 四个既有目录必须齐全。
    status_bytes = STATUS_PATH.read_bytes()  # 保存根状态原始字节供 lineage 原样归档和失败回滚。
    manifest_bytes = MANIFEST_PATH.read_bytes()  # 保存根 manifest 原始字节供 lineage 原样归档和失败回滚。
    status = read_json(STATUS_PATH)  # 解析 prepare 根状态供身份和布尔事实门禁。
    manifest = read_json(MANIFEST_PATH)  # 解析 prepare manifest 供完整历史字段继承。
    require(status.get("run_dir_name") == RUN_NAME and manifest.get("run_dir_name") == RUN_NAME, "prepare 根文件的 run 身份不匹配。")  # 两份根对象必须指向固定 run。
    require(status.get("status") == EXPECTED_PREPARE_STATUS and manifest.get("status") == EXPECTED_PREPARE_STATUS, "根状态不是允许的一次性 prepare 起点。")  # 防止重复执行或错误起点。
    require(status.get("execution_attempted") is False and status.get("mapdl_started") is False, "prepare 状态已声称执行，拒绝覆盖历史。")  # prepare 原件必须明确未执行。
    require(manifest.get("prepare_only") is True and manifest.get("mapdl_execution_attempted") is False, "prepare manifest 的未执行事实不成立。")  # manifest 必须仍是准备期原件。
    for new_path in (PREPARE_STATUS_ARCHIVE, PREPARE_MANIFEST_ARCHIVE, POSTRUN_GATE_PATH, EXTERNAL_COMPLETION_QA_PATH, WARNING_DISPOSITION_PATH, EXECUTION_FIELDS_PATH, FINALIZER_SNAPSHOT_PATH):  # 枚举首次最终化才允许创建的固定目标，包括统一外部完成 QA 入口。
        require(not new_path.exists(), f"最终化新目标已存在，拒绝重复或覆盖：{new_path}")  # 任一既有新目标均意味着状态不确定。
    return {"status_bytes": status_bytes, "manifest_bytes": manifest_bytes, "status": status, "manifest": manifest, "status_sha256": sha256_bytes(status_bytes), "manifest_sha256": sha256_bytes(manifest_bytes)}  # 返回事务所需全部 prepare 证据。


def resolve_latest_qa(prefix: str, explicit_path: Path | None) -> Path:  # 输入目录前缀和可选显式 QA 路径并返回 run 内唯一授权路径。
    """默认选择字典序最新目录；显式路径仅用于缺失依赖测试或固定正式 QA，且不得越出 run。"""  # 函数说明给出选择和路径安全规则。
    if explicit_path is None:  # 未指定路径时采用最新正式目录的固定 qa_summary.json。
        candidates = sorted(path for path in RUN_DIR.glob(f"{prefix}*") if path.is_dir())  # 只枚举 run 根下匹配前缀的普通目录。
        require(bool(candidates), f"未发现 {prefix} 正式目录。")  # 缺目录即拒绝，不回退到其他 run。
        qa_path = candidates[-1] / "qa_summary.json"  # 字典序最新目录必须自身给出完成 QA。
    else:  # 显式路径分支用于测试或严格绑定指定正式 QA。
        qa_path = explicit_path if explicit_path.is_absolute() else RUN_DIR / explicit_path  # 相对路径仅相对固定 run 解析。
        qa_path = qa_path.resolve(strict=False)  # 规范化点段和符号链接文本以实施越界门禁。
        try:  # 尝试把规范路径表示为 run 内相对路径。
            qa_path.relative_to(RUN_DIR.resolve())  # 只有 run 子路径才允许继续。
        except ValueError as exc:  # 越界路径进入明确拒绝分支。
            raise RuntimeError(f"显式 QA 路径越出 A10 run：{qa_path}") from exc  # 保留底层异常链并阻止任意文件读取。
        require(qa_path.parent.name.startswith(prefix), f"显式 QA 父目录前缀不匹配：{qa_path}")  # 防止误把其他 QA 冒充目标类型。
    return qa_path  # 返回尚待存在性和字段门禁验证的规范 QA 路径。


def validate_link180_qa(explicit_path: Path | None) -> dict[str, Any]:  # 输入可选 LINK180 QA 路径并返回正式通过摘要。
    """必须命中 status=PASSED、73692 项、nonpositive=0 和源完整性通过；缺失时零写入拒绝。"""  # 函数说明给出父任务要求的四个硬字段。
    qa_path = resolve_latest_qa("A10_LINK180_POSTONLY_", explicit_path)  # 解析最新或显式指定的 run 内正式 QA。
    qa = read_json(qa_path)  # 缺失或半写 JSON 在任何重文件读取与最终写入前立即失败。
    require(qa.get("status") == "PASSED", "LINK180 正式 QA 尚未 PASSED。")  # 完成状态必须精确匹配。
    force = qa.get("link180_axial_force")  # 提取正式 SMISC,1 统计对象。
    source = qa.get("source_integrity")  # 提取源 DB/RST 运行前后完整性对象。
    execution = qa.get("execution")  # 提取只读 SMP1 执行、warning 与 error 对象。
    require(isinstance(force, dict) and isinstance(source, dict) and isinstance(execution, dict), "LINK180 QA 缺少轴力、源完整性或执行对象。")  # 三个正式对象必须齐全。
    require(qa.get("gate_passed") is True, "LINK180 正式 gate_passed 不是 true。")  # 机器门禁必须与 PASSED 状态一致。
    require(force.get("actual_count") == EXPECTED_LINK180_COUNT and force.get("written_count") == EXPECTED_LINK180_COUNT and force.get("csv_row_count") == EXPECTED_LINK180_COUNT and force.get("unique_element_count") == EXPECTED_LINK180_COUNT, f"LINK180 覆盖数量不是四项 {EXPECTED_LINK180_COUNT}。")  # TYPE4 实际、写出、CSV 与唯一计数必须全部闭合。
    require(force.get("duplicate_element_count") == 0 and force.get("invalid_numeric_line_count") == 0, "LINK180 CSV 存在重复元素或非法数值行。")  # 原始表身份和数值必须有效。
    require(force.get("nonpositive_count") == 0 and float(force.get("minimum_force_n", 0.0)) > 0.0, "LINK180 存在非正轴力元素。")  # 所有 LINK180 必须保持正拉力且最小值严格为正。
    require(source.get("source_integrity_passed") is True, "LINK180 QA 未证明源 DB/RST 完整性。")  # 只读源哈希必须前后不变。
    require(execution.get("input_forbidden_command_count") == 0 and execution.get("uncommented_executable_line_count") == 0, "LINK180 输入含禁止命令或未注释执行行。")  # 正式 APDL 必须只读且逐行注释。
    require(execution.get("mapdl_warning_count") == 0 and execution.get("mapdl_error_count") == 0 and execution.get("exit_without_saving_confirmed") is True, "LINK180 MAPDL 执行不是零警告零错误或未确认 NOSAVE。")  # 后处理会话必须干净退出。
    postflight_name = str(source.get("postflight_path", ""))  # 读取 QA 指向的运行前后源身份明细文件名。
    require(Path(postflight_name).name == postflight_name and postflight_name.endswith(".json"), "LINK180 postflight 路径不是同目录安全 JSON 文件名。")  # 禁止路径逃逸或非 JSON 冒充。
    postflight_path = qa_path.parent / postflight_name  # 将安全文件名绑定到 LINK180 正式目录。
    postflight = read_json(postflight_path)  # 读取含 DB/RST before/after 大小、时间和摘要的机器明细。
    require(postflight.get("source_integrity_passed") is True and postflight.get("exit_without_saving_confirmed") is True, "LINK180 postflight 未同时证明源完整性和 NOSAVE。")  # 明细结论必须与摘要一致。
    source_records = postflight.get("files")  # 提取两个源文件的 before/after 记录列表。
    require(isinstance(source_records, list) and len(source_records) == 2, "LINK180 postflight 源记录数不是 2。")  # 静力后处理必须恰好绑定平衡 DB 与静力 RST。
    records_by_role = {str(record.get("role")): record for record in source_records if isinstance(record, dict)}  # 按固定证据角色建立记录映射并忽略非法非对象项。
    require(set(records_by_role) == {"equilibrium_database", "static_result"}, "LINK180 postflight 源角色不完整。")  # 两个角色必须无缺失、无额外项。
    expected_link_paths = {"equilibrium_database": EQUILIBRIUM_DB_PATH, "static_result": STATIC_RST_PATH}  # 绑定角色到固定 solver 权威文件，禁止通配择优。
    expected_link_summary_hashes = {"equilibrium_database": str(source.get("equilibrium_database_sha256_before_after", "")), "static_result": str(source.get("static_result_sha256_before_after", ""))}  # 绑定摘要层声明的两个 before/after SHA-256。
    current_link_sources: dict[str, dict[str, Any]] = {}  # 初始化两个当前时点源身份对象。
    for role, expected_path in expected_link_paths.items():  # 逐一复核平衡 DB 与静力 RST 的三层证据。
        record = records_by_role[role]  # 取得当前角色的 postflight 明细对象。
        before = record.get("before")  # 提取后处理运行前文件身份。
        after = record.get("after")  # 提取后处理运行后文件身份。
        require(isinstance(before, dict) and isinstance(after, dict) and before == after, f"LINK180 {role} 的 before/after 身份不一致。")  # 大小、创建时间、修改时间和摘要必须逐字段相同。
        require(record.get("path") == f"../solver/{expected_path.name}", f"LINK180 {role} 未绑定固定 solver 文件。")  # 防止 QA 指向同名外部副本。
        require(record.get("length_unchanged") is True and record.get("creation_time_unchanged") is True and record.get("last_write_time_unchanged") is True and record.get("sha256_unchanged") is True, f"LINK180 {role} 的四项不变标志未全通过。")  # postflight 的全部源不变布尔必须为真。
        require(str(before.get("sha256", "")).lower() == expected_link_summary_hashes[role].lower(), f"LINK180 {role} 摘要与 postflight 哈希不一致。")  # QA 摘要层和明细层必须闭合。
        current_link_sources[role] = validate_current_source_file(expected_path, int(before.get("length_bytes", 0)), str(before.get("sha256", "")), role)  # 重算当前文件摘要以排除后处理完成后的漂移。
    postonly_execution = validate_clean_postonly_out_err(qa_path.parent, "a10_link180_post.out", "a10_link180_post.err")  # 直接复核正式 LINK180 OUT/ERR 为零警告零错误并 NOSAVE。
    csv_name = str(force.get("csv_path", ""))  # 读取 QA 声明的纯数值轴力 CSV 文件名。
    require(Path(csv_name).name == csv_name and csv_name.endswith(".csv"), "LINK180 CSV 路径不是同目录安全文件名。")  # 禁止路径逃逸和非 CSV 冒充。
    csv_path = qa_path.parent / csv_name  # 将安全文件名绑定到正式 QA 同目录。
    csv_rows = parse_numeric_csv(csv_path, 2)  # 直接读取元素号和轴力两列纯数值表。
    require(len(csv_rows) == EXPECTED_LINK180_COUNT, "LINK180 原始 CSV 行数不是 73692。")  # 直接行数必须与 QA 声明一致。
    element_ids = [int(row[0]) for row in csv_rows]  # 提取整数元素号供唯一性复核。
    require(all(row[0].is_integer() for row in csv_rows) and len(set(element_ids)) == EXPECTED_LINK180_COUNT, "LINK180 原始 CSV 元素号非整数或不唯一。")  # 73692 个元素身份必须唯一。
    forces = [row[1] for row in csv_rows]  # 提取 N 单位轴力列供正值和极值复核。
    require(all(value > 0.0 for value in forces), "LINK180 原始 CSV 含非正轴力。")  # 原始数据必须逐行严格正值。
    require(min(forces) == float(force["minimum_force_n"]) and max(forces) == float(force["maximum_force_n"]), "LINK180 原始 CSV 极值与 QA 摘要不一致。")  # QA 极值必须由原始表直接复现。
    return {"qa_path": qa_path, "qa_relative": qa_path.relative_to(RUN_DIR).as_posix(), "qa_sha256": sha256_file(qa_path), "qa": qa, "actual_count": int(force["actual_count"]), "nonpositive_count": int(force["nonpositive_count"]), "minimum_force_n": float(force["minimum_force_n"]), "maximum_force_n": float(force["maximum_force_n"]), "source_integrity_passed": bool(source["source_integrity_passed"]), "current_source_files": current_link_sources, "postflight_relative": postflight_path.relative_to(RUN_DIR).as_posix(), "postflight_sha256": sha256_file(postflight_path), "postonly_execution": postonly_execution, "csv_relative": csv_path.relative_to(RUN_DIR).as_posix(), "csv_sha256": sha256_file(csv_path)}  # 返回轴力、当前源哈希、OUT/ERR、postflight 与原始 CSV 的统一证据。


def validate_sene6_qa() -> dict[str, Any]:  # 无输入并返回最新六组件正式 QA 与直接 CSV 复核摘要。
    """同时读取 qa_summary.json 和三份正式纯数值 CSV，拒绝仅凭声明通过。"""  # 函数说明实现父任务要求的六组件正式 QA 与原始数据双门禁。
    qa_path = resolve_latest_qa("A10_SENE6_POSTONLY_", None)  # 选择最新六组件正式目录的机器摘要。
    qa = read_json(qa_path)  # 读取合法 JSON 对象。
    require(qa.get("status") == "PASSED", "六组件 SENE 正式 QA 不是 PASSED。")  # 状态必须明确通过。
    execution = qa.get("execution")  # 提取正式 MAPDL 版本、资源、警告、错误与成功标记对象。
    safety = qa.get("safety")  # 提取只读安全对象供类型与字段门禁。
    modal_qa = qa.get("modal_qa")  # 提取 80 阶能量对象供行数和数值门禁。
    counts_qa = qa.get("component_counts")  # 提取六组件集合对象供 17679 闭合门禁。
    require(isinstance(execution, dict) and isinstance(safety, dict) and isinstance(modal_qa, dict) and isinstance(counts_qa, dict), "六组件 QA 缺少结构化执行、安全、模态或计数对象。")  # 四个正式对象必须齐全。
    require(execution.get("warnings") == 0 and execution.get("errors") == 0 and execution.get("success_marker_count") == 1 and execution.get("executed_fail_marker_count") == 0, "六组件 MAPDL 执行不是零警告零错误或成功/失败标记不闭合。")  # 会话摘要和 APDL 标记必须同时通过。
    require(safety.get("solve_command_count") == 0 and safety.get("solution_processor_command_count") == 0, "六组件后处理含求解命令。")  # 后处理必须严格只读。
    require(safety.get("source_db_unchanged") is True and safety.get("source_rstp_unchanged") is True and safety.get("new_db_rst_rstp_file_count") == 0 and safety.get("exit_without_saving") is True and safety.get("uncommented_command_count") == 0, "六组件 QA 未证明源 DB/RSTP 不变、零新结果文件、逐行注释或 NOSAVE。")  # 全部只读安全字段必须闭合。
    require(counts_qa.get("arithmetic_sum") == 17679 and counts_qa.get("set_union") == 17679 and counts_qa.get("type70_total") == 17679 and counts_qa.get("union_intersection_type70") == 17679, "六组件集合未闭合到 17679。")  # 和、并集、类型和交集必须一致。
    require(modal_qa.get("result_set_count") == 80 and modal_qa.get("total_csv_rows") == 80 and modal_qa.get("long_csv_rows") == 480, "六组件 QA 的 80/480 行结构不匹配。")  # 80 阶乘六组件必须闭合。
    require(modal_qa.get("all_totals_finite_and_positive") is True and modal_qa.get("all_component_energies_finite_and_nonnegative") is True and modal_qa.get("all_ratios_finite_and_in_closed_interval_0_1") is True, "六组件 QA 的能量或比例有效性失败。")  # 三类数值门禁均须通过。
    formal_dir = qa_path.parent  # 三份正式 CSV 必须与 qa_summary 位于同一目录。
    count_rows = parse_numeric_csv(formal_dir / "a10_sene6_counts_numeric.csv", 11)  # 直接读取一行十一列集合计数。
    total_rows = parse_numeric_csv(formal_dir / "a10_sene6_mode_totals_numeric.csv", 2)  # 直接读取 80 行总能量。
    long_rows = parse_numeric_csv(formal_dir / "a10_sene6_modal_numeric.csv", 5)  # 直接读取 480 行组件长表。
    require(len(count_rows) == 1 and [int(value) for value in count_rows[0]] == EXPECTED_COMPONENT_COUNTS, "六组件计数 CSV 不匹配冻结数列。")  # 原始计数必须逐列一致。
    require(len(total_rows) == 80 and [int(row[0]) for row in total_rows] == list(range(1, 81)) and all(row[1] > 0.0 for row in total_rows), "六组件总能量 CSV 不是连续 80 阶正值。")  # 总能量直接门禁。
    require(len(long_rows) == 480 and all(row[3] >= 0.0 and 0.0 <= row[4] <= 1.0 for row in long_rows), "六组件长表能量或比例越界。")  # 长表直接数值门禁。
    for mode in range(1, 81):  # 逐阶核对恰有组件代码 1 至 6。
        codes = sorted(int(row[1]) for row in long_rows if int(row[0]) == mode)  # 提取当前模态的六个组件代码。
        require(codes == [1, 2, 3, 4, 5, 6], f"六组件长表第 {mode} 阶代码不完整。")  # 缺失、重复或错码均拒绝。
    source_records = qa.get("sources")  # 提取模态 DB 与合并 RSTP 的运行前后共同身份记录。
    require(isinstance(source_records, list) and len(source_records) == 2, "六组件 QA 源记录数不是 2。")  # 模态后处理必须恰好绑定两个固定源文件。
    records_by_name = {str(record.get("name")): record for record in source_records if isinstance(record, dict)}  # 按文件名建立两个源记录映射并忽略非法非对象项。
    expected_sene_paths = {MODAL_DB_PATH.name: MODAL_DB_PATH, MODAL_RSTP_PATH.name: MODAL_RSTP_PATH}  # 绑定固定模态 DB 与 RSTP，禁止通配或旧 run 混入。
    require(set(records_by_name) == set(expected_sene_paths), "六组件 QA 的模态 DB/RSTP 名称不完整。")  # 两个文件名必须无缺失、无额外项。
    current_sene_sources: dict[str, dict[str, Any]] = {}  # 初始化两个当前时点模态源身份对象。
    for source_name, expected_path in expected_sene_paths.items():  # 逐一重算当前模态 DB 与 RSTP 的完整摘要。
        record = records_by_name[source_name]  # 取得当前固定文件的历史身份记录。
        current_sene_sources[source_name] = validate_current_source_file(expected_path, int(record.get("bytes", 0)), str(record.get("sha256_before_and_after", "")), source_name)  # 当前大文件必须继续匹配 POSTONLY 前后共同身份。
    postonly_execution = validate_clean_postonly_out_err(formal_dir, "a10_sene6_post.out", "a10_sene6_post_final.err")  # 直接复核正式六组件 OUT/ERR 为零警告零错误并 NOSAVE。
    energy_scope = {"taskbook_target_mode_count": TASKBOOK_TARGET_MODES, "raw_solver_mode_count": EXPECTED_MODES, "component_count": 6, "raw_energy_row_count": len(long_rows), "all_raw_modes_preserved": True, "hard_order_target_pairing_claimed": False, "coverage_status": "ALL_80_RAW_MODES_AVAILABLE_FOR_DOWNSTREAM_PHYSICAL_TARGET_MAPPING"}  # 说明 80×6 原始输出覆盖后续 14 目标物理模态映射所需数据，但不违反任务书的禁止硬配规则。
    return {"qa_path": qa_path, "qa_relative": qa_path.relative_to(RUN_DIR).as_posix(), "qa_sha256": sha256_file(qa_path), "directory_relative": formal_dir.relative_to(RUN_DIR).as_posix(), "total_csv_path": (formal_dir / "a10_sene6_mode_totals_numeric.csv").relative_to(RUN_DIR).as_posix(), "total_csv_sha256": sha256_file(formal_dir / "a10_sene6_mode_totals_numeric.csv"), "long_csv_path": (formal_dir / "a10_sene6_modal_numeric.csv").relative_to(RUN_DIR).as_posix(), "long_csv_sha256": sha256_file(formal_dir / "a10_sene6_modal_numeric.csv"), "count_csv_path": (formal_dir / "a10_sene6_counts_numeric.csv").relative_to(RUN_DIR).as_posix(), "count_csv_sha256": sha256_file(formal_dir / "a10_sene6_counts_numeric.csv"), "total_min": min(row[1] for row in total_rows), "total_max": max(row[1] for row in total_rows), "ratio_min": min(row[4] for row in long_rows), "ratio_max": max(row[4] for row in long_rows), "energy_scope": energy_scope, "current_source_files": current_sene_sources, "postonly_execution": postonly_execution}  # 返回正式引用、三份原始能量摘要、目标映射口径、当前源哈希、OUT/ERR 和数值范围。


def parse_static_table() -> dict[str, float]:  # 无输入并返回通过门禁的静力键值对象。
    """核对 LS1/LS2、端点 SENE/STEN、质量、支承和重力反力闭合；不声称未保存的逐子步 STEN 历史。"""  # 函数说明明确证据能力边界。
    text = read_mixed_text(STATIC_TABLE_PATH)  # 读取六行权威静力表。
    values: dict[str, float] = {}  # 初始化键名到有限浮点值的映射。
    for key, token in re.findall(r"([A-Z][A-Z0-9_]*)=\s*([-+0-9.Ee]+)", text):  # 提取所有 NAME=科学计数法字段。
        value = float(token)  # 将当前字段转换为双精度浮点。
        require(math.isfinite(value), f"静力字段 {key} 非有限。")  # 拒绝 NaN 与无穷。
        values[key] = value  # 保存当前字段的最终唯一值。
    required_keys = {"LS1_CNVG", "LS2_CNVG", "LS2", "TIME2", "SENE1", "STEN1", "RATIO1", "SENE2", "STEN2", "RATIO2", "MASS", "EXPECTED", "ABS_ERROR", "UZ", "RF_EXPECTED", "RF_ACTUAL", "RF_ERROR", "RF_RELATIVE_ERROR"}  # 列出全部静力硬门禁字段。
    require(required_keys <= values.keys(), f"静力表缺少字段：{sorted(required_keys - values.keys())}")  # 任一缺字段即拒绝。
    require(values["LS1_CNVG"] == 1.0 and values["LS2_CNVG"] == 1.0, "LS1 或 LS2 未收敛。")  # 两个载荷步收敛标志必须均为 1。
    require(values["LS2"] == 2.0 and abs(values["TIME2"] - 1.001) <= 1.0e-12, "LS2 结果集或时间不匹配。")  # 保持步必须是载荷步 2、伪时间 1.001。
    require(values["SENE1"] > 0.0 and values["SENE2"] > 0.0, "LS1 或 LS2 总势能非正。")  # 两步端点总能量必须物理有效。
    require(abs(values["RATIO1"]) <= 1.0e-2 and abs(values["RATIO2"]) <= 1.0e-8, "LS1 或 LS2 STEN/SENE 超过封板阈值。")  # 稳定化端点比例必须满足原输入硬门禁。
    require(values["ABS_ERROR"] <= 1.0e-6 and values["UZ"] == 464.0, "总质量或 UZ 支承数不闭合。")  # 质量误差单位 tonne，容差来自 prepare contract。
    require(values["RF_RELATIVE_ERROR"] <= 1.0e-4, "重力反力相对误差超过 1E-4。")  # 实际反力与质量重力必须闭合。
    return values  # 返回已通过全部静力门禁的字段映射。


def validate_vectors(pattern: str, expected_title: str) -> dict[str, Any]:  # 输入文件模式和标题片段并返回 80 份向量摘要。
    """核对文件名连续、文件非空壳、首部类型和尾部极值段；不把文件大小相同误作内容相同。"""  # 函数说明给出轻量结构门禁与限制。
    files = sorted(SOLVER_DIR.glob(pattern), key=lambda path: path.name.lower())  # 按文件名稳定枚举当前向量类型。
    require(len(files) == EXPECTED_VECTOR_FILES, f"向量文件数量不是 {EXPECTED_VECTOR_FILES}：{pattern}")  # 每类必须恰有 80 份。
    mode_pattern = re.compile(r"mode_(\d{2})_(?:all_nodes|rotations)\.txt\Z", re.ASCII)  # 固定两位模态编号与两类允许后缀。
    mode_numbers: list[int] = []  # 保存文件名解析出的模态序号。
    for path in files:  # 逐文件检查结构、大小和边界文本。
        match = mode_pattern.fullmatch(path.name)  # 严格解析完整文件名。
        require(match is not None, f"向量文件名不合约：{path.name}")  # 任一额外命名形式均拒绝。
        mode_numbers.append(int(match.group(1)))  # 登记两位模态号。
        require(path.stat().st_size >= MIN_VECTOR_BYTES, f"向量文件疑似空壳：{path}")  # 全桥 PRNSOL 文本不得小于 1 MB。
        with path.open("rb") as stream:  # 以二进制只读方式抽查首尾，不改变文件指针外状态。
            head = stream.read(65536).decode("ascii", errors="ignore")  # 首 64 KiB 足以覆盖标题和 POST1 列表头。
            stream.seek(max(path.stat().st_size - 8192, 0))  # 定位末尾 8 KiB 以覆盖极值汇总。
            tail = stream.read().decode("ascii", errors="ignore")  # 读取尾部并忽略非 ASCII 注释字节。
        require(expected_title in head and "POST1 NODAL DEGREE OF FREEDOM LISTING" in head, f"向量首部类型不匹配：{path}")  # 标题与列表类型必须正确。
        require("MAXIMUM ABSOLUTE VALUES" in tail, f"向量尾部缺少极值汇总：{path}")  # 完整 PRNSOL 输出必须正常收尾。
    require(mode_numbers == list(range(1, 81)), f"向量模态编号不是 1..80：{pattern}")  # 文件名覆盖必须连续且无重复。
    return {"count": len(files), "minimum_bytes": min(path.stat().st_size for path in files), "maximum_bytes": max(path.stat().st_size for path in files), "first": files[0].name, "last": files[-1].name}  # 返回规模与边界摘要。


def validate_modal(main_out_text: str, main_commands: list[str]) -> dict[str, Any]:  # 输入主 OUT 文本和 APDL 命令序列并返回模态闭合摘要。
    """核对 80 行属性、80 结果集、80+80 向量、无频带上限以及第 59 阶越过 0.35 Hz。"""  # 函数说明覆盖父任务全部模态门禁。
    rows = parse_numeric_csv(MODAL_TABLE_PATH, 15)  # 读取权威十五列属性表。
    require(len(rows) == EXPECTED_MODES, "模态属性表不是 80 行。")  # 行数必须严格等于请求阶数。
    require([int(row[0]) for row in rows] == list(range(1, 81)) and all(row[0].is_integer() for row in rows), "模态属性序号不是连续整数 1..80。")  # 阶次列必须精确连续。
    frequencies = [row[1] for row in rows]  # 提取 Hz 频率列。
    require(all(value > 0.0 for value in frequencies), "模态频率含非正值。")  # 预应力模态频率必须全部为正。
    require(all(frequencies[index] > frequencies[index - 1] for index in range(1, len(frequencies))), "模态频率不是严格递增。")  # LANB 结果必须按升序无重复。
    in_band_count = sum(value <= FREQUENCY_BAND_HZ for value in frequencies)  # 统计 0 至 0.35 Hz 内阶数。
    require(in_band_count == EXPECTED_IN_BAND_MODES and frequencies[58] > FREQUENCY_BAND_HZ and frequencies[-1] > FREQUENCY_BAND_HZ, "80 阶结果未形成对 0-0.35 Hz 的上界越界证明。")  # 第 59 阶和末阶均须越界。
    export_text = read_mixed_text(MODAL_MANIFEST_PATH)  # 读取 requested/available/exported 三字段文本。
    export_match = re.search(r"REQUESTED=\s*80\.,\s*AVAILABLE=\s*80\.,\s*EXPORTED=\s*80\.", export_text)  # 严格查找三个 80 的同一记录。
    require(export_match is not None, "模态导出 manifest 未闭合 80/80/80。")  # 任何缺失或较少阶数均拒绝。
    set_text = read_mixed_text(MODAL_SET_LIST_PATH)  # 读取 RSTP 原生 SET 列表。
    set_numbers = [int(match.group(1)) for match in re.finditer(r"(?m)^\s*(\d+)\s+[-+0-9.Ee]+\s+1\s+\d+\s+\d+\s*$", set_text)]  # 提取载荷步 1 的结果集序号。
    require(set_numbers == list(range(1, 81)), "RSTP SET 列表不是连续 1..80。")  # 原生结果集必须完整覆盖 80 阶。
    require(main_commands.count("MODOPT,LANB,80") == 1 and not any(command.startswith("MODOPT,LANB,80,") for command in main_commands), "MODOPT 未采用无频带上限 LANB 80。")  # 精确三字段命令证明没有 FREQB/FREQE 截断。
    require(main_commands.count("MXPAND,80,,,YES") == 1 and main_commands.count("LUMPM,OFF") == 1, "MXPAND Elcalc 或一致质量控制不匹配。")  # 元素能量与一致质量必须启用。
    require(main_commands.count("OUTRES,NSOL,ALL") == 1 and main_commands.count("OUTRES,VENG,ALL") == 1, "模态 NSOL 或 VENG 输出控制缺失。")  # 向量和 SENE 均须保存全部阶。
    require("80 Eigenvalues Converged" in main_out_text, "主 OUT 缺少 80 个特征值收敛标记。")  # 求解器自身必须确认 80 阶收敛。
    displacement = validate_vectors("mode_*_all_nodes.txt", "PRINT U    NODAL SOLUTION PER NODE")  # 核对 80 份全节点位移向量。
    rotations = validate_vectors("mode_*_rotations.txt", "PRINT ROT  NODAL SOLUTION PER NODE")  # 核对 80 份全节点转角向量。
    gate_status = read_mixed_text(GATE_STATUS_PATH)  # 读取 solver 端导出完成状态。
    require("STATUS=SOLVER_EXPORT_COMPLETED PHASE=EXTERNAL_QA_REQUIRED" in gate_status, "solver gate 状态不是导出完成。")  # 该状态是进入本 external QA 的合法前置。
    return {"property_rows": len(rows), "set_count": len(set_numbers), "frequency_first_hz": frequencies[0], "frequency_last_hz": frequencies[-1], "frequency_in_0_to_0_35_hz_count": in_band_count, "first_frequency_above_0_35_hz": frequencies[in_band_count], "first_mode_above_0_35_hz": in_band_count + 1, "unbounded_lanb_80": True, "not_truncated_at_0_35_hz": True, "displacement_vectors": displacement, "rotation_vectors": rotations}  # 返回模态规模、频带与向量摘要。


def validate_main_out(main_out_text: str) -> dict[str, Any]:  # 输入主 OUT 全文并返回错误、pivot 和五条 warning 处置基础数据。
    """实际 warning 标记必须恰为五条且顺序和文本唯一匹配；任何额外 warning 均视为未处置。"""  # 函数说明实现全部警告逐项处置的硬门禁。
    lines = main_out_text.splitlines()  # 分行以获取一基 OUT 行号和每条 warning 局部块。
    warning_indices = [index for index, line in enumerate(lines) if re.match(r"^\s*\*\*\* WARNING \*\*\*", line)]  # 定位所有实际 warning 标题行。
    require(len(warning_indices) == EXPECTED_WARNINGS, f"主 OUT 实际 warning 数不是 {EXPECTED_WARNINGS}：{len(warning_indices)}")  # 禁止漏处置或新增警告。
    warning_blocks = [re.sub(r"\s+", " ", "\n".join(lines[index:index + 10])).strip().lower() for index in warning_indices]  # 规范化每条标题后十行供片段识别。
    for position, fragment in enumerate(WARNING_FRAGMENTS):  # 按冻结顺序逐条匹配唯一警告片段。
        require(fragment in warning_blocks[position], f"第 {position + 1} 条 warning 文本不匹配：{fragment}")  # 顺序或内容漂移均拒绝。
    error_markers = len(re.findall(r"(?m)^\s*\*\*\* ERROR \*\*\*", main_out_text))  # 统计真实 MAPDL error 标题行而非注释词语。
    negative_pivots = len(re.findall(r"negative\s+pivot", main_out_text, flags=re.IGNORECASE))  # 统计全部 negative pivot 原始短语。
    zero_pivots = len(re.findall(r"zero\s+pivot", main_out_text, flags=re.IGNORECASE))  # 统计全部 zero pivot 原始短语。
    summary_warnings = [int(value) for value in re.findall(r"NUMBER OF WARNING MESSAGES ENCOUNTERED=\s*(\d+)", main_out_text)]  # 读取 MAPDL 会话摘要 warning 数。
    summary_errors = [int(value) for value in re.findall(r"NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*(\d+)", main_out_text)]  # 读取 MAPDL 会话摘要 error 数。
    require(error_markers == 0 and summary_errors == [0], "主 OUT 存在 ERROR 或摘要错误数不为 0。")  # 两类错误证据必须同时为零。
    require(negative_pivots == 0 and zero_pivots == 0, "主 OUT 存在 negative 或 zero pivot。")  # 奇异或负主元短语不得出现。
    require(summary_warnings == [EXPECTED_SUMMARY_WARNINGS], "主 OUT 摘要 warning 数不是 4。")  # 第五条发生于摘要之后，必须保持明确口径。
    require("EXIT MAPDL WITHOUT SAVING DATABASE" in main_out_text, "主 OUT 未以不保存数据库方式退出。")  # 成功会话必须正常结束且不保存 DB。
    require("Number of processes requested           :    4" in main_out_text and "Distributed Memory Parallel" in main_out_text and "MPI Type: INTELMPI" in main_out_text, "主 OUT 的 DMP4/INTELMPI 执行身份不完整。")  # 实际执行资源必须与准备命令一致。
    records: list[dict[str, Any]] = []  # 初始化五条 warning 的机器处置记录。
    dispositions = ["保留为 legacy CERIG 大变形兼容性限制；由 LS1/LS2 收敛、质量反力闭合、LINK180 全正与 80 阶模态结果共同约束。", "保留为刚度尺度病态限制；0 negative/zero pivot、两步收敛和 80 特征值收敛证明本次结果可用。", "LS1 参考弯矩低于内部阈值仅改变收敛参考尺度；该载荷步随后收敛且端点门禁全部通过。", "LS2 参考弯矩低于内部阈值仅改变收敛参考尺度；保持步在一次平衡迭代后收敛。", "退出后 elapsed/CPU 33% 差异属于内存与磁盘性能提示；发生在 0 error 正常退出之后，不改变数值结果。"]  # 按五条冻结顺序定义工程处置。
    limitation_flags = [True, True, False, False, False]  # 前两条构成 PASS_WITH_LEGACY_LIMITATIONS，其余三条已由结果证据处置。
    for index, line_index in enumerate(warning_indices):  # 逐条构造行号、识别片段和处置状态。
        records.append({"warning_id": index + 1, "out_line": line_index + 1, "recognition_fragment": WARNING_FRAGMENTS[index], "disposition": dispositions[index], "status": "DISPOSED", "contributes_legacy_limitation": limitation_flags[index]})  # 保存机器可读警告记录。
    return {"actual_warning_markers": len(warning_indices), "summary_warning_count": summary_warnings[0], "tail_warning_after_summary_count": 1, "error_markers": error_markers, "summary_error_count": summary_errors[0], "negative_pivot_count": negative_pivots, "zero_pivot_count": zero_pivots, "all_warnings_disposed": True, "records": records}  # 返回全部主 OUT 门禁摘要。


def validate_sten_control(main_out_text: str, main_commands: list[str], static_values: dict[str, float]) -> dict[str, Any]:  # 输入 OUT、命令和静力端点值并返回 STEN 控制证据。
    """证明 LS1/LS2 全求解区间均在 KEY=OFF 控制下，并把未保存的逐子步数值列为证据边界。"""  # 函数说明区分控制状态全历程证明与逐子步数值不可恢复。
    stabilize_commands = [command for command in main_commands if command.startswith("STABILIZE,")]  # 提取所有显式稳定化控制命令。
    require(stabilize_commands == ["STABILIZE,OFF", "STABILIZE,OFF"], "主输入不是恰好两次 STABILIZE,OFF。")  # LS1 与 LS2 必须各关闭一次且无其他模式。
    stabilize_indices = [index for index, command in enumerate(main_commands) if command.startswith("STABILIZE,")]  # 记录两次 OFF 在完整命令序列中的位置。
    static_solve_indices = [index for index, command in enumerate(main_commands) if command == "SOLVE"][:2]  # 前两个裸 SOLVE 分别是 LS1 与 LS2；后续裸 SOLVE 属于模态阶段。
    require(len(static_solve_indices) == 2 and stabilize_indices[0] < static_solve_indices[0] < stabilize_indices[1] < static_solve_indices[1], "两次 STABILIZE,OFF 未分别包络 LS1/LS2 求解。")  # 控制命令必须在各自静力 SOLVE 前生效且无交叉。
    out_off_count = len(re.findall(r"NONLINEAR STABILIZATION CONTROL:\s*KEY=OFF", main_out_text, flags=re.IGNORECASE))  # 统计 MAPDL 实际回显的 KEY=OFF 控制块。
    require(out_off_count == 2, f"主 OUT 的 KEY=OFF 控制块不是 2：{out_off_count}")  # 输入声明和引擎回显必须双重闭合。
    require(abs(static_values["STEN1"]) <= 1.0e-20 and abs(static_values["STEN2"]) <= 1.0e-20, "LS1 或 LS2 端点 STEN 未接近数值零。")  # 当前实际端点约 1.36E-25 N·mm。
    return {"input_stabilize_off_count": len(stabilize_commands), "out_key_off_count": out_off_count, "ls1_stabilization_control": "OFF_FOR_FULL_LOAD_STEP", "ls2_stabilization_control": "OFF_FOR_FULL_LOAD_STEP", "taskbook_full_history_peak_gate_status": "PASSED_BY_DISABLED_STABILIZATION_CONTROL", "taskbook_full_history_threshold": 1.0e-2, "ls1_sten_n_mm": static_values["STEN1"], "ls2_sten_n_mm": static_values["STEN2"], "ls1_abs_sten_over_sene": abs(static_values["RATIO1"]), "ls2_abs_sten_over_sene": abs(static_values["RATIO2"]), "full_substep_numeric_history_available": False, "evidence_limitation": "RST 仅保存 LS1/LS2 端点 VENG；逐子步数值不可由 POST1 恢复，但输入顺序与两次求解器 KEY=OFF 回显证明两个静力载荷步全历程均未启用非线性稳定化。"}  # 返回任务书全历程控制门禁、端点数值和逐子步数值能力边界。


def solver_binary_metadata() -> dict[str, tuple[int, int]]:  # 无输入并返回 solver 二进制相对路径到字节数和 mtime_ns 的映射。
    """该快照只读 stat，不打开写句柄；用于证明 finalizer 没有触碰 solver 二进制。"""  # 函数说明给出轻量前后不变门禁。
    result: dict[str, tuple[int, int]] = {}  # 初始化稳定路径到元数据二元组的映射。
    for path in sorted((candidate for candidate in SOLVER_DIR.iterdir() if candidate.is_file() and candidate.suffix.lower() in BINARY_SUFFIXES), key=lambda candidate: candidate.name.lower()):  # 仅枚举冻结二进制后缀。
        stat = path.stat()  # 读取当前文件大小和纳秒修改时间。
        result[path.name] = (stat.st_size, stat.st_mtime_ns)  # 保存不涉及内容修改的元数据身份。
    require(bool(result), "solver 未发现需要保护的二进制文件。")  # 空集合表示路径或后缀契约失效。
    return result  # 返回供提交前后严格相等比较的映射。


def collect_evidence(explicit_link_qa: Path | None) -> dict[str, Any]:  # 输入可选 LINK180 QA 路径并返回全部只读门禁证据。
    """本阶段绝不写文件；LINK180 未 PASS 时在读取大 OUT 和执行任何最终状态变更前拒绝。"""  # 函数说明给出零写入拒绝保证和读取顺序。
    prepare = validate_prepare_roots()  # 首先固定 prepare 原件身份和一次性最终化前提。
    link180 = validate_link180_qa(explicit_link_qa)  # 第二步要求最新 LINK180 正式 QA 已 PASS，否则立即零写入失败。
    lock_files = sorted(path.relative_to(RUN_DIR).as_posix() for path in RUN_DIR.rglob("*.lock") if path.is_file())  # 枚举可能表示仍在运行的 MAPDL 锁文件。
    require(not lock_files, f"A10 run 仍存在锁文件，拒绝最终化：{lock_files}")  # 防止与后处理或求解进程并发封板。
    binary_before = solver_binary_metadata()  # 在任何大文本读取前记录 solver 二进制元数据。
    main_out_text = read_mixed_text(MAIN_OUT_PATH)  # 读取唯一权威主 OUT。
    main_input_text = read_mixed_text(MAIN_INPUT_PATH)  # 读取主输入用于控制状态和无频带上限门禁。
    main_commands = apdl_commands(main_input_text)  # 解析可执行 APDL 命令序列。
    warnings = validate_main_out(main_out_text)  # 核对 5 warning、0 error 和 0 pivot。
    static_values = parse_static_table()  # 核对两步静力、能量、质量与反力。
    sten = validate_sten_control(main_out_text, main_commands, static_values)  # 核对两次 KEY=OFF 与端点 STEN。
    modal = validate_modal(main_out_text, main_commands)  # 核对 80 属性、80+80 向量和频带未截断。
    sene6 = validate_sene6_qa()  # 核对六组件正式 QA 与三份原始纯数值 CSV。
    binary_after_reads = solver_binary_metadata()  # 只读门禁结束后再次读取 solver 二进制元数据。
    require(binary_after_reads == binary_before, "只读证据收集期间 solver 二进制元数据发生变化。")  # 防止外部并发修改。
    return {"prepare": prepare, "link180": link180, "sene6": sene6, "warnings": warnings, "static": static_values, "sten": sten, "modal": modal, "main_out_sha256": sha256_file(MAIN_OUT_PATH), "main_input_sha256": sha256_file(MAIN_INPUT_PATH), "static_table_sha256": sha256_file(STATIC_TABLE_PATH), "modal_table_sha256": sha256_file(MODAL_TABLE_PATH), "binary_metadata": binary_before, "finalizer_sha256": sha256_file(SCRIPT_PATH)}  # 返回完整只读证据汇总。


def legacy_limitations() -> list[dict[str, str]]:  # 无输入并返回固定三项 legacy 或证据边界说明。
    """这些限制不否定已通过数值门禁，但禁止把终态简化为无条件 PASS。"""  # 函数说明给出 FINAL_STATUS 的工程语义。
    return [{"id": "LEGACY_CERIG_LARGE_DEFLECTION", "description": "legacy CERIG 约束在大变形下的适用性 warning 仍存在；本轮未改变 legacy 连接运动学。"}, {"id": "HIGH_COEFFICIENT_RATIO", "description": "静力矩阵系数比超过 1E8，虽无负/零主元且全部收敛，仍保留尺度病态限制。"}, {"id": "STEN_SUBSTEP_NUMERIC_HISTORY_UNAVAILABLE", "description": "输入顺序与两次求解器 KEY=OFF 回显证明 LS1/LS2 全历程未启用稳定化，因而任务书全历程控制门禁通过；但 RST 只保存两个端点 VENG，逐子步 STEN 数值表不可恢复。"}]  # 返回稳定顺序的三项工程或证据边界。


def make_warning_markdown(evidence: dict[str, Any]) -> str:  # 输入全证据并返回五条 warning 的中文处置 Markdown。
    """每条 warning 均给出 OUT 行号、识别文本、处置、证据和是否形成 legacy 限制。"""  # 函数说明覆盖用户要求的逐项处置。
    records = evidence["warnings"]["records"]  # 提取五条已验证机器记录。
    lines = ["# A10 主 OUT 警告逐项处置", "", f"主 OUT 实际出现 {EXPECTED_WARNINGS} 个 `*** WARNING ***` 标记。MAPDL 摘要先记录 {EXPECTED_SUMMARY_WARNINGS} 条，摘要之后又输出 1 条 elapsed/CPU 性能警告，因此两种计数口径并不矛盾。全部五条均已识别并处置；未处置警告数为 0。", ""]  # 构造文档标题与计数口径说明。
    titles = ["legacy 约束方程与大变形", "矩阵系数比超过 1E8", "LS1 参考弯矩阈值", "LS2 参考弯矩阈值", "退出后 elapsed/CPU 性能提示"]  # 定义五条用户可读标题。
    evidence_lines = ["LS1/LS2 均收敛；质量误差小于 1E-6 tonne；反力相对误差小于 1E-4；LINK180 73692 项全部正；80 阶模态完整。", "主 OUT 为 0 ERROR、0 negative pivot、0 zero pivot；两步静力和 80 个特征值均收敛。", "该警告后 LS1 继续迭代并收敛；LS1 SENE 为正，端点 STEN/SENE 远小于 1E-2。", "该警告所在 LS2 在一次平衡迭代后收敛；LS2 时间为 1.001，端点 STEN/SENE 远小于 1E-8。", "警告发生于 `EXIT MAPDL WITHOUT SAVING DATABASE` 和 0 ERROR 摘要之后，仅反映资源与 I/O 效率。"]  # 定义每条处置所依赖的独立证据。
    for index, record in enumerate(records):  # 按 OUT 原顺序写出五个处置小节。
        lines.extend([f"## W{index + 1}：{titles[index]}", "", f"- OUT 行：{record['out_line']}。", f"- 识别片段：`{record['recognition_fragment']}`。", f"- 处置：{record['disposition']}", f"- 支撑证据：{evidence_lines[index]}", f"- 处置状态：`DISPOSED`；形成 legacy 限制：`{str(record['contributes_legacy_limitation']).lower()}`。", ""])  # 写入行号、片段、处置、证据和状态。
    lines.extend(["## 终态口径", "", "五条 warning 均不构成此次数值门禁失败，但 W1 与 W2 仍是工程适用性边界；另有 STEN 仅端点可恢复的证据边界。因此根状态采用 `PASS_WITH_LEGACY_LIMITATIONS`，不得改写为无条件 `PASS`。", ""])  # 解释为何保留限制状态。
    return "\n".join(lines)  # 返回末尾含 LF 的完整 Markdown。


def make_field_dictionary() -> str:  # 无输入并返回最终执行字段字典 Markdown。
    """解释 JSON 不支持注释的字段、单位、布尔含义、状态区别与账本自排除规则。"""  # 函数说明满足相邻 Markdown 注释要求。
    lines = ["# A10 最终执行字段字典", "", "## 状态字段", "", "- `execution_status=EXECUTED`：MAPDL 主作业已经由 prepare 之外的外部命令真实运行完成。", "- `gate_status=PASSED`：本脚本要求的全部 post-run 硬门禁均通过。", "- `status=PASS_WITH_LEGACY_LIMITATIONS`：数值门禁通过，但仍保留 legacy CERIG 大变形、矩阵尺度病态和逐子步 STEN 数值未保存三项边界。", "- `next_action=NONE_FINALIZED`：当前 run 已最终封板，不再等待 launch。", "- `qa/a10_external_completion_qa.json`：供 A30 与后续任务复用的权威入口；与 `qa/postrun_gate.json` 逐字节一致。", "", "## 数值字段", "", "- `static.*_n_mm`：势能或稳定化能，单位 N·mm。", "- `static.mass_*_tonne`：质量与绝对误差，单位 tonne。", "- `static.reaction_*_n`：重力反力，单位 N；`reaction_relative_error` 无量纲。", "- `modal.frequency_*_hz`：频率，单位 Hz；第 59 阶首次超过 0.35 Hz 是频带未截断的直接证据。", "- `modal.displacement_vectors.count` 与 `rotation_vectors.count`：两类 PRNSOL 文件均必须为 80。", "- `sene6`：六组件正式只读 QA；80 行总能量、480 行组件长表、比例闭区间 0–1。", "- `sene6.energy_scope`：任务书有 14 个目标物理模态，但禁止按阶号硬配；A10 保留 80×6 原始能量供后续 MAC/物理描述映射，因此 `hard_order_target_pairing_claimed=false`。", "- `link180.actual_count=73692` 与 `nonpositive_count=0`：LS2 LINK180 TYPE4 全覆盖且全部正拉力。", "", "## 证据与账本", "", "- `source_integrity`：当前时点重新计算平衡 DB、静力 RST、模态 DB 和 RSTP 四个大文件的 SHA-256，并与两个 POSTONLY 的运行前后共同记录逐项比较。", "- `postonly_execution`：直接读取两个正式 OUT/ERR；均须 0 warning、0 error、80 字节版本 ERR 且 `EXIT ... WITHOUT SAVING DATABASE`。", "- `prepare_lineage` 指向 prepare 根状态和 manifest 的原始字节副本；其 SHA-256 与最终化前根文件相同。", "- `artifact_hashes.sha256` 递归覆盖 run 下全部其他普通文件，包括 solver 二进制、正式 QA、lineage 与 rejected 尝试；账本按设计排除自身，避免自引用。", "- `solver_binary_metadata_unchanged=true` 表示 finalizer 写入前后所有受保护 solver 二进制的字节数与纳秒修改时间完全一致；账本另给出其内容 SHA-256。", "- `sten_control.taskbook_full_history_peak_gate_status=PASSED_BY_DISABLED_STABILIZATION_CONTROL`：两次 `STABILIZE,OFF` 在各自静力 `SOLVE` 前生效且 OUT 各回显一次 `KEY=OFF`，故 LS1/LS2 全历程未启用人工稳定化。", "- `sten_control.full_substep_numeric_history_available=false` 是证据能力边界，不是门禁失败；RST 未保存的逐子步数值不得由端点伪造。", ""]  # 构造完整字段、单位、14 目标映射边界、四源完整性和 STEN 控制说明。
    return "\n".join(lines)  # 返回末尾含 LF 的 Markdown 文本。


def build_postrun_gate(evidence: dict[str, Any], generated_utc: str) -> dict[str, Any]:  # 输入全证据和时间并返回机器 postrun gate 对象。
    """对象只在全部门禁已通过后构造，checks 字段均为可复核的真值而非待办项。"""  # 函数说明给出生成时序和语义。
    static = evidence["static"]  # 提取静力字段映射以构造带单位对象。
    checks = {"main_out_zero_errors": True, "main_out_zero_negative_pivots": True, "main_out_zero_zero_pivots": True, "all_five_warnings_disposed": True, "ls1_converged": True, "ls2_converged": True, "mass_closed": True, "reaction_closed": True, "sten_control_proven_at_saved_endpoints": True, "sten_full_history_threshold_proven_by_disabled_control": True, "modal_properties_80": True, "modal_displacement_vectors_80": True, "modal_rotation_vectors_80": True, "frequency_band_0_to_0_35_not_truncated": True, "sene6_80_by_6_passed": True, "taskbook_14_target_energy_basis_preserved_without_hard_order_pairing": True, "link180_all_positive": True, "four_solver_source_hashes_current": True, "both_postonly_out_err_clean": True, "solver_binary_metadata_unchanged": True}  # 汇总主 OUT、静力、全历程 STEN 控制、80×6 能量、14 目标后续映射基础、LINK180 与四源完整性的全部布尔硬门禁。
    result: dict[str, Any] = {}  # 初始化顶层机器对象。
    result["schema_version"] = 1  # 第一版最终执行字段契约。
    result["run_id"] = "A10_H175_AXIS"  # 固定运行标识。
    result["run_dir_name"] = RUN_NAME  # 固定目录身份。
    result["generated_utc"] = generated_utc  # 记录最终化 UTC 时间。
    result["execution_status"] = EXECUTION_STATUS  # 真实执行状态。
    result["gate_status"] = "PASSED"  # 全部硬门禁结果。
    result["final_status"] = FINAL_STATUS  # 带 legacy 限制的工程终态。
    result["checks"] = checks  # 嵌入全部布尔门禁。
    result["main_out"] = {"path": MAIN_OUT_PATH.relative_to(RUN_DIR).as_posix(), "sha256": evidence["main_out_sha256"], "actual_warning_markers": evidence["warnings"]["actual_warning_markers"], "summary_warning_count": evidence["warnings"]["summary_warning_count"], "tail_warning_after_summary_count": evidence["warnings"]["tail_warning_after_summary_count"], "error_count": 0, "negative_pivot_count": 0, "zero_pivot_count": 0, "parallel_mode": "DMP", "processes": 4, "mpi": "INTELMPI"}  # 记录 OUT 身份和执行摘要。
    result["static"] = {"ls1_cnvg": int(static["LS1_CNVG"]), "ls2_cnvg": int(static["LS2_CNVG"]), "ls2_load_step": int(static["LS2"]), "ls2_time": static["TIME2"], "ls1_sene_n_mm": static["SENE1"], "ls1_sten_n_mm": static["STEN1"], "ls1_abs_sten_over_sene": abs(static["RATIO1"]), "ls2_sene_n_mm": static["SENE2"], "ls2_sten_n_mm": static["STEN2"], "ls2_abs_sten_over_sene": abs(static["RATIO2"]), "mass_actual_tonne": static["MASS"], "mass_expected_tonne": static["EXPECTED"], "mass_abs_error_tonne": static["ABS_ERROR"], "uz_support_count": int(static["UZ"]), "reaction_expected_n": static["RF_EXPECTED"], "reaction_actual_n": static["RF_ACTUAL"], "reaction_abs_error_n": static["RF_ERROR"], "reaction_relative_error": static["RF_RELATIVE_ERROR"], "source_path": STATIC_TABLE_PATH.relative_to(RUN_DIR).as_posix(), "source_sha256": evidence["static_table_sha256"]}  # 记录带单位静力结果。
    result["sten_control"] = evidence["sten"]  # 嵌入两次 KEY=OFF、端点值和历史能力边界。
    result["modal"] = evidence["modal"] | {"properties_path": MODAL_TABLE_PATH.relative_to(RUN_DIR).as_posix(), "properties_sha256": evidence["modal_table_sha256"], "main_input_path": MAIN_INPUT_PATH.relative_to(RUN_DIR).as_posix(), "main_input_sha256": evidence["main_input_sha256"]}  # 合并 80 阶、频带和向量摘要。
    result["warnings"] = evidence["warnings"]  # 嵌入五条逐项机器处置记录。
    result["sene6"] = {"qa_path": evidence["sene6"]["qa_relative"], "qa_sha256": evidence["sene6"]["qa_sha256"], "status": "PASSED", "directory": evidence["sene6"]["directory_relative"], "total_csv_path": evidence["sene6"]["total_csv_path"], "total_csv_sha256": evidence["sene6"]["total_csv_sha256"], "long_csv_path": evidence["sene6"]["long_csv_path"], "long_csv_sha256": evidence["sene6"]["long_csv_sha256"], "count_csv_path": evidence["sene6"]["count_csv_path"], "count_csv_sha256": evidence["sene6"]["count_csv_sha256"], "total_sene_min_n_mm": evidence["sene6"]["total_min"], "total_sene_max_n_mm": evidence["sene6"]["total_max"], "ratio_min": evidence["sene6"]["ratio_min"], "ratio_max": evidence["sene6"]["ratio_max"], "energy_scope": evidence["sene6"]["energy_scope"], "postonly_execution": evidence["sene6"]["postonly_execution"]}  # 仅嵌入 JSON 可序列化的六组件路径、摘要、数值范围、80×6 口径与直接 OUT/ERR。
    result["link180"] = {"qa_path": evidence["link180"]["qa_relative"], "qa_sha256": evidence["link180"]["qa_sha256"], "status": evidence["link180"]["qa"]["status"], "actual_count": evidence["link180"]["actual_count"], "nonpositive_count": evidence["link180"]["nonpositive_count"], "minimum_force_n": evidence["link180"]["minimum_force_n"], "maximum_force_n": evidence["link180"]["maximum_force_n"], "source_integrity_passed": evidence["link180"]["source_integrity_passed"], "postonly_execution": evidence["link180"]["postonly_execution"], "csv_path": evidence["link180"]["csv_relative"], "csv_sha256": evidence["link180"]["csv_sha256"]}  # 嵌入 LINK180 正式门禁、极值、直接 OUT/ERR 和原始 CSV 身份。
    result["source_integrity"] = {"status": "PASSED", "all_four_current_hashes_match_postonly_records": True, "link180_static_sources": evidence["link180"]["current_source_files"], "sene6_modal_sources": evidence["sene6"]["current_source_files"], "link180_postflight_path": evidence["link180"]["postflight_relative"], "link180_postflight_sha256": evidence["link180"]["postflight_sha256"]}  # 汇总当前平衡 DB、静力 RST、模态 DB 与 RSTP 四个源文件的直接哈希闭合。
    result["prepare_lineage"] = {"status_archive": PREPARE_STATUS_ARCHIVE.relative_to(RUN_DIR).as_posix(), "status_original_sha256": evidence["prepare"]["status_sha256"], "manifest_archive": PREPARE_MANIFEST_ARCHIVE.relative_to(RUN_DIR).as_posix(), "manifest_original_sha256": evidence["prepare"]["manifest_sha256"]}  # 记录 prepare 原件归档身份。
    result["legacy_limitations"] = legacy_limitations()  # 嵌入三项终态边界。
    result["solver_binary_protection"] = {"write_target_count": 0, "metadata_file_count": len(evidence["binary_metadata"]), "metadata_unchanged_before_commit": True, "content_hashes_in_full_run_ledger": True}  # 说明 solver 永久只读和账本覆盖。
    result["artifact_ledger"] = {"path": LEDGER_PATH.relative_to(RUN_DIR).as_posix(), "coverage": "ALL_REGULAR_FILES_UNDER_RUN_EXCEPT_LEDGER_ITSELF", "self_excluded": True}  # 明确全 run 与自引用规则。
    result["authoritative_alias"] = {"path": EXTERNAL_COMPLETION_QA_PATH.relative_to(RUN_DIR).as_posix(), "byte_identical_to": POSTRUN_GATE_PATH.relative_to(RUN_DIR).as_posix()}  # 声明供 A30 复用的统一文件与本对象主路径逐字节一致。
    return result  # 返回完整机器门禁对象。


def build_status(evidence: dict[str, Any], generated_utc: str) -> dict[str, Any]:  # 输入证据和时间并返回新的根 A10_status 对象。
    """根状态不再携带误导性的未启动终态；prepare 事实通过 lineage 字段保留。"""  # 函数说明区分历史准备状态和当前执行终态。
    return {"run_id": "A10_H175_AXIS", "run_dir_name": RUN_NAME, "jobname": evidence["prepare"]["status"].get("jobname"), "model_line": "LEGACY_A10_H175_AXIS_ONLY", "status": FINAL_STATUS, "execution_status": EXECUTION_STATUS, "prepare_status": EXPECTED_PREPARE_STATUS, "prepare_gate_passed": True, "execution_attempted": True, "process_started": True, "mapdl_started": True, "postrun_gate_passed": True, "main_out_warning_markers": EXPECTED_WARNINGS, "main_out_errors": 0, "negative_pivot_count": 0, "zero_pivot_count": 0, "modes_available": 80, "modes_exported": 80, "displacement_vector_files": 80, "rotation_vector_files": 80, "sene6_status": "PASSED", "link180_status": "PASSED", "source_integrity_status": "PASSED_FOUR_CURRENT_HASHES", "legacy_limitations": legacy_limitations(), "finalized_utc": generated_utc, "next_action": "NONE_FINALIZED", "prepare_lineage": {"status": PREPARE_STATUS_ARCHIVE.relative_to(RUN_DIR).as_posix(), "manifest": PREPARE_MANIFEST_ARCHIVE.relative_to(RUN_DIR).as_posix()}, "postrun_gate": POSTRUN_GATE_PATH.relative_to(RUN_DIR).as_posix(), "external_completion_qa": EXTERNAL_COMPLETION_QA_PATH.relative_to(RUN_DIR).as_posix()}  # 返回结论优先且含四源当前哈希与统一 QA 入口的真实根状态。


def build_manifest(evidence: dict[str, Any], generated_utc: str) -> dict[str, Any]:  # 输入证据和时间并返回保留历史字段的新 manifest。
    """深复制 prepare manifest 后更新顶层执行事实，并把准备时资源快照明确标为历史。"""  # 函数说明防止删除原有依赖与物理差异审计。
    manifest = copy.deepcopy(evidence["prepare"]["manifest"])  # 深复制以免修改只读证据对象。
    manifest["status"] = FINAL_STATUS  # 更新根终态为带 legacy 限制的通过。
    manifest["execution_status"] = EXECUTION_STATUS  # 记录真实执行完成。
    manifest["next_action"] = "NONE_FINALIZED"  # 移除仍需 launch 的误导性下一动作。
    manifest["prepare_only"] = False  # 当前根 manifest 已不再是 prepare-only 终态。
    manifest["mapdl_execution_attempted"] = True  # 真实主作业确已尝试且完成。
    manifest["process_started"] = True  # 外部 MAPDL 进程确已启动。
    manifest["mapdl_started"] = True  # 与根状态保持一致。
    manifest["execution_policy"] = "EXTERNALLY_EXECUTED_AFTER_PREPARE_USER_OVERRIDE"  # 说明执行发生在 prepare 脚本之外。
    manifest["prepare_state_archived"] = {"status_path": PREPARE_STATUS_ARCHIVE.relative_to(RUN_DIR).as_posix(), "status_sha256": evidence["prepare"]["status_sha256"], "manifest_path": PREPARE_MANIFEST_ARCHIVE.relative_to(RUN_DIR).as_posix(), "manifest_sha256": evidence["prepare"]["manifest_sha256"]}  # 记录 prepare 原件位置与摘要。
    manifest["actual_execution"] = {"status": EXECUTION_STATUS, "parallel_mode": "DMP", "processes": 4, "mpi": "INTELMPI", "main_out": MAIN_OUT_PATH.relative_to(RUN_DIR).as_posix(), "main_out_sha256": evidence["main_out_sha256"], "warning_markers": EXPECTED_WARNINGS, "errors": 0, "negative_pivots": 0, "zero_pivots": 0, "finalized_utc": generated_utc}  # 补入实际命令环境和 OUT 结果。
    manifest["postrun_finalization"] = {"gate_status": "PASSED", "final_status": FINAL_STATUS, "postrun_gate": POSTRUN_GATE_PATH.relative_to(RUN_DIR).as_posix(), "external_completion_qa": EXTERNAL_COMPLETION_QA_PATH.relative_to(RUN_DIR).as_posix(), "warning_disposition": WARNING_DISPOSITION_PATH.relative_to(RUN_DIR).as_posix(), "field_dictionary": EXECUTION_FIELDS_PATH.relative_to(RUN_DIR).as_posix(), "sene6_qa": evidence["sene6"]["qa_relative"], "link180_qa": evidence["link180"]["qa_relative"], "four_current_source_hashes_match_postonly_records": True, "modal_properties": 80, "displacement_vectors": 80, "rotation_vectors": 80, "frequency_band_0_to_0_35_not_truncated": True, "taskbook_target_mode_count": TASKBOOK_TARGET_MODES, "raw_component_energy_modes": EXPECTED_MODES, "hard_order_target_pairing_claimed": False, "artifact_ledger": LEDGER_PATH.relative_to(RUN_DIR).as_posix(), "artifact_ledger_self_excluded": True, "finalizer_snapshot": FINALIZER_SNAPSHOT_PATH.relative_to(RUN_DIR).as_posix(), "finalizer_sha256": evidence["finalizer_sha256"]}  # 补入统一 QA、四源当前哈希、80×6 能量与 14 目标后续物理映射边界、正式子 QA 和账本入口。
    manifest["legacy_limitations"] = legacy_limitations()  # 使终态边界在 manifest 顶层直接可见。
    if isinstance(manifest.get("memory_snapshot"), dict):  # prepare 内存快照保留但必须明确历史角色。
        manifest["memory_snapshot"]["snapshot_role"] = "PREPARE_TIME_HISTORICAL_ONLY"  # 不把准备瞬间资源误当执行时资源。
    if isinstance(manifest.get("disk_snapshot"), dict):  # prepare 磁盘快照同样保留历史事实。
        manifest["disk_snapshot"]["snapshot_role"] = "PREPARE_TIME_HISTORICAL_ONLY"  # 明确该字段不代表最终化时磁盘状态。
    if isinstance(manifest.get("future_launch"), dict):  # 原未来命令仍用于谱系，但其状态必须反映已外部执行。
        manifest["future_launch"]["status"] = "EXECUTED_EXTERNALLY_AFTER_PREPARE"  # 更新命令生命周期状态。
        manifest["future_launch"]["execution_attempted"] = True  # 记录命令已实际尝试。
        manifest["future_launch"]["historical_prepare_record"] = True  # 说明 argv 来源仍是准备期文本证据。
    return manifest  # 返回保留全部旧依赖审计的新 manifest。


def make_result_packet(evidence: dict[str, Any], generated_utc: str) -> str:  # 输入证据和时间并返回最终结果包 Markdown。
    """以结论优先方式汇总真实执行、静力、模态、六组件、LINK180、warning 和限制。"""  # 函数说明替换不可读 prepare 文本并提供用户入口。
    static = evidence["static"]  # 提取静力数值供格式化。
    modal = evidence["modal"]  # 提取模态频带与向量摘要。
    lines = ["# A10 H175 局部轴正式执行结果", "", f"- 最终状态：`{FINAL_STATUS}`；执行状态：`{EXECUTION_STATUS}`；最终化时间：`{generated_utc}`。", "- MAPDL：DMP4 / INTELMPI 已真实完成；主 OUT 为 0 ERROR、0 negative pivot、0 zero pivot。", f"- warning：实际 5 条，摘要计 4 条且退出后追加 1 条性能 warning；五条均已在 `qa/warning_disposition.md` 逐项处置。", f"- 静力：LS1/LS2 均收敛；LS2 时间={static['TIME2']:.16g}；质量绝对误差={static['ABS_ERROR']:.16g} tonne；反力相对误差={static['RF_RELATIVE_ERROR']:.16g}。", f"- STEN：两次 `STABILIZE,OFF` 分别在 LS1/LS2 `SOLVE` 前生效且 OUT 各回显一次 KEY=OFF；端点 STEN/SENE 分别为 {abs(static['RATIO1']):.16g} 和 {abs(static['RATIO2']):.16g}，任务书全历程控制门禁通过。", f"- 模态：80 行属性、80 份位移向量、80 份转角向量；频率范围 {modal['frequency_first_hz']:.16g}–{modal['frequency_last_hz']:.16g} Hz；第 {modal['first_mode_above_0_35_hz']} 阶已越过 0.35 Hz。", "- 六组件 SENE：80 行总能量和 480 行组件长表通过；六组件并集与 TYPE70 均为 17679；全部 80 阶原始能量保留，供后续 14 目标模态按物理描述/MAC 映射，不作按阶号硬配。", f"- LINK180：{evidence['link180']['actual_count']} 个 TYPE4 全覆盖，非正轴力数={evidence['link180']['nonpositive_count']}，最小轴力={evidence['link180']['minimum_force_n']:.16g} N。", "- 源完整性：当前时点重新计算平衡 DB、静力 RST、模态 DB 与 RSTP 四个 SHA-256，均与两个 POSTONLY 运行前后共同记录一致；两个正式 OUT/ERR 均为 0 warning、0 error 并 NOSAVE。", "- prepare 原件：根 `A10_status.json` 与 `manifest.json` 的原始字节已归档到 `lineage/`，根文件已更新为真实终态。", "- 全 run 哈希：`artifact_hashes.sha256` 覆盖除自身外全部普通文件，包含 solver 二进制、正式 QA、lineage 与 rejected 尝试。", "", "## 保留边界", "", "1. legacy CERIG 大变形兼容性 warning 仍存在。", "2. 矩阵系数比超过 1E8，虽无负/零主元且结果收敛，仍保留尺度病态限制。", "3. LS1/LS2 全历程稳定化关闭已有控制证据，但 RST 只保存端点 VENG，逐子步 STEN 数值表不可由 POST1 恢复。", "", "权威机器结论见 `qa/a10_external_completion_qa.json`（与 `qa/postrun_gate.json` 逐字节一致）；字段解释见 `qa/execution_field_dictionary.md`。", ""]  # 构造含四源当前哈希、80×6/14 目标口径和 STEN 控制边界的用户入口文档。
    return "\n".join(lines)  # 返回末尾含 LF 的最终结果包。


def atomic_write(path: Path, payload: bytes) -> None:  # 输入授权目标和完整字节，并以同目录临时文件原子替换。
    """写目标不得位于 solver；临时文件 fsync 后 replace，任何异常由事务层回滚。"""  # 函数说明给出路径安全、持久化和异常语义。
    resolved_parent = path.parent.resolve()  # 规范化目标父目录供越界比较。
    require(resolved_parent == RUN_DIR.resolve() or RUN_DIR.resolve() in resolved_parent.parents, f"写目标越出 A10 run：{path}")  # 所有产物必须位于固定 run。
    require(not (resolved_parent == SOLVER_DIR.resolve() or SOLVER_DIR.resolve() in resolved_parent.parents), f"禁止写入 solver：{path}")  # solver 目录永久只读。
    temp_path = path.with_name(f".{path.name}.ultra_a10_finalize_{os.getpid()}.tmp")  # 在同目录生成当前进程唯一临时文件名。
    require(not temp_path.exists(), f"原子写临时文件已存在：{temp_path}")  # 防止覆盖不明残留。
    try:  # 在异常时确保未完成临时文件被清理。
        with temp_path.open("xb") as stream:  # 排他创建临时文件并禁止文本转换。
            stream.write(payload)  # 一次写出调用方已在内存构造的完整字节。
            stream.flush()  # 把 Python 缓冲区刷新到操作系统。
            os.fsync(stream.fileno())  # 请求操作系统把当前文件内容持久化。
        os.replace(temp_path, path)  # 在同一卷上原子替换目标或创建新目标。
    finally:  # 无论成功或失败都检查临时残留。
        if temp_path.exists():  # replace 失败时临时文件仍可能存在。
            temp_path.unlink()  # 仅删除本函数当前 PID 创建且位于授权目录的临时文件。


def build_full_ledger() -> tuple[bytes, int]:  # 无输入并返回全 run 账本字节和条目数。
    """递归哈希除账本自身外全部普通文件，并在每个文件哈希前后核对大小与 mtime_ns 防并发漂移。"""  # 函数说明给出覆盖范围和竞态门禁。
    temp_files = sorted(path for path in RUN_DIR.rglob("*.tmp") if path.is_file())  # 检查是否遗留任何事务临时文件。
    require(not temp_files, f"构建账本前发现临时文件：{temp_files}")  # 临时文件不得进入正式覆盖范围。
    files = sorted((path for path in RUN_DIR.rglob("*") if path.is_file() and path != LEDGER_PATH), key=lambda path: path.relative_to(RUN_DIR).as_posix())  # 按 POSIX 相对路径稳定枚举全部其他普通文件。
    require(bool(files), "A10 run 没有可哈希文件。")  # 空 run 不允许形成正式账本。
    entries: list[str] = []  # 初始化规范 `<hash>  <relative>` 行列表。
    print(f"A10 finalize: 开始哈希 {len(files)} 个文件，账本按设计排除自身。", flush=True)  # 向调用方报告可能耗时的 20 GB 哈希阶段。
    for index, path in enumerate(files, start=1):  # 逐文件流式哈希并实施竞态检查。
        before = path.stat()  # 记录哈希前大小和纳秒修改时间。
        digest = sha256_file(path)  # 计算当前文件完整内容摘要。
        after = path.stat()  # 记录哈希后元数据。
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"哈希期间文件发生变化：{path}")  # 外部并发写入即拒绝。
        entries.append(f"{digest}  {path.relative_to(RUN_DIR).as_posix()}")  # 写入稳定相对路径且不泄露环境前缀。
        if index % 25 == 0 or index == len(files):  # 每 25 个文件或最后一个文件报告进度。
            print(f"A10 finalize: 哈希进度 {index}/{len(files)}。", flush=True)  # 保持长运行可观测且不修改证据。
    return ("\n".join(entries) + "\n").encode("utf-8"), len(entries)  # 返回末尾含 LF 的账本字节和条目数。


def rollback(originals: dict[Path, bytes | None]) -> None:  # 输入目标到原始字节或不存在标志的映射并恢复事务前状态。
    """仅处理本脚本固定授权目标；既有文件原子恢复，新建文件删除，solver 永不涉及。"""  # 函数说明限定回滚作用域。
    for path, original in reversed(list(originals.items())):  # 按提交相反顺序恢复，降低根状态与附件短暂不一致窗口。
        if original is None:  # None 表示事务前目标不存在。
            if path.exists():  # 仅当本事务已创建目标时需要删除。
                path.unlink()  # 删除本事务新建且位于授权非 solver 路径的文件。
        else:  # 既有目标必须恢复原始完整字节。
            atomic_write(path, original)  # 复用原子写确保旧根状态、结果包或账本完整恢复。


def commit_finalization(evidence: dict[str, Any]) -> dict[str, Any]:  # 输入已全部通过的只读证据并执行一次性最终状态事务。
    """先构造全部内存产物，再提交非 solver 目标、核对二进制不变、构建全 run 账本；任一异常整体回滚。"""  # 函数说明给出事务时序和失败语义。
    generated_utc = datetime.now(timezone.utc).isoformat()  # 生成最终化 UTC 时间并供全部输出复用。
    postrun_gate = build_postrun_gate(evidence, generated_utc)  # 构造机器门禁对象。
    status = build_status(evidence, generated_utc)  # 构造真实根状态对象。
    manifest = build_manifest(evidence, generated_utc)  # 构造保留历史字段的新 manifest。
    outputs: dict[Path, bytes] = {}  # 初始化账本之前的固定写目标与完整字节映射。
    outputs[PREPARE_STATUS_ARCHIVE] = evidence["prepare"]["status_bytes"]  # 原样归档 prepare 根状态字节。
    outputs[PREPARE_MANIFEST_ARCHIVE] = evidence["prepare"]["manifest_bytes"]  # 原样归档 prepare manifest 字节。
    outputs[FINALIZER_SNAPSHOT_PATH] = SCRIPT_PATH.read_bytes()  # 原样快照当前 finalizer 源码。
    outputs[WARNING_DISPOSITION_PATH] = make_warning_markdown(evidence).encode("utf-8")  # 写五条警告逐项处置。
    outputs[EXECUTION_FIELDS_PATH] = make_field_dictionary().encode("utf-8")  # 写机器字段与单位说明。
    outputs[POSTRUN_GATE_PATH] = json_bytes(postrun_gate)  # 写机器 postrun gate。
    outputs[EXTERNAL_COMPLETION_QA_PATH] = json_bytes(postrun_gate)  # 以同一内存对象写供 A30 复用的逐字节相同统一外部完成 QA。
    outputs[RESULT_PACKET_PATH] = make_result_packet(evidence, generated_utc).encode("utf-8")  # 更新用户入口结果包。
    outputs[STATUS_PATH] = json_bytes(status)  # 更新真实根状态。
    outputs[MANIFEST_PATH] = json_bytes(manifest)  # 更新真实根 manifest。
    ordered_targets = list(outputs.keys()) + [LEDGER_PATH]  # 固定所有可能变更目标并把账本置于最后。
    originals = {path: path.read_bytes() if path.exists() else None for path in ordered_targets}  # 捕获事务前完整字节供异常回滚。
    try:  # 包裹全部提交、二进制复核和账本阶段。
        for path, payload in outputs.items():  # 按 lineage、快照、QA、结果包、状态、manifest 顺序提交。
            atomic_write(path, payload)  # 单文件原子写入完整内存字节。
            require(path.read_bytes() == payload, f"落盘字节复核失败：{path}")  # 立即从磁盘读回并逐字节验证。
        require(sha256_file(PREPARE_STATUS_ARCHIVE) == evidence["prepare"]["status_sha256"], "prepare 状态归档哈希不闭合。")  # 原件归档必须逐字节一致。
        require(sha256_file(PREPARE_MANIFEST_ARCHIVE) == evidence["prepare"]["manifest_sha256"], "prepare manifest 归档哈希不闭合。")  # manifest 原件归档必须逐字节一致。
        require(sha256_file(FINALIZER_SNAPSHOT_PATH) == evidence["finalizer_sha256"], "finalizer 快照哈希不闭合。")  # 源码快照必须与执行脚本一致。
        require(POSTRUN_GATE_PATH.read_bytes() == EXTERNAL_COMPLETION_QA_PATH.read_bytes(), "统一外部完成 QA 与 postrun gate 未逐字节一致。")  # 两个机器入口必须完全同源且无字段漂移。
        require(solver_binary_metadata() == evidence["binary_metadata"], "最终状态写入后 solver 二进制元数据发生变化。")  # 写目标隔离必须得到前后元数据证明。
        ledger_payload, ledger_entries = build_full_ledger()  # 在全部其他产物稳定后计算全 run 内容摘要。
        atomic_write(LEDGER_PATH, ledger_payload)  # 最后原子替换旧 prepare 账本。
        require(LEDGER_PATH.read_bytes() == ledger_payload, "全 run 哈希账本落盘字节不一致。")  # 账本本身必须逐字节闭合。
        require(len(LEDGER_PATH.read_text(encoding="utf-8").splitlines()) == ledger_entries, "全 run 哈希账本行数不匹配。")  # 行数必须等于被哈希普通文件数。
        require(solver_binary_metadata() == evidence["binary_metadata"], "账本构建后 solver 二进制元数据发生变化。")  # 20 GB 读取期间也不得有外部写入。
    except Exception:  # 任一写入、哈希、竞态或复核异常进入整体回滚。
        rollback(originals)  # 恢复 prepare 根文件、旧结果包和旧账本，并删除本事务新建目标。
        raise  # 保留原始异常供顶层输出具体失败原因。
    return {"status": FINAL_STATUS, "execution_status": EXECUTION_STATUS, "generated_utc": generated_utc, "postrun_gate": str(POSTRUN_GATE_PATH), "external_completion_qa": str(EXTERNAL_COMPLETION_QA_PATH), "artifact_ledger": str(LEDGER_PATH), "artifact_ledger_entries": ledger_entries, "solver_binary_metadata_count": len(evidence["binary_metadata"])}  # 返回最终状态、双机器入口、账本规模和受保护二进制数摘要。


def parse_arguments() -> argparse.Namespace:  # 无输入并返回可选 LINK180 QA 路径参数对象。
    """不存在求解、删除、强制通过或跳过门禁参数；指定缺失路径可用于验证零写入拒绝。"""  # 函数说明固定 CLI 能力边界。
    parser = argparse.ArgumentParser(description="Finalize the fixed A10 run only after every post-run gate passes; never writes solver files.")  # 创建命令行解析器并强调只最终化固定 run。
    parser.add_argument("--link-qa", type=Path, default=None, help="Optional run-internal A10_LINK180_POSTONLY_*/qa_summary.json; default selects the latest directory.")  # 提供测试缺失依赖或显式绑定正式 QA 的唯一参数。
    return parser.parse_args()  # 让 argparse 处理帮助页和非法参数且不写文件。


def main() -> int:  # 无输入并返回零表示最终化成功、二表示 fail-closed 拒绝或事务回滚。
    """先完成全部只读门禁，再提交一次性状态事务；LINK180 未 PASS 时保证 run 零写入。"""  # 函数说明概括最关键的时序保证。
    arguments = parse_arguments()  # 解析唯一可选 LINK180 QA 路径。
    try:  # 捕获全部门禁、竞态、写入和哈希异常。
        evidence = collect_evidence(arguments.link_qa)  # 执行零写入证据阶段，任何失败都不会调用提交函数。
        result = commit_finalization(evidence)  # 仅在所有证据通过后执行事务化最终状态写入。
    except Exception as exc:  # 任一失败进入统一非零退出路径。
        print(f"A10 finalize FAILED: {exc}", flush=True)  # 报告具体拒绝原因且不伪造完成状态。
        return 2  # 非零退出明确表示根状态未成功最终化或已完整回滚。
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)  # 成功时输出与磁盘状态一致的机器摘要。
    return 0  # 零退出表示真实 EXECUTED 与 PASS_WITH_LEGACY_LIMITATIONS 已完整封板。


if __name__ == "__main__":  # 仅直接运行脚本时进入最终化；导入模块不会读取大文件或写状态。
    raise SystemExit(main())  # 把明确退出码交给操作系统和调用编排器。
