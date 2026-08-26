from __future__ import annotations  # 启用延迟类型求值，使 Python 3.10 及以上环境可稳定解析本脚本的类型标注。

import argparse  # 解析唯一允许的父准备运行参数，防止脚本自动猜测或错配输入包。
import hashlib  # 计算输入、求解器、输出和结果文件的 SHA-256，保证运行前后字节身份可追溯。
import json  # 读取准备计划并写出不含伪注释的合法机器记录。
import re  # 从 MAPDL 文本输出中提取错误数、警告数和每次组装的方程数。
import shutil  # 把冻结输入复制到独立案例目录，同时保留源文件时间信息。
import subprocess  # 以参数数组方式串行调用 MAPDL，避免经过命令行 shell 拼接。
from datetime import datetime, timezone  # 生成唯一 UTC 运行名并记录每个案例的起止时刻。
from pathlib import Path  # 以可处理中文路径的对象方式定位项目、父运行和执行工件。
from typing import Any  # 表达异构 JSON 对象、案例字典和进程记录的值类型。

import psutil  # 在启动前精确检查是否已有 MAPDL 或 MPI 求解进程占用资源。

BASE_DIR = Path(__file__).resolve().parents[1]  # 将脚本父级的父级固定为本项目 V2.0 根目录。
RUNS_ROOT = BASE_DIR / "ultra_runs"  # 将所有新运行限定在既有不可覆盖的 ultra_runs 证据目录中。
MAPDL_EXE = Path(r"D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe")  # 固定使用已登记的 ANSYS 2026 R1 MAPDL 可执行文件。
EXPECTED_CASE_COUNT = 12  # 新单层约束合同包含三项 UXYZ 载荷、三项有限转动和六项 ALL 载荷，共十二项。
CASE_TIMEOUT_SECONDS = 300  # 每个仅含少量单元的微算例最多允许运行五分钟，超时即停止该案例并保留证据。
MAPDL_PROCESS_NAMES = {"ansys.exe", "ansys261.exe", "mapdl.exe", "mapdl261.exe", "mpiexec.exe", "hydra_service.exe", "hydra_pmi_proxy.exe"}  # 列出会与本次串行求解冲突的求解器及 MPI 进程名。
ERROR_COUNT_PATTERN = re.compile(r"NUMBER OF ERROR MESSAGES ENCOUNTERED\s*=\s*(\d+)", re.IGNORECASE)  # 匹配 MAPDL 页尾累计错误数并提取非负整数。
WARNING_COUNT_PATTERN = re.compile(r"NUMBER OF WARNING MESSAGES ENCOUNTERED\s*=\s*(\d+)", re.IGNORECASE)  # 匹配 MAPDL 页尾累计警告数并提取非负整数。
EQUATION_COUNT_PATTERN = re.compile(r"NUMBER OF EQUATIONS\s*=\s*(\d+)", re.IGNORECASE)  # 匹配每次矩阵组装报告的方程总数以检查迭代中依赖自由度是否切换。


def require(condition: bool, message: str) -> None:  # 接收必须成立的布尔条件和失败说明；失败时阻断运行且无返回值。
    if not condition:  # 仅在身份、范围或求解前门禁不满足时进入拒绝路径。
        raise RuntimeError(message)  # 抛出明确异常，确保错误输入不会继续调用 MAPDL。


def sha256_file(path: Path) -> str:  # 接收现有文件路径并返回完整二进制内容的六十四位小写 SHA-256。
    digest = hashlib.sha256()  # 为当前文件创建独立哈希累加器，避免不同工件之间状态串扰。
    with path.open("rb") as handle:  # 使用只读二进制模式，避免换行和字符编码改变原始字节。
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):  # 以一 MiB 数据块读取直到文件末尾，控制大文件内存占用。
            digest.update(chunk)  # 把当前原始字节块加入 SHA-256 计算。
    return digest.hexdigest()  # 返回可写入 JSON 和清单的固定长度摘要字符串。


def read_json(path: Path) -> dict[str, Any]:  # 接收 UTF-8 JSON 文件并返回已验证为对象的顶层字典。
    require(path.is_file(), f"缺少 JSON 文件：{path}")  # 在解析前拒绝缺失路径，避免产生含糊的下游异常。
    payload = json.loads(path.read_text(encoding="utf-8"))  # 严格按 UTF-8 读取并解析整个 JSON 文档。
    require(isinstance(payload, dict), f"JSON 顶层不是对象：{path}")  # 禁止数组或标量冒充运行清单。
    return payload  # 返回已通过顶层结构门禁的异构字典。


def write_json(path: Path, payload: dict[str, Any]) -> None:  # 接收目标路径和对象字典并写出稳定、可读且合法的 JSON。
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"  # 保留中文、使用两空格缩进并固定单个末尾换行。
    path.write_text(rendered, encoding="utf-8", newline="\n")  # 以 UTF-8 和 LF 写入；字段说明另存 Markdown，避免破坏 JSON 语法。


def active_solver_processes() -> list[dict[str, Any]]:  # 无输入；返回当前精确匹配的 MAPDL/MPI 进程 PID 与名称列表。
    matches: list[dict[str, Any]] = []  # 初始化冲突进程集合，空列表表示可安全启动串行微算例。
    for process in psutil.process_iter(["pid", "name"]):  # 仅请求进程 PID 和名称两个只读字段，降低枚举成本和权限风险。
        name = str(process.info.get("name") or "").lower()  # 将可能为空的进程名规范为小写字符串以执行精确比较。
        if name in MAPDL_PROCESS_NAMES:  # 只把求解器和 MPI worker 视为冲突，不误伤许可证服务。
            matches.append({"pid": int(process.info["pid"]), "name": name})  # 保存可审计的冲突进程身份。
    return matches  # 返回全部冲突项供启动门禁判定和错误说明使用。


def last_integer(pattern: re.Pattern[str], text_value: str) -> int | None:  # 接收正则和输出文本并返回最后一个匹配整数，未匹配时返回空值。
    matches = pattern.findall(text_value)  # 收集求解过程中所有累计计数，避免误取较早页面的中间值。
    return int(matches[-1]) if matches else None  # 有匹配时返回末项整数，否则用 None 明确表示日志合同缺失。


def make_run_name(created_at: datetime) -> str:  # 接收带时区的 UTC 时刻并返回不会覆盖既有工件的微验证运行名。
    stamp = created_at.strftime("%Y%m%dT%H%M%S%fZ")  # 使用年月日至微秒的 UTC 字符串提供跨进程唯一性。
    return f"C10_MICRO_VALIDATION_{stamp}"  # 添加固定族前缀，使后续验收器能够拒绝错误运行类型。


def execute_case(case: dict[str, Any], prepare_dir: Path, run_dir: Path) -> dict[str, Any]:  # 接收单案例计划、父目录和执行目录并返回完整 MAPDL 原始运行记录。
    case_id = str(case["case_id"])  # 读取稳定案例标识，用于目录、作业名和审计映射。
    case_slug = case_id.lower().replace("-", "_")  # 将连字符改为下划线，生成 MAPDL 和 Windows 均安全的短名称。
    case_dir = run_dir / case_slug  # 为每个案例分配独立工作目录，隔离数据库、锁文件和结果文本。
    case_dir.mkdir(parents=False, exist_ok=False)  # 新建且禁止复用案例目录，杜绝覆盖历史或混合输出。
    source_input = prepare_dir / str(case["input_file"])  # 按冻结计划中的相对路径定位权威微算例输入。
    require(source_input.is_file(), f"案例 {case_id} 缺少父输入：{source_input}")  # 拒绝缺失输入，避免启动空作业。
    source_hash = sha256_file(source_input)  # 在复制前复算父输入字节身份。
    require(source_hash == str(case["input_sha256"]), f"案例 {case_id} 父输入 SHA-256 漂移")  # 只允许执行准备阶段登记的精确字节。
    frozen_input = case_dir / source_input.name  # 为执行子运行指定自包含的冻结输入副本路径。
    shutil.copy2(source_input, frozen_input)  # 复制输入并保留时间元数据，便于独立归档和复算。
    require(sha256_file(frozen_input) == source_hash, f"案例 {case_id} 输入复制后 SHA-256 不一致")  # 确认复制未发生截断或编码变换。
    output_path = case_dir / f"{case_slug}.out"  # 指定本案例完整 MAPDL 标准输出文件。
    result_name = Path(str(case["future_result_file"])).name  # 只取准备合同登记的机器结果文件名，目录由本次运行隔离。
    result_path = case_dir / result_name  # 指定 APDL *CFOPEN 应在独立工作目录生成的数值结果路径。
    jobname = f"c10n_{case_slug}"  # 使用 n 表示新单层拓扑，并保持作业名短于 MAPDL 常见长度限制。
    argv = [str(MAPDL_EXE), "-b", "-smp", "-np", "1", "-j", jobname, "-dir", str(case_dir), "-i", str(frozen_input), "-o", str(output_path)]  # 固定批处理、共享内存和单进程参数以降低微验证资源波动。
    started_at = datetime.now(timezone.utc)  # 在创建外部进程前记录本案例 UTC 开始时刻。
    timed_out = False  # 初始化超时标志；正常完成时保持假值。
    try:  # 进入带硬超时的 MAPDL 同步执行路径。
        completed = subprocess.run(argv, cwd=case_dir, check=False, timeout=CASE_TIMEOUT_SECONDS, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))  # 前台等待案例结束，不经 shell，并在 Windows 隐藏控制台窗口。
        exit_code: int | None = int(completed.returncode)  # 保存 MAPDL 进程退出码；零仅表示进程层完成，不能替代工程门禁。
    except subprocess.TimeoutExpired:  # 仅在五分钟硬上限触发时进入超时证据路径。
        timed_out = True  # 标记该案例未在批准时限内完成。
        exit_code = None  # 超时没有可信正常退出码，因此显式记录空值。
    ended_at = datetime.now(timezone.utc)  # 无论正常或超时，都记录 UTC 结束时刻用于持续时间审计。
    output_exists = output_path.is_file()  # 检查 MAPDL 是否产生标准输出工件。
    output_text = output_path.read_text(encoding="utf-8", errors="replace") if output_exists else ""  # 读取可用输出并仅对不可解码字节使用替换占位符。
    equation_counts = [int(value) for value in EQUATION_COUNT_PATTERN.findall(output_text)]  # 提取按出现顺序记录的全部方程数。
    unique_equation_counts = sorted(set(equation_counts))  # 去重后保留升序集合，多个值即表示同一案例内约束秩发生变化。
    result_exists = result_path.is_file()  # 检查 APDL 是否按合同写出机器数值结果。
    record = {"case_id": case_id, "case_family": str(case["case_family"]), "input_file": str(frozen_input), "input_sha256": source_hash, "source_input_file": str(source_input), "case_dir": str(case_dir), "argv": argv, "output_file": str(output_path), "output_exists": output_exists, "output_sha256": sha256_file(output_path) if output_exists else None, "result_file": str(result_path), "result_exists": result_exists, "result_sha256": sha256_file(result_path) if result_exists else None, "exit_code": exit_code, "timed_out": timed_out, "run_completed": "RUN COMPLETED" in output_text.upper(), "fatal_marker": "PROBLEM TERMINATED" in output_text.upper(), "automatic_cnvtol_reset": "INTERNALLY RESET TO CNVTOL" in output_text.upper(), "zero_pivot": "ZERO PIVOT" in output_text.upper(), "small_pivot": "SMALL EQUATION SOLVER PIVOT" in output_text.upper() or "SMALL PIVOT" in output_text.upper(), "negative_pivot": "NEGATIVE PIVOT" in output_text.upper(), "coefficient_ratio_warning": "COEFFICIENT RATIO EXCEEDS" in output_text.upper(), "error_count": last_integer(ERROR_COUNT_PATTERN, output_text), "warning_count": last_integer(WARNING_COUNT_PATTERN, output_text), "equation_counts": equation_counts, "unique_equation_counts": unique_equation_counts, "equation_count_constant": len(unique_equation_counts) <= 1 and len(equation_counts) >= 1, "started_at_utc": started_at.isoformat(), "ended_at_utc": ended_at.isoformat(), "elapsed_seconds": (ended_at - started_at).total_seconds()}  # 汇总进程、原始工件、日志异常和方程秩证据；不在执行器中宣称数值验收通过。
    return record  # 返回单案例记录供逐项落盘和最终验收器复核。


def main() -> None:  # 解析父运行、关闭输入门禁、串行执行十二案例并写出不可混淆的原始记录，无业务返回值。
    parser = argparse.ArgumentParser(description="执行 C10 单层 MPC 十二项微算例并冻结原始工件")  # 创建只接受明确父准备运行名的命令行接口。
    parser.add_argument("--prepare-run", required=True, help="以 C10_MPC_ONLY_ 开头且尚未执行的父准备运行名")  # 要求调用者显式指定输入包，禁止选择 latest。
    args = parser.parse_args()  # 解析命令行并让 argparse 拒绝缺失或未知参数。
    prepare_name = str(args.prepare_run)  # 把父运行名规范为普通字符串以进行前缀和清单比较。
    require(prepare_name.startswith("C10_MPC_ONLY_"), f"父运行名不属于 C10_MPC_ONLY：{prepare_name}")  # 限定允许的准备运行族。
    prepare_dir = (RUNS_ROOT / prepare_name).resolve()  # 在固定运行根下解析父目录绝对路径。
    require(prepare_dir.is_dir(), f"父准备运行不存在：{prepare_dir}")  # 拒绝缺失或拼写错误的父运行。
    plan_path = prepare_dir / "qa" / "connection_unit_test_plan.json"  # 定位新单层约束的十二案例冻结计划。
    plan = read_json(plan_path)  # 读取计划以验证案例数量、公式和输入哈希。
    require(plan.get("schema_version") == 3, "微算例计划版本不是单层拓扑 schema 3")  # 阻断旧十五案例串联链计划。
    require(plan.get("status") == "PREPARED_NOT_STARTED", "父微算例计划状态不是未启动")  # 保证执行来源是纯准备包。
    require(plan.get("planned_case_count") == EXPECTED_CASE_COUNT, "父微算例计划数量不是十二")  # 固定三加三加六覆盖范围。
    formulation = plan.get("formulation")  # 读取约束公式对象以禁止旧辅助节点或 TYPE73 混入。
    require(isinstance(formulation, dict), "父微算例计划缺少 formulation 对象")  # 确保后续键访问具有明确类型。
    require(formulation.get("aux_node_count") == 0 and formulation.get("type73_count") == 0, "父微算例仍包含辅助节点或 TYPE73")  # 只允许待验证的新单层 TYPE72 方案。
    cases = plan.get("cases")  # 读取十二个案例对象数组。
    require(isinstance(cases, list) and len(cases) == EXPECTED_CASE_COUNT, "父微算例 cases 不是十二项数组")  # 阻断案例缺失、重复压缩或错误顶层结构。
    require(MAPDL_EXE.is_file(), f"MAPDL 可执行文件不存在：{MAPDL_EXE}")  # 在创建运行目录前确认求解器仍可用。
    conflicting = active_solver_processes()  # 获取当前求解器冲突进程快照。
    require(not conflicting, f"已有 MAPDL/MPI 进程，拒绝并发启动：{conflicting}")  # 确保十二项串行微验证不与全桥求解争抢内存或许可证。
    created_at = datetime.now(timezone.utc)  # 在任何写入前固定本次运行的 UTC 身份时刻。
    run_name = make_run_name(created_at)  # 根据微秒级 UTC 时刻生成唯一执行运行名。
    run_dir = RUNS_ROOT / run_name  # 将本次执行限定到 ultra_runs 下的新证据目录。
    run_dir.mkdir(parents=False, exist_ok=False)  # 原子式创建且禁止覆盖任何同名历史运行。
    script_snapshot = run_dir / Path(__file__).name  # 指定实际执行器源码快照路径以便复现。
    shutil.copy2(Path(__file__).resolve(), script_snapshot)  # 复制当前执行脚本字节和时间信息到新运行根。
    record = {"schema_version": 3, "run_name": run_name, "status": "RUNNING_MICRO_VALIDATION", "created_at_utc": created_at.isoformat(), "prepare_run": prepare_name, "prepare_plan_sha256": sha256_file(plan_path), "executor_snapshot": str(script_snapshot), "executor_snapshot_sha256": sha256_file(script_snapshot), "mapdl_executable": str(MAPDL_EXE), "mapdl_executable_sha256": sha256_file(MAPDL_EXE), "execution_mode": "SMP_SERIAL_NP1", "planned_case_count": EXPECTED_CASE_COUNT, "completed_case_count": 0, "cases": []}  # 初始化运行级原始账本；状态不会预先宣称任何案例通过。
    record_path = run_dir / "solver_run_record.json"  # 固定执行记录路径，供崩溃恢复和独立 finalizer 使用。
    write_json(record_path, record)  # 在首个求解前落盘运行身份，避免中途失败后完全无记录。
    for case in cases:  # 按准备计划冻结顺序串行执行十二项，避免并行进程造成资源和日志混淆。
        require(isinstance(case, dict), "父微算例 cases 含非对象条目")  # 每次访问字段前验证当前案例是对象。
        case_record = execute_case(case, prepare_dir, run_dir)  # 执行当前 MAPDL 微算例并收集不带通过结论的原始证据。
        record["cases"].append(case_record)  # 将当前案例记录追加到运行级账本的有序数组。
        record["completed_case_count"] = len(record["cases"])  # 用实际已返回案例数更新完成计数，支持中途诊断。
        write_json(record_path, record)  # 每完成一项立即持久化，防止后续案例故障丢失已完成证据。
    record["status"] = "RAW_EXECUTION_COMPLETED_PENDING_NUMERICAL_FINALIZATION"  # 十二个进程均返回后只标记原始执行完成，数值验收仍待 finalizer。
    record["ended_at_utc"] = datetime.now(timezone.utc).isoformat()  # 记录全部案例串行结束的 UTC 时刻。
    write_json(record_path, record)  # 写出可供独立验收的最终原始运行记录。
    field_dictionary = "# 微算例执行字段说明\n\n`RAW_EXECUTION_COMPLETED_PENDING_NUMERICAL_FINALIZATION` 只表示十二个外部进程均已返回，不表示数值或工程通过。`equation_counts` 按 MAPDL 输出出现顺序记录每次矩阵组装的方程数；`equation_count_constant=true` 要求至少出现一次且去重后只有一个值。`small_pivot`、`zero_pivot`、`negative_pivot`、`automatic_cnvtol_reset` 和 `fatal_marker` 均为禁止项。力单位为 N，长度为 mm，力矩为 N·mm，转角为 rad。\n"  # 为不支持注释的 JSON 逐项解释关键状态、门禁和单位。
    (run_dir / "field_dictionary.md").write_text(field_dictionary, encoding="utf-8", newline="\n")  # 写出相邻 Markdown 字段字典而不污染 JSON 有效性。
    print(json.dumps({"run_name": run_name, "run_dir": str(run_dir), "status": record["status"], "completed_case_count": record["completed_case_count"]}, ensure_ascii=False))  # 向调用者返回精简机器摘要，便于立即进入 finalizer。


if __name__ == "__main__":  # 仅在直接运行本文件时进入十二案例执行流程，导入时不产生外部求解副作用。
    main()  # 执行一次 fail-closed 的 C10 新单层约束微验证原始求解。
