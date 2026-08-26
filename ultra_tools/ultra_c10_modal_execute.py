"""对已准备的 C10 隔离模态 run 实施哈希、进程、8 GiB RAM 与 40 GiB 磁盘硬门后异步启动 SMP1。"""  # 本模块不降低任何门槛，也不把启动等同于求解完成。

from __future__ import annotations  # 启用延迟类型注解，保持 Windows 运行时依赖简单稳定。

import argparse  # 解析唯一允许的模态运行目录参数并拒绝未知参数。
import hashlib  # 复算准备态账本、主输入、四项重启动种子和 MAPDL 二进制摘要。
import json  # 读取模态 manifest/status 并写出机器可读异步启动回执。
import os  # 刷新关键启动回执到磁盘并以同目录原子替换推进启动声明状态。
import re  # 严格解析 SHA-256 账本行和相对路径标签。
import shutil  # 读取新 solver 所在卷的实时可用磁盘空间。
import subprocess  # 以无窗口独立进程启动冻结的 MAPDL SMP1 命令。
import uuid  # 为同目录原子 JSON 替换生成不可碰撞的唯一暂存文件名。
from datetime import datetime, timezone  # 记录资源检查和启动的统一 UTC 时间。
from pathlib import Path  # 规范化包含中文的项目与运行路径并阻断目录逃逸。
from typing import Any  # 描述 JSON 动态对象、进程记录和启动结果。

import psutil  # 读取实时可用物理内存和精确求解器/MPI 进程表。


SCRIPT_PATH = Path(__file__).resolve()  # 固定当前执行脚本路径供启动回执记录源码身份。
TOOLS_DIR = SCRIPT_PATH.parent  # ultra_tools 是脚本所在目录。
PROJECT_ROOT = TOOLS_DIR.parent  # 项目根目录承载 ultra_runs。
RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # execute 只允许操作该目录的直属模态 run。
MANIFEST_NAME = "C10_modal_manifest.json"  # prepare 冻结的执行与数值 QA 机器合同。
STATUS_NAME = "C10_modal_status.json"  # prepare 根状态必须仍为未启动状态。
LEDGER_NAME = "prepare_artifact_hashes.sha256"  # 启动前必须全量闭合的准备态文件账本。
RUNTIME_LAUNCH_NAME = "runtime_launch.json"  # 启动后唯一写出的 PID、资源和参数回执。
RUNTIME_STATUS_NAME = "C10_modal_runtime_status.json"  # 启动后单独写出的非最终运行状态。
LAUNCH_CLAIM_NAME = "runtime_launch_claim.json"  # Popen 前独占创建的启动所有权声明，防止并发 execute 双启动。
LAUNCH_FAILURE_NAME = "runtime_launch_failure.json"  # Popen 异常时保留具体失败且阻断无审查重试的记录。
EXPECTED_PREPARE_STATUS = "MODAL_DIAGNOSTIC_PREPARED"  # 只有未启动准备状态可首次执行。
EXPECTED_EXECUTION_MODE = "SMP_SERIAL_NP1_DIAGNOSTIC_ONLY"  # 首轮只允许 SMP 单进程诊断。
EXPECTED_SCHEMA_VERSION = 1  # execute 只接受与当前 prepare/finalize 共同冻结的首版机器合同。
EXPECTED_MODES = 80  # 首轮必须从最低频率起请求并外部闭合恰好八十阶模态。
MIN_AVAILABLE_RAM_BYTES = 8 * 1024**3  # 实时可用物理内存必须至少 8 GiB，禁止继承静力例外。
MIN_FREE_DISK_BYTES = 40 * 1024**3  # 新 solver 所在卷实时空闲空间必须至少 40 GiB。
MAX_NORMALIZED_RESIDUAL = 1.0e-6  # 每阶尺度化特征残差合同固定不超过一百万分之一。
MAX_ORTHOGONALITY_ERROR = 1.0e-6  # 质量 Gram 矩阵对角与非对角误差合同固定不超过一百万分之一。
RIGID_BODY_FREQUENCY_LIMIT_HZ = 1.0e-6  # 频率小于等于一微赫兹的数值刚体阶必须由 finalizer 拒绝。
EXPECTED_RESTART_COMMAND = "ANTYPE,,RESTART,2,1,PERTURB"  # 线性扰动必须精确从载荷步二、子步一对应的 `.r002` 进入。
EXPECTED_PERTURB_COMMAND = "PERTURB,MODAL,AUTO,CURRENT,PARKEEP"  # 扰动合同必须使用当前切线并保持冻结的约束处理语义。
EXPECTED_ELEMENT_FORM_COMMAND = "SOLVE,ELFORM"  # 提取模态前必须先形成最终静力状态的扰动单元矩阵。
EXPECTED_MASS_MATRIX_COMMAND = "LUMPM,OFF"  # 模态求解必须使用一致质量矩阵，禁止集中质量近似漂移。
EXPECTED_MODAL_SOLVER_COMMAND = "MODOPT,LANB,80"  # 模态提取必须使用 Block Lanczos 且请求恰好八十阶。
EXPECTED_MODE_EXPANSION_COMMAND = "MXPAND,80,,,YES"  # 必须展开八十阶并保存后续能量审计所需的单元结果。
EXPECTED_MODAL_OUTRES_COMMANDS = [  # manifest 与实际主输入必须共同冻结这三条且仅这三条模态结果输出命令。
    "OUTRES,ALL,NONE",  # 先关闭默认结果输出，避免未审计字段和体积失控。
    "OUTRES,NSOL,ALL",  # 保存全部实际模态的节点解供八十阶向量导出。
    "OUTRES,VENG,ALL",  # 保存全部实际模态的元素能量供六组件审计。
]  # 完成批准的有序模态 OUTRES 命令数组。
EXPECTED_MODAL_SOLVE_COMMAND = "SOLVE"  # 扰动矩阵形成和模态控制完成后只允许一次正式模态求解。
EXPECTED_RESOURCE_GATES = {  # manifest 必须逐键等于该资源合同，禁止跨版本门槛或隐藏例外混入。
    "available_ram_min_bytes": MIN_AVAILABLE_RAM_BYTES,  # 可用物理内存硬门精确为 8 GiB 字节数。
    "solver_volume_free_disk_min_bytes": MIN_FREE_DISK_BYTES,  # solver 所在卷空闲空间硬门精确为 40 GiB 字节数。
    "exceptions_allowed": False,  # 模态诊断不允许继承任何静力低内存或低磁盘例外。
}  # 完成 execute 唯一批准的资源合同对象。
EXPECTED_NUMERICAL_QA_CONTRACT = {  # manifest 必须逐键等于该八十阶残差、正交和刚体数值合同。
    "residual_definition": "NORM2_KPHI_MINUS_LAMBDA_MPHI_OVER_MAX_NORM2_KPHI_AND_ABS_LAMBDA_NORM2_MPHI",  # 冻结无量纲特征方程残差的分子与尺度分母定义。
    "maximum_normalized_residual": MAX_NORMALIZED_RESIDUAL,  # 每一阶尺度化残差均不得超过 1E-6。
    "orthogonality_definition": "PHI_TRANSPOSE_M_PHI_VERSUS_IDENTITY",  # 冻结质量归一化模态的 Gram 单位阵判据。
    "maximum_diagonal_deviation": MAX_ORTHOGONALITY_ERROR,  # Gram 对角相对一的最大偏差固定为 1E-6。
    "maximum_off_diagonal_absolute": MAX_ORTHOGONALITY_ERROR,  # Gram 非对角元素最大绝对值固定为 1E-6。
    "rigid_body_frequency_limit_hz": RIGID_BODY_FREQUENCY_LIMIT_HZ,  # 数值刚体模态排除限值固定为 1E-6 Hz。
}  # 完成 execute 唯一批准的外部数值 QA 合同对象。
DIRECT_MAPDL_PROCESS_NAMES = {  # 这些映像本身就是实际 MAPDL 求解进程，存活时可直接判为资源冲突。
    "ansys.exe",  # MAPDL 实际计算进程常用映像名。
    "ansys261.exe",  # MAPDL 2026 R1 启动包装进程映像名。
    "mapdl.exe",  # 通用 MAPDL 映像名。
    "mapdl261.exe",  # 带版本号的 MAPDL 映像名。
}  # 完成无需依赖命令行即可识别的实际 MAPDL 映像集合。
MPI_INFRASTRUCTURE_PROCESS_NAMES = {  # 这些 MPI 基础设施仅在命令行或父子链绑定 MAPDL 时才构成冲突。
    "mpiexec.exe",  # MPI 启动进程，出现时说明存在并行求解冲突。
    "hydra_service.exe",  # Intel MPI Hydra 常驻服务本身不再被无条件误判为正在求解。
    "hydra_pmi_proxy.exe",  # Intel MPI Hydra 工作代理进程。
}  # 完成必须追加 MAPDL 身份证据的 MPI 候选映像集合。
REQUIRED_RESTART_SUFFIXES = {".rdb", ".ldhi", ".r002", ".rst"}  # 启动前必须再次闭合的四项同 jobname 重启动种子。
LEDGER_PATTERN = re.compile(r"^([0-9a-f]{64})  (.+)$")  # 账本每行固定为小写 SHA-256、两个空格和 POSIX 相对路径。


def require(condition: bool, message: str) -> None:  # condition 是启动硬门，message 是失败原因；成功无返回。
    """任一身份、资源、进程或文件门失败时立即阻断 Popen。"""  # 函数不提供任何诊断例外分支。
    if not condition:  # 仅当硬门不成立时进入拒绝路径。
        raise RuntimeError(message)  # 抛出明确原因并保证后续启动代码不执行。


class PostLaunchReceiptError(RuntimeError):  # 表示 Popen 已返回正 PID、但磁盘启动回执事务未完整提交的专用异常。
    """携带已启动 PID，使 CLI 即使遇到磁盘回执异常也能输出不可歧义的禁止重启状态。"""  # 该异常绝不表示 MAPDL 未启动。

    def __init__(self, main_pid: int, reason: str, recording_errors: list[str]) -> None:  # main_pid 是已启动 PID，reason 是首个失败，recording_errors 是补写失败列表；成功无返回。
        super().__init__(reason)  # 把首个回执失败原因保留为标准异常文本供日志与人工审阅。
        self.main_pid = main_pid  # 保存 Popen 已返回的正整数 PID，禁止上层误判为启动前失败。
        self.reason = reason  # 保存不丢失上下文的首个回执事务失败说明。
        self.recording_errors = recording_errors  # 保存更新 claim 或补写 failure 记录时出现的全部次级异常。


def sha256_file(path: Path) -> str:  # path 是现存普通文件，返回完整字节的小写 SHA-256。
    """以 8 MiB 分块复核大型 RST/RDB，避免启动前出现整文件内存峰值。"""  # 函数只读文件。
    digest = hashlib.sha256()  # 初始化独立 SHA-256 累加器。
    with path.open("rb") as stream:  # 以二进制只读方式打开，禁止文本转换。
        while True:  # 循环读取直到文件末尾。
            block = stream.read(8 * 1024 * 1024)  # 每块读取 8 MiB 原始字节。
            if not block:  # 空块表示已经完整读取文件。
                break  # 退出读取循环。
            digest.update(block)  # 将当前块按顺序纳入摘要。
    return digest.hexdigest()  # 返回六十四位小写摘要。


def read_json(path: Path) -> dict[str, Any]:  # path 是必需 JSON，返回顶层对象。
    """严格读取 UTF-8 JSON 对象，不为缺失字段提供默认通过值。"""  # 所有业务字段由调用方精确核对。
    require(path.is_file(), f"缺少必需 JSON：{path}")  # 解码前关闭文件存在性门。
    payload = json.loads(path.read_text(encoding="utf-8-sig"))  # 接受可选 BOM 并由标准解析器拒绝无效 JSON。
    require(isinstance(payload, dict), f"JSON 顶层不是对象：{path}")  # manifest、status 与回执均要求对象顶层。
    return payload  # 返回已通过类型门的对象。


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:  # path 必须尚不存在，payload 是禁止 NaN 的回执对象；成功无返回。
    """以独占创建并强制刷新方式写出首次启动回执，拒绝覆盖或二次启动。"""  # 文件存在即由操作系统触发失败。
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 保留中文、拒绝非有限数并统一末尾 LF。
    with path.open("x", encoding="utf-8", newline="\n") as stream:  # 使用 x 模式原子占有目标文件名并禁止覆盖。
        stream.write(rendered)  # 一次写出完整 JSON 文本。
        stream.flush()  # 把 Python 用户态缓冲区全部推送给操作系统再视为回执已写。
        os.fsync(stream.fileno())  # 强制刷新文件内容，降低 Popen 后断电留下空壳回执的风险。


def replace_json_atomic(path: Path, payload: dict[str, Any]) -> None:  # path 是已存在的启动 claim，payload 是其下一状态；成功无返回。
    """在目标同目录写满并刷新唯一暂存 JSON，再以原子替换推进已占有 claim。"""  # 读者只会看到旧状态或完整新状态。
    require(path.is_file(), f"待推进的启动声明不存在：{path}")  # 只有先由独占创建取得所有权的 claim 才允许更新。
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 预先完成严格序列化，避免替换后才发现 NaN 或类型错误。
    temporary_name = f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"  # 以 execute PID 和随机 UUID 生成同目录不可碰撞暂存名。
    temporary_path = path.with_name(temporary_name)  # 同目录保证最终 os.replace 不跨卷且保持原子语义。
    try:  # 暂存写入、刷新或原子替换任一步失败都进入安全清理路径。
        with temporary_path.open("x", encoding="utf-8", newline="\n") as stream:  # 独占创建暂存文件，拒绝覆盖任何异常残留。
            stream.write(rendered)  # 一次写出完整下一状态 JSON 文本。
            stream.flush()  # 把用户态缓冲区推送到操作系统缓存。
            os.fsync(stream.fileno())  # 在替换正式 claim 前强制刷新完整暂存字节。
        os.replace(temporary_path, path)  # 在同目录一次性把完整下一状态替换为权威 claim。
    finally:  # 无论成功或异常都不得把本次唯一暂存文件长期留在 run 根目录。
        if temporary_path.exists():  # 仅当替换未消费暂存文件或异常发生在替换前时需要清理。
            temporary_path.unlink()  # 删除本函数唯一拥有的 UUID 暂存文件，不触碰其他运行工件。


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:  # argv 是可选测试参数，返回显式 run-dir 命名空间。
    """要求调用方明确指定已准备的隔离模态 run。"""  # 脚本不会猜测最新目录。
    parser = argparse.ArgumentParser(description="在全部硬门通过后异步启动 C10 SMP1 模态诊断。")  # 创建带用途边界的参数解析器。
    parser.add_argument("--run-dir", required=True, help="ultra_runs 下由 ultra_c10_modal_prepare.py 创建的直属运行目录。")  # 唯一业务参数不得省略。
    return parser.parse_args(argv)  # 解析未知参数时由 argparse 自动拒绝。


def normalize_run_dir(path: Path) -> Path:  # path 是用户给出的模态 run，返回 ultra_runs 直属规范目录。
    """阻断项目外、嵌套或不存在目录进入执行链。"""  # 本函数只读检查目录范围。
    resolved = path.resolve()  # 消解相对段与可解析链接。
    require(resolved.is_dir(), f"模态运行目录不存在：{resolved}")  # 只有现存目录可执行。
    require(resolved.parent == RUNS_ROOT.resolve(), f"模态运行目录不是 ultra_runs 直属子目录：{resolved}")  # 禁止跨 run 或项目外路径。
    require(resolved.name.startswith("C10_MODAL_DIAGNOSTIC_"), f"运行目录名不是 C10 模态诊断前缀：{resolved.name}")  # 防止误执行静力或历史 run。
    return resolved  # 返回已通过范围和命名门的目录。


def safe_ledger_path(run_dir: Path, label: str) -> Path:  # run_dir 是隔离运行根，label 是账本 POSIX 标签；返回范围内规范路径。
    """拒绝绝对标签、反斜杠、空段和任何目录上跳。"""  # 避免恶意或损坏账本读取项目外文件。
    require(label and "\\" not in label, f"准备态账本标签为空或含反斜杠：{label!r}")  # 账本统一使用 POSIX 分隔符。
    relative = Path(label)  # 把 POSIX 标签转换为本机相对路径对象。
    require(not relative.is_absolute() and ".." not in relative.parts and "." not in relative.parts, f"准备态账本标签不是安全相对路径：{label}")  # 阻断绝对路径和目录跳转。
    resolved = (run_dir / relative).resolve()  # 规范化标签指向的实际路径。
    require(resolved != run_dir and run_dir in resolved.parents, f"准备态账本标签逃逸运行目录：{label}")  # 目标必须是 run 内部文件。
    return resolved  # 返回已经通过范围门的绝对路径。


def validate_prepare_ledger(run_dir: Path) -> dict[str, str]:  # run_dir 是未启动模态 run，返回相对标签到摘要的完整映射。
    """证明从 prepare 发布后到 execute 启动前没有任何文件增删或字节变化。"""  # 账本自身按设计排除。
    ledger_path = run_dir / LEDGER_NAME  # 定位准备阶段生成的唯一账本。
    require(ledger_path.is_file() and ledger_path.stat().st_size > 0, "缺少或为空的准备态账本")  # 空账本不能授权启动。
    records: dict[str, str] = {}  # 初始化安全相对标签到预期摘要的映射。
    for line_number, raw_line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):  # 按一基行号解析全部非空账本行。
        match = LEDGER_PATTERN.fullmatch(raw_line)  # 按固定双空格格式验证当前行。
        require(match is not None, f"准备态账本第 {line_number} 行格式无效")  # 格式漂移即拒绝。
        expected_hash, label = match.groups()  # 解包预期摘要和 POSIX 相对标签。
        require(label not in records, f"准备态账本存在重复标签：{label}")  # 每个文件只能承诺一次。
        target = safe_ledger_path(run_dir, label)  # 解析并验证目标仍在 run 内。
        require(target.is_file(), f"准备态账本目标缺失：{label}")  # 文件删除即拒绝。
        require(sha256_file(target) == expected_hash, f"准备态文件 SHA-256 漂移：{label}")  # 任一字节变化即拒绝。
        records[label] = expected_hash  # 保存已经复算闭合的记录。
    actual_labels = {path.relative_to(run_dir).as_posix() for path in run_dir.rglob("*") if path.is_file() and path.resolve() != ledger_path.resolve()}  # 枚举当前除账本自身外全部普通文件。
    require(actual_labels == set(records), f"准备态文件集合与账本不闭合：新增={sorted(actual_labels - set(records))}，缺失={sorted(set(records) - actual_labels)}")  # 文件增删同样阻断启动。
    return records  # 返回已全量复算闭合的账本映射。


def command_line_has_mapdl_identity(arguments: list[str], jobname: str, solver_dir: Path) -> bool:  # arguments 是候选进程参数，jobname/solver_dir 是本 run 身份；返回是否含 MAPDL 证据。
    """只用可执行文件名、精确 `-j` 作业名或隔离 solver 路径识别 MPI 基础设施是否真正服务 MAPDL。"""  # 常驻 Hydra 服务的普通端口参数不会通过。
    normalized_arguments = [str(argument).strip().strip('"').casefold() for argument in arguments if str(argument).strip()]  # 去除空参数和外层引号并统一大小写。
    normalized_jobname = jobname.casefold()  # Windows 作业名比较采用不区分大小写语义。
    normalized_solver_dir = str(solver_dir).rstrip("\\/").casefold()  # 去除末尾分隔符后冻结隔离 solver 绝对路径标记。
    executable_marker = any("ansys" in Path(argument).name.casefold() or "mapdl" in Path(argument).name.casefold() for argument in normalized_arguments)  # 参数中出现 MAPDL/ANSYS 可执行映像即形成直接命令行证据。
    job_marker = any(argument == normalized_jobname or argument == f"-j{normalized_jobname}" for argument in normalized_arguments)  # 精确作业名参数或紧凑 `-jJOB` 形式绑定本 run。
    for argument_index, argument in enumerate(normalized_arguments[:-1]):  # 检查标准拆分形式 `-j JOB`，最后一项不可能拥有后一参数。
        if argument == "-j" and normalized_arguments[argument_index + 1] == normalized_jobname:  # 当前标志和后一参数必须共同精确匹配本 jobname。
            job_marker = True  # 登记标准 `-j` 参数已经绑定本 run。
            break  # 找到唯一充分证据后停止继续扫描参数对。
    solver_dir_marker = any(normalized_solver_dir == argument.rstrip("\\/") or normalized_solver_dir in argument for argument in normalized_arguments)  # 精确路径或嵌入式工作路径绑定本隔离 solver。
    return executable_marker or job_marker or solver_dir_marker  # 任一独立身份标记成立即可把候选 MPI 进程关联到 MAPDL。


def active_solver_processes(jobname: str, solver_dir: Path) -> list[dict[str, Any]]:  # jobname/solver_dir 是本 run 身份，返回具有直接或谱系证据的活动求解冲突。
    """直接识别实际 MAPDL；MPI/Hydra 仅在命令行或父子链关联 MAPDL 时阻断。"""  # 常驻但空闲的 hydra_service.exe 不再造成永久误拒绝。
    process_snapshot: dict[int, dict[str, Any]] = {}  # 初始化单次一致性进程快照，保存后续父子图所需字段。
    for process in psutil.process_iter(["pid", "ppid", "name", "cmdline"]):  # 一次读取 PID、父 PID、映像名和参数，避免分阶段枚举造成谱系漂移。
        try:  # 进程可能在枚举期间退出、变成僵尸或拒绝读取命令行。
            process_id = int(process.info["pid"])  # 读取当前进程正整数身份供图索引使用。
            parent_id = int(process.info.get("ppid") or 0)  # 缺失父进程时使用零表示无可用谱系证据。
            process_name = str(process.info.get("name") or "").casefold()  # 以不区分大小写形式规范化 Windows 映像名。
            raw_arguments = process.info.get("cmdline") or []  # 读取结构化参数数组，空值表示没有命令行证据。
            arguments = [str(argument) for argument in raw_arguments]  # 把 psutil 返回项统一为字符串，供身份检查和审计输出共用。
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, KeyError, TypeError, ValueError):  # 捕获瞬时、权限和损坏字段异常。
            continue  # 不用不稳定或不可解释的记录制造无依据冲突结论。
        process_snapshot[process_id] = {"pid": process_id, "ppid": parent_id, "name": process_name, "arguments": arguments, "cmdline": " ".join(arguments)}  # 保存当前进程完整只读证据。
    related_reasons: dict[int, str] = {}  # 记录每个已关联 PID 的首个充分冲突理由，便于拒绝报告审查。
    for process_id, record in process_snapshot.items():  # 第一轮只建立直接 MAPDL 与显式命令行关联集合。
        if record["name"] in DIRECT_MAPDL_PROCESS_NAMES:  # 实际 MAPDL 映像无需依赖可能被截断的命令行。
            related_reasons[process_id] = "DIRECT_MAPDL_PROCESS_IMAGE"  # 记录直接求解器映像理由。
        elif record["name"] in MPI_INFRASTRUCTURE_PROCESS_NAMES and command_line_has_mapdl_identity(record["arguments"], jobname, solver_dir):  # MPI 候选必须额外含 MAPDL 或本 run 身份。
            related_reasons[process_id] = "MPI_COMMAND_LINE_BINDS_MAPDL_OR_CURRENT_RUN"  # 记录命令行绑定理由，区别于常驻服务误报。
    graph_changed = True  # 初始化父子图固定点循环，使多层 Hydra→proxy→solver 链能够完整传播。
    while graph_changed:  # 持续传播直至一轮没有新增相关 MPI 节点。
        graph_changed = False  # 每轮开始先假定谱系集合已收敛。
        related_ids = set(related_reasons)  # 冻结本轮已知相关 PID 集合，避免遍历中集合变化造成不稳定顺序。
        for process_id, record in process_snapshot.items():  # 检查尚未关联的 MPI 候选是否与相关节点直接相邻。
            if process_id in related_reasons or record["name"] not in MPI_INFRASTRUCTURE_PROCESS_NAMES:  # 已关联节点和普通应用进程无需重复推断。
                continue  # 进入下一进程记录。
            parent_is_related = record["ppid"] in related_ids  # 候选的父进程若已关联，则候选属于同一求解进程树。
            child_is_related = any(child_record["ppid"] == process_id and child_id in related_ids for child_id, child_record in process_snapshot.items())  # 候选若直接拥有相关子进程，也属于同一求解树。
            if parent_is_related or child_is_related:  # 只有存在明确相邻父子边时才关联 MPI/Hydra 候选。
                related_reasons[process_id] = "MPI_PARENT_CHILD_CHAIN_BINDS_MAPDL"  # 记录父子谱系理由，避免依赖服务映像名本身。
                graph_changed = True  # 标记集合扩展，下一轮继续向多层祖先或后代传播。
    conflicts: list[dict[str, Any]] = []  # 初始化稳定排序后的最终冲突证据数组。
    for process_id in sorted(related_reasons):  # 以 PID 升序形成确定性错误报告，便于重复审计比较。
        record = process_snapshot[process_id]  # 读取已确认相关的原始进程快照。
        conflicts.append({"pid": process_id, "ppid": record["ppid"], "name": record["name"], "cmdline": record["cmdline"], "reason": related_reasons[process_id]})  # 输出直接身份、命令行、谱系和理由。
    return conflicts  # 空数组表示未发现具有 MAPDL 身份证据的活动求解进程。


def validate_main_input_contract(main_text: str, jobname: str) -> None:  # main_text 是已验哈希 APDL 全文，jobname 是冻结作业名；成功无返回。
    """在 Popen 前从实际输入字节复核重启动、八十阶求解、输出和 APDL Math QA 的完整有序命令。"""  # 仅相信 manifest 字段不足以授权长时求解。
    normalized_lines = [line.strip() for line in main_text.splitlines()]  # 去除行首尾空白但保留每条 APDL 命令内部字符与字段顺序。
    unique_modal_commands = (  # 这些求解与结果合同命令在隔离模态尾段中必须各出现恰好一次。
        EXPECTED_RESTART_COMMAND,  # 精确 LS2/子步1线性扰动重启动入口。
        EXPECTED_PERTURB_COMMAND,  # 当前切线模态扰动与 PARKEEP 合同。
        EXPECTED_ELEMENT_FORM_COMMAND,  # 扰动单元矩阵形成步骤。
        EXPECTED_MASS_MATRIX_COMMAND,  # 一致质量矩阵选择，避免低阶频率被集中质量近似改变。
        EXPECTED_MODAL_SOLVER_COMMAND,  # Block Lanczos 八十阶请求。
        EXPECTED_MODE_EXPANSION_COMMAND,  # 展开恰好八十阶并保存单元结果。
        *EXPECTED_MODAL_OUTRES_COMMANDS,  # 按冻结顺序加入关闭默认、节点解和元素能量三条输出命令。
        EXPECTED_MODAL_SOLVE_COMMAND,  # 执行一次最终预应力切线模态求解。
        "C10_REQUESTED=80",  # 后处理请求计数必须固定为八十。
        "*IF,C10_AVAILABLE,NE,80,THEN",  # RSTP 实际结果集不等于八十时必须 fail-closed。
        "C10_EXPORTED=C10_REQUESTED",  # 实际导出计数必须继承已闭合的请求计数。
    )  # 完成唯一模态命令集合。
    for command in unique_modal_commands:  # 逐条阻断命令缺失、重复或通过注释伪造合同。
        require(normalized_lines.count(command) == 1, f"模态主输入命令必须恰好一处：{command}，实际={normalized_lines.count(command)}")  # 精确整行计数避免 substring 误通过。
    modal_order = (EXPECTED_RESTART_COMMAND, EXPECTED_PERTURB_COMMAND, EXPECTED_ELEMENT_FORM_COMMAND, EXPECTED_MASS_MATRIX_COMMAND, EXPECTED_MODAL_SOLVER_COMMAND, EXPECTED_MODE_EXPANSION_COMMAND, *EXPECTED_MODAL_OUTRES_COMMANDS, EXPECTED_MODAL_SOLVE_COMMAND)  # 冻结从重启动到实际模态求解的控制流顺序。
    modal_positions = [normalized_lines.index(command) for command in modal_order]  # 取得每条已证明唯一命令的一基文件顺序索引。
    require(modal_positions == sorted(modal_positions), "模态主输入的 RESTART→PERTURB→ELFORM→LANB80→MXPAND/OUTRES→SOLVE 顺序漂移")  # 乱序命令不得启动。
    elform_position = normalized_lines.index(EXPECTED_ELEMENT_FORM_COMMAND)  # 定位扰动单元矩阵形成命令供处理器连续性检查。
    modal_solve_position = normalized_lines.index(EXPECTED_MODAL_SOLVE_COMMAND)  # 定位实际模态求解命令供处理器连续性检查。
    require("FINISH" not in normalized_lines[elform_position + 1 : modal_solve_position], "SOLVE,ELFORM 与模态 SOLVE 之间出现 FINISH，线性扰动处理器连续性失效")  # 防止尾段漂移切断扰动分析状态。
    qa_begin_marker = "! C10_MODAL_NUMERICAL_QA_BEGIN"  # 冻结 APDL Math 数值 QA 块唯一开始标记。
    qa_end_marker = "! C10_MODAL_NUMERICAL_QA_END"  # 冻结 APDL Math 数值 QA 块唯一结束标记。
    require(normalized_lines.count(qa_begin_marker) == 1 and normalized_lines.count(qa_end_marker) == 1, "APDL Math 数值 QA 起止标记不是各唯一一处")  # 重复或缺失块均无法证明证据来源。
    qa_begin_position = normalized_lines.index(qa_begin_marker)  # 定位 QA 块开始行供范围约束。
    qa_end_position = normalized_lines.index(qa_end_marker)  # 定位 QA 块结束行供范围约束。
    require(qa_begin_position < qa_end_position, "APDL Math 数值 QA 起止标记顺序无效")  # 结束标记必须严格晚于开始标记。
    qa_lines = normalized_lines[qa_begin_position + 1 : qa_end_position]  # 提取标记内部命令，防止同名字符串在块外伪造通过。
    required_qa_commands = (  # 这些 APDL Math 命令共同生成八十阶频率、Gram 矩阵和逐阶特征残差证据。
        "*DIM,C10_QF,ARRAY,80",  # 分配恰好八十项官方频率数组。
        "*GET,C10_QF(C10QI),MODE,C10QI,FREQ",  # 按阶读取求解器官方频率。
        f"*SMAT,C10QM,D,IMPORT,FULL,{jobname}.full,MASS",  # 从同 jobname FULL 导入约束质量矩阵。
        f"*SMAT,C10QK,D,IMPORT,FULL,{jobname}.full,STIFF",  # 从同 jobname FULL 导入切线刚度矩阵。
        f"*SMAT,C10QMAP,D,IMPORT,FULL,{jobname}.full,NOD2SOLV",  # 从同 jobname FULL 导入官方自由度映射。
        f"*DMAT,C10QPHI,D,IMPORT,MODE,{jobname}.mode",  # 从同 jobname MODE 导入全部模态向量。
        "*MULT,C10QSPHI,TRANS,C10QMPHI,,C10QGRAM",  # 形成质量 Gram 矩阵 ΦᵀMΦ。
        "*EXPORT,C10QGRAM,CSV,c10_modal_mass_orthogonality.csv,16",  # 以十六位小数导出完整 80×80 正交矩阵。
        "*CFOPEN,c10_modal_eigen_residuals,csv",  # 打开逐阶特征方程残差 CSV。
        "*AXPY,-C10QLAM,0,C10QMP,1,0,C10QR",  # 形成 r=Kφ−λMφ 的逐阶残差向量。
        "C10QREL=C10QRN/C10QDEN",  # 形成 finalizer 使用的无量纲尺度化残差。
        "*VWRITE,C10QI,C10_QF(C10QI),C10QLAM,C10QRN,C10QKN,C10QLMN,C10QREL",  # 导出阶次、频率、特征值与残差七列证据。
        "(F8.0,6(',',E24.16))",  # 固定与 *VWRITE 相邻的双精度 CSV 格式行。
        "/COM,STATUS=NUMERICAL_QA_ARTIFACTS_GENERATED EXTERNAL_THRESHOLDS_PENDING",  # 明确 MAPDL 仅生成证据，外部阈值仍待复核。
    )  # 完成 APDL Math QA 必需命令集合。
    for command in required_qa_commands:  # 逐条核对命令确实位于唯一 QA 标记内部。
        require(qa_lines.count(command) == 1, f"APDL Math QA 命令必须在 QA 块内恰好一处：{command}，实际={qa_lines.count(command)}")  # 缺失或重复均拒绝启动。
    require(qa_lines.count("*DO,C10QI,1,80,1") == 2, f"APDL Math QA 的八十阶循环必须精确两处，实际={qa_lines.count('*DO,C10QI,1,80,1')}")  # 一次读取频率、一次计算残差，二者均不得缺失。
    residual_write_position = qa_lines.index("*VWRITE,C10QI,C10_QF(C10QI),C10QLAM,C10QRN,C10QKN,C10QLMN,C10QREL")  # 定位逐阶残差写出命令。
    require(residual_write_position + 1 < len(qa_lines), "残差 *VWRITE 后缺少裸 Fortran 格式行")  # 先关闭数组越界门再读取后一行。
    require(qa_lines[residual_write_position + 1] == "(F8.0,6(',',E24.16))", "残差 *VWRITE 与裸 Fortran 格式行不再相邻")  # APDL 要求格式行紧邻，否则输出合同失效。


def validate_manifest_and_inputs(run_dir: Path) -> dict[str, Any]:  # run_dir 是未启动隔离 run，返回已闭合 manifest 和启动路径证据。
    """复核准备状态、全账本、同 jobname 四种子、主输入、二进制和冻结 SMP1 参数。"""  # 任一不一致均发生在 Popen 前。
    runtime_launch_path = run_dir / RUNTIME_LAUNCH_NAME  # 定位首次启动回执目标。
    runtime_status_path = run_dir / RUNTIME_STATUS_NAME  # 定位首次运行状态目标。
    launch_claim_path = run_dir / LAUNCH_CLAIM_NAME  # 定位 Popen 前并发互斥声明目标。
    launch_failure_path = run_dir / LAUNCH_FAILURE_NAME  # 定位既有启动异常记录目标。
    require(not runtime_launch_path.exists() and not runtime_status_path.exists() and not launch_claim_path.exists() and not launch_failure_path.exists(), "本模态 run 已存在启动声明、回执、失败记录或运行状态，拒绝二次启动")  # 保证一个 run 只启动一次。
    manifest = read_json(run_dir / MANIFEST_NAME)  # 读取 prepare 冻结的共享合同。
    status = read_json(run_dir / STATUS_NAME)  # 读取 prepare 根状态。
    require(type(manifest.get("schema_version")) is int and manifest.get("schema_version") == EXPECTED_SCHEMA_VERSION, "manifest.schema_version 不是批准的整数首版合同")  # 严格拒绝布尔值、旧版或未知新版 schema。
    require(type(status.get("schema_version")) is int and status.get("schema_version") == EXPECTED_SCHEMA_VERSION, "status.schema_version 不是批准的整数首版合同")  # manifest 与根状态必须采用同一 schema。
    require(manifest.get("run_name") == run_dir.name and status.get("run_name") == run_dir.name, "manifest/status.run_name 与目录名不一致")  # 防止复制改名借用状态。
    require(manifest.get("status") == EXPECTED_PREPARE_STATUS and status.get("status") == EXPECTED_PREPARE_STATUS, "模态 run 不是精确 PREPARED 状态")  # 只允许首次从准备态启动。
    require(manifest.get("execution_mode") == EXPECTED_EXECUTION_MODE and status.get("execution_mode") == EXPECTED_EXECUTION_MODE, "模态 run 执行模式不是批准的 SMP1 诊断")  # 阻断 DMP 或多进程漂移。
    require(manifest.get("production") is False and manifest.get("valid_for_production") is False and status.get("production") is False and status.get("valid_for_production") is False, "模态准备证据存在生产用途真值")  # 用途标志必须持续为假。
    static_load_path_mode = manifest.get("static_load_path_mode")  # 读取 prepare 从静力 manifest/final status/verification 三方闭合后冻结的荷载路径模式。
    require(isinstance(static_load_path_mode, str) and bool(static_load_path_mode.strip()), "manifest.static_load_path_mode 缺失或不是非空字符串")  # 模态续算必须保留可审计的静力基态路径身份。
    resource_gates = manifest.get("resource_gates")  # 读取启动瞬间必须复测的资源硬门对象。
    require(isinstance(resource_gates, dict) and resource_gates == EXPECTED_RESOURCE_GATES, f"manifest.resource_gates 未精确冻结 8 GiB/40 GiB/无例外合同：{resource_gates!r}")  # 同时拒绝非对象、字段缺失、额外字段或阈值漂移。
    require(resource_gates.get("exceptions_allowed") is False, "manifest.resource_gates.exceptions_allowed 必须是 JSON 布尔 false")  # 显式阻断数值零利用 Python 等值语义冒充无例外布尔值。
    require(type(manifest.get("modes_requested")) is int and manifest.get("modes_requested") == EXPECTED_MODES, "manifest.modes_requested 不是精确整数 80")  # 布尔值或其他阶数不得进入执行。
    require(manifest.get("frequency_bounds_hz") is None, "manifest.frequency_bounds_hz 必须为 null，禁止频带截断八十阶")  # 第一轮从最低阶起且不设置上下限。
    require(manifest.get("restart_command") == EXPECTED_RESTART_COMMAND, "manifest.restart_command 不是精确 LS2/子步1 PERTURB 入口")  # 阻断自动最高子步或其他基态混入。
    require(manifest.get("perturb_command") == EXPECTED_PERTURB_COMMAND, "manifest.perturb_command 不是冻结的 MODAL/AUTO/CURRENT/PARKEEP 合同")  # 阻断扰动类型、切线或载荷处理语义漂移。
    require(manifest.get("element_form_command") == EXPECTED_ELEMENT_FORM_COMMAND, "manifest.element_form_command 不是精确 SOLVE,ELFORM")  # 扰动单元矩阵形成步骤不得省略。
    require(manifest.get("mass_matrix_command") == EXPECTED_MASS_MATRIX_COMMAND, "manifest.mass_matrix_command 不是精确 LUMPM,OFF")  # 一致质量矩阵选择必须由 prepare 明文冻结。
    require(manifest.get("modal_solver_command") == EXPECTED_MODAL_SOLVER_COMMAND, "manifest.modal_solver_command 不是精确 MODOPT,LANB,80")  # 算法和阶数必须共同冻结。
    require(manifest.get("mode_expansion_command") == EXPECTED_MODE_EXPANSION_COMMAND, "manifest.mode_expansion_command 不是精确 MXPAND,80,,,YES")  # 八十阶展开和单元结果保存不得漂移。
    require(manifest.get("modal_outres_commands") == EXPECTED_MODAL_OUTRES_COMMANDS, f"manifest.modal_outres_commands 不是批准的有序三条输出合同：{manifest.get('modal_outres_commands')!r}")  # 字段数量、顺序或内容任何变化均拒绝。
    require(manifest.get("modal_solve_command") == EXPECTED_MODAL_SOLVE_COMMAND, "manifest.modal_solve_command 不是精确 SOLVE")  # 正式模态求解命令必须由 prepare 单独冻结。
    require(manifest.get("numerical_qa_contract") == EXPECTED_NUMERICAL_QA_CONTRACT, f"manifest.numerical_qa_contract 与批准的残差/正交/刚体合同不一致：{manifest.get('numerical_qa_contract')!r}")  # 缺字段、阈值变化或定义变化均在长时求解前拒绝。
    require(manifest.get("launch_allowed_after_execute_preflight_only") is True and manifest.get("mapdl_execution_attempted") is False and manifest.get("mapdl_started") is False, "manifest 的启动授权或 prepare 未执行事实不闭合")  # prepare 必须明确未启动，且启动只能由本预检授权。
    require(status.get("modal_status") == "NOT_RUN" and status.get("restart_seed_status") == "FOUR_REQUIRED_ARTIFACTS_COPIED_AND_HASH_CLOSED", "准备状态未证明模态未运行或四项种子已闭合")  # 根状态必须与 manifest 的首次执行语义一致。
    records = validate_prepare_ledger(run_dir)  # 全量复算 prepare 发布后的文件集合与摘要。
    solver_dir = (run_dir / "solver").resolve()  # 规范化隔离 solver 工作目录。
    require(solver_dir.is_dir() and solver_dir.parent == run_dir, "模态 solver 目录缺失或不属于本 run")  # 工作目录必须唯一隔离。
    main_input = (run_dir / str(manifest.get("main_input"))).resolve()  # 解析冻结主输入相对路径。
    require(main_input.parent == solver_dir and main_input.is_file(), "模态主输入不在本 run solver 或不存在")  # -i 只能指向本 run 输入。
    require(sha256_file(main_input) == manifest.get("main_input_sha256"), "模态主输入 SHA-256 与 manifest 不一致")  # 再次闭合实际执行字节。
    jobname = manifest.get("jobname")  # 读取必须与四种子和 -j 同值的作业名。
    require(isinstance(jobname, str) and jobname, "manifest.jobname 缺失")  # 作业名必须非空。
    require(jobname.strip() == jobname and re.fullmatch(r"[A-Za-z0-9_]+", jobname) is not None, "manifest.jobname 含首尾空白或 APDL 文件字段不安全字符")  # 只允许 ASCII 字母、数字和下划线，阻断路径、逗号与命令注入。
    require(len(jobname) + len(".full") <= 32 and len(jobname) + len(".mode") <= 32, "manifest.jobname 与 .full/.mode 后缀组合超过 APDL Math 三十二字符文件字段上限")  # FULL 与 MODE 导入字段均必须满足 APDL Math 长度约束。
    main_text = main_input.read_text(encoding="utf-8")  # 只在哈希闭合后读取实际 APDL 字节供完整命令合同复核。
    validate_main_input_contract(main_text, jobname)  # 证明实际执行文本与 manifest 的八十阶、重启动和 QA 合同共同一致。
    restart_records = manifest.get("restart_artifacts")  # 读取四项复制种子记录。
    require(isinstance(restart_records, list) and len(restart_records) == 4, "manifest.restart_artifacts 不是四项")  # 数量必须精确闭合。
    seen_suffixes: set[str] = set()  # 初始化已验证后缀集合。
    for record in restart_records:  # 逐项复核同 jobname 文件名、路径、大小和 SHA-256。
        require(isinstance(record, dict), "restart_artifacts 含非对象记录")  # 每项必须是结构化记录。
        suffix = record.get("suffix")  # 读取合同后缀。
        require(isinstance(suffix, str) and suffix in REQUIRED_RESTART_SUFFIXES and suffix not in seen_suffixes, f"重启动后缀缺失、重复或未批准：{suffix}")  # 每种后缀恰好一次。
        target = (run_dir / str(record.get("copied_path"))).resolve()  # 解析隔离复制件相对路径。
        require(target.parent == solver_dir and target.name.lower() == f"{jobname}{suffix}".lower(), f"重启动复制件路径或同 jobname 文件名不匹配：{target}")  # 路径和命名均需精确。
        require(target.is_file() and target.stat().st_size == record.get("size_bytes") and target.stat().st_size > 0, f"重启动复制件缺失、为空或大小漂移：{target.name}")  # 关闭截断门。
        require(sha256_file(target) == record.get("sha256"), f"重启动复制件 SHA-256 漂移：{target.name}")  # 关闭内容门。
        seen_suffixes.add(suffix)  # 登记当前后缀已经唯一闭合。
    require(seen_suffixes == REQUIRED_RESTART_SUFFIXES, f"四项重启动后缀集合不闭合：{sorted(seen_suffixes)}")  # 最终集合必须精确一致。
    executable = Path(str(manifest.get("mapdl_executable"))).resolve()  # 解析冻结 MAPDL 二进制绝对路径。
    require(executable.is_file(), f"MAPDL 可执行文件不存在：{executable}")  # 启动前确认二进制仍存在。
    require(sha256_file(executable) == manifest.get("mapdl_executable_sha256"), "MAPDL 可执行文件 SHA-256 漂移")  # 版本或补丁变化即拒绝。
    launch_argv = manifest.get("launch_argv")  # 读取 prepare 冻结的完整参数数组。
    require(isinstance(launch_argv, list) and all(isinstance(value, str) for value in launch_argv), "manifest.launch_argv 不是字符串数组")  # 禁止动态拼接未知类型参数。
    expected_argv = [str(executable), "-b", "-smp", "-np", "1", "-j", jobname, "-dir", str(solver_dir), "-i", str(main_input), "-o", str(solver_dir / f"{jobname}.out")]  # 重新构造唯一批准的 SMP1 命令。
    require(launch_argv == expected_argv, "manifest.launch_argv 不等于重新构造的精确 SMP1 命令")  # 阻断参数顺序、模式或路径漂移。
    require(not any(solver_dir.glob("*.lock")), "模态 solver 目录已存在 MAPDL lock 文件")  # 防止未登记进程或旧崩溃状态被覆盖。
    return {"manifest": manifest, "status": status, "records": records, "solver_dir": solver_dir, "main_input": main_input, "executable": executable, "launch_argv": expected_argv}  # 返回启动所需的全部已闭合对象。


def persist_post_launch_incomplete(run_dir: Path, claim_payload: dict[str, Any], main_pid: int, reason: str) -> list[str]:  # 输入 run、现有 claim、已启动 PID 和首错；返回补写时的次级错误。
    """把 Popen 后任何回执事务失败同时写入带 PID 的权威 claim 和独占 failure 文件。"""  # 原 claim 已存在并永久阻断自动重启。
    failed_at = datetime.now(timezone.utc).isoformat()  # 为 claim 与 failure 文件共用同一个 UTC 失败时点。
    recording_errors: list[str] = []  # 收集补写过程自身异常，避免覆盖首个回执错误。
    incomplete_claim = dict(claim_payload)  # 复制当前已占有 claim，保留预检资源和 execute 身份。
    incomplete_claim.update({"main_pid": main_pid, "launch_state": "MAPDL_STARTED_RUNTIME_RECEIPTS_INCOMPLETE_RESTART_FORBIDDEN", "receipt_failure_at_utc": failed_at, "receipt_failure_reason": reason, "restart_forbidden": True})  # 形成包含正 PID 和不可重启语义的权威不完整状态。
    try:  # 优先原子推进已存在 claim，使即使新文件创建失败也保留 PID。
        replace_json_atomic(run_dir / LAUNCH_CLAIM_NAME, incomplete_claim)  # 把旧 claim 一次性替换为完整的 Popen 后失败状态。
    except Exception as claim_exc:  # 磁盘、权限或外部干预可能阻止 claim 原子更新。
        recording_errors.append(f"更新带 PID 的启动 claim 失败：{claim_exc}")  # 保存次级异常供 CLI 和 failure 文件共同报告。
    failure_payload = {  # 构造第二份独占失败记录，为 claim 更新失败提供不同文件名的补救路径。
        "schema_version": EXPECTED_SCHEMA_VERSION,  # 与当前模态执行合同使用相同首版 schema。
        "run_name": run_dir.name,  # 绑定发生回执失败的隔离运行目录。
        "jobname": claim_payload["jobname"],  # 绑定 Popen 实际使用的冻结作业名。
        "status": "MAPDL_STARTED_RUNTIME_RECEIPTS_INCOMPLETE_RESTART_FORBIDDEN",  # 明确进程已启动，禁止误当作启动前拒绝后重试。
        "main_pid": main_pid,  # 保存 Popen 返回的正整数包装进程 PID。
        "failed_at_utc": failed_at,  # 保存首个回执事务失败时间。
        "reason": reason,  # 保存触发补写的原始回执事务异常。
        "claim_update_errors": list(recording_errors),  # 把写 failure 前已知的 claim 更新异常一并封存。
        "runtime_launch_exists": (run_dir / RUNTIME_LAUNCH_NAME).exists(),  # 说明正式启动回执是否已创建或留下占位文件。
        "runtime_status_exists": (run_dir / RUNTIME_STATUS_NAME).exists(),  # 说明运行状态回执是否已创建或留下占位文件。
        "restart_forbidden": True,  # 机器可读地禁止任何自动或人工无审查二次 Popen。
        "production": False,  # 回执失败不改变诊断用途边界。
        "valid_for_production": False,  # 与全链非生产字段保持一致。
    }  # 完成独占 Popen 后失败回执对象。
    try:  # 无论 claim 更新是否成功都尝试写出独立 failure 记录，形成双路径证据。
        write_json_exclusive(run_dir / LAUNCH_FAILURE_NAME, failure_payload)  # 独占创建且强制刷新带 PID 的失败回执。
    except Exception as failure_exc:  # 目标已存在、磁盘失败或权限错误进入该路径。
        recording_errors.append(f"写入带 PID 的启动 failure 回执失败：{failure_exc}")  # 把第二路径错误返回给结构化 CLI 输出。
    return recording_errors  # 空列表表示 claim 与 failure 两份带 PID 证据均已成功持久化。


def execute_modal(run_dir: Path) -> dict[str, Any]:  # run_dir 是规范未启动模态目录，返回异步启动 PID 与资源证据。
    """全部静态身份门通过后再实测进程、RAM、磁盘，最后执行一次 Popen。"""  # 资源不足时绝不启动。
    evidence = validate_manifest_and_inputs(run_dir)  # 在读取实时资源前先关闭全部准备态身份门。
    conflicts = active_solver_processes(evidence["manifest"]["jobname"], evidence["solver_dir"])  # 只枚举实际 MAPDL 或有命令行/父子链证据的 MPI 冲突。
    require(not conflicts, f"存在冲突求解器/MPI 进程，禁止启动：{json.dumps(conflicts, ensure_ascii=False)}")  # 任一冲突进程均硬拒绝。
    memory = psutil.virtual_memory()  # 获取当前系统物理内存快照。
    available_ram = int(memory.available)  # 读取可供新进程使用的实时物理内存字节数。
    require(available_ram >= MIN_AVAILABLE_RAM_BYTES, f"可用 RAM {available_ram} bytes 低于硬门 {MIN_AVAILABLE_RAM_BYTES} bytes，未启动")  # 低于 8 GiB 不允许例外。
    disk = shutil.disk_usage(evidence["solver_dir"])  # 获取隔离 solver 所在卷的实时容量快照。
    free_disk = int(disk.free)  # 读取可供模态输出使用的实时空闲字节数。
    require(free_disk >= MIN_FREE_DISK_BYTES, f"solver 卷空闲空间 {free_disk} bytes 低于硬门 {MIN_FREE_DISK_BYTES} bytes，未启动")  # 低于 40 GiB 不允许例外。
    checked_at = datetime.now(timezone.utc).isoformat()  # 记录全部实时门通过后的 UTC 启动时点。
    claim_payload = {"schema_version": EXPECTED_SCHEMA_VERSION, "run_name": run_dir.name, "jobname": evidence["manifest"]["jobname"], "status": "LAUNCH_CLAIMED_AFTER_ALL_PREFLIGHT_GATES", "launch_state": "PREFLIGHT_PASSED_POPEN_NOT_YET_RETURNED", "claimed_at_utc": checked_at, "execute_pid": int(psutil.Process().pid), "main_pid": None, "available_ram_bytes": available_ram, "free_disk_bytes": free_disk, "restart_forbidden": True, "production": False, "valid_for_production": False}  # 构造 Popen 前启动所有权、资源证据和明确未获 MAPDL PID 状态。
    write_json_exclusive(run_dir / LAUNCH_CLAIM_NAME, claim_payload)  # 独占占有本 run 启动权；并发第二个 execute 将在 Popen 前失败。
    creation_flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))  # Windows 使用无窗口标志，非 Windows 测试环境回退为零。
    try:  # 单独捕获 Popen 异常并保留不可覆盖的失败回执。
        process = subprocess.Popen(evidence["launch_argv"], cwd=evidence["solver_dir"], creationflags=creation_flags)  # 仅此一行真正异步启动冻结的 SMP1 MAPDL 命令。
    except Exception as launch_exc:  # 可执行文件、许可证包装或操作系统启动失败进入此路径。
        failed_at = datetime.now(timezone.utc).isoformat()  # 记录操作系统未返回 MAPDL PID 的失败时点。
        failed_claim = dict(claim_payload)  # 复制已独占 claim 以原子推进 Popen 失败状态。
        failed_claim.update({"launch_state": "POPEN_FAILED_NO_MAPDL_PID_RECORDED_REVIEW_REQUIRED", "popen_failed_at_utc": failed_at, "popen_failure_reason": str(launch_exc), "restart_forbidden": True})  # 明确没有成功 PID，但仍禁止无审查重试。
        recording_errors: list[str] = []  # 收集 Popen 失败证据补写异常，避免掩盖原始操作系统错误。
        try:  # 优先把权威 claim 从 Popen 待定推进为明确未获得 PID。
            replace_json_atomic(run_dir / LAUNCH_CLAIM_NAME, failed_claim)  # 原子保存 Popen 失败状态和原因。
        except Exception as claim_exc:  # claim 推进失败时原独占文件仍持续阻断并发重启。
            recording_errors.append(f"更新 Popen 失败 claim 失败：{claim_exc}")  # 记录次级异常供最终错误文本审计。
        failure_payload = {"schema_version": EXPECTED_SCHEMA_VERSION, "run_name": run_dir.name, "jobname": evidence["manifest"]["jobname"], "status": "POPEN_FAILED_AFTER_PREFLIGHT_NO_MAPDL_PID_RECORDED_REVIEW_REQUIRED", "main_pid": None, "failed_at_utc": failed_at, "reason": str(launch_exc), "claim_update_errors": list(recording_errors), "restart_forbidden": True, "production": False, "valid_for_production": False}  # 构造明确不含成功 PID 且禁止自动重试的失败证据。
        try:  # 独立文件为 claim 更新失败提供第二条持久化路径。
            write_json_exclusive(run_dir / LAUNCH_FAILURE_NAME, failure_payload)  # 保留 Popen 失败记录并由 claim 阻断未经审查的自动重试。
        except Exception as failure_exc:  # 磁盘或权限异常可能阻止第二份失败证据写入。
            recording_errors.append(f"写入 Popen 失败回执失败：{failure_exc}")  # 保存次级异常且不把它误报为 Popen 成功。
        if recording_errors:  # 证据补写有异常时把原始 Popen 原因和全部次级错误共同上报。
            raise RuntimeError(f"Popen 未返回 MAPDL PID：{launch_exc}；失败证据补写异常：{recording_errors}") from launch_exc  # 保持因果链并返回非零状态。
        raise  # 两份失败证据均成功时把原始 Popen 异常交给 CLI 输出非零状态。
    main_pid = int(process.pid)  # Popen 已成功返回正整数包装进程 PID，此后任何异常都属于启动后回执失败。
    popen_returned_at = datetime.now(timezone.utc).isoformat()  # 记录操作系统成功创建进程并返回 PID 的独立 UTC 时点。
    pid_claim = dict(claim_payload)  # 复制 Popen 前 claim 以加入不可丢失的 PID 和待提交状态。
    pid_claim.update({"main_pid": main_pid, "launch_state": "MAPDL_STARTED_RUNTIME_RECEIPTS_PENDING_RESTART_FORBIDDEN", "popen_returned_at_utc": popen_returned_at, "restart_forbidden": True})  # 明确进程已启动且正式回执仍待完成。
    try:  # 在构造或写入任何其他回执前，优先把正 PID 原子持久化到权威 claim。
        replace_json_atomic(run_dir / LAUNCH_CLAIM_NAME, pid_claim)  # 原子推进 claim，保证后续回执失败仍可定位已启动进程。
    except Exception as claim_exc:  # 首次带 PID claim 写入失败时立即尝试独立 failure 文件补救。
        reason = f"MAPDL PID {main_pid} 已启动，但带 PID 的启动 claim 持久化失败：{claim_exc}"  # 构造不可误解为未启动的首错文本。
        recording_errors = persist_post_launch_incomplete(run_dir, claim_payload, main_pid, reason)  # 再尝试 claim 与独立 failure 双路径写入 PID。
        raise PostLaunchReceiptError(main_pid, reason, recording_errors) from claim_exc  # 以专用异常让 CLI 输出结构化 PID 和禁止重启状态。
    try:  # 从此处起任一构造、写入或 claim 完成更新异常都必须进入带 PID 的不完整回执路径。
        launch_payload = {  # 构造绑定 PID、资源、源码和精确参数的正式启动回执。
            "schema_version": EXPECTED_SCHEMA_VERSION,  # 本模态 execute 首版回执 schema。
            "run_name": run_dir.name,  # 绑定隔离运行身份。
            "jobname": evidence["manifest"]["jobname"],  # 绑定保持不变的静力作业名。
            "status": "RUNNING_UNFINALIZED",  # 仅表示进程已启动且尚未最终化。
            "started_at_utc": popen_returned_at,  # 使用 Popen 实际返回 PID 的时点而非较早资源检查时点。
            "main_pid": main_pid,  # 记录 Popen 返回的包装进程 PID。
            "execution_mode": EXPECTED_EXECUTION_MODE,  # 明确首轮 SMP1 诊断模式。
            "launch_argv": evidence["launch_argv"],  # 原样记录实际传入 Popen 的参数数组。
            "cwd": str(evidence["solver_dir"]),  # 记录实际工作目录。
            "resource_preflight": {  # 保存启动瞬间两项硬门和冲突进程事实。
                "available_ram_bytes": available_ram,  # 实测可用 RAM 字节数。
                "available_ram_min_bytes": MIN_AVAILABLE_RAM_BYTES,  # 8 GiB 硬门字节数。
                "available_ram_gate_passed": True,  # 只有通过后才可能生成本回执。
                "free_disk_bytes": free_disk,  # 实测 solver 卷空闲字节数。
                "free_disk_min_bytes": MIN_FREE_DISK_BYTES,  # 40 GiB 硬门字节数。
                "free_disk_gate_passed": True,  # 只有通过后才可能生成本回执。
                "conflicting_solver_process_count": 0,  # 启动前具有 MAPDL 身份证据的冲突进程数为零。
            },  # 完成启动前资源证据对象。
            "prepare_ledger_sha256": sha256_file(run_dir / LEDGER_NAME),  # 记录已经全量复算的准备态账本摘要。
            "main_input_sha256": evidence["manifest"]["main_input_sha256"],  # 记录实际主输入摘要。
            "mapdl_executable_sha256": evidence["manifest"]["mapdl_executable_sha256"],  # 记录实际 MAPDL 二进制摘要。
            "execute_script_sha256": sha256_file(SCRIPT_PATH),  # 记录真正启动本进程的 execute 源码摘要。
            "production": False,  # 启动不改变诊断用途边界。
            "valid_for_production": False,  # 与全链状态字段保持一致的非生产标志。
            "finalizer_required": True,  # 明确 PID 启动或退出都不构成结果通过。
        }  # 完成异步启动回执对象。
        runtime_status = {"schema_version": EXPECTED_SCHEMA_VERSION, "run_name": run_dir.name, "jobname": evidence["manifest"]["jobname"], "status": "RUNNING_UNFINALIZED", "main_pid": main_pid, "modal_status": "RUNNING", "production": False, "valid_for_production": False, "next_action": "WAIT_FOR_PROCESS_EXIT_THEN_RUN_ULTRA_C10_MODAL_FINALIZE"}  # 构造简洁运行状态且不冒充完成。
        write_json_exclusive(run_dir / RUNTIME_LAUNCH_NAME, launch_payload)  # 独占发布并强制刷新首次启动回执，拒绝二次启动覆盖。
        write_json_exclusive(run_dir / RUNTIME_STATUS_NAME, runtime_status)  # 独占发布并强制刷新人机共享的运行中状态。
        completed_claim = dict(pid_claim)  # 复制已含 PID 的 claim 以记录两份正式回执均已落盘。
        completed_claim.update({"launch_state": "MAPDL_STARTED_RUNTIME_RECEIPTS_COMPLETE", "receipts_completed_at_utc": datetime.now(timezone.utc).isoformat(), "runtime_launch_name": RUNTIME_LAUNCH_NAME, "runtime_status_name": RUNTIME_STATUS_NAME})  # 形成成功提交状态且保留永久禁止二次启动语义。
        replace_json_atomic(run_dir / LAUNCH_CLAIM_NAME, completed_claim)  # 原子推进 claim，读者不会看到半写的完成状态。
    except Exception as receipt_exc:  # 捕获 payload 构造、哈希、任一文件写入或 claim 完成替换异常。
        reason = f"MAPDL PID {main_pid} 已启动，但启动回执事务未完整提交：{receipt_exc}"  # 构造含 PID 的不可歧义首错文本。
        recording_errors = persist_post_launch_incomplete(run_dir, pid_claim, main_pid, reason)  # 把 claim 和独立 failure 文件推进为禁止重启的不完整状态。
        raise PostLaunchReceiptError(main_pid, reason, recording_errors) from receipt_exc  # 以专用非零状态阻止编排器误判未启动后重试。
    return {"status": "RUNNING_UNFINALIZED", "run_dir": str(run_dir), "jobname": evidence["manifest"]["jobname"], "main_pid": int(process.pid), "available_ram_bytes": available_ram, "free_disk_bytes": free_disk, "production": False}  # 返回调用方所需的最小启动摘要。


def main(argv: list[str] | None = None) -> int:  # argv 是可选 CLI 参数；返回零为已启动、二为启动前/Popen 失败、三为已启动但回执不完整。
    """执行一次性 SMP1 启动入口并打印机器可读结果。"""  # 本函数不等待求解完成。
    try:  # 统一捕获全部身份、资源和启动异常。
        args = parse_args(argv)  # 解析显式模态 run 目录。
        run_dir = normalize_run_dir(Path(args.run_dir))  # 规范化并限制运行范围。
        result = execute_modal(run_dir)  # 通过全部硬门后异步启动一次 MAPDL。
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))  # 输出 PID 和资源证据。
        return 0  # 零码仅表示进程成功启动并记录，不表示求解成功。
    except PostLaunchReceiptError as exc:  # 专门捕获 Popen 已返回 PID 后的回执事务异常，禁止混同启动前拒绝。
        failure = {"status": "MAPDL_STARTED_RUNTIME_RECEIPTS_INCOMPLETE_RESTART_FORBIDDEN", "main_pid": exc.main_pid, "reason": exc.reason, "recording_errors": exc.recording_errors, "restart_forbidden": True, "production": False, "valid_for_production": False}  # 输出含 PID、首错和补写错误的机器可读不完整回执。
        print(json.dumps(failure, ensure_ascii=False, indent=2, allow_nan=False))  # 即使磁盘两条补写路径异常，标准输出仍保留已启动 PID。
        return 3  # 独立非零码告诉编排器不得自动重跑 Popen，也不得把它当作求解完成。
    except Exception as exc:  # 捕获 Popen 前后的全部异常并返回明确原因。
        failure = {"status": "MODAL_EXECUTE_REJECTED_OR_FAILED", "reason": str(exc), "production": False}  # 构造不含通过语义的失败对象。
        print(json.dumps(failure, ensure_ascii=False, indent=2, allow_nan=False))  # 输出具体失败门或启动异常。
        return 2  # 非零码阻止编排器误调用 finalizer。


if __name__ == "__main__":  # 仅直接调用时执行 CLI，导入不会启动任何进程。
    raise SystemExit(main())  # 把 main 返回码传递给操作系统。
