"""在静力终态证据闭合后，构造保持原 jobname 的 C10 隔离式 SMP1 模态诊断运行包。"""  # 本模块只准备文件，不启动 MAPDL，也不授予生产用途。

from __future__ import annotations  # 启用延迟类型注解，避免动态证据字典在导入阶段产生兼容性副作用。

import argparse  # 解析唯一必需的静力运行目录参数，并提供标准命令行帮助。
import hashlib  # 以流式 SHA-256 复核静力原件、复制件、模态主控和准备态账本。
import json  # 严格读取三份静力终态 JSON，并输出模态 manifest 与状态文件。
import os  # 使用同卷原子目录替换提交完整运行包，避免半成品被误执行。
import re  # 从既有 C10 主控尾段识别原 jobname、重启动入口和唯一插入锚点。
import shutil  # 复制已封存的重启动文件和证据快照，并清理仅由本脚本创建的失败暂存目录。
import tempfile  # 在 ultra_runs 内创建唯一暂存目录，完成后一次性原子发布。
from datetime import datetime, timezone  # 生成不可复用的 UTC 运行名和统一准备时间。
from pathlib import Path  # 规范化项目、静力 run、solver 与新运行包路径并实施越界门禁。
from typing import Any  # 描述 JSON 动态对象、重启动工件记录和函数返回证据。


SCRIPT_PATH = Path(__file__).resolve()  # 固定当前准备脚本绝对路径，供运行清单记录真实源码身份。
TOOLS_DIR = SCRIPT_PATH.parent  # ultra_tools 是本脚本所在目录，也是项目根目录的直接子目录。
PROJECT_ROOT = TOOLS_DIR.parent  # 项目根目录承载 ultra_runs 与全部既有 C10 运行。
RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # 所有新模态诊断包只能原子发布到冻结的 ultra_runs 目录。
STATIC_FINAL_STATUS_NAME = "C10_static_final_status.json"  # 静力根提交标志必须使用现有 finalizer 的精确文件名。
STATIC_VERIFICATION_NAME = "static_solution_verification.json"  # 静力数值门证据必须位于 qa 下的精确文件名。
STATIC_RAW_MANIFEST_NAME = "static_raw_result_manifest.json"  # 静力原始结果哈希清单必须位于 qa 下的精确文件名。
STATIC_FINAL_LEDGER_NAME = "artifact_hashes.final.sha256"  # 静力 finalizer 发布的最终账本必须再次承诺四项重启动原件摘要。
MODAL_MAIN_NAME = "c10_modal_restart_main.inp"  # 新运行仅执行线性扰动模态和既有 C10 后处理尾段。
MODAL_MANIFEST_NAME = "C10_modal_manifest.json"  # 准备、执行和最终化共享的机器可读身份入口。
MODAL_STATUS_NAME = "C10_modal_status.json"  # 根状态在准备期明确保持非生产且尚未启动。
PREPARE_LEDGER_NAME = "prepare_artifact_hashes.sha256"  # 准备态账本冻结启动前所有普通文件且排除自身。
EXPECTED_STATIC_STATUS = "STATIC_DIAGNOSTIC_COMPLETED_WITH_REVIEWED_WARNINGS"  # 只有现有静力 finalizer 的精确条件性终态可进入模态准备。
EXPECTED_STATIC_VERIFICATION = "STATIC_NUMERIC_GATES_PASSED_WITH_REVIEWED_WARNINGS_DIAGNOSTIC_ONLY"  # 只接受数值门通过但仍属诊断用途的精确 QA 状态。
EXPECTED_RESTART_STATUS = "PRESERVED_AND_HASHED_NOT_YET_RESUME_TESTED"  # 静力端必须明确声明重启动文件已封存哈希但尚未续算验证。
EXPECTED_MODES = 80  # C10 固定从最低频率起提取并展开八十阶，不设置频带上限。
MIN_AVAILABLE_RAM_BYTES = 8 * 1024**3  # 真正执行时可用物理内存硬门为 8 GiB，本准备包不得声明任何例外。
MIN_FREE_DISK_BYTES = 40 * 1024**3  # 真正执行时 solver 卷可用空间硬门为 40 GiB，低于此值禁止启动。
MAX_NORMALIZED_RESIDUAL = 1.0e-6  # 最终化要求每阶 ||Kφ-λMφ|| 的尺度化二范数不超过一百万分之一。
MAX_ORTHOGONALITY_ERROR = 1.0e-6  # 最终化要求质量 Gram 矩阵对角偏差和非对角绝对值均不超过一百万分之一。
RIGID_BODY_FREQUENCY_LIMIT_HZ = 1.0e-6  # 小于等于一微赫兹的提取阶按数值刚体模态处理并拒绝。
MODAL_TAIL_ANCHOR = "! 进入求解处理器并从 LS2 最高收敛帧建立线性扰动。"  # 既有 C10 主控模态尾段的唯一中文起始锚点。
QA_INSERT_ANCHOR = "! 把 RSTP 原生 SET 列表封存为独立证据。"  # 在八十阶计数闭合后、既有 SET LIST 前插入 APDL Math 数值 QA。
OLD_RESTART_COMMAND = "ANTYPE,,RESTART,2,,PERTURB"  # 既有尾段使用最高可用 LS2 子步的旧重启动写法。
NEW_RESTART_COMMAND = "ANTYPE,,RESTART,2,1,PERTURB"  # 新链精确绑定载荷步二、子步一的已封存 `.r002` 状态。
OLD_RESTART_COMMENT = "! 从载荷步 2 的最高可用子步进入线性扰动重启动。"  # 既有尾段与空子步写法对应的旧说明。
NEW_RESTART_COMMENT = "! 从载荷步 2、子步 1 的已封存 .r002 精确进入线性扰动重启动。"  # 新入口必须同步锁死 LS2/SS1 说明。
OLD_PARKEEP_COMMENT = "! 使用当前接触/材料切线并保留参数、位移与约束定义。"  # 既有说明把 PARKEEP 误写成保留 APDL 参数。
NEW_PARKEEP_COMMENT = "! 使用当前切线；PARKEEP 保留位移约束，删除机械/惯性载荷并保留 CP/CE，不解释为保留 APDL 参数。"  # 按线性扰动命令语义更正用途说明。
REQUIRED_NATIVE_BOOLEAN_GATES = (  # 这些原生完成门必须在静力 solution verification 中逐项为真。
    "wrapper_pid_gone",  # 启动包装进程已经退出，排除仍在运行中封板。
    "matching_ansys_job_processes_gone",  # 携带同 jobname 的真实 ANSYS 子进程已经全部退出。
    "run_lock_absent",  # 静力 solver 目录不存在仍被 MAPDL 占用的锁文件。
    "out_and_binary_artifacts_stable",  # 主 OUT 与关键二进制已经通过稳定窗口检查。
    "run_completed_marker",  # 主 OUT 含 MAPDL 原生正常完成标志。
    "normal_nosave_exit_marker",  # 主 OUT 含显式 NOSAVE 正常退出标志。
)  # 完成静力原生完成布尔门清单。
REQUIRED_RESTART_SUFFIXES = (  # 模态准备必须同时复制并闭合四类精确重启动原件。
    ".rdb",  # 多帧重启动数据库保存模型与求解控制状态。
    ".ldhi",  # 载荷历史索引保存可用载荷步和子步定位信息。
    ".r002",  # 载荷步二、子步一对应的多帧重启动状态文件。
    ".rst",  # 静力结果文件保存基态结果并参与线性扰动续算谱系。
)  # 完成四项强制重启动后缀清单。


def require(condition: bool, message: str) -> None:  # condition 是必须成立的硬门，message 是失败时唯一明确原因；函数成功无返回。
    """在任一身份、状态、哈希或控制流门失败时立即拒绝准备。"""  # 函数实现 fail-closed，不尝试猜测或自动修复来源证据。
    if not condition:  # 仅当调用方给出的硬门为假时进入拒绝路径。
        raise RuntimeError(message)  # 抛出带具体门名的异常，阻止创建可执行运行包。


def sha256_file(path: Path) -> str:  # path 必须是可读普通文件，返回其小写六十四位 SHA-256 十六进制摘要。
    """以 8 MiB 分块读取文件，避免对多 GiB RST/RDB 产生整文件内存峰值。"""  # 函数只读目标文件且不改变时间戳或内容。
    digest = hashlib.sha256()  # 初始化标准 SHA-256 累加器用于字节身份闭合。
    with path.open("rb") as stream:  # 以二进制只读方式打开文件，保证摘要不受文本编码或换行转换影响。
        while True:  # 持续读取固定大小分块，直至明确遇到文件末尾。
            block = stream.read(8 * 1024 * 1024)  # 每次读取 8 MiB，在吞吐量与内存占用之间取稳定折中。
            if not block:  # 空字节串表示已经完整读取到文件末尾。
                break  # 结束分块循环并进入最终摘要返回。
            digest.update(block)  # 按原始出现顺序把当前分块纳入摘要状态。
    return digest.hexdigest()  # 返回小写十六进制摘要供 JSON、账本和复制复核共用。


def read_json(path: Path) -> dict[str, Any]:  # path 是 UTF-8 JSON 文件，返回顶层对象字典并拒绝其他顶层类型。
    """严格读取 JSON 对象并保留字段原义，不容忍缺文件或数组顶层。"""  # 函数不对业务字段作默认填充。
    require(path.is_file(), f"缺少必需 JSON：{path}")  # 在解码前关闭文件存在性门。
    payload = json.loads(path.read_text(encoding="utf-8-sig"))  # 接受标准 UTF-8 与可选 BOM，并由解析器拒绝无效 JSON。
    require(isinstance(payload, dict), f"JSON 顶层不是对象：{path}")  # 三份终态证据和 manifest 均必须是键值对象。
    return payload  # 返回已经通过顶层类型门的动态对象。


def write_json(path: Path, payload: dict[str, Any]) -> None:  # path 是新文件目标，payload 是禁止 NaN 的机器对象；成功无返回。
    """以确定性缩进、UTF-8 和末尾 LF 写出机器证据。"""  # 新运行包尚未发布，因此普通独占写入不会覆盖用户既有文件。
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 保留中文、拒绝非有限数并统一末尾换行。
    path.write_text(rendered, encoding="utf-8", newline="\n")  # 使用 UTF-8/LF 写入暂存目录中的唯一目标文件。


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:  # argv 是可选测试参数列表，返回含规范静力运行目录文本的命名空间。
    """只接受显式静力运行目录，避免脚本猜测最新目录并误接失败 run。"""  # 调用方必须主动指明已经最终化的静力 run。
    parser = argparse.ArgumentParser(description="准备 C10 隔离式 SMP1 模态诊断运行包，但不启动求解器。")  # 创建带用途边界的标准参数解析器。
    parser.add_argument("--static-run-dir", required=True, help="已通过现有 C10 静力 finalizer 的运行目录绝对路径。")  # 静力目录是唯一业务输入且不得省略。
    return parser.parse_args(argv)  # 解析未知参数时由 argparse 自动拒绝并返回非零状态。


def ensure_direct_run_child(path: Path) -> Path:  # path 是用户给出的静力目录，返回其规范绝对路径并要求其直属 ultra_runs。
    """阻断符号逃逸、项目外目录和嵌套子目录被当成权威运行。"""  # 本函数只检查路径，不创建或修改目录。
    resolved = path.resolve()  # 消解相对段和可解析的链接，形成后续比较使用的规范路径。
    require(resolved.is_dir(), f"静力运行目录不存在：{resolved}")  # 只有现存目录可作为来源。
    require(resolved.parent == RUNS_ROOT.resolve(), f"静力运行目录不是 ultra_runs 的直属子目录：{resolved}")  # 禁止项目外或嵌套目录进入谱系。
    return resolved  # 返回已经通过范围门的静力运行目录。


def validate_static_source(static_run: Path) -> dict[str, Any]:  # static_run 必须是 ultra_runs 直属目录，返回全部已交叉闭合来源证据。
    """交叉验证根终态、数值 QA、原始清单、manifest 及四项重启动字节身份。"""  # 任一文件或字段不一致即拒绝。
    manifest_path = static_run / "manifest.json"  # 静力准备 manifest 提供冻结 jobname、主输入来源和 MAPDL 二进制身份。
    final_status_path = static_run / STATIC_FINAL_STATUS_NAME  # 根终态是静力 finalizer 最后发布的提交标志。
    verification_path = static_run / "qa" / STATIC_VERIFICATION_NAME  # 完整数值 QA 提供原生完成门和重启动 inventory。
    raw_manifest_path = static_run / "qa" / STATIC_RAW_MANIFEST_NAME  # 原始清单提供实际 path、size 与 SHA-256。
    final_ledger_path = static_run / STATIC_FINAL_LEDGER_NAME  # 最终账本提供独立于 raw manifest 的 run 内相对路径摘要承诺。
    manifest = read_json(manifest_path)  # 读取静力准备身份合同。
    final_status = read_json(final_status_path)  # 读取静力最终提交状态。
    verification = read_json(verification_path)  # 读取静力解验证完整证据。
    raw_manifest = read_json(raw_manifest_path)  # 读取静力原始结果清单。
    run_name = static_run.name  # 目录名是 manifest 与三份静力终态 JSON 必须共同承诺的运行身份。
    require(manifest.get("run_name") == run_name, "静力 manifest.run_name 与目录名不一致")  # 防止复制或改名后的目录借用原状态。
    require(final_status.get("run_name") == run_name, "静力 final status.run_name 与目录名不一致")  # 根提交标志必须绑定同一 run。
    require(verification.get("run_name") == run_name, "静力 verification.run_name 与目录名不一致")  # 数值 QA 必须绑定同一 run。
    require(raw_manifest.get("run_name") == run_name, "静力 raw manifest.run_name 与目录名不一致")  # 原始哈希清单必须绑定同一 run。
    require(final_status.get("status") == EXPECTED_STATIC_STATUS, "静力 final status 不是批准的条件性完成状态")  # 精确阻断 PREPARED、REJECTED 或其他历史状态。
    require(final_status.get("static_numeric_gates") == "PASSED", "静力 final status 未声明数值硬门 PASSED")  # 只有数值门通过才可建立切线模态。
    require(final_status.get("restart_status") == EXPECTED_RESTART_STATUS, "静力 final status 重启动状态不符合冻结合同")  # 根状态必须承诺已封存哈希。
    require(final_status.get("modal_status") == "NOT_RUN", "静力来源已声明运行过模态，拒绝复用含混阶段身份")  # 本链只从尚未模态化的静力 run 出发。
    require(final_status.get("valid_for_production") is False, "静力来源错误地声明 valid_for_production=true")  # 条件性诊断不得在子链中升级用途。
    require(verification.get("status") == EXPECTED_STATIC_VERIFICATION, "静力 solution verification 状态不符合精确合同")  # QA 状态必须与根状态同为诊断用途。
    require(verification.get("full_bridge_modal_status") == "NOT_RUN", "静力 verification 已声明模态运行")  # 防止阶段结果被重复或混合。
    require(verification.get("valid_for_production") is False, "静力 verification 错误地声明生产有效")  # 数值门通过不等于工程生产签认。
    load_path_mode = final_status.get("load_path_mode")  # 读取根终态冻结的初始状态/恒载配对路径身份。
    require(isinstance(load_path_mode, str) and load_path_mode and verification.get("load_path_mode") == load_path_mode and manifest.get("load_path_mode") == load_path_mode, "静力 load_path_mode 在 final status、verification 与 manifest 间不一致")  # 防止把另一种载荷路径结果误接入模态。
    native = verification.get("solver_native_completion")  # 提取 MAPDL 原生完成证据组供逐项核对。
    require(isinstance(native, dict), "静力 verification 缺少 solver_native_completion 对象")  # 原生完成门不得由顶层状态替代。
    for gate_name in REQUIRED_NATIVE_BOOLEAN_GATES:  # 逐项核对包装进程、真实进程、锁、稳定性和页尾标志。
        require(native.get(gate_name) is True, f"静力原生完成门未通过：{gate_name}")  # 任一门缺失或非布尔真均拒绝。
    error_summary = native.get("error_summary")  # 提取所有 MAPDL 页尾错误累计值。
    require(isinstance(error_summary, list) and error_summary and all(isinstance(value, int) and value == 0 for value in error_summary), "静力 MAPDL error_summary 不是非空全零整数列表")  # 每个页尾累计错误数必须精确为零。
    restart_inventory = verification.get("restart_inventory")  # 提取静力 finalizer 发布的重启动路径清单。
    require(isinstance(restart_inventory, dict), "静力 verification 缺少 restart_inventory 对象")  # 重启动路径不能只从目录猜测。
    require(restart_inventory.get("status") == EXPECTED_RESTART_STATUS, "静力 restart_inventory.status 不符合冻结合同")  # inventory 与根状态必须同值。
    jobname = manifest.get("jobname")  # 读取必须跨静力与模态保持不变的 MAPDL 作业名。
    require(isinstance(jobname, str) and jobname.strip() == jobname and jobname, "静力 manifest.jobname 缺失或含首尾空白")  # jobname 必须是可直接用于文件族和 -j 的非空字符串。
    require(re.fullmatch(r"[A-Za-z0-9_]+", jobname) is not None, "静力 manifest.jobname 含 APDL 文件字段不安全字符")  # 仅允许 ASCII 字母、数字和下划线，阻断逗号、空格、路径分隔符及命令注入。
    require(len(jobname) + len(".full") <= 32 and len(jobname) + len(".mode") <= 32, "静力 jobname 与 .full/.mode 后缀组合超过 APDL Math 三十二字符文件字段上限")  # FULL 与 MODE 导入字段均不得超过三十二个字符。
    solver_dir = (static_run / "solver").resolve()  # 规范化静力原始求解目录供范围和文件名检查。
    require(solver_dir.is_dir(), "静力 solver 目录不存在")  # 原始结果必须仍位于冻结 solver 目录。
    raw_files = raw_manifest.get("files")  # 读取原始清单中的逐文件记录数组。
    require(isinstance(raw_files, list) and raw_files, "静力 raw manifest.files 不是非空数组")  # 空清单不能证明任何重启动原件身份。
    require(raw_manifest.get("file_count") == len(raw_files), "静力 raw manifest.file_count 与 files 长度不一致")  # 清单自描述计数必须闭合。
    require(final_ledger_path.is_file() and final_ledger_path.stat().st_size > 0, f"缺少或为空的静力最终账本：{final_ledger_path}")  # 三份 JSON 之外还必须由最终发布账本承诺原始工件。
    final_ledger_records: dict[str, str] = {}  # 初始化静力最终账本相对路径到摘要的唯一映射。
    for line_number, ledger_line in enumerate(final_ledger_path.read_text(encoding="utf-8").splitlines(), start=1):  # 按一基行号解析全部最终账本记录。
        ledger_match = re.fullmatch(r"([0-9a-f]{64})  (.+)", ledger_line)  # 要求小写 SHA-256、两个空格和相对路径。
        require(ledger_match is not None, f"静力最终账本第 {line_number} 行格式无效")  # 任一格式漂移均阻断模态准备。
        ledger_hash, ledger_label = ledger_match.groups()  # 解包当前摘要与 POSIX 相对标签。
        require(ledger_label not in final_ledger_records, f"静力最终账本存在重复标签：{ledger_label}")  # 每个工件只能被唯一承诺。
        ledger_target = (static_run / Path(ledger_label)).resolve()  # 解析账本标签指向的规范绝对路径。
        require(static_run in ledger_target.parents and ledger_target.is_file(), f"静力最终账本目标缺失或逃逸：{ledger_label}")  # 目标必须仍在同一静力 run 内。
        final_ledger_records[ledger_label] = ledger_hash  # 保存记录供四项重启动工件交叉核对。
    records_by_name: dict[str, dict[str, Any]] = {}  # 初始化不区分大小写文件名到唯一记录的映射。
    for record in raw_files:  # 逐项验证 raw manifest 记录结构和路径范围。
        require(isinstance(record, dict), "静力 raw manifest.files 含非对象记录")  # 每项必须含 path/sha256/size_bytes 键值。
        record_path_text = record.get("path")  # 读取 finalizer 冻结的绝对原始路径文本。
        require(isinstance(record_path_text, str) and record_path_text, "静力 raw manifest 记录缺少 path")  # 路径文本不得缺失或为空。
        record_path = Path(record_path_text).resolve()  # 规范化记录路径以阻断相对段或链接逃逸。
        require(record_path.parent == solver_dir, f"静力 raw manifest 工件不在 solver 直属目录：{record_path}")  # 重启动原件不得来自其他 run。
        record_key = record_path.name.lower()  # Windows 文件族按不区分大小写的文件名建立唯一键。
        require(record_key not in records_by_name, f"静力 raw manifest 存在重复文件名记录：{record_path.name}")  # 同名多记录会造成来源歧义。
        records_by_name[record_key] = record  # 保存已经通过结构和范围门的原始记录。
    restart_artifacts: dict[str, dict[str, Any]] = {}  # 初始化四项后缀到已实测闭合工件证据的映射。
    for suffix in REQUIRED_RESTART_SUFFIXES:  # 按 .rdb、.ldhi、.r002、.rst 固定顺序逐项验真。
        expected_name = f"{jobname}{suffix}"  # 保持同 jobname 形成必须存在的精确文件名。
        record = records_by_name.get(expected_name.lower())  # 只从静力 finalizer 的 raw manifest 选择对应记录。
        require(isinstance(record, dict), f"静力 raw manifest 缺少重启动工件：{expected_name}")  # 不允许从目录中未登记文件补位。
        source_path = Path(str(record["path"])).resolve()  # 解析该记录指向的真实原件路径。
        require(source_path.name.lower() == expected_name.lower(), f"静力重启动工件文件名不匹配：{source_path.name}")  # 后缀和 jobname 必须同时精确一致。
        require(source_path.is_file(), f"静力重启动原件不存在：{source_path}")  # 哈希前确认原件仍存在。
        size_bytes = source_path.stat().st_size  # 读取当前真实字节数供非空与清单一致性门使用。
        require(isinstance(record.get("size_bytes"), int) and record["size_bytes"] == size_bytes and size_bytes > 0, f"静力重启动工件大小不闭合或为空：{source_path.name}")  # 零字节 RST/RNNN 不可续算。
        expected_sha256 = record.get("sha256")  # 读取静力 finalizer 冻结的摘要文本。
        require(isinstance(expected_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None, f"静力重启动工件摘要格式无效：{source_path.name}")  # 摘要必须是小写 SHA-256。
        actual_sha256 = sha256_file(source_path)  # 对当前原始字节重新流式计算摘要，防止 finalizer 后漂移。
        require(actual_sha256 == expected_sha256, f"静力重启动工件 SHA-256 漂移：{source_path.name}")  # 任何字节变化均阻断模态准备。
        ledger_label = source_path.relative_to(static_run).as_posix()  # 生成该原件在静力最终账本中的规范 POSIX 标签。
        require(final_ledger_records.get(ledger_label) == actual_sha256, f"静力最终账本未以同摘要承诺重启动工件：{ledger_label}")  # raw manifest、当前字节和最终账本必须三方同值。
        restart_artifacts[suffix] = {"path": source_path, "sha256": actual_sha256, "size_bytes": size_bytes}  # 保存后续复制和 manifest 共用的闭合证据。
    require(Path(str(restart_inventory.get("rdb"))).resolve() == restart_artifacts[".rdb"]["path"], "restart_inventory.rdb 与 raw manifest 不一致")  # RDB 路径必须在两份 QA 中交叉闭合。
    require(Path(str(restart_inventory.get("ldhi"))).resolve() == restart_artifacts[".ldhi"]["path"], "restart_inventory.ldhi 与 raw manifest 不一致")  # LDHI 路径必须在两份 QA 中交叉闭合。
    rnnn_files = restart_inventory.get("rnnn_files")  # 读取 finalizer 枚举的全部多帧状态文件路径。
    require(isinstance(rnnn_files, list) and any(Path(str(path)).resolve() == restart_artifacts[".r002"]["path"] for path in rnnn_files), "restart_inventory.rnnn_files 未包含精确 .r002")  # LS2/子步1入口必须由 inventory 明示。
    source_main_path = (static_run / "input_snapshot" / "c10_mpc_only_main.inp").resolve()  # 使用静力 run 自带的既有 C10 主控审阅快照作为模态尾段来源。
    require(source_main_path.is_file(), f"静力 run 缺少 C10 主控输入快照：{source_main_path}")  # 不从外部最新文件猜测模板。
    source_main_sha256 = sha256_file(source_main_path)  # 复算尾段来源主控完整字节摘要。
    require(source_main_sha256 == manifest.get("parent_main_sha256"), "C10 主控输入快照 SHA-256 与静力 manifest.parent_main_sha256 不一致")  # 确保尾段正是静力 prepare 使用的父主控。
    required_ledger_paths = {  # 冻结进入模态所依赖的静力身份、终态、数值 QA、原始清单和主控快照集合。
        manifest_path: "manifest.json",  # 静力准备合同必须由最终发布账本承诺。
        final_status_path: STATIC_FINAL_STATUS_NAME,  # 根最终状态必须由同一账本承诺。
        verification_path: f"qa/{STATIC_VERIFICATION_NAME}",  # 静力数值验证包必须由同一账本承诺。
        raw_manifest_path: f"qa/{STATIC_RAW_MANIFEST_NAME}",  # 静力原始结果清单必须由同一账本承诺。
        source_main_path: "input_snapshot/c10_mpc_only_main.inp",  # 被复用的 C10 模态尾段来源必须由同一账本承诺。
    }  # 完成五项非重启动来源的最终账本标签映射。
    for required_path, required_label in required_ledger_paths.items():  # 逐项复算并交叉核对静力最终账本中的权威摘要。
        require(required_path.is_file(), f"静力最终发布依赖文件缺失：{required_label}")  # 哈希前确认依赖仍是现存普通文件。
        required_hash = sha256_file(required_path)  # 对当前真实字节计算摘要，避免只信任账本文本。
        require(final_ledger_records.get(required_label) == required_hash, f"静力最终账本未以当前摘要承诺依赖文件：{required_label}")  # 当前字节、规范标签和最终账本必须三方闭合。
    mapdl_executable = Path(str(manifest.get("mapdl_executable"))).resolve()  # 解析静力 run 冻结的 MAPDL 2026 R1 可执行文件路径。
    require(mapdl_executable.is_file(), f"静力 manifest 指定的 MAPDL 可执行文件不存在：{mapdl_executable}")  # 执行脚本只能复用同一二进制。
    mapdl_sha256 = sha256_file(mapdl_executable)  # 复算当前 MAPDL 二进制身份供新 manifest 冻结。
    require(mapdl_sha256 == manifest.get("mapdl_executable_sha256"), "MAPDL 可执行文件 SHA-256 与静力 manifest 不一致")  # 禁止版本或补丁静默漂移。
    return {  # 返回准备阶段所需的全部已闭合来源证据。
        "manifest": manifest,  # 静力准备 manifest 原对象。
        "manifest_path": manifest_path,  # 静力准备 manifest 原件路径供隔离谱系快照复制。
        "final_status_path": final_status_path,  # 根终态原件路径供快照复制。
        "verification_path": verification_path,  # 数值 QA 原件路径供快照复制。
        "raw_manifest_path": raw_manifest_path,  # 原始哈希清单路径供快照复制。
        "final_ledger_path": final_ledger_path,  # 静力最终账本路径供快照复制和谱系摘要记录。
        "jobname": jobname,  # 静力与模态必须保持不变的作业名。
        "load_path_mode": load_path_mode,  # 三份静力身份文件共同冻结的载荷路径模式。
        "restart_artifacts": restart_artifacts,  # 四项已复算闭合的重启动原件。
        "source_main_path": source_main_path,  # 既有 C10 主控尾段来源。
        "source_main_sha256": source_main_sha256,  # 既有 C10 主控完整摘要。
        "mapdl_executable": mapdl_executable,  # 冻结 MAPDL 二进制路径。
        "mapdl_sha256": mapdl_sha256,  # 冻结 MAPDL 二进制摘要。
    }  # 完成来源证据返回对象。


def build_apdl_math_qa_block(jobname: str, newline: str) -> str:  # jobname 是保持不变的 MAPDL 作业名，newline 是来源文件换行风格；返回可插入 APDL 文本。
    """生成质量正交 Gram 矩阵与逐阶尺度化特征残差的官方 APDL Math 复核块。"""  # 该块依据 FULL/MODE/NOD2SOLV 的求解器顺序开展数值验证。
    lines = [  # 每条 APDL 命令均由紧邻中文注释说明用途，裸格式行仅与 *VWRITE 保持语法相邻。
        "! C10_MODAL_NUMERICAL_QA_BEGIN",  # 标记新增数值 QA 块起点供准备和最终化静态审计。
        "! 分配八十项频率数组，供残差中的 λ=(2πf)^2 使用。",  # 说明频率数组长度和后续用途。
        "*DIM,C10_QF,ARRAY,80",  # 创建一维双精度 APDL 数组保存八十阶频率，单位 Hz。
        "! 逐阶读取求解器已提取的官方频率。",  # 说明循环数据来源而非重新求解。
        "*DO,C10QI,1,80,1",  # 以一基阶次从 1 循环到 80，步长为 1。
        "! 读取当前阶 MODE 实体频率，单位 Hz。",  # 说明 *GET 目标和单位。
        "*GET,C10_QF(C10QI),MODE,C10QI,FREQ",  # 把当前官方频率写入同阶数组单元。
        "! 结束八十阶频率读取循环。",  # 说明循环结束语义。
        "*ENDDO",  # 结束固定八十次频率读取循环。
        "! 从当前 job 的 FULL 文件导入约束后的质量矩阵。",  # 说明质量矩阵来源和自由度空间。
        f"*SMAT,C10QM,D,IMPORT,FULL,{jobname}.full,MASS",  # 以双精度稀疏格式导入质量矩阵 M。
        "! 从当前 job 的 FULL 文件导入约束后的切线刚度矩阵。",  # 说明刚度矩阵对应预应力切线状态。
        f"*SMAT,C10QK,D,IMPORT,FULL,{jobname}.full,STIFF",  # 以双精度稀疏格式导入切线刚度矩阵 K。
        "! 从 FULL 文件导入内部自由度到求解器自由度的官方映射。",  # 说明必须采用相同自由度顺序。
        f"*SMAT,C10QMAP,D,IMPORT,FULL,{jobname}.full,NOD2SOLV",  # 导入 NOD2SOLV 映射矩阵。
        "! 从 MODE 文件导入八十列质量归一化特征向量。",  # 说明 MODOPT 默认质量归一化合同。
        f"*DMAT,C10QPHI,D,IMPORT,MODE,{jobname}.mode",  # 导入内部顺序的双精度模态向量矩阵。
        "! 把模态向量转换到 FULL 中 K、M 使用的求解器自由度顺序。",  # 说明乘法目的和排序一致性。
        "*MULT,C10QMAP,,C10QPHI,,C10QSPHI",  # 计算 Φ_s=NOD2SOLV·Φ。
        "! 释放内部顺序模态矩阵，降低后续 APDL Math 内存峰值。",  # 说明释放不影响已生成求解器顺序矩阵。
        "*FREE,C10QPHI",  # 删除不再使用的内部顺序 Φ 对象。
        "! 计算 MΦ，供质量正交 Gram 矩阵使用。",  # 说明第一次数值乘法。
        "*MULT,C10QM,,C10QSPHI,,C10QMPHI",  # 计算八十列 MΦ。
        "! 计算 Φ^T M Φ；质量归一化实模态应得到 80×80 单位矩阵。",  # 说明官方正交判据。
        "*MULT,C10QSPHI,TRANS,C10QMPHI,,C10QGRAM",  # 形成八十阶质量 Gram 矩阵。
        "! 以十六位小数 CSV 导出完整 Gram 矩阵供外部 finalizer 独立重算。",  # 说明输出精度和消费者。
        "*EXPORT,C10QGRAM,CSV,c10_modal_mass_orthogonality.csv,16",  # 写出 80×80 双精度正交矩阵。
        "! 释放完整 MΦ 和 Gram 对象，残差阶段改为逐列计算以控制内存。",  # 说明内存控制策略。
        "*FREE,C10QMPHI",  # 删除八十列 MΦ 临时矩阵。
        "! 释放已经落盘的 80×80 Gram 小矩阵。",  # 说明该对象不再参与残差。
        "*FREE,C10QGRAM",  # 删除 Gram 对象。
        "! 打开逐阶特征方程残差 CSV。",  # 说明输出文件和后续列结构。
        "*CFOPEN,c10_modal_eigen_residuals,csv",  # 创建或覆盖本隔离 run 的残差 CSV。
        "! 逐阶计算 r=Kφ-λMφ 的尺度化二范数。",  # 说明残差定义和循环范围。
        "*DO,C10QI,1,80,1",  # 以一基阶次遍历八十列特征向量。
        "! 链接当前求解器顺序模态列，避免复制完整 Φ。",  # 说明 LINK 视图的内存目的。
        "*VEC,C10QPC,D,LINK,C10QSPHI,C10QI",  # 建立当前 φ_i 的双精度列视图。
        "! 计算当前阶 Kφ。",  # 说明刚度乘积。
        "*MULT,C10QK,,C10QPC,,C10QKP",  # 形成当前阶刚度作用向量。
        "! 计算当前阶 Mφ。",  # 说明质量乘积。
        "*MULT,C10QM,,C10QPC,,C10QMP",  # 形成当前阶质量作用向量。
        "! 复制 Kφ 作为残差向量初值。",  # 说明后续 AXPY 不修改原始 Kφ 范数证据。
        "*VEC,C10QR,D,COPY,C10QKP",  # 创建 r 的初始副本。
        "! 由频率计算圆频率，单位 rad/s。",  # 说明 2πf 转换。
        "C10QOMG=2*ACOS(-1)*C10_QF(C10QI)",  # 使用 APDL 双精度 π 计算 ω。
        "! 由圆频率平方得到广义特征值 λ，单位 s^-2。",  # 说明特征值物理量。
        "C10QLAM=C10QOMG*C10QOMG",  # 计算 λ=ω²。
        "! 对残差副本执行 r=Kφ-λMφ。",  # 说明 AXPY 的两个系数和目标。
        "*AXPY,-C10QLAM,0,C10QMP,1,0,C10QR",  # 以双精度线性组合形成特征方程残差。
        "! 计算残差二范数，不归一化残差向量。",  # 说明输出为绝对残差。
        "*NRM,C10QR,NRM2,C10QRN,NO",  # 取得 ||r||₂。
        "! 计算 Kφ 二范数，作为尺度分母候选。",  # 说明刚度尺度来源。
        "*NRM,C10QKP,NRM2,C10QKN,NO",  # 取得 ||Kφ||₂。
        "! 计算 Mφ 二范数，随后乘以 |λ| 形成质量侧尺度。",  # 说明质量尺度来源。
        "*NRM,C10QMP,NRM2,C10QMN,NO",  # 取得 ||Mφ||₂。
        "! 计算 |λ|·||Mφ||₂。",  # 说明第二个尺度候选。
        "C10QLMN=ABS(C10QLAM)*C10QMN",  # 形成质量侧特征方程量级。
        "! 初始采用 ||Kφ||₂ 作为尺度分母。",  # 说明分母选择起点。
        "C10QDEN=C10QKN",  # 保存当前最大物理尺度。
        "! 若质量侧尺度更大则改用质量侧尺度。",  # 说明条件分支目的。
        "*IF,C10QLMN,GT,C10QDEN,THEN",  # 比较两侧二范数量级。
        "! 更新尺度分母为 |λ|·||Mφ||₂。",  # 说明分支赋值。
        "C10QDEN=C10QLMN",  # 选择更大尺度避免虚假放大相对残差。
        "! 结束尺度最大值分支。",  # 说明条件结束。
        "*ENDIF",  # 结束质量侧尺度比较。
        "! 若两侧尺度均近零则把分母钳制到 1E-30，后续刚体门仍会拒绝零频。",  # 说明极端退化数值保护。
        "*IF,C10QDEN,LT,1.0E-30,THEN",  # 检查分母是否小于安全正数。
        "! 设置仅用于防止除零的最小分母。",  # 说明该值不是验收放宽。
        "C10QDEN=1.0E-30",  # 采用 1E-30 作为双精度尺度保护值。
        "! 结束最小分母保护分支。",  # 说明条件结束。
        "*ENDIF",  # 结束除零保护。
        "! 计算尺度化残差 η=||r||₂/max(||Kφ||₂,|λ|·||Mφ||₂)。",  # 说明最终无量纲指标。
        "C10QREL=C10QRN/C10QDEN",  # 形成 finalizer 使用的每阶尺度化残差。
        "! 写出 mode,f,λ,||r||,||Kφ||,|λ|·||Mφ||,η 七列数值。",  # 说明 CSV 精确列定义。
        "*VWRITE,C10QI,C10_QF(C10QI),C10QLAM,C10QRN,C10QKN,C10QLMN,C10QREL",  # 写出当前阶全部残差证据。
        "(F8.0,6(',',E24.16))",  # 使用整数阶次和六个双精度科学计数列，不得与 *VWRITE 分离。
        "! 释放当前阶残差向量。",  # 说明逐列内存回收。
        "*FREE,C10QR",  # 删除 r_i。
        "! 释放当前阶刚度作用向量。",  # 说明逐列内存回收。
        "*FREE,C10QKP",  # 删除 Kφ_i。
        "! 释放当前阶质量作用向量。",  # 说明逐列内存回收。
        "*FREE,C10QMP",  # 删除 Mφ_i。
        "! 释放当前阶模态列链接。",  # 说明 LINK 视图生命周期结束。
        "*FREE,C10QPC",  # 删除 φ_i 列视图。
        "! 结束当前阶残差计算并进入下一阶。",  # 说明循环结束。
        "*ENDDO",  # 结束固定八十次残差循环。
        "! 正常关闭残差 CSV 并刷新全部八十行。",  # 说明文件关闭语义。
        "*CFCLOS",  # 关闭 *CFOPEN 文件。
        "! 释放求解器顺序模态矩阵。",  # 说明完整 Φ 不再被既有后处理使用。
        "*FREE,C10QSPHI",  # 删除 Φ_s。
        "! 释放切线刚度矩阵。",  # 说明稀疏 K 的生命周期结束。
        "*FREE,C10QK",  # 删除 K。
        "! 释放质量矩阵。",  # 说明稀疏 M 的生命周期结束。
        "*FREE,C10QM",  # 删除 M。
        "! 释放自由度映射矩阵。",  # 说明 NOD2SOLV 的生命周期结束。
        "*FREE,C10QMAP",  # 删除映射对象。
        "! 写出 APDL Math 数值证据已生成的阶段状态，该状态不代表外部 QA 通过。",  # 说明阶段状态用途边界。
        "/OUTPUT,c10_modal_numerical_qa_status,txt",  # 打开独立数值 QA 状态文件。
        "! 固定机器可读状态供 finalizer 检查两个 CSV 均由本次求解生成。",  # 说明状态文本内容。
        "/COM,STATUS=NUMERICAL_QA_ARTIFACTS_GENERATED EXTERNAL_THRESHOLDS_PENDING",  # 声明仅完成证据生成。
        "! 恢复 MAPDL 主输出，继续复用既有 C10 SET LIST 和八十阶导出尾段。",  # 说明输出恢复和控制流延续。
        "/OUTPUT",  # 关闭独立状态输出并恢复主 OUT。
        "! C10_MODAL_NUMERICAL_QA_END",  # 标记新增数值 QA 块终点供静态审计。
    ]  # 完成新增 APDL Math 数值 QA 行列表。
    return newline.join(lines) + newline  # 按来源换行风格拼接，并保留块末尾换行与插入锚点分隔。


def build_modal_main(source_path: Path, jobname: str) -> str:  # source_path 是已验真 C10 主控快照，jobname 是静力原作业名；返回新模态主控全文。
    """精确抽取既有 C10 模态尾段，只固定 LS2/1 重启动、同 jobname 和新增数值 QA。"""  # 不重新生成八十阶属性、向量和能量导出逻辑。
    source_text = source_path.read_text(encoding="utf-8")  # 严格按既有主控 UTF-8 编码读取，拒绝替代字符掩盖锚点漂移。
    newline = "\r\n" if "\r\n" in source_text else "\n"  # 保留来源 CRLF 或 LF 换行风格以便可追溯比较。
    require(source_text.count(MODAL_TAIL_ANCHOR) == 1, "既有 C10 主控模态尾段锚点不是唯一一处")  # 唯一锚点防止截取错误阶段。
    tail = source_text[source_text.index(MODAL_TAIL_ANCHOR) :]  # 从既有线性扰动注释开始复用到原主控正常退出。
    require(tail.count(OLD_RESTART_COMMAND) == 1, "既有 C10 模态尾段旧重启动命令不是唯一一处")  # 只允许受控替换一个入口。
    ordered_tail_commands = [  # 冻结从线性扰动入口到最终模态求解的完整有序命令协议。
        OLD_RESTART_COMMAND,  # 从 LS2 已封存重启动帧进入线性扰动。
        "PERTURB,MODAL,AUTO,CURRENT,PARKEEP",  # 使用当前切线并按 PARKEEP 处理约束与载荷。
        "SOLVE,ELFORM",  # 形成线性扰动单元矩阵。
        "LUMPM,OFF",  # 使用一致质量矩阵。
        "MODOPT,LANB,80",  # 使用 Block Lanczos 提取八十阶。
        "MXPAND,80,,,YES",  # 展开八十阶并计算单元结果。
        "OUTRES,ALL,NONE",  # 先关闭默认模态结果输出。
        "OUTRES,NSOL,ALL",  # 保存全部模态节点解。
        "OUTRES,VENG,ALL",  # 保存全部模态单元能量。
        "SOLVE",  # 执行最终预应力切线模态求解。
    ]  # 完成必须唯一且严格递增的命令序列。
    ordered_positions: list[int] = []  # 保存每条完整命令在既有尾段中的字符位置供顺序闭合。
    for command in ordered_tail_commands:  # 逐条按完整独立行锁定命令，避免注释或相似前缀造成误计数。
        command_matches = list(re.finditer(rf"(?mi)^\s*{re.escape(command)}\s*$", tail))  # 只接受忽略大小写的独立 APDL 命令行。
        require(len(command_matches) == 1, f"既有 C10 尾段命令不是唯一一处：{command}")  # 任一缺失或重复均说明尾段已漂移。
        ordered_positions.append(command_matches[0].start())  # 保存唯一命令起点供严格递增检查。
    require(ordered_positions == sorted(ordered_positions) and len(set(ordered_positions)) == len(ordered_positions), "既有 C10 尾段线性扰动命令顺序不符合冻结协议")  # 从重启动到模态 SOLVE 不允许换序或回跳。
    elform_to_modal_solve = tail[ordered_positions[2] : ordered_positions[-1]]  # 截取 ELFORM 起点至最终模态 SOLVE 之前的控制流窗口。
    require(re.search(r"(?mi)^\s*FINISH\s*$", elform_to_modal_solve) is None, "既有 C10 尾段在 ELFORM 与模态 SOLVE 之间含 FINISH，扰动求解上下文已断开")  # 形成切线矩阵后不得离开求解处理器再求模态。
    result_match = re.search(r"(?mi)^FILE,([^,\r\n]+),rstp\s*$", tail)  # 从既有 RSTP FILE 命令识别旧 jobname。
    require(result_match is not None, "既有 C10 尾段无法识别 RSTP FILE jobname")  # 后处理文件身份必须可唯一映射。
    old_jobname = result_match.group(1).strip()  # 去除命令字段首尾空白得到旧作业名。
    require(tail.count(old_jobname) == 2, "既有 C10 模态尾段旧 jobname 引用数不是冻结的两处")  # FILE 与 modal DB SAVE 应各引用一次。
    require(f"SAVE,{old_jobname}_modal,db" in tail, "既有 C10 尾段 modal DB SAVE 未绑定识别出的旧 jobname")  # 防止只替换结果读取而漏改保存身份。
    candidate = tail.replace(OLD_RESTART_COMMAND, NEW_RESTART_COMMAND)  # 精确指定载荷步二、子步一和 `.r002`。
    require(candidate.count(OLD_RESTART_COMMENT) == 1 and candidate.count(OLD_PARKEEP_COMMENT) == 1, "既有 C10 尾段重启动或 PARKEEP 说明不是唯一冻结文本")  # 只允许窄范围更正两处已知误导说明。
    candidate = candidate.replace(OLD_RESTART_COMMENT, NEW_RESTART_COMMENT, 1)  # 把“最高可用子步”说明同步改为精确 LS2/SS1。
    candidate = candidate.replace(OLD_PARKEEP_COMMENT, NEW_PARKEEP_COMMENT, 1)  # 更正 PARKEEP 语义而不改变实际命令。
    candidate = candidate.replace(old_jobname, jobname)  # 保持静力原 jobname 以便 MAPDL 找到复制的重启动文件族。
    require(candidate.count(NEW_RESTART_COMMAND) == 1 and OLD_RESTART_COMMAND not in candidate, "新模态主控重启动命令替换未闭合")  # 证明只有批准入口存在。
    require(candidate.count(jobname) == 2, "新模态主控同 jobname 引用数不是两处")  # FILE 与 modal SAVE 必须保持同一作业身份。
    require(candidate.count(QA_INSERT_ANCHOR) == 1, "既有 C10 模态尾段 QA 插入锚点不是唯一一处")  # 防止 APDL Math 块插入错误位置。
    qa_block = build_apdl_math_qa_block(jobname, newline)  # 生成绑定当前作业文件族的正交与残差证据块。
    candidate = candidate.replace(QA_INSERT_ANCHOR, qa_block + QA_INSERT_ANCHOR, 1)  # 在八十阶计数通过后插入一次 QA，再继续原尾段。
    header = newline.join([  # 构造不改变数据库的三行用途声明头。
        "! C10 独立模态诊断：仅从已封存 LS2/子步1重启动，禁止静力重算。",  # 明确本输入不含建模或静力阶段。
        "! 保持静力 jobname 不变，使 ANTYPE,,RESTART,2,1,PERTURB 读取同名 RDB/LDHI/R002/RST。",  # 明确同 jobname 原因。
        "! production=false；求解与导出完成仍必须通过外部残差、正交、刚体模态和结果闭合门。",  # 明确用途和后续门禁。
    ]) + newline  # 为头部追加一个换行后紧接原模态尾段。
    return header + candidate  # 返回只含声明、既有尾段受控替换和数值 QA 插入的完整 APDL 输入。


def write_prepare_ledger(run_dir: Path, ledger_path: Path) -> int:  # run_dir 是暂存运行根，ledger_path 是排除自身的账本目标；返回条目数。
    """冻结准备完成时全部普通文件的 POSIX 相对路径和 SHA-256。"""  # 执行脚本据此拒绝启动前漂移。
    files = sorted((path for path in run_dir.rglob("*") if path.is_file() and path.resolve() != ledger_path.resolve()), key=lambda path: path.relative_to(run_dir).as_posix())  # 收集除账本自身外全部普通文件并稳定排序。
    lines = [f"{sha256_file(path)}  {path.relative_to(run_dir).as_posix()}" for path in files]  # 对每个准备态文件生成标准摘要与 POSIX 标签。
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")  # 以 LF 写出完整账本并保留末尾换行。
    return len(lines)  # 返回账本条目数供 manifest 外部摘要和控制台结果使用。


def prepare_modal_run(static_run: Path) -> dict[str, Any]:  # static_run 是已规范化静力运行目录，返回新运行包身份与摘要。
    """在唯一暂存目录中复制重启动原件、生成输入与证据，最后原子发布。"""  # 函数从不调用 MAPDL 或执行新输入。
    source = validate_static_source(static_run)  # 在任何新目录创建前完成静力状态、哈希和二进制身份硬门。
    created_at = datetime.now(timezone.utc)  # 生成统一 UTC 时间对象供运行名和 JSON 时间共用。
    run_name = f"C10_MODAL_DIAGNOSTIC_{created_at.strftime('%Y%m%dT%H%M%S%fZ')}"  # 使用微秒级 UTC 形成不可覆盖运行名。
    final_dir = RUNS_ROOT / run_name  # 构造最终发布目录但暂不创建。
    require(not final_dir.exists(), f"目标模态运行目录已存在：{final_dir}")  # 永不覆盖任何既有 run。
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{run_name}_building_", dir=RUNS_ROOT))  # 在同卷 ultra_runs 创建仅本次拥有的唯一暂存目录。
    require(staging_dir.resolve().parent == RUNS_ROOT.resolve(), "暂存目录逃逸 ultra_runs")  # 对后续失败清理建立明确安全范围。
    try:  # 任一复制、哈希或写入失败都进入仅清理本暂存目录的回滚路径。
        solver_dir = staging_dir / "solver"  # 新 solver 目录只承载四项种子、模态输入和未来输出。
        snapshot_dir = staging_dir / "input_snapshot"  # 输入快照保存完整既有 C10 主控和新模态主控副本。
        lineage_dir = staging_dir / "lineage"  # 谱系目录原样保存静力 manifest、三份终态证据和最终摘要账本。
        qa_dir = staging_dir / "qa"  # 预建 QA 目录供未来 finalizer 输出，不在 prepare 伪造结果。
        solver_dir.mkdir()  # 创建唯一 solver 子目录；父暂存目录已存在。
        snapshot_dir.mkdir()  # 创建唯一输入快照子目录。
        lineage_dir.mkdir()  # 创建唯一谱系子目录。
        qa_dir.mkdir()  # 创建唯一 QA 子目录。
        modal_text = build_modal_main(source["source_main_path"], source["jobname"])  # 从已验真主控尾段生成同 jobname 模态输入。
        modal_main_path = solver_dir / MODAL_MAIN_NAME  # 定位未来 MAPDL -i 使用的唯一主输入。
        modal_main_path.write_text(modal_text, encoding="utf-8", newline="")  # 按生成文本自带换行风格写入，不触发额外转换。
        modal_main_sha256 = sha256_file(modal_main_path)  # 冻结未来 execute 必须重新核对的输入摘要。
        source_snapshot_path = snapshot_dir / "c10_mpc_only_main.inp"  # 保留完整既有 C10 主控快照供尾段来源审计。
        shutil.copy2(source["source_main_path"], source_snapshot_path)  # 原样复制来源主控并保留基础文件元数据。
        require(sha256_file(source_snapshot_path) == source["source_main_sha256"], "C10 主控快照复制后 SHA-256 不闭合")  # 复制字节必须与来源相同。
        modal_snapshot_path = snapshot_dir / MODAL_MAIN_NAME  # 保存新模态输入的审阅副本。
        shutil.copy2(modal_main_path, modal_snapshot_path)  # 原样复制未来执行输入到快照目录。
        require(sha256_file(modal_snapshot_path) == modal_main_sha256, "模态主控快照复制后 SHA-256 不闭合")  # solver 与快照副本必须同字节。
        lineage_sources = {  # 定义静力 manifest、三份终态证据与最终账本到隔离谱系文件名的映射。
            "static_manifest.json": source["manifest_path"],  # 静力准备身份合同快照。
            "static_final_status.json": source["final_status_path"],  # 根提交状态快照。
            "static_solution_verification.json": source["verification_path"],  # 完整数值 QA 快照。
            "static_raw_result_manifest.json": source["raw_manifest_path"],  # 原始结果清单快照。
            "static_artifact_hashes.final.sha256": source["final_ledger_path"],  # 最终发布账本快照，独立承诺四项重启动摘要。
        }  # 完成五份谱系来源映射。
        lineage_hashes: dict[str, str] = {}  # 初始化谱系快照相对名到摘要的映射。
        for target_name, source_path in lineage_sources.items():  # 逐份复制并复核静力终态证据原始字节。
            target_path = lineage_dir / target_name  # 构造隔离 run 内的唯一谱系目标。
            shutil.copy2(source_path, target_path)  # 原样复制 JSON，不重排字段或重新序列化。
            source_hash = sha256_file(source_path)  # 计算来源 JSON 完整字节摘要。
            require(sha256_file(target_path) == source_hash, f"静力谱系快照复制后 SHA-256 不闭合：{target_name}")  # 证明快照逐字节一致。
            lineage_hashes[target_name] = source_hash  # 保存摘要供 modal manifest 记录。
        copied_restart_records: list[dict[str, Any]] = []  # 初始化四项复制种子的 manifest 记录数组。
        for suffix in REQUIRED_RESTART_SUFFIXES:  # 按固定后缀顺序复制同 jobname 重启动文件族。
            artifact = source["restart_artifacts"][suffix]  # 读取已验真来源路径、摘要和字节数。
            target_path = solver_dir / artifact["path"].name  # 在新 solver 中保持完全相同文件名和 jobname。
            shutil.copy2(artifact["path"], target_path)  # 原样复制静力重启动种子供未来续算。
            require(target_path.stat().st_size == artifact["size_bytes"], f"重启动复制件大小不闭合：{target_path.name}")  # 先以字节数关闭截断门。
            require(sha256_file(target_path) == artifact["sha256"], f"重启动复制件 SHA-256 不闭合：{target_path.name}")  # 再以完整摘要关闭内容门。
            copied_restart_records.append({  # 记录来源、复制件和不变身份供 execute 复核。
                "suffix": suffix,  # 四项合同中的标准后缀。
                "source_path": str(artifact["path"]),  # 静力 raw manifest 指向的原件绝对路径。
                "copied_path": f"solver/{target_path.name}",  # 新 run 内复制件 POSIX 相对路径。
                "size_bytes": artifact["size_bytes"],  # 来源与复制件共同字节数。
                "sha256": artifact["sha256"],  # 来源与复制件共同 SHA-256。
            })  # 完成当前重启动工件记录。
        final_solver_dir = final_dir / "solver"  # 构造发布后 execute 必须使用的 solver 绝对路径。
        final_main_path = final_solver_dir / MODAL_MAIN_NAME  # 构造发布后 -i 主输入绝对路径。
        final_output_path = final_solver_dir / f"{source['jobname']}.out"  # 构造发布后唯一主 OUT 绝对路径。
        launch_argv = [  # 冻结未来 execute 必须逐项采用的 SMP1 批处理参数。
            str(source["mapdl_executable"]),  # argv[0] 使用与静力 run 同摘要的 MAPDL 可执行文件。
            "-b",  # 采用非交互批处理模式。
            "-smp",  # 第一轮只允许共享内存并行模式。
            "-np",  # 后一参数指定 SMP 进程/线程数量。
            "1",  # 第一轮诊断固定单进程，禁止 DMP 或多线程变量混入。
            "-j",  # 后一参数指定必须保持不变的静力 jobname。
            source["jobname"],  # 复用静力作业名以读取同名 RDB/LDHI/R002/RST。
            "-dir",  # 后一参数指定完全隔离的新 solver 工作目录。
            str(final_solver_dir),  # 所有新二进制和文本只允许写入本 run solver。
            "-i",  # 后一参数指定只含模态重启动尾段的新主输入。
            str(final_main_path),  # 绑定发布后的主输入绝对路径。
            "-o",  # 后一参数指定唯一主输出文件。
            str(final_output_path),  # 绑定同 jobname 的发布后主 OUT 路径。
        ]  # 完成冻结 SMP1 启动参数数组。
        manifest_payload = {  # 构造 execute 与 finalizer 的共享机器合同。
            "schema_version": 1,  # 本模态隔离链首版 schema。
            "run_name": run_name,  # 新运行目录和全部状态文件共同身份。
            "status": "MODAL_DIAGNOSTIC_PREPARED",  # 只表示准备完成，未表示求解或 QA 通过。
            "created_at_utc": created_at.isoformat(),  # 记录带时区的统一准备时间。
            "static_run_name": static_run.name,  # 绑定唯一静力来源 run。
            "static_run_path": str(static_run),  # 记录静力来源规范绝对路径。
            "static_load_path_mode": source["load_path_mode"],  # 记录静力 manifest、根状态和验证包三方闭合的载荷路径身份。
            "jobname": source["jobname"],  # 明确静力与模态同 jobname 合同。
            "main_input": f"solver/{MODAL_MAIN_NAME}",  # 新模态主输入 POSIX 相对路径。
            "main_input_sha256": modal_main_sha256,  # 新模态主输入完整摘要。
            "modal_tail_source": "input_snapshot/c10_mpc_only_main.inp",  # 既有 C10 主控来源快照相对路径。
            "modal_tail_source_sha256": source["source_main_sha256"],  # 既有主控完整摘要。
            "modal_tail_anchor": MODAL_TAIL_ANCHOR,  # 冻结尾段截取起点文本。
            "restart_command": NEW_RESTART_COMMAND,  # 冻结 LS2/子步1线性扰动入口。
            "perturb_command": "PERTURB,MODAL,AUTO,CURRENT,PARKEEP",  # 冻结当前切线及“保留位移约束、删除机械/惯性载荷、保留 CP/CE”的 PARKEEP 语义。
            "element_form_command": "SOLVE,ELFORM",  # 冻结模态求解前的扰动单元矩阵形成步骤。
            "mass_matrix_command": "LUMPM,OFF",  # 冻结一致质量矩阵选项，禁止执行阶段改用集中质量近似。
            "modal_solver_command": "MODOPT,LANB,80",  # 冻结 Block Lanczos 八十阶合同。
            "mode_expansion_command": "MXPAND,80,,,YES",  # 冻结八十阶展开及单元结果计算合同。
            "modal_outres_commands": ["OUTRES,ALL,NONE", "OUTRES,NSOL,ALL", "OUTRES,VENG,ALL"],  # 冻结关闭默认输出后保留全部节点解和单元能量的三条有序命令。
            "modal_solve_command": "SOLVE",  # 冻结在上述线性扰动设置后执行一次最终模态求解。
            "modes_requested": EXPECTED_MODES,  # 外部 QA 必须闭合的提取阶数。
            "frequency_bounds_hz": None,  # 不设置上下限，避免固定频带截断八十阶。
            "execution_mode": "SMP_SERIAL_NP1_DIAGNOSTIC_ONLY",  # 第一轮只允许 SMP1 诊断。
            "mapdl_executable": str(source["mapdl_executable"]),  # 冻结可执行文件绝对路径。
            "mapdl_executable_sha256": source["mapdl_sha256"],  # 冻结可执行文件 SHA-256。
            "launch_argv": launch_argv,  # 冻结未来 execute 完整参数序列。
            "resource_gates": {  # 记录 execute 必须在启动瞬间重新实测的硬门。
                "available_ram_min_bytes": MIN_AVAILABLE_RAM_BYTES,  # 可用 RAM 至少 8 GiB。
                "solver_volume_free_disk_min_bytes": MIN_FREE_DISK_BYTES,  # solver 卷空闲空间至少 40 GiB。
                "exceptions_allowed": False,  # 模态诊断不继承静力 4 GiB 例外。
            },  # 完成资源硬门对象。
            "numerical_qa_contract": {  # 冻结 finalizer 的残差、正交与刚体模态阈值。
                "residual_definition": "NORM2_KPHI_MINUS_LAMBDA_MPHI_OVER_MAX_NORM2_KPHI_AND_ABS_LAMBDA_NORM2_MPHI",  # 说明无量纲残差公式。
                "maximum_normalized_residual": MAX_NORMALIZED_RESIDUAL,  # 每阶最大允许残差。
                "orthogonality_definition": "PHI_TRANSPOSE_M_PHI_VERSUS_IDENTITY",  # 说明质量正交 Gram 判据。
                "maximum_diagonal_deviation": MAX_ORTHOGONALITY_ERROR,  # Gram 对角相对单位阵的最大偏差。
                "maximum_off_diagonal_absolute": MAX_ORTHOGONALITY_ERROR,  # Gram 非对角最大绝对值。
                "rigid_body_frequency_limit_hz": RIGID_BODY_FREQUENCY_LIMIT_HZ,  # 数值刚体模态排除阈值。
            },  # 完成数值 QA 合同对象。
            "restart_artifacts": copied_restart_records,  # 四项静力原件和隔离复制件的共同身份。
            "static_lineage_sha256": lineage_hashes,  # 静力 manifest、三份终态证据与最终账本共五份快照摘要。
            "production": False,  # 精确满足用户要求，任何数值通过都不自动升级生产用途。
            "valid_for_production": False,  # 与既有桥梁运行包字段保持一致的非生产标志。
            "launch_allowed_after_execute_preflight_only": True,  # 只有 execute 重新核对资源、进程和哈希后才允许启动。
            "mapdl_execution_attempted": False,  # prepare 本身从未调用求解器。
            "mapdl_started": False,  # prepare 完成时不存在本 run MAPDL 进程。
        }  # 完成模态 manifest 对象。
        manifest_path = staging_dir / MODAL_MANIFEST_NAME  # 定位暂存根机器 manifest。
        write_json(manifest_path, manifest_payload)  # 写出完整准备合同。
        status_payload = {  # 构造根级准备状态提交标志。
            "schema_version": 1,  # 与 manifest 使用同一首版 schema。
            "run_name": run_name,  # 绑定新运行身份。
            "jobname": source["jobname"],  # 明确保持静力 jobname。
            "status": "MODAL_DIAGNOSTIC_PREPARED",  # 表示只准备未启动。
            "static_source_status": EXPECTED_STATIC_STATUS,  # 记录已通过的静力根状态。
            "restart_seed_status": "FOUR_REQUIRED_ARTIFACTS_COPIED_AND_HASH_CLOSED",  # 记录四项复制完成事实。
            "modal_status": "NOT_RUN",  # 明确八十阶尚未求解。
            "execution_mode": "SMP_SERIAL_NP1_DIAGNOSTIC_ONLY",  # 明确首轮执行模式。
            "production": False,  # 根状态永久不授予生产用途。
            "valid_for_production": False,  # 兼容既有状态字段并保持假。
            "next_action": "RUN_ULTRA_C10_MODAL_EXECUTE_AFTER_8_GIB_RAM_40_GIB_DISK_AND_NO_SOLVER_PROCESS_GATES",  # 指向唯一安全后续步骤。
        }  # 完成准备状态对象。
        write_json(staging_dir / MODAL_STATUS_NAME, status_payload)  # 写出根状态但仍处于未发布暂存目录。
        launch_text = " ".join(f'"{value}"' if " " in value else value for value in launch_argv) + "\n"  # 生成仅供人工审阅的带引号 SMP1 命令文本。
        (staging_dir / "launch_command_smp1.txt").write_text(launch_text, encoding="utf-8", newline="\n")  # 写出审阅命令但绝不执行。
        result_packet = "# C10 隔离式模态诊断准备包\n\n- 已从静力终态复制并逐项复核 `.rdb/.ldhi/.r002/.rst`。\n- 保持静力 jobname；入口为 `ANTYPE,,RESTART,2,1,PERTURB`，随后 `PERTURB,MODAL,AUTO,CURRENT,PARKEEP`、`SOLVE,ELFORM` 与 `MODOPT,LANB,80`。\n- 首轮只允许 SMP1；启动瞬间可用 RAM 必须不少于 8 GiB，solver 卷空闲空间必须不少于 40 GiB。\n- APDL Math 将输出质量正交矩阵和八十阶特征残差；外部 finalizer 未通过前不构成完成。\n- `production=false`；本包未运行任何求解器。\n"  # 生成简明人读用途和硬门说明。
        (staging_dir / "result_packet.md").write_text(result_packet, encoding="utf-8", newline="\n")  # 写出准备说明且不冒充结果报告。
        script_snapshot_path = lineage_dir / SCRIPT_PATH.name  # 保存实际 prepare 源码快照供未来审计。
        shutil.copy2(SCRIPT_PATH, script_snapshot_path)  # 原样复制当前脚本字节到谱系目录。
        require(sha256_file(script_snapshot_path) == sha256_file(SCRIPT_PATH), "prepare 脚本谱系快照 SHA-256 不闭合")  # 证明快照与实际执行源码一致。
        ledger_path = staging_dir / PREPARE_LEDGER_NAME  # 定位准备态全文件账本目标。
        ledger_entries = write_prepare_ledger(staging_dir, ledger_path)  # 在所有准备文件稳定后冻结除账本自身外的完整目录。
        ledger_sha256 = sha256_file(ledger_path)  # 计算账本自身摘要供控制台结果返回。
        os.replace(staging_dir, final_dir)  # 在同一 ultra_runs 卷内原子发布完整运行目录。
        return {  # 返回供 CLI 打印和调用方记录的最小成功摘要。
            "status": "MODAL_DIAGNOSTIC_PREPARED",  # 准备成功但未启动。
            "run_dir": str(final_dir),  # 新运行包规范绝对路径。
            "run_name": run_name,  # 新运行身份。
            "jobname": source["jobname"],  # 保持不变的静力作业名。
            "main_input_sha256": modal_main_sha256,  # 新模态主输入摘要。
            "prepare_ledger_entries": ledger_entries,  # 准备态账本条目数。
            "prepare_ledger_sha256": ledger_sha256,  # 准备态账本摘要。
            "production": False,  # 再次明确不授予生产用途。
            "solver_started": False,  # 再次明确本函数未启动求解器。
        }  # 完成成功摘要对象。
    except Exception:  # 捕获暂存构造中的任意异常以避免残留半成品。
        if staging_dir.exists() and staging_dir.resolve().parent == RUNS_ROOT.resolve() and staging_dir.name.startswith(f".{run_name}_building_"):  # 只允许清理本次创建且仍在 ultra_runs 的精确暂存目录。
            shutil.rmtree(staging_dir)  # 删除未发布暂存目录；既有静力 run 和任何正式 run 均不在目标范围。
        raise  # 保留原异常和具体失败门给调用方，禁止用模糊状态替代。


def main(argv: list[str] | None = None) -> int:  # argv 是可选 CLI 参数序列，返回零表示只准备成功、二表示拒绝且未启动。
    """执行命令行入口并以 JSON 打印成功摘要或明确拒绝原因。"""  # 无论成功失败均不调用 MAPDL。
    try:  # 统一捕获业务门异常并转换为稳定非零退出码。
        args = parse_args(argv)  # 解析显式静力运行目录参数。
        static_run = ensure_direct_run_child(Path(args.static_run_dir))  # 规范化并限制来源目录范围。
        result = prepare_modal_run(static_run)  # 完成来源验真、隔离复制、主控生成和原子发布。
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))  # 向调用方输出机器可读成功摘要。
        return 0  # 零退出码只代表准备包成功发布，绝不代表求解或工程通过。
    except Exception as exc:  # 捕获参数后全部业务拒绝和文件系统异常。
        failure = {"status": "MODAL_PREPARE_REJECTED", "reason": str(exc), "solver_started": False, "production": False}  # 构造不含虚假通过字段的失败摘要。
        print(json.dumps(failure, ensure_ascii=False, indent=2, allow_nan=False))  # 输出明确失败原因供人工和编排器读取。
        return 2  # 非零退出码阻止后续 execute 自动串行运行。


if __name__ == "__main__":  # 仅当脚本被直接调用时进入 CLI，导入供测试不会产生文件或进程副作用。
    raise SystemExit(main())  # 把 main 返回码传递给操作系统并正常结束解释器。
