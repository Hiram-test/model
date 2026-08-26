from __future__ import annotations  # 启用延迟类型注解，保持运行时依赖最小且便于静态检查。

import argparse  # 解析唯一允许的运行目录参数，禁止脚本猜测或复用错误运行。
import hashlib  # 复算全部准备工件、主输入和 MAPDL 可执行文件 SHA-256 身份。
import json  # 读取准备清单并写出机器可解析的启动记录。
import re  # 严格解析准备阶段标准 SHA-256 账本行并检查路径边界。
import subprocess  # 以独立无窗口进程启动 MAPDL 静力诊断。
from datetime import datetime, timezone  # 记录可追溯的 UTC 启动时间。
from pathlib import Path  # 安全处理包含中文的绝对路径。
from typing import Any  # 标注 JSON 字典的异构值类型。

import psutil  # 读取物理内存、磁盘和精确进程名，执行诊断例外资源门。


MIN_DIAGNOSTIC_RAM_BYTES = 4 * 1024**3  # 诊断例外绝对最低可用物理内存为 4 GiB；正式门仍为 8 GiB。
FORMAL_RAM_BYTES = 8 * 1024**3  # 正式全桥既定可用物理内存门槛为 8 GiB。
MIN_DIAGNOSTIC_DISK_BYTES = 50 * 1024**3  # 启动诊断要求 D 盘至少保留 50 GiB，硬停线仍为 32 GiB。
MAPDL_PROCESS_NAMES = {"ansys.exe", "ansys261.exe", "mapdl.exe", "mapdl261.exe", "mpiexec.exe", "hydra_service.exe", "hydra_pmi_proxy.exe"}  # 精确列出会与本次诊断冲突的求解器和 MPI 进程名。
ADAPTIVE_MIGRATION_SUBTYPE = "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_ADAPTIVE_CUTBACK_TO_0_05_PERCENT"  # 冻结执行器需要额外验证的唯一自适应迁移子类型。
LEDGER_PATTERN = re.compile(r"^([0-9a-f]{64})  (.+)$")  # 只接受六十四位小写摘要、双空格和运行内相对路径格式。


def require(condition: bool, message: str) -> None:  # 输入门禁条件与失败说明；失败时阻断启动且无返回值。
    if not condition:  # 仅在证据、资源或运行身份不满足时进入拒绝路径。
        raise RuntimeError(message)  # 抛出明确异常，保证任何失败都不会继续启动 MAPDL。


def sha256_file(path: Path) -> str:  # 输入文件路径并返回完整内容的 SHA-256 小写摘要。
    digest = hashlib.sha256()  # 创建本文件独立摘要器。
    with path.open("rb") as handle:  # 以二进制只读模式打开，避免换行或编码变化。
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):  # 每次读取一 MiB 直至文件末尾。
            digest.update(chunk)  # 将当前原始字节块加入摘要计算。
    return digest.hexdigest()  # 返回六十四位小写十六进制摘要。


def load_json(path: Path) -> dict[str, Any]:  # 输入 UTF-8 JSON 路径并返回顶层对象字典。
    require(path.is_file(), f"缺少运行清单：{path}")  # 读取前拒绝缺失文件。
    payload = json.loads(path.read_text(encoding="utf-8"))  # 解析完整 UTF-8 JSON 内容。
    require(isinstance(payload, dict), f"JSON 顶层不是对象：{path}")  # 禁止数组或标量冒充清单。
    return payload  # 返回已验证的对象字典。


def write_json(path: Path, payload: dict[str, Any]) -> None:  # 输入目标路径和对象字典并输出稳定 UTF-8 JSON。
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"  # 保留中文并使用两空格缩进和唯一末尾换行。
    with path.open("x", encoding="utf-8", newline="\n") as handle:  # 使用操作系统排他创建阻断并发启动器覆盖同一认领或记录。
        handle.write(rendered)  # 一次写入已完成序列化的合法 JSON，字段解释由同运行 QA 文档承担。


def verify_prepared_ledger(run_dir: Path) -> dict[str, str]:  # 输入运行根并返回已逐项复算通过的相对路径到摘要映射。
    ledger_path = run_dir / "artifact_hashes.sha256"  # 定位准备器最后写出的启动前完整工件账本。
    require(ledger_path.is_file(), "缺少准备阶段 artifact_hashes.sha256")  # 没有完整输入字节身份时禁止启动求解器。
    entries: dict[str, str] = {}  # 初始化唯一相对路径到冻结摘要的映射。
    for line_number, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):  # 按真实行号遍历全部标准账本行。
        match = LEDGER_PATTERN.fullmatch(line)  # 对当前整行执行严格摘要和路径格式匹配。
        require(match is not None, f"准备账本第 {line_number} 行格式错误")  # 拒绝空行、非小写摘要或不唯一分隔符。
        relative_text = match.group(2)  # 读取保持 POSIX 分隔符的运行内相对路径文本。
        require(relative_text not in entries, f"准备账本重复路径：{relative_text}")  # 禁止后值覆盖前值造成歧义。
        relative_path = Path(relative_text)  # 转换为当前平台路径对象供边界和存在性检查。
        require(not relative_path.is_absolute() and ".." not in relative_path.parts, f"准备账本路径越界：{relative_text}")  # 阻断绝对路径和父目录逃逸。
        artifact_path = run_dir / relative_path  # 构造当前运行根内的真实准备工件路径。
        require(artifact_path.is_file(), f"准备账本工件缺失：{relative_text}")  # 拒绝被删除、移动或替换为目录的工件。
        require(sha256_file(artifact_path) == match.group(1), f"准备账本工件 SHA-256 漂移：{relative_text}")  # 在临近 Popen 时复算每一项当前真实字节。
        entries[relative_text] = match.group(1)  # 保存通过全部门禁的唯一路径和摘要。
    require(len(entries) >= 20, "准备账本条目异常不足")  # 阻断只冻结主控而遗漏 include、QA 或清单的残缺包。
    return entries  # 返回完整通过格式、路径、存在性和摘要门的准备映射。


def active_solver_processes() -> list[dict[str, Any]]:  # 无输入；返回当前精确匹配的 MAPDL/MPI 进程身份列表。
    matches: list[dict[str, Any]] = []  # 初始化冲突进程记录列表。
    for process in psutil.process_iter(["pid", "name"]):  # 遍历系统进程并只请求 PID 与名称两个只读字段。
        name = str(process.info.get("name") or "").lower()  # 规范化进程名以执行不区分大小写的精确匹配。
        if name in MAPDL_PROCESS_NAMES:  # 仅把真实求解器或 MPI worker 视为冲突，不包含 ansyslmd 许可服务。
            matches.append({"pid": int(process.info["pid"]), "name": name})  # 记录冲突 PID 和进程名供拒绝信息审计。
    return matches  # 返回全部冲突进程；空列表表示无并发求解。


def argument_value(arguments: list[str], flag: str) -> str:  # 接收冻结启动参数数组和标志并返回其唯一相邻后继值。
    indices = [index for index, value in enumerate(arguments) if value.lower() == flag.lower()]  # 忽略大小写查找全部标志位置，保留重复检测能力。
    require(len(indices) == 1, f"启动参数 {flag} 出现 {len(indices)} 次，预期 1")  # 缺失或重复都会导致实际 job、目录或输入输出路径歧义。
    index = indices[0]  # 读取已经确认唯一的标志下标。
    require(index + 1 < len(arguments), f"启动参数 {flag} 缺少后继值")  # 防止数组越界或空配置被传入 MAPDL。
    return arguments[index + 1]  # 返回求解器实际采用的相邻参数文本。


def main() -> None:  # 解析运行目录、关闭启动前门禁并异步启动一次 MAPDL 静力诊断，无业务返回值。
    parser = argparse.ArgumentParser(description="启动已准备的 C10 静力诊断")  # 建立只接受明确运行目录的命令行解析器。
    parser.add_argument("--run-dir", required=True, type=Path, help="C10_STATIC_DIAGNOSTIC 或 C10_LOAD_MIGRATION_DIAGNOSTIC 唯一绝对目录")  # 要求调用者显式指定静力或恒总荷载迁移目标，禁止自动选择 latest。
    args = parser.parse_args()  # 解析并验证命令行参数结构。
    run_dir = args.run_dir.resolve()  # 规范化目标运行绝对路径，避免相对目录歧义。
    require(run_dir.is_dir(), f"运行目录不存在：{run_dir}")  # 拒绝缺失或非目录目标。
    approved_run_prefixes = ("C10_STATIC_DIAGNOSTIC_", "C10_LOAD_MIGRATION_DIAGNOSTIC_")  # 只批准普通静力诊断与恒总荷载位置迁移诊断两个唯一目录族。
    require(run_dir.name.startswith(approved_run_prefixes), f"运行目录名称不属于批准的 C10 静力诊断族：{run_dir.name}")  # 阻断微验证、模态、历史生产或任意目录被此低内存执行器启动。
    launch_claim_path = run_dir / "runtime_launch_claim.json"  # 定位启动前排他认领文件；该文件先于进程创建，关闭并发启动器的检查到使用时间窗。
    runtime_launch_path = run_dir / "runtime_launch.json"  # 定位进程创建后启动记录；该文件保存真实 PID 并供监控器与终结器交叉核对。
    require(not launch_claim_path.exists() and not runtime_launch_path.exists(), "该运行已存在启动认领或启动记录，禁止重复启动")  # 绝不复用同一作业名、覆盖既有求解或允许两个启动器同时越过门禁。
    manifest = load_json(run_dir / "manifest.json")  # 读取准备阶段冻结清单。
    root_status = load_json(run_dir / "C10_static_status.json")  # 独立读取准备器根状态，避免只撤销状态但执行器仍信任旧 manifest。
    require(manifest.get("run_name") == run_dir.name, "清单运行名与目录名不一致")  # 防止目录被错误复制或改名。
    require(root_status.get("run_name") == run_dir.name and root_status.get("jobname") == manifest.get("jobname"), "根状态运行名或 jobname 与清单不一致")  # 关闭根状态与清单双重身份。
    require(manifest.get("status") == "STATIC_DIAGNOSTIC_PREPARED", "运行状态不是可启动的准备态")  # 只允许准备完成且未运行的包。
    require(root_status.get("status") == "STATIC_DIAGNOSTIC_PREPARED" and root_status.get("launch_allowed_for_diagnostic") is True, "根状态未明确批准诊断启动")  # 作废、阻断或缺省 launch 权限一律 fail-closed。
    require(root_status.get("mapdl_execution_attempted") is False and root_status.get("mapdl_started") is False, "根状态显示 MAPDL 已尝试或已启动")  # 禁止根状态已登记运行却缺少 runtime_launch 的目录被重用。
    prepared_entries = verify_prepared_ledger(run_dir)  # 在临近启动时复算全部准备输入、清单、状态和 QA 字节身份。
    require("manifest.json" in prepared_entries and "C10_static_status.json" in prepared_entries, "准备账本未冻结清单或根状态")  # 禁止只冻结主控而遗漏启动权限字段。
    require(manifest.get("execution_mode") == "SMP_SERIAL_NP1_DIAGNOSTIC_ONLY", "运行模式不是批准的 SMP1 诊断")  # 禁止误启 DMP4 或生产模态。
    require(manifest.get("modal_requested") is False, "清单仍请求模态分析")  # 双重阻断低内存下的模态求解。
    solver_dir = run_dir / "solver"  # 定位独立 MAPDL 工作目录。
    main_input = run_dir / str(manifest["main_input"])  # 按清单定位唯一诊断主输入。
    executable = Path(str(manifest["mapdl_executable"]))  # 按清单定位冻结 MAPDL 可执行文件。
    require(main_input.is_file(), f"缺少诊断主输入：{main_input}")  # 拒绝缺失主控。
    require(executable.is_file(), f"缺少 MAPDL 可执行文件：{executable}")  # 拒绝求解器路径漂移。
    require(sha256_file(main_input) == str(manifest["main_input_sha256"]), "诊断主输入 SHA-256 漂移")  # 拒绝准备后人工编辑的主控。
    require(sha256_file(executable) == str(manifest["mapdl_executable_sha256"]), "MAPDL 可执行文件 SHA-256 漂移")  # 拒绝未登记求解器版本变化。
    main_text = main_input.read_text(encoding="utf-8")  # 读取短静力主控执行末次命令级检查。
    require("PERTURB,MODAL" not in main_text and "MODOPT," not in main_text, "主输入仍含模态命令")  # 启动前再次确认静力专用截断。
    require(manifest.get("constraint_topology") == "SINGLE_TYPE72_NO_AUX_NO_TYPE73", "清单拓扑不是单层 TYPE72")  # 阻断旧串联 TYPE72—TYPE73 诊断包被误启动。
    require(main_text.count("CNVTOL,") == 4, "主输入未固定四项 CNVTOL")  # 确认力、力矩、平移和转角四项禁止自动放宽的收敛标准存在。
    if manifest.get("diagnostic_subtype") == ADAPTIVE_MIGRATION_SUBTYPE:  # 自适应迁移在 Popen 前执行唯一变量、K5、谱系和步长专项门禁。
        require(len(prepared_entries) >= 27, "自适应迁移准备账本少于二十七项")  # 要求输入基准、授权证据和迁移审计均已冻结。
        require(manifest.get("single_variable_change") == "LS2_NSBMX_200_TO_2000_ONLY", "自适应迁移唯一变量不是 NSBMX 200→2000")  # 阻断多变量候选。
        require(manifest.get("mpc184_keyopt5_static") == 0 and manifest.get("prestressed_modal_requires_keyopt5_restore_to_zero") is False, "自适应迁移未保持默认 KEYOPT(5)=0")  # 已证伪 K5 不得混入。
        increment_change = manifest.get("migration_increment_change")  # 读取清单冻结的 NSUBST 和迁移增量上下界对象。
        require(isinstance(increment_change, dict), "自适应迁移缺少 migration_increment_change 对象")  # 后续数值门只接受对象结构。
        require(increment_change.get("nsbstp") == 200 and increment_change.get("nsbmx") == 2000 and increment_change.get("nsbmn") == 200, "自适应迁移清单 NSUBST 不是 200/2000/200")  # 固定初始、最大和最小子步数。
        require(float(increment_change.get("new_initial_fraction", -1.0)) == 0.005 and float(increment_change.get("new_minimum_fraction", -1.0)) == 0.0005, "自适应迁移清单增量上下界不是 0.5%/0.05%")  # 固定物理百分比语义。
        executable_commands = [line.split("!", maxsplit=1)[0].strip().upper().replace(" ", "") for line in main_text.splitlines()]  # 规范化主控可执行命令并排除说明注释。
        require(executable_commands.count("NSUBST,200,2000,200") == 1 and executable_commands.count("NSUBST,200,200,200") == 0, "自适应主控 NSUBST 新旧值计数不正确")  # 确认唯一新值且旧值完全移除。
        require(executable_commands.count("KEYOPT,72,5,1") == 0 and executable_commands.count("KBC,1") == 1 and executable_commands.count("KBC,0") == 1, "自适应主控 K5 或 KBC 合同漂移")  # 保持默认 K5 和两步加载边界。
        require(executable_commands.count("/INPUT,APPLY_CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_V1,INP") == 2, "自适应主控位置修正 include 调用数不是两次")  # 固定 beta=1/0 两个端点调用。
        required_qa_paths = ["qa/load_position_migration_audit.json", "qa/migration_control_audit.json", "qa/previous_migration_reference.json", "qa/adaptive_authorization_reference.json"]  # 冻结启动前必须存在于账本的四项迁移 QA 相对路径。
        require(all(relative_path in prepared_entries for relative_path in required_qa_paths), "自适应迁移准备账本缺少守恒、控制、输入基准或授权证据")  # 阻断谱系不完整候选。
        runtime_execute_relative = str(manifest.get("runtime_execute_script", "")).replace("\\", "/")  # 读取清单冻结的本执行器运行内相对路径并规范分隔符。
        runtime_monitor_relative = str(manifest.get("runtime_monitor_script", "")).replace("\\", "/")  # 读取清单冻结的后续监控器运行内相对路径并规范分隔符。
        require(runtime_execute_relative == "input_snapshot/ultra_c10_static_execute.py" and runtime_monitor_relative == "input_snapshot/ultra_c10_adaptive_monitor.py", "自适应运行脚本快照路径不符合冻结合同")  # 只允许准备账本内固定文件名的执行器和监控器。
        require(runtime_execute_relative in prepared_entries and runtime_monitor_relative in prepared_entries, "准备账本未冻结执行器或自适应监控器快照")  # 阻断运行代码不受输入账本保护的候选。
        runtime_execute_path = (run_dir / runtime_execute_relative).resolve()  # 构造本运行内冻结执行器绝对路径。
        runtime_monitor_path = (run_dir / runtime_monitor_relative).resolve()  # 构造本运行内冻结监控器绝对路径。
        require(runtime_execute_path.is_file() and runtime_execute_path == Path(__file__).resolve(), "实际调用的执行器不是本运行冻结快照")  # 禁止从可继续编辑的工具源直接启动已准备包。
        require(runtime_monitor_path.is_file() and sha256_file(runtime_monitor_path) == str(manifest.get("runtime_monitor_script_sha256")), "冻结监控器缺失或摘要与清单不一致")  # 确保启动后可立即调用同账本监控代码。
        require(sha256_file(runtime_execute_path) == str(manifest.get("runtime_execute_script_sha256")) and prepared_entries[runtime_execute_relative] == str(manifest.get("runtime_execute_script_sha256")), "实际执行器摘要未与清单和准备账本三方闭合")  # 证明当前运行启动代码字节身份唯一。
        require(prepared_entries[runtime_monitor_relative] == str(manifest.get("runtime_monitor_script_sha256")), "监控器清单摘要与准备账本不一致")  # 关闭监控器当前文件、清单和账本身份。
        migration_audit = load_json(run_dir / "qa" / "load_position_migration_audit.json")  # 读取位置修正节点、总和和命令计数审计。
        control_audit = load_json(run_dir / "qa" / "migration_control_audit.json")  # 读取命令级单差异和步长控制审计。
        baseline_reference = load_json(run_dir / "qa" / "previous_migration_reference.json")  # 读取默认 K5=0 输入基准引用。
        authorization_reference = load_json(run_dir / "qa" / "adaptive_authorization_reference.json")  # 读取 K5=1 同轨发散授权引用。
        require(migration_audit.get("status") == "PASSED" and migration_audit.get("correction_node_count") == 15071 and migration_audit.get("rendered_correction_sum_n") == "2.08526E-10", "位置修正审计未证明 15,071 节点和微牛级恒总荷载")  # 固定修正向量规模与守恒量。
        require(control_audit.get("mpc184_keyopt5_static") == 0 and control_audit.get("ls2", {}).get("nsubst") == [200, 2000, 200] and control_audit.get("single_difference_input_baseline", {}).get("only_executable_change") == "NSUBST,200,200,200_TO_NSUBST,200,2000,200", "迁移控制审计未闭合 K5、NSUBST 或唯一差异")  # 关闭主控与机器审计分叉。
        require(baseline_reference.get("role") == "SINGLE_DIFFERENCE_INPUT_BASELINE" and authorization_reference.get("role") == "FOLLOWUP_AUTHORIZATION_EVIDENCE_NOT_INPUT_BASELINE", "输入基准与授权证据角色混淆")  # 保持 K5 运行只作授权而非派生输入。
        require(authorization_reference.get("single_difference_observed_effect") == "NO_CHANGE_IN_LS2_FIRST_TWO_NR_STATES_AT_PRINTED_PRECISION" and authorization_reference.get("authorized_next_diagnostic") == "LS2_ADAPTIVE_SUBSTEPS_200_2000_200_ALLOW_0_05_PERCENT_MINIMUM_INCREMENT", "授权证据未证明 K5 无效或未批准当前下一步")  # 固定自适应运行的工程授权链。
    conflicting = active_solver_processes()  # 获取当前精确冲突进程列表。
    require(not conflicting, f"已有 MAPDL/MPI 进程，拒绝并发启动：{conflicting}")  # 保证本次诊断独占求解环境。
    memory = psutil.virtual_memory()  # 读取实时物理内存快照。
    disk = psutil.disk_usage(str(run_dir.drive + "\\"))  # 读取运行所在 D 盘实时空间快照。
    require(int(memory.available) >= MIN_DIAGNOSTIC_RAM_BYTES, f"可用物理内存低于诊断绝对下限 4 GiB：{memory.available}")  # 不满足例外下限时拒绝启动。
    require(int(disk.free) >= MIN_DIAGNOSTIC_DISK_BYTES, f"D 盘空余低于诊断启动线 50 GiB：{disk.free}")  # 防止求解中写满磁盘。
    launch_argv = [str(value) for value in manifest["launch_argv"]]  # 从冻结清单恢复完整参数数组，避免重新拼接产生差异。
    require(launch_argv[0] == str(executable), "启动参数中的求解器路径与清单不一致")  # 验证首参数身份。
    require(launch_argv.count("-b") == 1 and launch_argv.count("-smp") == 1 and argument_value(launch_argv, "-np") == "1", "启动参数不是唯一批处理 SMP 单进程")  # 固定低内存诊断并行模式并拒绝重复标志。
    require("-dis" not in launch_argv and "-mpi" not in launch_argv, "启动参数意外包含 DMP/MPI")  # 禁止正式 DMP 参数混入诊断。
    require(argument_value(launch_argv, "-j") == str(manifest["jobname"]), "启动参数 -j 与清单 jobname 不一致")  # 固定唯一结果文件族身份。
    require(Path(argument_value(launch_argv, "-dir")).resolve() == solver_dir.resolve(), "启动参数 -dir 未指向本运行 solver 目录")  # 阻断跨运行工作目录污染。
    require(Path(argument_value(launch_argv, "-i")).resolve() == main_input.resolve(), "启动参数 -i 未指向已哈希主输入")  # 防止正确清单却实际执行另一输入。
    expected_output = (solver_dir / f"{manifest['jobname']}.out").resolve()  # 构造本 job 在本 solver 目录中的唯一权威 OUT 路径。
    require(Path(argument_value(launch_argv, "-o")).resolve() == expected_output, "启动参数 -o 未指向本 job 唯一 OUT")  # 防止跨目录输出覆盖或借用另一运行日志。
    prepared_ledger_path = run_dir / "artifact_hashes.sha256"  # 定位已经逐项复算通过的准备账本原件，供认领与运行记录冻结其整体身份。
    prepared_ledger_sha256 = sha256_file(prepared_ledger_path)  # 计算准备账本自身摘要，关闭逐项复算结果与启动记录之间的时间窗。
    manifest_sha256 = sha256_file(run_dir / "manifest.json")  # 计算已受准备账本保护的清单摘要，供认领、运行和终结三方核对。
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows 使用无窗口标志；非 Windows 回退为零但本项目固定运行于 Windows。
    started_at = datetime.now(timezone.utc)  # 在排他认领与创建进程前记录同一 UTC 启动时刻。
    prelaunch_resources = {"physical_memory_total_bytes": int(memory.total), "physical_memory_available_bytes": int(memory.available), "formal_8_gib_gate_passed": int(memory.available) >= FORMAL_RAM_BYTES, "diagnostic_4_gib_exception_gate_passed": True, "disk_free_bytes": int(disk.free), "disk_50_gib_gate_passed": True, "conflicting_solver_process_count": len(conflicting)}  # 冻结进程创建前通过的内存、磁盘和独占性门禁快照。
    resource_gate_disposition = "FORMAL_8_GIB_PASSED_DIAGNOSTIC_SCOPE_STILL_NONPRODUCTION" if prelaunch_resources["formal_8_gib_gate_passed"] else "FORMAL_8_GIB_FAILED_DIAGNOSTIC_ONLY"  # 按真实启动快照区分正式内存门通过或诊断例外，且两者都不提升本运行生产权限。
    launch_claim = {"schema_version": 1, "run_name": run_dir.name, "jobname": manifest["jobname"], "status": "LAUNCH_CLAIMED_NOT_YET_STARTED", "claimed_at_utc": started_at.isoformat(), "execution_mode": manifest["execution_mode"], "diagnostic_subtype": manifest.get("diagnostic_subtype"), "single_variable_change": manifest.get("single_variable_change"), "launch_argv": launch_argv, "manifest_sha256": manifest_sha256, "prepared_ledger_sha256": prepared_ledger_sha256, "prepared_ledger_entry_count": len(prepared_entries), "prelaunch_resources": prelaunch_resources, "production_claim_allowed": False}  # 在 Popen 前冻结唯一运行身份、输入谱系、批准单变量和已通过资源门，且不虚构尚未取得的 PID。
    write_json(launch_claim_path, launch_claim)  # 以排他创建写出不可覆盖的启动认领；即使后续 Popen 失败，同一目录也保持 fail-closed 且不会被再次启动。
    launch_claim_sha256 = sha256_file(launch_claim_path)  # 计算已经落盘的认领摘要，使运行记录和最终账本可证明采用同一份启动权声明。
    process = subprocess.Popen(launch_argv, cwd=solver_dir, creationflags=creation_flags)  # 仅在认领成功后启动独立 MAPDL 进程并立即取得真实 PID 供外部监控。
    process_identity_path = run_dir / "runtime_process_identity.json"  # 定位 Popen 后独立排他写出的创建时刻、二进制和真实命令行身份工件。
    record = {"schema_version": 1, "run_name": run_dir.name, "jobname": manifest["jobname"], "status": "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURE_PENDING", "started_at_utc": started_at.isoformat(), "main_pid": int(process.pid), "process_identity_path": process_identity_path.name, "execution_mode": manifest["execution_mode"], "diagnostic_subtype": manifest.get("diagnostic_subtype"), "single_variable_change": manifest.get("single_variable_change"), "launch_argv": launch_argv, "manifest_sha256": manifest_sha256, "prepared_ledger_sha256": prepared_ledger_sha256, "prepared_ledger_entry_count": len(prepared_entries), "launch_claim_sha256": launch_claim_sha256, "prelaunch_resources": prelaunch_resources, "resource_gate_exception": resource_gate_disposition, "production_claim_allowed": False, "monitor_hard_stops": {"available_ram_below_bytes": 512 * 1024**2, "available_ram_below_1_gib_sustained_seconds": 60, "disk_free_below_bytes": 32 * 1024**3}}  # 在取得 PID 后立即冻结最小不可覆盖启动记录，避免后续 psutil 竞争造成已启动却无 PID 证据。
    write_json(runtime_launch_path, record)  # Popen 后第一时间排他写出 PID、job、参数和资源记录，再尝试采集增强进程身份。
    try:  # 增强身份采集可能因包装器快速交接或系统访问策略失败，必须留下单独失败证据并安全请求中止。
        process_identity = psutil.Process(process.pid)  # 按刚取得的真实 PID 获取不可由名称猜测的包装器进程对象。
        process_create_time = float(process_identity.create_time())  # 冻结操作系统进程创建时刻，供监控器阻断 PID 回收后误附着。
        process_executable = str(Path(process_identity.exe()).resolve())  # 冻结真实进程可执行文件规范路径，供监控器与批准 MAPDL 二进制比较。
        process_command_line = [str(value) for value in process_identity.cmdline()]  # 冻结操作系统实际命令行数组，禁止监控器只信清单而忽略启动替换。
        require(Path(process_executable).resolve() == executable.resolve(), "Popen 后主进程可执行文件不是批准 MAPDL 二进制")  # 若包装器身份在记录前已漂移则拒绝写成功身份。
        require(process_command_line == launch_argv, "Popen 后主进程真实命令行与冻结 launch_argv 不一致")  # 要求操作系统实际参数数组逐项相同。
        identity_record = {"schema_version": 1, "status": "MAIN_PROCESS_IDENTITY_CAPTURED", "run_name": run_dir.name, "jobname": manifest["jobname"], "captured_at_utc": datetime.now(timezone.utc).isoformat(), "runtime_launch_sha256": sha256_file(runtime_launch_path), "pid": int(process.pid), "create_time_epoch_seconds": process_create_time, "executable": process_executable, "command_line": process_command_line}  # 保存可防 PID 回收并与最小启动记录绑定的增强身份。
        write_json(process_identity_path, identity_record)  # 以排他创建提交增强身份，监控器只有同时验证该工件才允许附着。
    except Exception as identity_error:  # 捕获身份采集、验证或排他写入的全部异常，绝不让已启动进程失去可见故障记录。
        identity_failure_path = run_dir / "runtime_process_identity_failure.json"  # 定位仅在增强身份失败时创建的不可覆盖故障记录。
        identity_failure = {"schema_version": 1, "status": "MAIN_PROCESS_IDENTITY_CAPTURE_FAILED_ABORT_REQUESTED", "run_name": run_dir.name, "jobname": manifest["jobname"], "failed_at_utc": datetime.now(timezone.utc).isoformat(), "main_pid": int(process.pid), "runtime_launch_sha256": sha256_file(runtime_launch_path), "error_type": type(identity_error).__name__, "error_message": str(identity_error)}  # 记录失败类别、文本和已存在 PID 启动工件身份。
        write_json(identity_failure_path, identity_failure)  # 以排他创建保存身份采集失败证据，禁止目录被误当作未启动重用。
        abort_path = solver_dir / f"{manifest['jobname']}.abt"  # 构造本 job 唯一 MAPDL 原生中止请求路径。
        if not abort_path.exists():  # 只有求解器尚未自行创建或响应其他中止请求时才创建。
            with abort_path.open("x", encoding="ascii", newline="\n") as abort_handle:  # 使用排他创建避免覆盖并发控制动作。
                abort_handle.write(f"C10_IDENTITY_CAPTURE_FAILURE {datetime.now(timezone.utc).isoformat()}\n")  # 写入失败原因族和 UTC 时间，文件存在性触发 MAPDL 原生中止检查。
        raise RuntimeError("MAPDL 已启动但增强进程身份采集失败，已写运行记录并请求原生中止") from identity_error  # 向调用者明确报告部分启动且禁止继续监控或复用。
    print(json.dumps({"run_dir": str(run_dir), "pid": process.pid, "status": "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURED", "process_identity_path": str(process_identity_path)}, ensure_ascii=False))  # 向调用者返回可解析的运行目录、PID、增强身份完成状态和工件路径。


if __name__ == "__main__":  # 仅在直接执行本文件时进入启动流程。
    main()  # 执行一次 fail-closed 诊断启动。
