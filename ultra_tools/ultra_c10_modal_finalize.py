"""只读核验 C10 隔离模态求解，并在八十阶、残差、质量正交和刚体模态门全部通过后发布非生产终态。"""  # 求解器完成不等于工程通过，本模块永久保持 production=false。

from __future__ import annotations  # 启用延迟类型注解，避免动态 QA 容器在导入阶段产生兼容性副作用。

import argparse  # 解析唯一允许的模态运行目录参数并提供标准帮助入口。
import csv  # 解析 APDL 属性、能量、残差和质量 Gram 矩阵 CSV。
import hashlib  # 复算关键结果、输入、二进制和最终全 run 账本 SHA-256。
import json  # 读取准备/启动证据并输出最终机器 QA、状态和运行回执。
import math  # 拒绝 NaN/Inf，并复算频率、特征值、残差与正交误差。
import msvcrt  # 在 Windows 上持有自动随进程释放的单字节文件区间锁，阻断并发 finalizer。
import os  # 通过同目录临时文件和 os.replace 原子发布非提交产物与最终状态。
import re  # 解析 MAPDL 完成标志、导出计数和 RSTP SET LIST 行。
from datetime import datetime, timezone  # 生成统一最终化 UTC 时间。
from pathlib import Path  # 规范化项目、run、solver 和最终账本标签路径。
from typing import Any  # 描述 JSON 动态对象和各类 QA 摘要。

import psutil  # 只读确认包装 PID 与携带同 jobname 的真实 ANSYS 进程均已退出。


SCRIPT_PATH = Path(__file__).resolve()  # 固定当前 finalizer 源码绝对路径供最终 QA 记录身份。
TOOLS_DIR = SCRIPT_PATH.parent  # ultra_tools 是脚本目录。
PROJECT_ROOT = TOOLS_DIR.parent  # 项目根目录承载 ultra_runs。
RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # finalizer 只允许读取和封板该目录直属模态 run。
MANIFEST_NAME = "C10_modal_manifest.json"  # prepare 冻结的身份、阈值和文件合同。
PREPARE_STATUS_NAME = "C10_modal_status.json"  # prepare 根状态必须仍保留未启动历史事实。
PREPARE_LEDGER_NAME = "prepare_artifact_hashes.sha256"  # prepare 冻结的启动前普通文件账本，重启动工作复制件除外仍须保持原字节。
RUNTIME_LAUNCH_NAME = "runtime_launch.json"  # execute 发布的 PID、参数和资源硬门回执。
RUNTIME_STATUS_NAME = "C10_modal_runtime_status.json"  # execute 发布的运行中状态原件。
LAUNCH_CLAIM_NAME = "runtime_launch_claim.json"  # execute 在 Popen 前独占创建的并发启动所有权证据。
LAUNCH_FAILURE_NAME = "runtime_launch_failure.json"  # execute 在 Popen 或启动回执事务异常时写出的永久审查阻断证据。
FINAL_STATUS_NAME = "C10_modal_final_status.json"  # 最后原子发布的唯一模态终态提交标志。
FINAL_RUNTIME_NAME = "C10_modal_runtime_final_status.json"  # 不覆盖运行中原件的最终运行回执。
QA_NAME = "modal_solution_verification.json"  # 完整数值和工件门机器 QA 输出。
FINAL_LEDGER_NAME = "final_artifact_hashes.sha256"  # 覆盖最终状态字节承诺且排除自身的全 run 账本。
RESULT_PACKET_NAME = "result_packet_final.md"  # 不覆盖 prepare 说明的人读最终诊断结果包。
FINALIZE_LOCK_NAME = ".c10_modal_finalize.lock"  # finalizer 进程持有的自动释放互斥锁文件名，文件本身保留供最终账本闭合。
EXPECTED_PREPARE_STATUS = "MODAL_DIAGNOSTIC_PREPARED"  # 只允许从 prepare 的精确未启动状态封板。
EXPECTED_RUNTIME_STATUS = "RUNNING_UNFINALIZED"  # 启动回执必须保留真实运行中历史状态。
EXPECTED_EXECUTION_MODE = "SMP_SERIAL_NP1_DIAGNOSTIC_ONLY"  # 首轮结果只接受 SMP 单进程执行。
EXPECTED_SOLVER_GATE_STATUS = "STATUS=SOLVER_EXPORT_COMPLETED PHASE=EXTERNAL_QA_REQUIRED"  # APDL 尾段唯一完成导出阶段标志。
EXPECTED_NUMERICAL_QA_STATUS = "STATUS=NUMERICAL_QA_ARTIFACTS_GENERATED EXTERNAL_THRESHOLDS_PENDING"  # APDL Math 两份数值证据生成阶段标志。
FINAL_STATUS = "MODAL_DIAGNOSTIC_COMPLETED_NONPRODUCTION"  # 全部数值门通过后的条件性非生产终态。
QA_STATUS = "PASSED_FOR_MODAL_DIAGNOSTIC_ONLY"  # QA 只授权本次诊断用途。
EXPECTED_MODES = 80  # 属性、结果集、残差、正交矩阵、能量和向量均固定八十阶。
MODAL_PROPERTY_COLUMNS = 15  # c10_modal_properties.csv 每行包含阶次、频率、广义质量及十二项参与/有效质量。
RESIDUAL_COLUMNS = 7  # 残差 CSV 每行包含阶次、频率、λ、绝对残差、两侧尺度和尺度化残差。
SENE_COLUMNS = 16  # 六组件模态应变能 CSV 每行固定十六列。
ORTHOGONALITY_SIZE = 80  # 质量 Gram 矩阵必须是 80×80。
MIN_VECTOR_BYTES = 1_000_000  # 每份全桥位移或转角文本至少 1 MB，防止空壳文件通过。
EXPECTED_VECTOR_NODE_ROWS = 91_407  # C10 每份位移/转角导出应覆盖 109086 总节点扣除 17679 个方向单元辅助节点后的九万一千四百零七节点。
EXPECTED_TOPOLOGY_NODE_COUNT = 109_086  # C10 冻结全桥拓扑节点总数，用于解释向量导出节点覆盖基数。
EXPECTED_DIRECTION_NODE_COUNT = 17_679  # 类型 70 方向单元辅助节点数，这些节点不进入既有全节点模态向量选择集。
MAX_NORMALIZED_RESIDUAL = 1.0e-6  # 每阶尺度化特征方程残差上限。
MAX_ORTHOGONALITY_ERROR = 1.0e-6  # Gram 对角偏差与非对角绝对值共同上限。
RIGID_BODY_FREQUENCY_LIMIT_HZ = 1.0e-6  # 小于等于一微赫兹的阶次视为数值刚体模态并拒绝。
FREQUENCY_MATCH_TOLERANCE_HZ = 1.0e-7  # 属性、RSTP SET LIST 和残差三处频率最大绝对差上限。
VECTOR_FREQUENCY_RELATIVE_TOLERANCE = 2.0e-5  # PRNSOL 向量标题仅打印约五位有效数字，因此按两万分之一相对舍入界核对属性频率。
LAMBDA_RELATIVE_TOLERANCE = 1.0e-10  # 由频率复算 λ 与残差 CSV λ 的尺度化差异上限。
IDENTITY_RELATIVE_TOLERANCE = 1.0e-10  # EFFM=PFACT² 和残差列内部恒等式复算上限。
REQUIRED_BINARY_SUFFIXES = (".rstp", ".mode", ".full")  # 八十阶求解和外部数值 QA 必须存在的三项同 jobname二进制。
SOLVER_PROCESS_NAMES = {"ansys.exe", "ansys261.exe", "mapdl.exe", "mapdl261.exe"}  # 用于识别仍携带本作业参数的真实求解器映像。
SET_LIST_PATTERN = re.compile(r"(?m)^\s*(\d+)\s+([0-9.+\-EeDd]+)\s+1\s+(\d+)\s+(\d+)\s*$")  # 解析 RSTP SET、频率、载荷步、子步和累计序号，并兼容 Fortran D 指数。
ERROR_COUNT_PATTERN = re.compile(r"NUMBER OF ERROR\s+MESSAGES ENCOUNTERED\s*=\s*(\d+)", re.IGNORECASE)  # 提取 MAPDL 正常退出页尾累计错误数。
WARNING_COUNT_PATTERN = re.compile(r"NUMBER OF WARNING\s+MESSAGES ENCOUNTERED\s*=\s*(\d+)", re.IGNORECASE)  # 提取 MAPDL 正常退出页尾累计警告数供披露。
WARNING_BLOCK_PATTERN = re.compile(r"\*\*\* WARNING \*\*\*[\s\S]*?(?=\n\s*\*\*\* (?:WARNING|ERROR|FATAL) \*\*\*|\Z)", re.IGNORECASE)  # 按下一原生消息标题或文件末尾切分完整 warning 块。
APPROVED_WARNING_PHRASES = {  # 只允许本诊断已知且必须继续阻断生产签认的两类 warning。
    "COEFFICIENT_RATIO_GT_1E8": "COEFFICIENT RATIO EXCEEDS 1.0E8 - CHECK RESULTS.",  # 条件尺度跨越八个数量级的求解器警告。
    "ELAPSED_TIME_GT_CPU_TIME_PERFORMANCE": "ELAPSED TIME EXCEEDS THE CPU TIME",  # 内存或磁盘性能不足导致墙钟时间高于 CPU 时间的性能警告。
}  # 完成显式警告白名单；未知或同时匹配多类的 warning 一律拒绝。


def require(condition: bool, message: str) -> None:  # condition 是最终化硬门，message 是失败时具体原因；成功无返回。
    """任一数值、身份、进程或文件门失败时拒绝发布最终状态。"""  # 不提供自动放宽阈值或生产升级路径。
    if not condition:  # 仅在硬门不成立时进入拒绝分支。
        raise RuntimeError(message)  # 抛出具体原因并阻止全部最终产物提交。


def sha256_bytes(payload: bytes) -> str:  # payload 是内存字节，返回小写 SHA-256 摘要。
    """为尚未发布的最终状态字节建立账本承诺。"""  # 函数无文件副作用。
    return hashlib.sha256(payload).hexdigest()  # 一次性计算内存字节摘要并返回六十四位十六进制文本。


def sha256_file(path: Path) -> str:  # path 是现存普通文件，返回完整字节的小写 SHA-256。
    """以 8 MiB 分块复核大型 FULL/MODE/RSTP 和全节点向量。"""  # 函数只读目标文件。
    digest = hashlib.sha256()  # 初始化当前文件独立摘要器。
    with path.open("rb") as stream:  # 以二进制只读方式打开，避免编码和换行转换。
        while True:  # 持续读取固定分块至文件末尾。
            block = stream.read(8 * 1024 * 1024)  # 每次读取 8 MiB 原始字节。
            if not block:  # 空字节串表示完整读取结束。
                break  # 退出读取循环。
            digest.update(block)  # 按原始顺序把当前块纳入摘要。
    return digest.hexdigest()  # 返回完整 SHA-256 摘要。


def json_bytes(payload: dict[str, Any]) -> bytes:  # payload 是禁止 NaN 的机器对象，返回 UTF-8/LF 完整字节。
    """确定性渲染最终 JSON，供文件写入和状态账本使用同一字节源。"""  # 保留中文且统一末尾换行。
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 以两空格缩进序列化并拒绝非有限数。
    return rendered.encode("utf-8")  # 返回不含 BOM 的 UTF-8 字节。


def read_json(path: Path) -> dict[str, Any]:  # path 是必需 JSON，返回顶层对象。
    """严格读取 UTF-8 JSON，不为缺失或错误字段提供默认通过值。"""  # 业务门由调用方逐项实施。
    require(path.is_file(), f"缺少必需 JSON：{path}")  # 解码前关闭存在性门。
    payload = json.loads(path.read_text(encoding="utf-8-sig"))  # 接受可选 BOM 并由解析器拒绝无效 JSON。
    require(isinstance(payload, dict), f"JSON 顶层不是对象：{path}")  # 所有状态和 manifest 均必须是对象。
    return payload  # 返回已经通过顶层类型门的对象。


def read_mixed_text(path: Path) -> str:  # path 是 MAPDL 文本文件，返回可搜索文本并保留 ASCII 证据。
    """以 UTF-8 优先和替代策略读取 MAPDL 本地编码混合文本。"""  # 固定机器标志均为 ASCII，不受替代字符影响。
    require(path.is_file() and path.stat().st_size > 0, f"缺少或为空的文本工件：{path}")  # 空输出不能通过任何门。
    return path.read_text(encoding="utf-8", errors="replace")  # 以替代字符保留可解析上下文而不丢弃字节位置。


def parse_unique_status_record(path: Path, expected_record: str) -> str:  # path 是 APDL 状态文件，expected_record 是唯一允许的完整 STATUS 行；返回该行。
    """要求状态文件只含一个 STATUS 键值记录且精确等于预期，拒绝历史通过后追加 REJECTED。"""  # 非状态标题和空白可以存在但不参与结论。
    text_value = read_mixed_text(path)  # 读取完整状态文件并保留 ASCII 状态文本。
    status_records = [line.strip() for line in text_value.splitlines() if line.strip().upper().startswith("STATUS=")]  # 只收集以 STATUS= 起始的机器状态行并去除外围空白。
    require(status_records == [expected_record], f"{path.name} 的唯一状态记录不是预期值：{status_records}")  # 零条、多条、旧通过加新拒绝或字段漂移均阻断。
    return status_records[0]  # 返回已证明唯一且精确的状态行供 QA 记录。


def classify_warning_blocks(output_text: str) -> list[dict[str, Any]]:  # output_text 是完整主 OUT，返回逐条已白名单分类的 warning 证据。
    """逐块分类所有原生 warning，仅接受唯一命中显式白名单短语的诊断警告。"""  # 未知或一块命中多类均 fail-closed。
    classifications: list[dict[str, Any]] = []  # 初始化逐 warning 分类记录数组。
    for warning_index, warning_match in enumerate(WARNING_BLOCK_PATTERN.finditer(output_text), start=1):  # 按原生出现顺序遍历每个完整 warning 块。
        warning_block = warning_match.group(0)  # 取得当前 warning 标题至下一消息标题或文件末尾的完整文本。
        warning_upper = warning_block.upper()  # 统一大写实现稳定的不区分大小写短语匹配。
        matched_categories = [category for category, phrase in APPROVED_WARNING_PHRASES.items() if phrase in warning_upper]  # 计算当前块命中的全部批准类别。
        require(len(matched_categories) == 1, f"主 OUT 第 {warning_index} 条 warning 未知或分类歧义：{warning_block[:500]}")  # 必须且只能命中一个显式批准短语。
        normalized_excerpt = " ".join(warning_block.split())[:500]  # 压缩空白并限制披露长度，保留足够审查上下文且避免 QA 膨胀。
        classifications.append({"index": warning_index, "category": matched_categories[0], "excerpt": normalized_excerpt})  # 保存序号、唯一类别和审查摘录。
    raw_warning_count = output_text.upper().count("*** WARNING ***")  # 独立按原生标题字面量统计 warning 总数。
    require(len(classifications) == raw_warning_count, f"warning 分块器只分类 {len(classifications)} 条，但原生标题共有 {raw_warning_count} 条")  # 分块正则若漏掉任何标题必须拒绝而非静默少报。
    return classifications  # 返回可能为空但绝不含未知类别的完整分类数组。


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:  # argv 是可选测试参数，返回显式 run-dir 命名空间。
    """要求调用方明确指定已退出求解器的隔离模态 run。"""  # 脚本不会猜测最新目录。
    parser = argparse.ArgumentParser(description="最终化 C10 SMP1 模态诊断并保持 production=false。")  # 创建带用途边界的标准解析器。
    parser.add_argument("--run-dir", required=True, help="ultra_runs 下已由 modal execute 启动并完成的直属运行目录。")  # 唯一业务参数不得省略。
    return parser.parse_args(argv)  # 未知参数由 argparse 自动拒绝。


def normalize_run_dir(path: Path) -> Path:  # path 是用户给出的 run，返回 ultra_runs 直属规范目录。
    """阻断项目外、嵌套或非 C10 模态诊断目录进入最终化。"""  # 本函数只读检查路径。
    resolved = path.resolve()  # 消解相对段和可解析链接。
    require(resolved.is_dir(), f"模态运行目录不存在：{resolved}")  # 只有现存目录可最终化。
    require(resolved.parent == RUNS_ROOT.resolve(), f"模态运行目录不是 ultra_runs 直属子目录：{resolved}")  # 禁止路径逃逸。
    require(resolved.name.startswith("C10_MODAL_DIAGNOSTIC_"), f"运行目录名不是 C10 模态诊断前缀：{resolved.name}")  # 防止误封静力或历史 run。
    return resolved  # 返回已通过范围和命名门的目录。


def acquire_finalize_lock(run_dir: Path) -> Any:  # run_dir 是规范模态 run，返回必须在 finally 中释放的已锁文件流。
    """独占锁定 run 内一个稳定字节，进程崩溃或句柄关闭时由 Windows 自动释放。"""  # 锁只协调 finalizer，不删除或覆盖任何用户证据。
    lock_path = run_dir / FINALIZE_LOCK_NAME  # 构造本 run 唯一互斥锁文件路径。
    try:  # 优先独占创建含一个固定字节的新锁文件，避免并发首次创建产生零长度竞态。
        lock_stream = lock_path.open("x+b")  # 以读写二进制和独占创建模式打开新锁文件。
        lock_stream.write(b"1")  # 写入固定 ASCII 1 作为可锁定的一字节区域，字面值不携带状态结论。
        lock_stream.flush()  # 刷新 Python 缓冲区以确保另一进程打开时能看到该字节。
        os.fsync(lock_stream.fileno())  # 请求固定锁字节落盘后再尝试区间锁。
    except FileExistsError:  # 已有锁文件可能来自前次正常或异常 finalizer，不能据此判断当前仍占有。
        lock_stream = lock_path.open("r+b")  # 以不截断方式打开现有锁文件，保留其账本身份。
        require(lock_path.stat().st_size == 1, f"finalizer 锁文件字节数不是冻结的一字节：{lock_path}")  # 防止外部内容被误当成互斥载体。
    lock_stream.seek(0)  # 把区间锁起点固定到唯一字节偏移零。
    try:  # 采用非阻塞锁，若另一 finalizer 活动则立即拒绝而不长时间等待。
        msvcrt.locking(lock_stream.fileno(), msvcrt.LK_NBLCK, 1)  # 独占锁定一个字节；锁随句柄或进程生命周期自动释放。
    except OSError as exc:  # Windows 在锁已被占有或句柄异常时抛出 OSError。
        lock_stream.close()  # 关闭本次未取得锁的句柄，避免资源泄漏。
        raise RuntimeError(f"另一个 C10 模态 finalizer 正在处理该 run：{run_dir}") from exc  # 以明确并发原因阻断第二提交者。
    return lock_stream  # 返回持续持锁的打开流，由最外层 finally 保证释放。


def release_finalize_lock(lock_stream: Any) -> None:  # lock_stream 是 acquire_finalize_lock 返回的打开流；函数释放锁并关闭句柄。
    """无论最终化成功或失败均显式释放锁，锁文件保留并进入证据账本。"""  # 释放失败仍通过 close 触发操作系统自动清理。
    try:  # 优先执行显式区间解锁以缩短互斥占有时间。
        lock_stream.seek(0)  # 把解锁起点恢复到偏移零。
        msvcrt.locking(lock_stream.fileno(), msvcrt.LK_UNLCK, 1)  # 释放与取得时完全相同的一字节区间。
    except OSError:  # 若显式解锁因句柄状态异常失败，关闭句柄仍由 Windows 保证释放锁。
        pass  # 不用成功结果掩盖关闭句柄这一更强的最终释放路径。
    finally:  # 即使显式解锁异常也必须关闭句柄，让 Windows 最终释放进程级锁。
        lock_stream.close()  # 关闭文件描述符并结束本 finalizer 的锁生命周期。


def capture_authoritative_snapshot(run_dir: Path) -> dict[str, dict[str, Any]]:  # run_dir 是尚未最终化的规范 run，返回全部现存普通文件的权威身份快照。
    """在解析任何 QA 内容前冻结文件集合、大小、mtime_ns 和 SHA-256。"""  # 后续解析和提交前必须再次逐项复核同一快照。
    snapshot: dict[str, dict[str, Any]] = {}  # 初始化 POSIX 相对标签到不可变身份的映射。
    for path in sorted((candidate for candidate in run_dir.rglob("*") if candidate.is_file()), key=lambda candidate: candidate.relative_to(run_dir).as_posix()):  # 以稳定标签顺序枚举全部现存普通文件。
        resolved = path.resolve()  # 规范化当前文件路径供越界检查。
        require(run_dir in resolved.parents, f"权威快照文件逃逸 run：{resolved}")  # 任何链接或路径逃逸均拒绝。
        label = path.relative_to(run_dir).as_posix()  # 生成跨平台稳定相对标签。
        require(label not in snapshot, f"权威快照存在重复文件标签：{label}")  # 同一标签只能对应一份字节证据。
        before = path.stat()  # 哈希前读取大小和纳秒修改时间。
        digest = sha256_file(path)  # 对当前文件完整字节计算 SHA-256。
        after = path.stat()  # 哈希后再次读取元数据以识别后台写入。
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"权威快照哈希期间文件变化：{label}")  # 活动文件不能进入最终证据。
        snapshot[label] = {"path": str(resolved), "size_bytes": before.st_size, "mtime_ns": before.st_mtime_ns, "sha256": digest}  # 保存解析前权威身份。
    require(snapshot, "模态 run 在最终化前没有任何普通文件")  # 空运行目录不能形成可验证快照。
    return snapshot  # 返回完整解析前权威快照。


def verify_authoritative_snapshot(run_dir: Path, snapshot: dict[str, dict[str, Any]], allowed_additional_labels: set[str] | None = None) -> None:  # 输入权威快照和可选本次新建标签；成功无返回。
    """在解析后及提交关键点逐项复算快照，阻断 QA 描述旧字节而账本封存新字节。"""  # 允许项只用于本 finalizer 已确定性写出的目标。
    additions = allowed_additional_labels or set()  # 未提供可选标签时使用空集合，禁止任何文件集合变化。
    actual_labels = {path.relative_to(run_dir).as_posix() for path in run_dir.rglob("*") if path.is_file()}  # 重新枚举当前全部普通文件标签。
    require(actual_labels == set(snapshot) | additions, f"权威快照后文件集合发生变化：新增={sorted(actual_labels - set(snapshot))}，缺失={sorted(set(snapshot) - actual_labels)}")  # 除显式最终化新文件外不允许增删。
    for label, record in snapshot.items():  # 对解析前每份文件逐项复核元数据和完整摘要。
        path = (run_dir / Path(label)).resolve()  # 从稳定标签恢复当前规范路径。
        require(run_dir in path.parents and path.is_file(), f"权威快照目标缺失或逃逸：{label}")  # 文件必须仍在同一 run 内。
        current_stat = path.stat()  # 读取当前大小和纳秒修改时间。
        require(current_stat.st_size == record["size_bytes"] and current_stat.st_mtime_ns == record["mtime_ns"], f"权威快照元数据漂移：{label}")  # 即使摘要碰巧相同也拒绝解析期间改写。
        require(sha256_file(path) == record["sha256"], f"权威快照 SHA-256 漂移：{label}")  # 重新计算完整摘要证明解析字节仍是权威字节。


def parse_prepare_ledger(run_dir: Path, runtime: dict[str, Any]) -> tuple[Path, dict[str, str]]:  # 输入规范 run 与 runtime 回执，返回已验真账本路径和记录映射。
    """先证明 manifest/status 自身受 execute 时账本保护，再允许消费其中任何外部路径。"""  # 该函数只读账本及 run 内目标。
    ledger_path = run_dir / PREPARE_LEDGER_NAME  # 定位 execute 启动前全量复算过的准备态账本。
    require(ledger_path.is_file() and sha256_file(ledger_path) == runtime.get("prepare_ledger_sha256"), "准备态账本缺失或与 runtime 记录摘要不一致")  # 账本自身必须保持 execute 时字节。
    records: dict[str, str] = {}  # 初始化准备态相对标签到摘要映射。
    for line_number, ledger_line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):  # 按一基行号解析全部准备态记录。
        ledger_match = re.fullmatch(r"([0-9a-f]{64})  (.+)", ledger_line)  # 验证固定小写 SHA-256 双空格格式。
        require(ledger_match is not None, f"准备态账本第 {line_number} 行格式无效")  # 任一格式错误即拒绝。
        expected_hash, relative_label = ledger_match.groups()  # 解包摘要和 POSIX 相对标签。
        require(relative_label not in records, f"准备态账本存在重复标签：{relative_label}")  # 每个准备文件只能承诺一次。
        target_path = (run_dir / Path(relative_label)).resolve()  # 解析当前准备文件规范路径。
        require(run_dir in target_path.parents and target_path.is_file(), f"准备态账本目标缺失或逃逸：{relative_label}")  # 目标必须仍位于本 run 内。
        records[relative_label] = expected_hash  # 保存全部记录供后续不可变文件复算。
    require(MANIFEST_NAME in records and PREPARE_STATUS_NAME in records, "准备态账本未覆盖 manifest 或根准备状态")  # 两个控制文件必须先受账本保护。
    require(sha256_file(run_dir / MANIFEST_NAME) == records[MANIFEST_NAME], "manifest SHA-256 已偏离 prepare 账本")  # 消费 manifest 外部路径前先证明其字节未改。
    require(sha256_file(run_dir / PREPARE_STATUS_NAME) == records[PREPARE_STATUS_NAME], "根准备状态 SHA-256 已偏离 prepare 账本")  # prepare 状态同样不得漂移。
    return ledger_path, records  # 返回已经验证控制文件身份的账本和完整映射。


def atomic_write(path: Path, payload: bytes) -> None:  # path 是允许的新最终产物目标，payload 是完整字节；成功无返回。
    """在同目录写入唯一临时文件、刷新后原子替换目标。"""  # 调用方必须先确认目标不存在或允许替换。
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")  # 以当前 finalizer PID 构造同目录唯一临时文件名。
    require(not temporary.exists(), f"原子写临时文件已存在：{temporary}")  # 防止并行 finalizer 复用同名临时文件。
    try:  # 把临时写入、刷新和原子替换纳入本目标的局部清理范围。
        with temporary.open("xb") as stream:  # 以二进制独占创建方式打开临时文件。
            stream.write(payload)  # 一次写出完整目标字节。
            stream.flush()  # 把 Python 缓冲区刷新到操作系统。
            os.fsync(stream.fileno())  # 请求文件内容落盘后再发布。
        os.replace(temporary, path)  # 在同目录原子替换目标，使读者只看到完整旧版或新版。
    except Exception:  # 任一局部写入或替换失败时清理仅由本次创建的临时碎片。
        if temporary.exists() and temporary.resolve().parent == path.resolve().parent:  # 删除前确认临时文件仍是目标同目录直属文件。
            temporary.unlink()  # 删除未发布临时文件，避免阻断后续安全重试。
        raise  # 保留原始异常给上层事务回滚和用户报告。


def parse_numeric_csv(path: Path, expected_columns: int) -> list[list[float]]:  # path 是纯数值 CSV，expected_columns 是精确列数；返回有限浮点行。
    """拒绝标题、缺列、多列、NaN、Inf 和空文件。"""  # APDL 生成文件按合同应为无标题纯数值。
    require(path.is_file() and path.stat().st_size > 0, f"缺少或为空的数值 CSV：{path}")  # 解析前关闭存在性和非空门。
    rows: list[list[float]] = []  # 初始化有效数值行数组。
    with path.open("r", encoding="utf-8", errors="replace", newline="") as stream:  # 以文本只读方式打开并保留 csv 模块换行处理。
        for line_number, raw_row in enumerate(csv.reader(stream), start=1):  # 按一基行号读取逗号分隔记录。
            if not raw_row or all(not cell.strip() for cell in raw_row):  # 忽略完全空白行而不改变有效行计数。
                continue  # 进入下一原始记录。
            require(len(raw_row) == expected_columns, f"{path.name} 第 {line_number} 行列数 {len(raw_row)} != {expected_columns}")  # 每行列数必须精确。
            try:  # 浮点转换失败需报告具体文件和行号。
                values = [float(cell.strip().replace("D", "E").replace("d", "e")) for cell in raw_row]  # 把 APDL 可能使用的 Fortran D 指数规范为 E 后转换为 Python 双精度浮点。
            except ValueError as exc:  # 捕获非数值字段。
                raise RuntimeError(f"{path.name} 第 {line_number} 行含非数值字段") from exc  # 保留原始转换异常链并阻断。
            require(all(math.isfinite(value) for value in values), f"{path.name} 第 {line_number} 行含 NaN/Inf")  # 所有结果必须有限。
            rows.append(values)  # 保存已通过结构和有限数门的行。
    require(rows, f"数值 CSV 无有效行：{path}")  # 至少一行才有验证意义。
    return rows  # 返回全部有限数值行。


def parse_orthogonality_matrix(path: Path) -> list[list[float]]:  # path 是 APDL Math *EXPORT CSV，返回精确 80×80 有限矩阵。
    """允许空白行但不猜测或删除索引列，确保 Gram 矩阵结构严格闭合。"""  # 任一标题或附加列均视为证据格式失败。
    rows = parse_numeric_csv(path, ORTHOGONALITY_SIZE)  # 复用严格纯数值和有限数门读取八十列。
    require(len(rows) == ORTHOGONALITY_SIZE, f"质量正交矩阵行数 {len(rows)} != {ORTHOGONALITY_SIZE}")  # 行列均必须八十。
    return rows  # 返回结构已经闭合的 Gram 矩阵。


def active_matching_solver_processes(jobname: str, solver_dir: Path) -> list[dict[str, Any]]:  # 输入本作业名和目录，返回仍活动的匹配 ANSYS 进程。
    """弥补包装 PID 先退出但真实计算子进程仍运行的常见情况。"""  # 只读枚举，不终止任何进程。
    matches: list[dict[str, Any]] = []  # 初始化匹配进程记录数组。
    for process in psutil.process_iter(["pid", "name", "cmdline"]):  # 一次读取 PID、映像名和参数。
        try:  # 进程可能在枚举期间退出或拒绝访问。
            name = str(process.info.get("name") or "").lower()  # 规范化映像名。
            command_line = " ".join(process.info.get("cmdline") or [])  # 合并参数供 jobname 和目录双筛选。
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):  # 捕获瞬时消失、权限和僵尸异常。
            continue  # 无法稳定读取的瞬时对象不作为仍运行证据。
        if name in SOLVER_PROCESS_NAMES and jobname.lower() in command_line.lower() and str(solver_dir).lower() in command_line.lower():  # 只匹配本 run 的真实求解器。
            matches.append({"pid": int(process.info["pid"]), "name": name, "cmdline": command_line})  # 保存完整身份供拒绝报告。
    return matches  # 零项表示没有发现本作业真实求解进程。


def validate_lineage_and_runtime(run_dir: Path) -> dict[str, Any]:  # run_dir 是规范模态 run，返回已闭合 manifest、启动回执和路径。
    """核对准备状态、SMP1 启动事实、资源硬门、输入身份和求解器完全退出。"""  # 该函数不解析结果数值。
    manifest = read_json(run_dir / MANIFEST_NAME)  # 读取 prepare 机器合同。
    prepare_status = read_json(run_dir / PREPARE_STATUS_NAME)  # 读取 prepare 根状态原件。
    launch_claim = read_json(run_dir / LAUNCH_CLAIM_NAME)  # 读取 Popen 前独占启动声明，证明并发双启动门已占有。
    runtime = read_json(run_dir / RUNTIME_LAUNCH_NAME)  # 读取 execute 启动回执。
    runtime_status = read_json(run_dir / RUNTIME_STATUS_NAME)  # 读取 execute 运行中状态原件。
    require(not (run_dir / LAUNCH_FAILURE_NAME).exists(), "存在 runtime_launch_failure.json，说明 Popen 或启动回执事务失败，禁止自动最终化")  # 含失败证据的 run 必须人工处置而不能靠结果文件绕过。
    prepare_ledger_path, prepare_ledger_records = parse_prepare_ledger(run_dir, runtime)  # 在使用 manifest 路径字段前证明其字节仍与 execute 账本一致。
    run_name = run_dir.name  # 目录名是四份状态必须共同绑定的运行身份。
    require(all(type(container.get("schema_version")) is int and container.get("schema_version") == 1 for container in (manifest, prepare_status, launch_claim, runtime, runtime_status)), "manifest/prepare/claim/runtime 的 schema_version 不是冻结整数值 1")  # 阻断 JSON 布尔 true 利用 Python 等值语义或跨版本字段语义混用。
    require(manifest.get("run_name") == run_name and prepare_status.get("run_name") == run_name and launch_claim.get("run_name") == run_name and runtime.get("run_name") == run_name and runtime_status.get("run_name") == run_name, "manifest/prepare/claim/runtime.run_name 与目录名不一致")  # 防止跨 run 拼接证据。
    require(manifest.get("status") == EXPECTED_PREPARE_STATUS and prepare_status.get("status") == EXPECTED_PREPARE_STATUS, "prepare 状态不是精确 MODAL_DIAGNOSTIC_PREPARED")  # 保留真实准备历史。
    require(prepare_status.get("modal_status") == "NOT_RUN" and prepare_status.get("execution_mode") == EXPECTED_EXECUTION_MODE, "prepare 根状态未保持 NOT_RUN 的 SMP1 诊断合同")  # prepare 文件只记录启动前历史事实。
    require(runtime.get("status") == EXPECTED_RUNTIME_STATUS and runtime_status.get("status") == EXPECTED_RUNTIME_STATUS, "启动回执或运行状态不是 RUNNING_UNFINALIZED")  # 只有 execute 正式启动的 run 可封板。
    require(runtime_status.get("modal_status") == "RUNNING" and runtime_status.get("next_action") == "WAIT_FOR_PROCESS_EXIT_THEN_RUN_ULTRA_C10_MODAL_FINALIZE", "运行状态未保留等待进程退出后最终化的精确历史语义")  # 阻断提前篡改为完成或其他动作。
    require(launch_claim.get("status") == "LAUNCH_CLAIMED_AFTER_ALL_PREFLIGHT_GATES", "启动声明不是全部预检通过后的精确状态")  # Popen 必须发生在资源和身份门之后且由唯一 execute 占有。
    require(launch_claim.get("launch_state") == "MAPDL_STARTED_RUNTIME_RECEIPTS_COMPLETE" and launch_claim.get("runtime_launch_name") == RUNTIME_LAUNCH_NAME and launch_claim.get("runtime_status_name") == RUNTIME_STATUS_NAME, "启动 claim 未证明带 PID 的两份 runtime 回执完整提交")  # Popen 后任何回执不完整状态永久阻断自动最终化。
    require(isinstance(launch_claim.get("receipts_completed_at_utc"), str) and bool(launch_claim["receipts_completed_at_utc"]), "启动 claim 缺少回执完成 UTC 时间")  # 完整提交状态必须有非空完成时间证据。
    require(manifest.get("execution_mode") == EXPECTED_EXECUTION_MODE and runtime.get("execution_mode") == EXPECTED_EXECUTION_MODE, "manifest/runtime 执行模式不是 SMP1 诊断")  # 阻断 DMP 或多进程结果混入。
    require(manifest.get("restart_command") == "ANTYPE,,RESTART,2,1,PERTURB", "manifest 重启动入口不是冻结 LS2/子步1线性扰动命令")  # 只允许精确使用 `.r002` 对应状态。
    require(manifest.get("perturb_command") == "PERTURB,MODAL,AUTO,CURRENT,PARKEEP", "manifest PERTURB 命令不是冻结当前切线合同")  # 阻断材料切线或 PARKEEP 语义漂移。
    require(manifest.get("element_form_command") == "SOLVE,ELFORM" and manifest.get("mass_matrix_command") == "LUMPM,OFF", "manifest ELFORM 或一致质量命令不符合冻结合同")  # 扰动矩阵形成和质量矩阵选择必须共同闭合。
    require(manifest.get("modal_solver_command") == "MODOPT,LANB,80" and manifest.get("mode_expansion_command") == "MXPAND,80,,,YES", "manifest LANB 或八十阶展开命令不符合冻结合同")  # 算法、阶数和单元结果展开不得漂移。
    require(manifest.get("modal_outres_commands") == ["OUTRES,ALL,NONE", "OUTRES,NSOL,ALL", "OUTRES,VENG,ALL"] and manifest.get("modal_solve_command") == "SOLVE", "manifest 模态 OUTRES 或最终 SOLVE 合同不一致")  # 三条输出命令顺序和唯一最终求解必须冻结。
    require(manifest.get("modes_requested") == EXPECTED_MODES and manifest.get("frequency_bounds_hz") is None, "manifest 未冻结无频带限制的八十阶请求")  # 防止频带截断或阶数不足。
    require(manifest.get("launch_allowed_after_execute_preflight_only") is True and manifest.get("mapdl_execution_attempted") is False and manifest.get("mapdl_started") is False, "manifest 未保持 prepare 阶段未执行且只允许预检后启动的历史事实")  # execute 不得回写或伪造 prepare 合同。
    require(launch_claim.get("production") is False and launch_claim.get("valid_for_production") is False and all(container.get("production") is False and container.get("valid_for_production") is False for container in (manifest, prepare_status, runtime, runtime_status)), "准备、声明或运行证据存在生产用途真值")  # 用途边界必须全链保持假。
    resources = runtime.get("resource_preflight")  # 提取 execute 启动瞬间资源证据。
    require(isinstance(resources, dict), "runtime_launch 缺少 resource_preflight 对象")  # 资源门不得由口头说明替代。
    resource_contract = manifest.get("resource_gates")  # 读取 prepare 冻结的启动资源硬门合同。
    require(isinstance(resource_contract, dict) and resource_contract.get("available_ram_min_bytes") == 8 * 1024**3 and resource_contract.get("solver_volume_free_disk_min_bytes") == 40 * 1024**3 and resource_contract.get("exceptions_allowed") is False, "manifest 资源硬门不是无例外的 8 GiB RAM/40 GiB 磁盘合同")  # 资源门值和无例外布尔值必须精确。
    require(resources.get("available_ram_gate_passed") is True and isinstance(resources.get("available_ram_bytes"), int) and resources["available_ram_bytes"] >= 8 * 1024**3, "启动瞬间 8 GiB RAM 硬门未闭合")  # 可用 RAM 必须实测通过。
    require(resources.get("available_ram_min_bytes") == 8 * 1024**3, "runtime 记录的 RAM 门槛不是精确 8 GiB")  # 实测值必须绑定同一冻结门槛。
    require(resources.get("free_disk_gate_passed") is True and isinstance(resources.get("free_disk_bytes"), int) and resources["free_disk_bytes"] >= 40 * 1024**3, "启动瞬间 40 GiB 磁盘硬门未闭合")  # 磁盘空间必须实测通过。
    require(resources.get("free_disk_min_bytes") == 40 * 1024**3, "runtime 记录的磁盘门槛不是精确 40 GiB")  # 实测值必须绑定同一冻结门槛。
    require(resources.get("conflicting_solver_process_count") == 0, "启动瞬间存在冲突求解器进程")  # 首轮必须独占执行环境。
    require(launch_claim.get("available_ram_bytes") == resources.get("available_ram_bytes") and launch_claim.get("free_disk_bytes") == resources.get("free_disk_bytes"), "启动声明与 runtime 回执的 RAM/磁盘实测值不一致")  # claim 与 Popen 后回执必须引用同一次预检快照。
    solver_dir = (run_dir / "solver").resolve()  # 规范化隔离求解目录。
    require(solver_dir.is_dir() and solver_dir.parent == run_dir, "solver 目录缺失或不属于本 run")  # 所有结果必须来自本隔离目录。
    require(runtime.get("cwd") == str(solver_dir) and runtime.get("finalizer_required") is True, "runtime 未证明在本 solver 工作且必须外部 finalizer")  # 启动目录和未最终化语义必须闭合。
    require(isinstance(runtime.get("execute_script_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", runtime["execute_script_sha256"]) is not None, "runtime.execute_script_sha256 格式无效")  # Popen 工具身份必须是完整小写 SHA-256。
    jobname = manifest.get("jobname")  # 读取静力与模态共用作业名。
    require(isinstance(jobname, str) and jobname and launch_claim.get("jobname") == jobname and runtime.get("jobname") == jobname and runtime_status.get("jobname") == jobname, "jobname 在 manifest/claim/runtime 间不一致")  # 文件族身份必须闭合。
    require(jobname.strip() == jobname and re.fullmatch(r"[A-Za-z0-9_]+", jobname) is not None and len(jobname) + len(".full") <= 32 and len(jobname) + len(".mode") <= 32, "jobname 不满足 APDL 安全字符或三十二字符文件字段合同")  # 再次阻断路径字符、命令注入和 APDL Math 文件名截断。
    launch_argv = manifest.get("launch_argv")  # 读取 prepare 冻结参数。
    require(runtime.get("launch_argv") == launch_argv, "实际 runtime launch_argv 与 prepare manifest 不一致")  # 实际启动必须逐项采用冻结命令。
    require(isinstance(launch_argv, list) and launch_argv.count("-smp") == 1 and launch_argv.count("-np") == 1 and launch_argv[launch_argv.index("-np") + 1] == "1" and "-dis" not in launch_argv and "-mpi" not in launch_argv, "实际启动参数不是唯一 SMP1 且含禁用并行标志")  # 固定首轮算法环境。
    main_input = (run_dir / str(manifest.get("main_input"))).resolve()  # 解析实际主输入路径。
    require(main_input.parent == solver_dir and main_input.is_file(), "实际模态主输入不在本 solver 或缺失")  # -i 文件必须仍存在。
    require(sha256_file(main_input) == manifest.get("main_input_sha256") == runtime.get("main_input_sha256"), "模态主输入 SHA-256 在 prepare/runtime/finalize 间不闭合")  # 输入字节不得漂移。
    executable = Path(str(manifest.get("mapdl_executable"))).resolve()  # 解析实际 MAPDL 二进制路径。
    require(executable.is_file(), f"MAPDL 可执行文件不存在：{executable}")  # 版本证据仍需可读。
    require(sha256_file(executable) == manifest.get("mapdl_executable_sha256") == runtime.get("mapdl_executable_sha256"), "MAPDL 二进制 SHA-256 在 prepare/runtime/finalize 间不闭合")  # 禁止版本漂移。
    expected_launch_argv = [str(executable), "-b", "-smp", "-np", "1", "-j", jobname, "-dir", str(solver_dir), "-i", str(main_input), "-o", str(solver_dir / f"{jobname}.out")]  # 按已验真路径和同 jobname 重建唯一批准 SMP1 参数数组。
    require(launch_argv == expected_launch_argv, f"prepare/runtime 启动参数未精确匹配批准数组：{launch_argv}")  # 防止额外参数、错误目录、错误输入或输出路径绕过简单标志计数。
    main_pid = runtime.get("main_pid")  # 读取 Popen 记录的包装 PID。
    require(isinstance(main_pid, int) and main_pid > 0, "runtime_launch.main_pid 不是正整数")  # PID 必须结构有效。
    require(launch_claim.get("main_pid") == main_pid and runtime_status.get("main_pid") == main_pid, "claim/runtime/runtime_status 的 Popen PID 不一致")  # 三份启动证据必须绑定同一实际进程。
    require(not psutil.pid_exists(main_pid), f"启动包装 PID {main_pid} 仍存在，拒绝在求解中最终化")  # 包装进程必须退出。
    matching_processes = active_matching_solver_processes(jobname, solver_dir)  # 枚举可能仍运行的真实 ANSYS 子进程。
    require(not matching_processes, f"仍有本 job 求解器进程活动：{json.dumps(matching_processes, ensure_ascii=False)}")  # 真实子进程同样必须退出。
    require(not any(solver_dir.glob("*.lock")), "solver 目录仍存在 MAPDL lock 文件")  # 数据库必须已经关闭。
    qa_contract = manifest.get("numerical_qa_contract")  # 读取 prepare 冻结的数值阈值合同。
    require(isinstance(qa_contract, dict), "manifest 缺少 numerical_qa_contract")  # 阈值不得由 finalizer 单方面新增。
    require(qa_contract.get("residual_definition") == "NORM2_KPHI_MINUS_LAMBDA_MPHI_OVER_MAX_NORM2_KPHI_AND_ABS_LAMBDA_NORM2_MPHI", "manifest 残差定义文本与冻结公式不一致")  # 防止阈值相同但分母或范数定义被替换。
    require(qa_contract.get("orthogonality_definition") == "PHI_TRANSPOSE_M_PHI_VERSUS_IDENTITY", "manifest 质量正交定义文本与冻结公式不一致")  # Gram 矩阵必须以 ΦᵀMΦ 对单位阵核验。
    require(qa_contract.get("maximum_normalized_residual") == MAX_NORMALIZED_RESIDUAL, "manifest 残差阈值与 finalizer 冻结值不一致")  # 防止阈值被放宽或脚本版本错配。
    require(qa_contract.get("maximum_diagonal_deviation") == MAX_ORTHOGONALITY_ERROR and qa_contract.get("maximum_off_diagonal_absolute") == MAX_ORTHOGONALITY_ERROR, "manifest 正交阈值与 finalizer 冻结值不一致")  # 正交两门必须同样闭合。
    require(qa_contract.get("rigid_body_frequency_limit_hz") == RIGID_BODY_FREQUENCY_LIMIT_HZ, "manifest 刚体频率阈值与 finalizer 冻结值不一致")  # 刚体排除门不得漂移。
    static_run_path = Path(str(manifest.get("static_run_path"))).resolve()  # 解析 prepare 冻结的唯一静力来源目录。
    require(static_run_path.is_dir() and static_run_path.parent == RUNS_ROOT.resolve() and static_run_path.name == manifest.get("static_run_name"), "manifest 静力来源目录身份无效")  # 静力来源必须仍是同项目 ultra_runs 直属且目录名闭合。
    lineage_hashes = manifest.get("static_lineage_sha256")  # 读取 prepare 原样复制的静力 manifest、三份终态证据和最终账本摘要。
    require(isinstance(lineage_hashes, dict) and len(lineage_hashes) == 5, "manifest.static_lineage_sha256 不是冻结的五份谱系摘要")  # 谱系快照数量必须精确。
    expected_lineage_names = {"static_manifest.json", "static_final_status.json", "static_solution_verification.json", "static_raw_result_manifest.json", "static_artifact_hashes.final.sha256"}  # 冻结五份静力谱系快照的精确文件名集合。
    require(set(lineage_hashes) == expected_lineage_names, f"manifest.static_lineage_sha256 文件名集合不符合冻结合同：{sorted(lineage_hashes)}")  # 同数量替换文件名同样拒绝。
    for lineage_name, expected_hash in lineage_hashes.items():  # 逐份复核隔离 run 内静力终态快照仍保持原字节。
        lineage_path = run_dir / "lineage" / str(lineage_name)  # 构造 prepare 使用的谱系快照路径。
        require(lineage_path.is_file() and sha256_file(lineage_path) == expected_hash, f"静力谱系快照缺失或 SHA-256 漂移：{lineage_name}")  # 任一快照变化均拒绝最终化。
    original_lineage_paths = {  # 把五份隔离快照映射回唯一静力来源 run 的规范原件路径。
        "static_manifest.json": static_run_path / "manifest.json",  # 静力准备 manifest 原件。
        "static_final_status.json": static_run_path / "C10_static_final_status.json",  # 静力根最终状态原件。
        "static_solution_verification.json": static_run_path / "qa" / "static_solution_verification.json",  # 静力数值验证原件。
        "static_raw_result_manifest.json": static_run_path / "qa" / "static_raw_result_manifest.json",  # 静力原始结果清单原件。
        "static_artifact_hashes.final.sha256": static_run_path / "artifact_hashes.final.sha256",  # 静力最终发布账本原件。
    }  # 完成五份原始谱系路径映射。
    for lineage_name, original_path in original_lineage_paths.items():  # 逐项确认静力来源在模态运行期间未被撤销、替换或改写。
        require(original_path.is_file() and sha256_file(original_path) == lineage_hashes[lineage_name], f"静力来源谱系原件缺失或相对 prepare 快照漂移：{original_path}")  # 原件、隔离快照和 modal manifest 摘要必须三方同值。
    static_manifest_snapshot = read_json(run_dir / "lineage" / "static_manifest.json")  # 读取已验真静力准备身份快照供语义交叉核对。
    static_status_snapshot = read_json(run_dir / "lineage" / "static_final_status.json")  # 读取已验真静力根终态快照。
    static_verification_snapshot = read_json(run_dir / "lineage" / "static_solution_verification.json")  # 读取已验真静力数值验证快照。
    require(static_manifest_snapshot.get("run_name") == manifest.get("static_run_name") and static_status_snapshot.get("run_name") == manifest.get("static_run_name") and static_verification_snapshot.get("run_name") == manifest.get("static_run_name"), "五份静力谱系中的 run_name 未绑定 modal manifest 来源")  # 防止同摘要映射被跨 run 拼装。
    require(static_manifest_snapshot.get("jobname") == jobname, "静力 manifest 快照 jobname 与模态 jobname 不一致")  # 重启动文件族身份必须来自同一静力作业。
    static_load_path_mode = manifest.get("static_load_path_mode")  # 读取 modal manifest 冻结的静力载荷路径身份。
    require(isinstance(static_load_path_mode, str) and static_load_path_mode and static_manifest_snapshot.get("load_path_mode") == static_load_path_mode and static_status_snapshot.get("load_path_mode") == static_load_path_mode and static_verification_snapshot.get("load_path_mode") == static_load_path_mode, "静力载荷路径身份在 modal manifest 与三份静力快照间不一致")  # 防止不同初始状态或恒载路径结果被混接。
    require(static_status_snapshot.get("status") == "STATIC_DIAGNOSTIC_COMPLETED_WITH_REVIEWED_WARNINGS" and static_status_snapshot.get("static_numeric_gates") == "PASSED" and static_status_snapshot.get("restart_status") == "PRESERVED_AND_HASHED_NOT_YET_RESUME_TESTED" and static_status_snapshot.get("modal_status") == "NOT_RUN", "静力根终态快照语义不符合批准入口")  # 最终化再次确认 prepare 所依赖的条件性静力入口。
    require(static_verification_snapshot.get("status") == "STATIC_NUMERIC_GATES_PASSED_WITH_REVIEWED_WARNINGS_DIAGNOSTIC_ONLY" and static_verification_snapshot.get("full_bridge_modal_status") == "NOT_RUN", "静力验证快照语义不符合批准入口")  # 数值 QA 必须仍是未运行模态的诊断状态。
    require(static_status_snapshot.get("valid_for_production") is False and static_verification_snapshot.get("valid_for_production") is False, "静力谱系快照存在生产用途真值")  # 子链不得提升来源用途。
    static_topology = static_verification_snapshot.get("runtime_topology")  # 读取静力求解时实测的节点和单元类型计数。
    static_topology_checks = static_verification_snapshot.get("topology_checks")  # 读取静力 finalizer 对冻结拓扑的独立闭合结论。
    require(isinstance(static_topology, dict) and static_topology.get("nodes") == EXPECTED_TOPOLOGY_NODE_COUNT and static_topology.get("TYPE70") == EXPECTED_DIRECTION_NODE_COUNT, "静力运行时节点总数或 TYPE70 方向节点数与向量覆盖合同不一致")  # 向量节点行基数必须由已验真静力拓扑支撑。
    require(isinstance(static_topology_checks, dict) and static_topology_checks.get("exact_counts") is True and static_topology_checks.get("type_sum_equals_elements") is True, "静力运行时拓扑检查未全部通过")  # 不允许在拓扑漂移模型上解释固定向量节点集合。
    restart_records = manifest.get("restart_artifacts")  # 读取四项静力来源和隔离复制件身份记录。
    require(isinstance(restart_records, list) and len(restart_records) == 4, "manifest.restart_artifacts 不是四项")  # 后续逐项核对需要精确四项。
    required_restart_suffixes = [".rdb", ".ldhi", ".r002", ".rst"]  # 冻结四项同 jobname 重启动文件族的有序后缀合同。
    require([record.get("suffix") if isinstance(record, dict) else None for record in restart_records] == required_restart_suffixes, "manifest.restart_artifacts 后缀或顺序不符合四项冻结合同")  # 缺项、重复、换序或替代后缀均拒绝。
    mutable_restart_labels = {str(record.get("copied_path")) for record in restart_records if isinstance(record, dict)}  # 收集可能被 MAPDL 合法改写的四个工作复制件标签。
    require(len(mutable_restart_labels) == 4, "四项工作重启动标签不是唯一四项")  # 只有这四个准备文件允许执行后字节变化。
    for relative_label, expected_hash in prepare_ledger_records.items():  # 逐项复算除四个工作种子外全部不可变准备文件。
        target_path = (run_dir / Path(relative_label)).resolve()  # 解析当前准备文件规范路径。
        if relative_label not in mutable_restart_labels:  # 主输入、manifest、状态、谱系和说明等不可变准备文件进入摘要复算。
            require(sha256_file(target_path) == expected_hash, f"不可变准备态工件 SHA-256 漂移：{relative_label}")  # 除四个工作种子外任何字节变化均拒绝。
    require(str(manifest.get("main_input")) in prepare_ledger_records and MANIFEST_NAME in prepare_ledger_records and PREPARE_STATUS_NAME in prepare_ledger_records, "准备态账本未覆盖主输入、manifest 或根准备状态")  # 三项核心控制文件必须受账本保护。
    static_source_rechecks: list[dict[str, Any]] = []  # 初始化最终化时对静力原始文件的再次哈希记录。
    working_restart_records: list[dict[str, Any]] = []  # 初始化模态结束后工作复制件当前身份记录，不假设求解器未改写。
    for restart_record in restart_records:  # 逐项验证静力原件保持不变并记录工作复制件当前状态。
        require(isinstance(restart_record, dict), "restart_artifacts 含非对象记录")  # 每项必须含 source/copied/size/sha256。
        suffix = str(restart_record.get("suffix"))  # 读取已经通过有序清单门的当前标准后缀。
        source_path = Path(str(restart_record.get("source_path"))).resolve()  # 解析静力 finalizer 已封存的原件绝对路径。
        expected_size = restart_record.get("size_bytes")  # 读取 prepare 冻结的原件字节数。
        expected_hash = restart_record.get("sha256")  # 读取 prepare 冻结的原件 SHA-256。
        require(source_path.parent == (static_run_path / "solver").resolve() and source_path.name.lower() == f"{jobname}{suffix}".lower(), f"静力重启动原件路径或同 jobname 文件名不闭合：{source_path}")  # 原件必须来自唯一静力 solver 且使用精确文件族名称。
        require(isinstance(expected_size, int) and expected_size > 0 and isinstance(expected_hash, str) and re.fullmatch(r"[0-9a-f]{64}", expected_hash) is not None, f"重启动记录大小或 SHA-256 格式无效：{suffix}")  # 哈希和大小合同必须结构有效。
        require(source_path.is_file() and source_path.stat().st_size == expected_size and source_path.stat().st_size > 0, f"静力重启动原件缺失、为空或大小漂移：{source_path}")  # 原始基态必须仍可审计。
        current_source_hash = sha256_file(source_path)  # 对静力原件重新计算完整摘要，证明隔离续算未写回来源 run。
        require(current_source_hash == expected_hash, f"静力重启动原件在模态期间发生 SHA-256 漂移：{source_path.name}")  # 来源 run 任一字节变化均拒绝。
        static_source_rechecks.append({"path": str(source_path), "size_bytes": expected_size, "sha256": current_source_hash})  # 保存静力原件不变证据。
        working_path = (run_dir / str(restart_record.get("copied_path"))).resolve()  # 解析本 solver 内可能被 MAPDL 合法改写的工作复制件。
        require(working_path.name.lower() == f"{jobname}{suffix}".lower(), f"模态工作重启动文件名未保持同 jobname：{working_path.name}")  # 隔离复制件必须保持静力作业文件族名称。
        require(working_path.parent == solver_dir and working_path.is_file() and working_path.stat().st_size > 0, f"模态工作重启动文件缺失或为空：{working_path}")  # 工作文件必须仍在隔离目录且非空。
        working_restart_records.append({"path": str(working_path), "size_bytes": working_path.stat().st_size, "sha256": sha256_file(working_path), "prepare_seed_sha256": expected_hash, "may_be_solver_modified": True})  # 记录当前字节并明确不把求解器合法改写误判为来源污染。
    return {"manifest": manifest, "prepare_status": prepare_status, "launch_claim": launch_claim, "runtime": runtime, "runtime_status": runtime_status, "solver_dir": solver_dir, "jobname": jobname, "main_input": main_input, "executable": executable, "prepare_ledger_entry_count": len(prepare_ledger_records), "prepare_ledger_sha256": sha256_file(prepare_ledger_path), "static_source_rechecks": static_source_rechecks, "working_restart_records": working_restart_records}  # 返回结果验证所需闭合证据。


def validate_main_output(evidence: dict[str, Any]) -> dict[str, Any]:  # evidence 来自 lineage/runtime 验证，返回 MAPDL 完成和错误摘要。
    """要求原生完成、八十特征值、NOSAVE 退出、零 ERROR/FATAL 和两个阶段状态文件。"""  # warning 被计数披露但不自动升级生产用途。
    solver_dir = evidence["solver_dir"]  # 提取隔离 solver 目录。
    jobname = evidence["jobname"]  # 提取同 jobname 文件族身份。
    output_path = solver_dir / f"{jobname}.out"  # 定位 execute 冻结的唯一主 OUT。
    output_text = read_mixed_text(output_path)  # 读取完整主 OUT 并保留 ASCII 标志。
    output_lower = output_text.lower()  # 统一小写供不区分大小写完成标志检查。
    output_upper = output_text.upper()  # 统一大写供 ERROR/FATAL 和异常关键词检查。
    require(output_lower.count("run completed") == 1, "主 OUT 的 RUN COMPLETED 原生标志不是唯一一处")  # 求解和后处理必须正常走到唯一会话页尾。
    require(output_lower.count("80 eigenvalues converged") == 1, "主 OUT 的 80 EIGENVALUES CONVERGED 标志不是唯一一处")  # Block Lanczos 必须在唯一会话中收敛全部八十阶。
    require(output_lower.count("exit mapdl without saving database") == 1, "主 OUT 的正常 NOSAVE 退出标志不是唯一一处")  # APDL 尾段必须只走到一次正常退出。
    error_blocks = output_upper.count("*** ERROR ***")  # 统计明确 MAPDL ERROR 消息块。
    fatal_blocks = output_upper.count("*** FATAL ***")  # 统计明确 MAPDL FATAL 消息块。
    require(error_blocks == 0 and fatal_blocks == 0, f"主 OUT 含 ERROR/FATAL：{error_blocks}/{fatal_blocks}")  # 任一错误或致命块均拒绝。
    require("ZERO PIVOT" not in output_upper and "NEGATIVE PIVOT" not in output_upper and "SMALL EQUATION SOLVER PIVOT" not in output_upper, "主 OUT 含 zero/negative/small pivot 异常")  # 秩或刚度异常不能被频率结果掩盖。
    error_path = solver_dir / f"{jobname}.err"  # 定位同 jobname 独立 MAPDL ERR 文件。
    require(error_path.is_file(), f"缺少独立 MAPDL ERR 文件：{error_path}")  # 即使零字节也必须存在以证明文件族完整。
    error_bytes = error_path.read_bytes()  # 读取 ERR 原始字节供文本检查和摘要共用。
    error_text = error_bytes.decode("utf-8", errors="replace")  # 以替代策略保留所有 ASCII ERROR/FATAL 标志。
    error_upper = error_text.upper()  # 统一大写供独立错误块计数。
    err_error_blocks = error_upper.count("*** ERROR ***")  # 统计 ERR 中明确 ERROR 消息块。
    err_fatal_blocks = error_upper.count("*** FATAL ***")  # 统计 ERR 中明确 FATAL 消息块。
    require(err_error_blocks == 0 and err_fatal_blocks == 0, f"独立 ERR 含 ERROR/FATAL：{err_error_blocks}/{err_fatal_blocks}")  # 任一独立错误块均拒绝。
    err_warning_classifications = classify_warning_blocks(error_text)  # ERR 中若重复或独立记录 warning，同样只允许显式白名单类别。
    gate_path = solver_dir / "c10_gate_status.txt"  # 定位既有 C10 尾段唯一阶段状态文件。
    gate_text = parse_unique_status_record(gate_path, EXPECTED_SOLVER_GATE_STATUS)  # 要求唯一完整状态精确为求解与导出完成，拒绝追加历史记录。
    numerical_status_path = solver_dir / "c10_modal_numerical_qa_status.txt"  # 定位新增 APDL Math 证据生成状态。
    numerical_status_text = parse_unique_status_record(numerical_status_path, EXPECTED_NUMERICAL_QA_STATUS)  # 要求唯一完整状态精确声明数值证据已生成且外部门待核。
    error_counts = [int(value) for value in ERROR_COUNT_PATTERN.findall(output_text)]  # 提取全部原生页尾错误累计值。
    require(error_counts == [0], f"主 OUT 必须且只能含一个零错误页尾汇总，实际为：{error_counts}")  # 防止缺失汇总、多个会话拼接或非零错误被块计数遗漏。
    warning_counts = [int(value) for value in WARNING_COUNT_PATTERN.findall(output_text)]  # 提取全部原生页尾警告累计值供机器披露。
    require(len(warning_counts) == 1, f"主 OUT 必须且只能含一个 warning 页尾汇总，实际为：{warning_counts}")  # 多会话拼接或缺失页尾均拒绝。
    warning_classifications = classify_warning_blocks(output_text)  # 对每个原生 warning 实施显式白名单分类，未知警告立即拒绝。
    warning_blocks = len(warning_classifications)  # 使用实际完成分类的块数作为权威 warning 总数。
    require(warning_counts[0] <= warning_blocks, f"主 OUT 页尾 warning 汇总 {warning_counts[0]} 大于实际原生 warning 块数 {warning_blocks}")  # 性能 warning 可能由 MAPDL 在汇总后追加，但汇总绝不能超过实际标题数。
    output_sha256 = sha256_file(output_path)  # 冻结主 OUT 完整字节身份。
    return {"path": str(output_path), "sha256": output_sha256, "size_bytes": output_path.stat().st_size, "err_path": str(error_path), "err_sha256": hashlib.sha256(error_bytes).hexdigest(), "err_size_bytes": len(error_bytes), "run_completed": True, "eigenvalues_converged": EXPECTED_MODES, "normal_nosave_exit": True, "error_blocks": error_blocks, "fatal_blocks": fatal_blocks, "err_error_blocks": err_error_blocks, "err_fatal_blocks": err_fatal_blocks, "err_warning_blocks": len(err_warning_classifications), "err_warning_classifications": err_warning_classifications, "error_summary": error_counts, "warning_summary": warning_counts, "warning_blocks": warning_blocks, "warning_classifications": warning_classifications, "solver_gate": gate_text, "numerical_qa_status": numerical_status_text}  # 返回 OUT/ERR 原生完成、唯一页尾汇总和白名单 warning 摘要。


def validate_modal_properties(solver_dir: Path) -> dict[str, Any]:  # solver_dir 是隔离结果目录，返回八十阶属性、结果集和刚体门摘要。
    """核对属性 80×15、频率有限正值、结果集闭合和 EFFM=PFACT²。"""  # 允许物理近重根但不允许频率下降。
    property_path = solver_dir / "c10_modal_properties.csv"  # 定位既有 C10 八十阶属性表。
    rows = parse_numeric_csv(property_path, MODAL_PROPERTY_COLUMNS)  # 解析纯数值十五列属性。
    require(len(rows) == EXPECTED_MODES, f"模态属性行数 {len(rows)} != {EXPECTED_MODES}")  # 必须恰好八十阶。
    require(all(abs(row[0] - index) <= 1.0e-9 for index, row in enumerate(rows, start=1)), "模态属性阶次不是连续 1..80")  # 阶次列必须一基连续。
    frequencies = [row[1] for row in rows]  # 提取八十阶频率，单位 Hz。
    require(all(value > 0.0 and math.isfinite(value) for value in frequencies), "模态频率含非正值或非有限值")  # 先关闭基本频率门。
    require(all(right + 1.0e-12 >= left for left, right in zip(frequencies, frequencies[1:])), "模态频率序列发生下降")  # 允许完全或数值近重根，不允许排序逆转。
    rigid_modes = [index for index, value in enumerate(frequencies, start=1) if value <= RIGID_BODY_FREQUENCY_LIMIT_HZ]  # 识别小于等于一微赫兹的数值刚体阶。
    require(not rigid_modes, f"检测到数值刚体模态：{rigid_modes}")  # 任一刚体阶均拒绝。
    generalized_masses = [row[2] for row in rows]  # 提取官方广义质量列。
    require(all(value > 0.0 and math.isfinite(value) for value in generalized_masses), "模态广义质量含非正值或非有限值")  # 质量归一化模态必须具有正广义质量。
    maximum_effm_identity_error = 0.0  # 初始化六方向 EFFM=PFACT² 最大尺度化误差。
    for row in rows:  # 逐阶核对六个平动/转动方向的参与因子和有效质量。
        for offset in range(6):  # 六方向对应 PX/PY/PZ/PRX/PRY/PRZ。
            expected_effm = row[3 + offset] ** 2  # 由官方参与因子平方复算有效质量。
            actual_effm = row[9 + offset]  # 读取对应官方有效质量。
            require(actual_effm >= 0.0, "模态有效质量出现负值")  # 有效质量不得为负。
            identity_error = abs(actual_effm - expected_effm) / max(1.0, abs(actual_effm), abs(expected_effm))  # 计算尺度稳定恒等式误差。
            maximum_effm_identity_error = max(maximum_effm_identity_error, identity_error)  # 更新全表最大误差。
    require(maximum_effm_identity_error <= IDENTITY_RELATIVE_TOLERANCE, f"EFFM=PFACT² 最大误差 {maximum_effm_identity_error} 超过阈值")  # 属性内部公式必须闭合。
    export_manifest_path = solver_dir / "c10_modal_export_manifest.txt"  # 定位 requested/available/exported 计数文件。
    export_text = read_mixed_text(export_manifest_path)  # 读取既有 C10 导出计数。
    export_values = [int(round(float(value))) for value in re.findall(r"(?:REQUESTED|AVAILABLE|EXPORTED)=\s*([0-9.]+)", export_text.upper())]  # 按固定标签提取三个整数。
    require(export_values == [EXPECTED_MODES, EXPECTED_MODES, EXPECTED_MODES], f"requested/available/exported 未全为 80：{export_values}")  # 三项必须共同闭合。
    set_list_path = solver_dir / "c10_modal_set_list.txt"  # 定位 RSTP 原生 SET LIST。
    set_rows = SET_LIST_PATTERN.findall(read_mixed_text(set_list_path))  # 解析八十条模态结果集记录。
    require(len(set_rows) == EXPECTED_MODES, f"RSTP SET LIST 记录数 {len(set_rows)} != {EXPECTED_MODES}")  # 结果集必须恰好八十。
    set_frequencies: list[float] = []  # 初始化 RSTP 频率列表。
    for expected_index, raw in enumerate(set_rows, start=1):  # 逐行核对 SET、子步和累计序号。
        set_number, frequency_text, substep, cumulative = raw  # 解包四个捕获字段。
        require(int(set_number) == expected_index and int(substep) == expected_index and int(cumulative) == expected_index, f"RSTP SET LIST 第 {expected_index} 阶编号不闭合")  # 三个一基编号必须一致连续。
        set_frequency = float(frequency_text.replace("D", "E").replace("d", "e"))  # 规范 Fortran D 指数后转换当前 RSTP 频率文本。
        require(math.isfinite(set_frequency) and set_frequency > 0.0, f"RSTP 第 {expected_index} 阶频率非正或非有限")  # 结果集频率必须有效。
        set_frequencies.append(set_frequency)  # 保存供属性表交叉比较。
    maximum_set_frequency_error = max(abs(left - right) for left, right in zip(frequencies, set_frequencies))  # 计算两份频率最大绝对差。
    require(maximum_set_frequency_error <= FREQUENCY_MATCH_TOLERANCE_HZ, f"属性与 RSTP 频率最大差 {maximum_set_frequency_error} Hz 超过阈值")  # 文本与结果集必须闭合。
    return {"rows": rows, "frequencies": frequencies, "property_rows": len(rows), "property_columns": MODAL_PROPERTY_COLUMNS, "frequency_first_hz": frequencies[0], "frequency_last_hz": frequencies[-1], "frequency_non_decreasing": True, "rigid_body_frequency_limit_hz": RIGID_BODY_FREQUENCY_LIMIT_HZ, "rigid_body_mode_count": 0, "generalized_mass_minimum": min(generalized_masses), "maximum_effm_equals_pfact_squared_error": maximum_effm_identity_error, "requested": EXPECTED_MODES, "available": EXPECTED_MODES, "exported": EXPECTED_MODES, "set_count": len(set_rows), "maximum_property_vs_set_frequency_error_hz": maximum_set_frequency_error, "properties_path": str(property_path), "properties_sha256": sha256_file(property_path), "set_list_path": str(set_list_path), "set_list_sha256": sha256_file(set_list_path)}  # 返回属性与刚体门完整摘要。


def validate_residuals(solver_dir: Path, frequencies: list[float]) -> dict[str, Any]:  # solver_dir 是结果目录，frequencies 是已验真属性频率；返回逐阶残差门摘要。
    """核对八十行七列、λ=(2πf)²、尺度公式和最大无量纲残差。"""  # 不接受只由求解器“converged”文字替代残差证据。
    residual_path = solver_dir / "c10_modal_eigen_residuals.csv"  # 定位新增 APDL Math 逐阶残差表。
    rows = parse_numeric_csv(residual_path, RESIDUAL_COLUMNS)  # 解析七列有限数值记录。
    require(len(rows) == EXPECTED_MODES, f"模态残差行数 {len(rows)} != {EXPECTED_MODES}")  # 每阶必须恰好一行。
    maximum_frequency_error = 0.0  # 初始化残差表与属性表频率最大差。
    maximum_lambda_error = 0.0  # 初始化 λ 公式最大尺度化误差。
    maximum_identity_error = 0.0  # 初始化尺度化残差列内部复算最大误差。
    normalized_values: list[float] = []  # 初始化八十阶无量纲残差列表。
    for expected_index, row in enumerate(rows, start=1):  # 逐阶核对七列物理和数值恒等式。
        require(abs(row[0] - expected_index) <= 1.0e-9, f"残差表第 {expected_index} 行阶次不匹配")  # 阶次必须连续 1..80。
        frequency = row[1]  # 读取当前残差表频率，单位 Hz。
        expected_frequency = frequencies[expected_index - 1]  # 读取属性表同阶频率。
        frequency_error = abs(frequency - expected_frequency)  # 计算两表绝对频率差。
        maximum_frequency_error = max(maximum_frequency_error, frequency_error)  # 更新全表最大频差。
        expected_lambda = (2.0 * math.pi * expected_frequency) ** 2  # 由属性频率独立复算 λ，单位 s^-2。
        actual_lambda = row[2]  # 读取 APDL 写出的 λ。
        lambda_error = abs(actual_lambda - expected_lambda) / max(1.0, abs(actual_lambda), abs(expected_lambda))  # 计算尺度稳定 λ 差异。
        maximum_lambda_error = max(maximum_lambda_error, lambda_error)  # 更新最大 λ 误差。
        absolute_residual = row[3]  # 读取 ||Kφ-λMφ||₂。
        stiffness_scale = row[4]  # 读取 ||Kφ||₂。
        mass_scale = row[5]  # 读取 |λ|·||Mφ||₂。
        normalized_residual = row[6]  # 读取 APDL 写出的无量纲残差 η。
        require(absolute_residual >= 0.0 and stiffness_scale >= 0.0 and mass_scale >= 0.0 and normalized_residual >= 0.0, f"残差表第 {expected_index} 阶含负范数")  # 范数及比例不得为负。
        expected_normalized = absolute_residual / max(stiffness_scale, mass_scale, 1.0e-30)  # 独立复算 APDL 分母选择和 η。
        identity_error = abs(normalized_residual - expected_normalized) / max(1.0, abs(normalized_residual), abs(expected_normalized))  # 计算残差列内部尺度化误差。
        maximum_identity_error = max(maximum_identity_error, identity_error)  # 更新全表最大内部误差。
        normalized_values.append(normalized_residual)  # 保存当前阶 η 供最大值和控制阶定位。
    require(maximum_frequency_error <= FREQUENCY_MATCH_TOLERANCE_HZ, f"残差与属性频率最大差 {maximum_frequency_error} Hz 超过阈值")  # 三处频率身份必须闭合。
    require(maximum_lambda_error <= LAMBDA_RELATIVE_TOLERANCE, f"残差 λ 公式最大误差 {maximum_lambda_error} 超过阈值")  # λ 必须由同阶频率正确生成。
    require(maximum_identity_error <= IDENTITY_RELATIVE_TOLERANCE, f"残差尺度公式最大内部误差 {maximum_identity_error} 超过阈值")  # CSV 七列必须自洽。
    maximum_residual = max(normalized_values)  # 取得八十阶控制残差值。
    controlling_mode = normalized_values.index(maximum_residual) + 1  # 把零基索引转换为一基控制阶次。
    require(maximum_residual <= MAX_NORMALIZED_RESIDUAL, f"最大尺度化特征残差 {maximum_residual} @ mode {controlling_mode} 超过 {MAX_NORMALIZED_RESIDUAL}")  # 残差硬门。
    return {"row_count": len(rows), "column_count": RESIDUAL_COLUMNS, "maximum_normalized_residual": maximum_residual, "controlling_mode": controlling_mode, "threshold": MAX_NORMALIZED_RESIDUAL, "maximum_frequency_error_hz": maximum_frequency_error, "maximum_lambda_relative_error": maximum_lambda_error, "maximum_internal_identity_error": maximum_identity_error, "path": str(residual_path), "sha256": sha256_file(residual_path)}  # 返回逐阶残差门摘要。


def validate_orthogonality(solver_dir: Path) -> dict[str, Any]:  # solver_dir 是结果目录，返回质量 Gram 矩阵两项误差门摘要。
    """独立计算 80×80 Gram 相对单位阵的最大对角偏差和最大非对角绝对值。"""  # 使用 APDL Math 官方 NOD2SOLV/MASS/MODE 路径生成的矩阵。
    matrix_path = solver_dir / "c10_modal_mass_orthogonality.csv"  # 定位新增 APDL Math 质量 Gram CSV。
    matrix = parse_orthogonality_matrix(matrix_path)  # 严格解析八十行八十列有限矩阵。
    maximum_diagonal_deviation = 0.0  # 初始化 |Gii-1| 最大值。
    maximum_off_diagonal_absolute = 0.0  # 初始化 |Gij|、i≠j 最大值。
    controlling_diagonal_mode = 1  # 初始化对角控制阶次为第一阶。
    controlling_off_diagonal_pair = [1, 2]  # 初始化非对角控制阶对为 1–2。
    for row_index, row in enumerate(matrix):  # 逐行遍历 Gram 矩阵。
        for column_index, value in enumerate(row):  # 逐列区分对角与非对角项。
            if row_index == column_index:  # 当前项位于 Gram 对角线。
                deviation = abs(value - 1.0)  # 质量归一化目标为单位值 1。
                if deviation > maximum_diagonal_deviation:  # 仅在发现更大偏差时更新控制项。
                    maximum_diagonal_deviation = deviation  # 保存新最大对角偏差。
                    controlling_diagonal_mode = row_index + 1  # 保存一基控制阶次。
            else:  # 当前项位于 Gram 非对角区域。
                absolute_value = abs(value)  # 正交目标为零，因此取绝对值。
                if absolute_value > maximum_off_diagonal_absolute:  # 仅在发现更大耦合时更新控制项。
                    maximum_off_diagonal_absolute = absolute_value  # 保存新最大非对角绝对值。
                    controlling_off_diagonal_pair = [row_index + 1, column_index + 1]  # 保存一基控制阶对。
    require(maximum_diagonal_deviation <= MAX_ORTHOGONALITY_ERROR, f"质量 Gram 最大对角偏差 {maximum_diagonal_deviation} @ mode {controlling_diagonal_mode} 超过阈值")  # 对角质量归一门。
    require(maximum_off_diagonal_absolute <= MAX_ORTHOGONALITY_ERROR, f"质量 Gram 最大非对角值 {maximum_off_diagonal_absolute} @ {controlling_off_diagonal_pair} 超过阈值")  # 模态质量正交门。
    return {"rows": ORTHOGONALITY_SIZE, "columns": ORTHOGONALITY_SIZE, "maximum_diagonal_deviation": maximum_diagonal_deviation, "controlling_diagonal_mode": controlling_diagonal_mode, "maximum_off_diagonal_absolute": maximum_off_diagonal_absolute, "controlling_off_diagonal_pair": controlling_off_diagonal_pair, "threshold": MAX_ORTHOGONALITY_ERROR, "path": str(matrix_path), "sha256": sha256_file(matrix_path)}  # 返回正交门完整摘要。


def validate_modal_vector_files(solver_dir: Path, frequencies: list[float]) -> dict[str, Any]:  # solver_dir 定位一百六十份向量，frequencies 是已验真属性频率；返回深度结构摘要。
    """逐文件核对标题、阶次、频率、有限值、九万余节点行及跨阶/跨族节点集合一致性。"""  # 不再用单纯文件大小代替向量内容验证。
    require(EXPECTED_TOPOLOGY_NODE_COUNT - EXPECTED_DIRECTION_NODE_COUNT == EXPECTED_VECTOR_NODE_ROWS, "冻结拓扑节点数与向量节点行合同内部不一致")  # 先验证三个硬编码拓扑常量自洽。
    family_contracts = {  # 定义位移和转角两个文件族的精确文件名、标题及列头合同。
        "displacement": {"filename": "mode_{mode:02d}_all_nodes.txt", "print_pattern": r"(?mi)^\s*PRINT\s+U\s+NODAL SOLUTION PER NODE\s*$", "header_pattern": r"(?mi)^\s*NODE\s+UX\s+UY\s+UZ\s+USUM\s*$"},  # 位移族必须由 PRNSOL,U 形成四列全局结果。
        "rotation": {"filename": "mode_{mode:02d}_rotations.txt", "print_pattern": r"(?mi)^\s*PRINT\s+ROT\s+NODAL SOLUTION PER NODE\s*$", "header_pattern": r"(?mi)^\s*NODE\s+ROTX\s+ROTY\s+ROTZ\s+RSUM\s*$"},  # 转角族必须由 PRNSOL,ROT 形成四列全局结果。
    }  # 完成两个向量家族的静态格式合同。
    baseline_node_ids: set[int] | None = None  # 保存第一份位移文件的权威节点集合供全部一百六十份交叉比较。
    family_summaries: dict[str, dict[str, Any]] = {}  # 初始化两个家族的计数、体量和节点集合摘要。
    global_minimum_bytes: int | None = None  # 初始化全部向量文件最小字节数，首文件后变为正整数。
    global_total_bytes = 0  # 初始化全部一百六十份向量总字节数。
    for family_name, contract in family_contracts.items():  # 先位移后转角逐族验证，保证确定性失败顺序。
        family_total_bytes = 0  # 初始化当前家族八十份文件总字节数。
        family_minimum_bytes: int | None = None  # 初始化当前家族最小文件体量。
        for mode in range(1, EXPECTED_MODES + 1):  # 以一基阶次逐份验证八十阶向量。
            path = solver_dir / str(contract["filename"]).format(mode=mode)  # 按冻结模板构造当前阶精确文件名。
            require(path.is_file() and path.stat().st_size >= MIN_VECTOR_BYTES, f"模态向量文件缺失或小于 {MIN_VECTOR_BYTES} bytes：{path.name}")  # 缺失、空壳或明显截断先行拒绝。
            size_bytes = path.stat().st_size  # 读取当前向量文件字节数供家族和全局摘要。
            text_value = path.read_text(encoding="utf-8", errors="replace")  # 读取当前完整文本以检查标题、阶次、频率和每个节点行。
            require(len(re.findall(str(contract["print_pattern"]), text_value)) == 1, f"{path.name} PRINT 标题不是唯一正确记录")  # 每份文件只能有一个正确求解器打印标题。
            header_count = len(re.findall(str(contract["header_pattern"]), text_value))  # 统计 MAPDL 分页时会在每页重复的正确节点列头。
            require(header_count > 0, f"{path.name} 缺少正确节点列头")  # 至少一页且列名必须与位移或转角家族精确匹配。
            substep_matches = re.findall(r"(?mi)^\s*LOAD STEP=\s*(\d+)\s+SUBSTEP=\s*(\d+)\s*$", text_value)  # 提取 MAPDL 每页重复的载荷步和模态子步标题。
            require(substep_matches and set(substep_matches) == {("1", str(mode))}, f"{path.name} 分页 LOAD STEP/SUBSTEP 含非 1/{mode} 记录")  # 所有重复页眉的结果集载荷步和子步必须与文件名阶次闭合。
            frequency_matches = re.findall(r"(?mi)^\s*FREQ=\s*([+\-0-9.EeDd]+)\s+LOAD CASE=\s*\d+\s*$", text_value)  # 提取 MAPDL 每页重复的模态频率标题。
            require(frequency_matches and len(substep_matches) == header_count == len(frequency_matches), f"{path.name} 分页节点列头、载荷步和频率记录数不一致")  # 每个 MAPDL 分页页眉必须结构完整。
            vector_frequencies = [float(value.replace("D", "E").replace("d", "e")) for value in frequency_matches]  # 规范全部分页 Fortran 指数并转换频率。
            require(all(math.isfinite(value) and value > 0.0 for value in vector_frequencies) and len(set(vector_frequencies)) == 1, f"{path.name} 分页频率含非正、非有限或不一致值")  # 同一文件全部重复页眉必须引用同一有效模态频率。
            vector_frequency = vector_frequencies[0]  # 读取已证明全分页一致的当前向量频率。
            vector_frequency_tolerance = max(1.0e-10, abs(frequencies[mode - 1]) * VECTOR_FREQUENCY_RELATIVE_TOLERANCE)  # 依据 PRNSOL 标题有限有效数字形成同阶舍入容差且保留极低频绝对下限。
            require(abs(vector_frequency - frequencies[mode - 1]) <= vector_frequency_tolerance, f"{path.name} 与属性表频率差超过 PRNSOL 舍入容差 {vector_frequency_tolerance} Hz")  # 向量与属性表必须属于同一阶结果。
            require("MAXIMUM ABSOLUTE VALUES" in text_value.upper(), f"{path.name} 缺少正常 PRNSOL 尾部最大绝对值摘要")  # 完整打印必须走到求解器尾部摘要。
            forbidden_match = re.search(r"(?i)(?:\*\*\* ERROR \*\*\*|\*\*\* FATAL \*\*\*|(?<![A-Z])NAN(?![A-Z])|(?<![A-Z])INFINITY(?![A-Z]))", text_value)  # 搜索错误、致命和非有限字面值。
            require(forbidden_match is None, f"{path.name} 含错误或非有限结果标志：{forbidden_match.group(0) if forbidden_match else ''}")  # 任一命中均拒绝当前向量。
            node_ids = [int(match.group(1)) for match in re.finditer(r"(?m)^\s*(\d+)\s+[+\-0-9.]", text_value)]  # 解析每个真实节点结果行的一基节点号并排除页眉/摘要行。
            require(len(node_ids) == EXPECTED_VECTOR_NODE_ROWS, f"{path.name} 节点结果行数 {len(node_ids)} != {EXPECTED_VECTOR_NODE_ROWS}")  # 每阶必须覆盖冻结选择集全部节点。
            node_id_set = set(node_ids)  # 建立当前文件唯一节点集合供重复和跨文件一致性核对。
            require(len(node_id_set) == EXPECTED_VECTOR_NODE_ROWS and min(node_id_set) > 0, f"{path.name} 含重复或非正节点号")  # 每个正节点号必须只出现一次。
            if baseline_node_ids is None:  # 第一份位移向量建立全链权威节点集合。
                baseline_node_ids = node_id_set  # 保存集合供后续一百五十九份精确比较。
            else:  # 其余所有阶次和转角族必须使用完全相同节点集合。
                require(node_id_set == baseline_node_ids, f"{path.name} 节点集合与第一阶位移向量不一致")  # 缺节点、多节点或替换节点均拒绝。
            family_total_bytes += size_bytes  # 把当前文件体量纳入家族总量。
            family_minimum_bytes = size_bytes if family_minimum_bytes is None else min(family_minimum_bytes, size_bytes)  # 更新当前家族最小文件体量。
            global_total_bytes += size_bytes  # 把当前文件体量纳入全部一百六十份总量。
            global_minimum_bytes = size_bytes if global_minimum_bytes is None else min(global_minimum_bytes, size_bytes)  # 更新全部向量最小文件体量。
        family_summaries[family_name] = {"file_count": EXPECTED_MODES, "node_rows_per_file": EXPECTED_VECTOR_NODE_ROWS, "minimum_bytes": family_minimum_bytes, "total_bytes": family_total_bytes}  # 保存当前家族完整深度验证摘要。
    require(baseline_node_ids is not None and len(baseline_node_ids) == EXPECTED_VECTOR_NODE_ROWS, "向量节点基准集合未成功建立")  # 类型收窄并再次关闭基准集合数量门。
    return {"families": family_summaries, "displacement_vector_count": EXPECTED_MODES, "rotation_vector_count": EXPECTED_MODES, "node_rows_per_file": EXPECTED_VECTOR_NODE_ROWS, "node_set_consistent_across_all_files": True, "minimum_vector_bytes": global_minimum_bytes, "vector_total_bytes": global_total_bytes}  # 返回不携带九万节点数组的紧凑深度验证摘要。


def validate_modal_artifacts(solver_dir: Path, jobname: str, frequencies: list[float]) -> dict[str, Any]:  # solver_dir、jobname 和频率定位结果文件族，返回二进制、向量和能量完整性摘要。
    """核对 RSTP/MODE/FULL/modal DB、160 份全节点向量和 80×16 能量表。"""  # 防止只有频率表的部分导出冒充完整结果。
    binary_records: list[dict[str, Any]] = []  # 初始化关键同 jobname 二进制记录数组。
    for suffix in REQUIRED_BINARY_SUFFIXES:  # 按 RSTP、MODE、FULL 固定后缀逐项核对。
        path = solver_dir / f"{jobname}{suffix}"  # 构造同 jobname 关键二进制路径。
        require(path.is_file() and path.stat().st_size > 0, f"缺少或为空的关键模态二进制：{path.name}")  # 任一缺失即拒绝。
        before = (path.stat().st_size, path.stat().st_mtime_ns)  # 哈希前记录大小和纳秒修改时间。
        digest = sha256_file(path)  # 计算完整二进制摘要。
        after = (path.stat().st_size, path.stat().st_mtime_ns)  # 哈希后再次记录元数据。
        require(before == after, f"关键模态二进制在哈希期间变化：{path.name}")  # 防止后台仍写入时封板。
        binary_records.append({"path": str(path), "size_bytes": before[0], "sha256": digest})  # 保存稳定二进制身份。
    modal_db_path = solver_dir / f"{jobname}_modal.db"  # 定位既有 C10 尾段最终 SAVE 的模态数据库。
    require(modal_db_path.is_file() and modal_db_path.stat().st_size > 0, f"缺少或为空的模态数据库：{modal_db_path.name}")  # 后处理完成必须生成该数据库。
    modal_db_record = {"path": str(modal_db_path), "size_bytes": modal_db_path.stat().st_size, "sha256": sha256_file(modal_db_path)}  # 冻结模态数据库身份。
    vector_summary = validate_modal_vector_files(solver_dir, frequencies)  # 深度核对一百六十份向量的内容、阶次、频率、节点行和跨文件集合。
    sene_path = solver_dir / "c10_section_modal_sene.csv"  # 定位既有 C10 六组件能量表。
    sene_rows = parse_numeric_csv(sene_path, SENE_COLUMNS)  # 解析八十行十六列有限数值。
    require(len(sene_rows) == EXPECTED_MODES, f"模态能量行数 {len(sene_rows)} != {EXPECTED_MODES}")  # 每阶必须有一行。
    require(all(abs(row[0] - index) <= 1.0e-9 for index, row in enumerate(sene_rows, start=1)), "模态能量阶次不是连续 1..80")  # 阶次列必须闭合。
    require(all(row[1] > 0.0 and all(value >= 0.0 for value in row[2:8]) for row in sene_rows), "模态总 SENE 非正或六组件 SENE 出现负值")  # 与 APDL 内部门保持一致并独立复核。
    return {"critical_binaries": binary_records, "modal_database": modal_db_record, "vector_validation": vector_summary, "displacement_vector_count": vector_summary["displacement_vector_count"], "rotation_vector_count": vector_summary["rotation_vector_count"], "minimum_vector_bytes": vector_summary["minimum_vector_bytes"], "vector_total_bytes": vector_summary["vector_total_bytes"], "sene_rows": len(sene_rows), "sene_columns": SENE_COLUMNS, "sene_path": str(sene_path), "sene_sha256": sha256_file(sene_path)}  # 返回关键结果、深度向量和能量完整性摘要。


def collect_evidence(run_dir: Path, authoritative_snapshot: dict[str, dict[str, Any]]) -> dict[str, Any]:  # run_dir 是规范隔离模态 run，authoritative_snapshot 是解析前文件身份；返回全部只读门通过证据。
    """按谱系/进程、原生完成、模态、残差、正交和工件顺序执行 fail-closed 验证。"""  # 任何一步失败均不写最终产物。
    lineage = validate_lineage_and_runtime(run_dir)  # 核对 prepare、execute、资源和进程退出事实。
    main_output = validate_main_output(lineage)  # 核对 MAPDL 原生完成和零错误。
    modal = validate_modal_properties(lineage["solver_dir"])  # 核对八十阶属性、结果集和刚体模态门。
    residuals = validate_residuals(lineage["solver_dir"], modal["frequencies"])  # 核对逐阶特征残差门。
    orthogonality = validate_orthogonality(lineage["solver_dir"])  # 核对质量正交单位阵门。
    artifacts = validate_modal_artifacts(lineage["solver_dir"], lineage["jobname"], modal["frequencies"])  # 核对二进制、向量内容和能量完整性。
    verify_authoritative_snapshot(run_dir, authoritative_snapshot)  # 全部解析完成后逐项复算文件集合、元数据和摘要，关闭解析期间 TOCTOU。
    modal_public = {key: value for key, value in modal.items() if key not in {"rows", "frequencies"}}  # 移除内部大数组，只保留可发布摘要。
    return {"lineage": lineage, "main_output": main_output, "modal": modal_public, "residuals": residuals, "orthogonality": orthogonality, "artifacts": artifacts, "authoritative_snapshot": authoritative_snapshot}  # 返回全部只读门证据及提交账本必须复用的权威摘要集。


def build_final_payloads(run_dir: Path, evidence: dict[str, Any], generated_at: str) -> tuple[bytes, bytes, bytes, bytes]:  # 输入已通过证据和时间，返回 QA、runtime、报告、最终状态四份字节。
    """构造互相一致且永久非生产的最终产物，不在本函数写文件。"""  # 最终状态字节还将被账本提前承诺。
    lineage = evidence["lineage"]  # 提取已闭合 prepare/runtime 证据。
    authoritative_snapshot = evidence["authoritative_snapshot"]  # 提取解析前且解析后已复核的权威文件身份集合。
    authoritative_snapshot_text = "\n".join(f"{authoritative_snapshot[label]['sha256']}  {authoritative_snapshot[label]['size_bytes']}  {authoritative_snapshot[label]['mtime_ns']}  {label}" for label in sorted(authoritative_snapshot)) + "\n"  # 以稳定标签顺序渲染摘要、大小、mtime_ns 和相对路径承诺。
    authoritative_snapshot_sha256 = sha256_bytes(authoritative_snapshot_text.encode("utf-8"))  # 对确定性权威快照文本计算总 SHA-256，供 QA 与最终账本关系审计。
    qa_payload = {  # 构造完整机器 QA 对象。
        "schema_version": 1,  # 本模态 solution verification 首版 schema。
        "run_name": run_dir.name,  # 绑定隔离运行身份。
        "jobname": lineage["jobname"],  # 绑定保持不变的静力作业名。
        "status": QA_STATUS,  # 明确只通过诊断用途 QA。
        "generated_at_utc": generated_at,  # 记录统一最终化时间。
        "execution_mode": EXPECTED_EXECUTION_MODE,  # 记录首轮 SMP1 算法环境。
        "static_source_run": lineage["manifest"]["static_run_name"],  # 记录唯一静力来源。
        "static_load_path_mode": lineage["manifest"]["static_load_path_mode"],  # 记录由三份静力快照再次闭合的载荷路径身份。
        "restart_command": lineage["manifest"]["restart_command"],  # 记录精确 LS2/子步1入口。
        "prepare_ledger_entry_count": lineage["prepare_ledger_entry_count"],  # 记录除四个合法工作种子外全部准备文件持续闭合的条目数。
        "prepare_ledger_sha256": lineage["prepare_ledger_sha256"],  # 记录 execute 与 finalizer 共同核对的准备态账本摘要。
        "execute_script_sha256": lineage["runtime"]["execute_script_sha256"],  # 记录实际执行 Popen 的 execute 源码身份。
        "authoritative_preparse_file_count": len(evidence["authoritative_snapshot"]),  # 记录解析前冻结且解析后再次闭合的普通文件数量。
        "authoritative_preparse_snapshot_sha256": authoritative_snapshot_sha256,  # 记录包含标签、摘要、大小和 mtime_ns 的解析前权威快照总摘要。
        "static_restart_source_integrity": lineage["static_source_rechecks"],  # 证明隔离模态期间未写回静力来源 `.rdb/.ldhi/.r002/.rst`。
        "working_restart_artifacts_after_modal": lineage["working_restart_records"],  # 记录 solver 工作复制件完成后的当前身份并允许求解器合法改写。
        "solver_native_completion": evidence["main_output"],  # 保存原生完成、错误和 warning 摘要。
        "modal": evidence["modal"],  # 保存八十阶、频率、结果集和刚体门摘要。
        "eigen_residuals": evidence["residuals"],  # 保存特征残差门摘要。
        "mass_orthogonality": evidence["orthogonality"],  # 保存质量 Gram 门摘要。
        "modal_artifacts": evidence["artifacts"],  # 保存二进制、向量和能量完整性。
        "hard_gates": {  # 汇总最终发布所需的核心布尔门。
            "modes_exactly_80": True,  # 属性、结果集和残差均八十阶。
            "frequencies_finite_positive": True,  # 全部频率有限且严格为正。
            "no_numerical_rigid_body_modes": True,  # 无频率低于刚体阈值的阶次。
            "eigen_residuals_passed": True,  # 最大尺度化残差不超过 1E-6。
            "mass_orthogonality_passed": True,  # Gram 对角和非对角误差均不超过 1E-6。
            "solver_error_summary_unique_zero": True,  # 主 OUT 含且仅含一个零错误页尾汇总。
            "all_warning_blocks_explicitly_whitelisted": True,  # 主 OUT 与独立 ERR 的全部 warning 均唯一命中批准类别。
            "vector_contents_and_node_sets_complete": True,  # 一百六十份向量的标题、阶次、频率、节点行和跨文件节点集合均闭合。
            "authoritative_file_snapshot_stable": True,  # QA 解析前、解析后和提交前复用同一文件摘要集且未发现漂移。
            "critical_binary_and_vector_outputs_complete": True,  # 关键二进制、深度核验的 160 向量和能量表完整。
        },  # 完成核心硬门对象。
        "limitations": [  # 明确数值通过后的工程使用边界。
            "STATIC_SOURCE_REMAINS_DIAGNOSTIC_WITH_REVIEWED_WARNINGS",  # 静力来源仍含已审阅条件尺度和收敛参考警告。
            "INITIAL_STATE_PHYSICAL_RECONCILIATION_NOT_APPROVED_FOR_PRODUCTION",  # 初始状态物理协调尚未获得生产签认。
            "SMP1_FIRST_RUN_ONLY_NO_PARALLEL_REPRODUCIBILITY_CLAIM",  # 尚未形成并行重现性结论。
            "NO_ENGINEERING_PRODUCTION_RELEASE",  # 本链不发布工程生产结果。
        ],  # 完成固定限制列表。
        "production": False,  # 精确满足用户要求并防止自动升级。
        "valid_for_production": False,  # 与既有项目状态字段保持一致。
        "finalizer_sha256": sha256_file(SCRIPT_PATH),  # 记录真正实施最终门的源码摘要。
    }  # 完成机器 QA 对象。
    runtime_payload = {  # 构造不覆盖运行中原件的最终运行回执。
        "schema_version": 1,  # 最终运行回执首版 schema。
        "run_name": run_dir.name,  # 绑定运行身份。
        "jobname": lineage["jobname"],  # 绑定作业名。
        "status": "EXECUTED_AND_FINALIZED_DIAGNOSTIC_ONLY",  # 表示真实执行和外部 QA 均完成。
        "finalized_at_utc": generated_at,  # 记录统一最终化时间。
        "execution_mode": EXPECTED_EXECUTION_MODE,  # 记录实际 SMP1 模式。
        "qa_status": QA_STATUS,  # 指向诊断用途 QA 结论。
        "production": False,  # 运行完成不授予生产用途。
        "valid_for_production": False,  # 兼容既有字段并保持假。
    }  # 完成最终运行回执对象。
    final_status_payload = {  # 构造最后发布的根提交标志。
        "schema_version": 1,  # 模态最终状态首版 schema。
        "run_name": run_dir.name,  # 绑定运行身份。
        "jobname": lineage["jobname"],  # 绑定作业名。
        "status": FINAL_STATUS,  # 发布条件性非生产完成状态。
        "qa_status": QA_STATUS,  # 记录对应机器 QA 状态。
        "modal_status": "80_MODES_VERIFIED",  # 明确八十阶完整并已验证。
        "frequency_first_hz": evidence["modal"]["frequency_first_hz"],  # 记录第一阶频率。
        "frequency_last_hz": evidence["modal"]["frequency_last_hz"],  # 记录第八十阶频率。
        "maximum_normalized_eigen_residual": evidence["residuals"]["maximum_normalized_residual"],  # 记录控制残差。
        "maximum_mass_gram_diagonal_deviation": evidence["orthogonality"]["maximum_diagonal_deviation"],  # 记录质量归一最大偏差。
        "maximum_mass_gram_off_diagonal_absolute": evidence["orthogonality"]["maximum_off_diagonal_absolute"],  # 记录质量正交最大耦合。
        "rigid_body_mode_count": 0,  # 明确数值刚体模态为零。
        "production": False,  # 永久保持非生产。
        "valid_for_production": False,  # 与全链一致的用途边界。
        "next_action": "ENGINEERING_REVIEW_OF_INITIAL_STATE_CONDITIONING_AND_STATIC_WARNINGS_BEFORE_ANY_PRODUCTION_USE",  # 指向生产签认前仍需完成的工程审查。
    }  # 完成根最终状态对象。
    report_text = f"# C10 隔离式模态诊断最终结果\n\n状态：`{FINAL_STATUS}`；QA：`{QA_STATUS}`；`production=false`。\n\n- 执行：保持静力 jobname，以 `ANTYPE,,RESTART,2,1,PERTURB` 进入 LS2/子步1，SMP1 首轮完成。\n- 模态：80 阶属性、80 个 RSTP 结果集、80 份位移和 80 份转角完整；频率范围 {evidence['modal']['frequency_first_hz']:.16g}–{evidence['modal']['frequency_last_hz']:.16g} Hz。\n- 刚体模态：阈值 {RIGID_BODY_FREQUENCY_LIMIT_HZ:.1e} Hz，检出 0 阶。\n- 特征残差：最大尺度化残差 {evidence['residuals']['maximum_normalized_residual']:.6e}，控制阶 {evidence['residuals']['controlling_mode']}，门槛 {MAX_NORMALIZED_RESIDUAL:.1e}。\n- 质量正交：最大对角偏差 {evidence['orthogonality']['maximum_diagonal_deviation']:.6e}；最大非对角绝对值 {evidence['orthogonality']['maximum_off_diagonal_absolute']:.6e}；门槛均为 {MAX_ORTHOGONALITY_ERROR:.1e}。\n- 主 OUT：0 ERROR、0 FATAL；warning 共 {evidence['main_output']['warning_blocks']} 条，保留在机器 QA 中审阅。\n- 限制：静力来源仍是含已审阅警告的诊断 run；初始状态物理协调、条件尺度和生产签认均未由本模态数值通过替代。\n\n机器证据见 `qa/{QA_NAME}`，全 run 摘要见 `{FINAL_LEDGER_NAME}`。\n"  # 生成与机器 QA 同值的人读摘要。
    return json_bytes(qa_payload), json_bytes(runtime_payload), report_text.encode("utf-8"), json_bytes(final_status_payload)  # 返回四份确定性字节供事务发布。


def build_final_ledger(run_dir: Path, ledger_path: Path, final_status_path: Path, final_status_bytes: bytes, authoritative_snapshot: dict[str, dict[str, Any]], new_artifacts: dict[Path, bytes]) -> tuple[bytes, int]:  # 输入权威快照和本次确定性字节，返回覆盖全 run 的账本字节和条目数。
    """复用解析前且提交前已复核的同一摘要集，并加入本次新工件与尚未发布状态承诺。"""  # 禁止重新遍历后让账本封存不同于 QA 解析的字节。
    require(not ledger_path.exists() and not final_status_path.exists(), "构建最终账本前账本或根最终状态已意外出现")  # 账本和提交标志都必须仍由本次事务独占创建。
    records = {label: str(record["sha256"]) for label, record in authoritative_snapshot.items()}  # 从同一权威快照复制全部既有文件摘要。
    for path, payload in new_artifacts.items():  # 对本 finalizer 已原子写出的 QA、runtime 和报告逐项闭合内存字节。
        label = path.relative_to(run_dir).as_posix()  # 生成当前新工件稳定相对标签。
        require(label not in records, f"最终化新工件与权威快照标签冲突：{label}")  # 新目标在解析前必须不存在。
        expected_hash = sha256_bytes(payload)  # 对写入所用的同一内存字节计算摘要。
        require(path.is_file() and sha256_file(path) == expected_hash, f"最终化新工件发布字节不闭合：{label}")  # 磁盘字节必须等于内存源。
        records[label] = expected_hash  # 把新工件确定性摘要加入最终账本。
    current_labels = {path.relative_to(run_dir).as_posix() for path in run_dir.rglob("*") if path.is_file()}  # 在账本发布前枚举当前普通文件集合。
    require(current_labels == set(records), f"构建最终账本时文件集合与权威摘要集不一致：新增={sorted(current_labels - set(records))}，缺失={sorted(set(records) - current_labels)}")  # 防止未解析文件混入或证据消失。
    status_label = final_status_path.relative_to(run_dir).as_posix()  # 生成根最终状态账本标签。
    records[status_label] = sha256_bytes(final_status_bytes)  # 在发布前承诺将要原子写入的精确状态字节。
    lines = [f"{records[label]}  {label}" for label in sorted(records)]  # 按标签稳定排序生成标准账本行。
    return ("\n".join(lines) + "\n").encode("utf-8"), len(lines)  # 返回 UTF-8/LF 账本字节和条目数。


def validate_existing_finalization(run_dir: Path) -> dict[str, Any]:  # run_dir 已存在最终状态，返回零写入幂等复核摘要。
    """复核既有根状态、机器 QA 和账本，避免重复覆盖正式终态。"""  # 不重新运行任何求解或写文件。
    final_status_path = run_dir / FINAL_STATUS_NAME  # 定位既有根提交标志。
    status = read_json(final_status_path)  # 读取既有最终状态。
    require(status.get("run_name") == run_dir.name and status.get("status") == FINAL_STATUS and status.get("qa_status") == QA_STATUS, "既有最终状态身份或结论不一致")  # 只接受本脚本精确终态。
    require(status.get("production") is False and status.get("valid_for_production") is False, "既有最终状态存在生产用途真值")  # 幂等复核仍保持用途门。
    qa = read_json(run_dir / "qa" / QA_NAME)  # 读取既有机器 QA。
    require(qa.get("status") == QA_STATUS and qa.get("production") is False and qa.get("valid_for_production") is False, "既有机器 QA 状态或用途不一致")  # QA 必须同样非生产。
    ledger_path = run_dir / FINAL_LEDGER_NAME  # 定位既有全 run 账本。
    require(ledger_path.is_file() and ledger_path.stat().st_size > 0, "既有最终账本缺失或为空")  # 最终状态必须有摘要闭环。
    ledger_records: dict[str, str] = {}  # 初始化账本标签映射供逐项复算。
    for line_number, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):  # 按一基行号解析账本。
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)  # 验证标准摘要行格式。
        require(match is not None, f"最终账本第 {line_number} 行格式无效")  # 格式错误即拒绝幂等通过。
        expected_hash, label = match.groups()  # 解包摘要与相对标签。
        target = (run_dir / Path(label)).resolve()  # 解析目标规范路径。
        require(run_dir in target.parents and target.is_file(), f"最终账本目标缺失或逃逸：{label}")  # 每项必须仍在 run 内且存在。
        require(sha256_file(target) == expected_hash, f"最终账本工件 SHA-256 漂移：{label}")  # 逐项复算所有承诺字节。
        ledger_records[label] = expected_hash  # 保存已闭合记录。
    actual_labels = {path.relative_to(run_dir).as_posix() for path in run_dir.rglob("*") if path.is_file() and path.resolve() != ledger_path.resolve()}  # 枚举当前除账本自身外全部普通文件。
    require(actual_labels == set(ledger_records), "既有最终账本文件集合与当前 run 不闭合")  # 新增或缺失文件均拒绝幂等通过。
    return {"status": "ALREADY_FINALIZED_VERIFIED", "run_dir": str(run_dir), "final_status": FINAL_STATUS, "qa_status": QA_STATUS, "ledger_entries": len(ledger_records), "ledger_sha256": sha256_file(ledger_path), "production": False}  # 返回零写入成功摘要。


def commit_finalization(run_dir: Path, evidence: dict[str, Any]) -> dict[str, Any]:  # run_dir 是已验证 run，evidence 是全部只读门证据；返回提交摘要。
    """先原子写 QA、最终运行回执和报告，再写账本，最后发布根状态提交标志。"""  # 根状态出现即表示全部前置产物已落盘。
    generated_at = datetime.now(timezone.utc).isoformat()  # 生成所有最终产物共享的 UTC 时间。
    qa_bytes, runtime_bytes, report_bytes, final_status_bytes = build_final_payloads(run_dir, evidence, generated_at)  # 在内存生成互相一致的四份产物。
    qa_path = run_dir / "qa" / QA_NAME  # 定位机器 QA 目标。
    runtime_path = run_dir / FINAL_RUNTIME_NAME  # 定位最终运行回执目标。
    report_path = run_dir / RESULT_PACKET_NAME  # 定位人读报告目标。
    ledger_path = run_dir / FINAL_LEDGER_NAME  # 定位最终全 run 账本目标。
    final_status_path = run_dir / FINAL_STATUS_NAME  # 定位最后发布的根提交标志。
    targets = [qa_path, runtime_path, report_path, ledger_path, final_status_path]  # 汇总本次唯一允许创建的五个目标。
    require(all(not path.exists() for path in targets), f"最终化目标已存在，拒绝覆盖：{[str(path) for path in targets if path.exists()]}")  # 首次最终化不覆盖任何既有文件。
    authoritative_snapshot = evidence["authoritative_snapshot"]  # 提取解析前并在解析后复核过的权威摘要集。
    require(isinstance(authoritative_snapshot, dict) and authoritative_snapshot, "提交缺少非空权威文件快照")  # 任何无快照提交均拒绝。
    verify_authoritative_snapshot(run_dir, authoritative_snapshot)  # 在首次写入前再次逐项复算，关闭解析结束到提交开始的时间窗。
    written_paths: list[Path] = []  # 登记本次实际成功创建的目标，任一后续异常时只回滚这些新文件。
    try:  # 把五项发布和发布后复核纳入同一可回滚事务。
        atomic_write(qa_path, qa_bytes)  # 首先发布完整机器 QA。
        written_paths.append(qa_path)  # 登记 QA 已由本次新建。
        atomic_write(runtime_path, runtime_bytes)  # 其次发布不覆盖运行中原件的最终运行回执。
        written_paths.append(runtime_path)  # 登记最终运行回执已由本次新建。
        atomic_write(report_path, report_bytes)  # 再发布人读结果摘要。
        written_paths.append(report_path)  # 登记结果摘要已由本次新建。
        preliminary_labels = {qa_path.relative_to(run_dir).as_posix(), runtime_path.relative_to(run_dir).as_posix(), report_path.relative_to(run_dir).as_posix()}  # 定义当前唯一允许新增的三份非提交工件标签。
        verify_authoritative_snapshot(run_dir, authoritative_snapshot, preliminary_labels)  # 三份新工件写出后再次证明所有被解析旧文件未变化且无其他新增。
        new_artifacts = {qa_path: qa_bytes, runtime_path: runtime_bytes, report_path: report_bytes}  # 把三份磁盘新工件绑定到实际写入的同一内存字节。
        ledger_bytes, ledger_entries = build_final_ledger(run_dir, ledger_path, final_status_path, final_status_bytes, authoritative_snapshot, new_artifacts)  # 复用权威摘要集并承诺尚未发布状态。
        atomic_write(ledger_path, ledger_bytes)  # 发布排除自身且承诺最终状态字节的全 run 账本。
        written_paths.append(ledger_path)  # 登记最终账本已由本次新建。
        precommit_labels = preliminary_labels | {ledger_path.relative_to(run_dir).as_posix()}  # 把刚发布的最终账本加入根状态发布前唯一允许新增集合。
        verify_authoritative_snapshot(run_dir, authoritative_snapshot, precommit_labels)  # 根状态发布前最后一次复核全部被解析旧文件仍为同一字节。
        require(sha256_file(qa_path) == sha256_bytes(qa_bytes) and sha256_file(runtime_path) == sha256_bytes(runtime_bytes) and sha256_file(report_path) == sha256_bytes(report_bytes), "根状态发布前三份最终化工件发生字节漂移")  # 三份新工件也必须仍等于生成时内存字节。
        require(sha256_file(ledger_path) == sha256_bytes(ledger_bytes), "根状态发布前最终账本字节发生漂移")  # 账本本身必须仍等于刚发布的确定性字节。
        atomic_write(final_status_path, final_status_bytes)  # 最后原子发布根状态，使其成为唯一 commit marker。
        written_paths.append(final_status_path)  # 登记根提交标志已由本次新建。
        require(sha256_file(final_status_path) == sha256_bytes(final_status_bytes), "最终状态发布后字节摘要不一致")  # 立即复核提交标志真实字节。
        ledger_lines = ledger_path.read_text(encoding="utf-8").splitlines()  # 读取已发布账本供状态条目复核。
        status_label = final_status_path.relative_to(run_dir).as_posix()  # 生成状态 POSIX 标签。
        require(f"{sha256_bytes(final_status_bytes)}  {status_label}" in ledger_lines, "最终账本未精确承诺根状态字节")  # 状态和账本必须交叉闭合。
    except Exception:  # 任一写入、哈希或交叉复核失败时进入精准回滚。
        for written_path in reversed(written_paths):  # 按创建相反顺序处理仅由本次新建的目标。
            if written_path.exists() and written_path.resolve().parent in {run_dir.resolve(), (run_dir / "qa").resolve()}:  # 删除前再次限制到本 run 根或 qa 直属目录。
                written_path.unlink()  # 删除未形成完整提交的本次新文件，使下次可重新最终化。
        raise  # 保留原始失败原因并确保根状态不存在时不冒充完成。
    return {"status": FINAL_STATUS, "run_dir": str(run_dir), "qa_status": QA_STATUS, "modal_modes": EXPECTED_MODES, "maximum_normalized_residual": evidence["residuals"]["maximum_normalized_residual"], "maximum_mass_gram_diagonal_deviation": evidence["orthogonality"]["maximum_diagonal_deviation"], "maximum_mass_gram_off_diagonal_absolute": evidence["orthogonality"]["maximum_off_diagonal_absolute"], "rigid_body_mode_count": 0, "final_ledger_entries": ledger_entries, "final_ledger_sha256": sha256_file(ledger_path), "production": False}  # 返回最终提交摘要。


def finalize_modal(run_dir: Path) -> dict[str, Any]:  # run_dir 是规范隔离模态 run，返回首次提交或幂等复核摘要。
    """在既有终态时只读复核，否则先收集全部证据再事务化提交。"""  # 失败时不会发布根最终状态。
    if (run_dir / FINAL_STATUS_NAME).exists():  # 已存在根提交标志时进入零写入幂等路径。
        return validate_existing_finalization(run_dir)  # 逐项复算既有 QA 和全 run 账本。
    authoritative_snapshot = capture_authoritative_snapshot(run_dir)  # 在解析任何 QA 文本或 CSV 前冻结全部普通文件的集合、元数据和摘要。
    evidence = collect_evidence(run_dir, authoritative_snapshot)  # 对同一权威字节执行全部只读硬门并在解析后复核快照。
    return commit_finalization(run_dir, evidence)  # 全门通过后按根状态最后顺序提交。


def main(argv: list[str] | None = None) -> int:  # argv 是可选 CLI 参数，返回零表示最终化/幂等成功、二表示拒绝。
    """执行最终化入口并打印机器可读摘要或明确拒绝原因。"""  # 本函数从不启动或停止求解器。
    lock_stream: Any | None = None  # 初始化可选锁句柄，只有 run 规范化后成功取得才会赋值。
    try:  # 统一捕获参数后全部验证和提交异常。
        args = parse_args(argv)  # 解析显式模态 run 目录。
        run_dir = normalize_run_dir(Path(args.run_dir))  # 规范化并限制运行范围。
        lock_stream = acquire_finalize_lock(run_dir)  # 在读取最终状态、解析证据或写任何产物前取得本 run 独占 finalizer 锁。
        result = finalize_modal(run_dir)  # 执行只读门和必要的最终产物提交。
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))  # 输出机器可读成功摘要。
        return 0  # 零码表示诊断终态或既有终态已严格闭合，仍不代表生产签认。
    except Exception as exc:  # 捕获任一验证或提交异常。
        failure = {"status": "MODAL_FINALIZE_REJECTED", "reason": str(exc), "production": False, "valid_for_production": False}  # 构造明确失败且不含通过语义的对象。
        print(json.dumps(failure, ensure_ascii=False, indent=2, allow_nan=False))  # 输出具体失败门供修复使用。
        return 2  # 非零码阻止编排器把部分结果当成完成。
    finally:  # 无论参数后验证、解析、提交或输出路径如何结束，都必须释放已取得的 OS 锁。
        if lock_stream is not None:  # 只有成功取得锁后才存在可释放句柄。
            release_finalize_lock(lock_stream)  # 显式解锁并关闭句柄，锁文件保留供账本和幂等复核。


if __name__ == "__main__":  # 仅直接调用时进入 CLI，导入模块不会读写 run 或控制进程。
    raise SystemExit(main())  # 把 main 返回码传递给操作系统。
