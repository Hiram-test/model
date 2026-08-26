"""只在 C10 自适应恒总荷载位置迁移自然达到最小步长仍不收敛时发布失败封板。"""  # 本模块不启动或终止 MAPDL，也不把失败运行升级为静力、模态或生产结果。

from __future__ import annotations  # 延迟解析类型标注，保持 Python 运行时依赖清晰且兼容复杂容器类型。

import argparse  # 解析用户显式指定的唯一自适应迁移运行目录，禁止隐式选择 latest。
import hashlib  # 复算准备账本、启动链、监控链、原生日志和最终追加账本的 SHA-256。
import json  # 读取无注释机器工件并渲染失败审计、根状态和标准输出摘要。
import math  # 检查主元、MNTR 增量、资源计时和全部解析浮点值的有限性。
import os  # 使用同卷硬链接实现“目标不存在才发布”的原子批量提交与安全回滚。
import re  # 从 APDL 主控、OUT、ERR 和 MNTR 中提取命令、方程、主元及非收敛路径。
import time  # 在封板前复核 OUT、ERR、MNTR 和运行目录文件集合已经停止变化。
from pathlib import Path  # 规范化含中文的项目路径并关闭跨运行、父目录和绝对路径逃逸。
from typing import Any  # 标注异构 JSON 对象和求解路径事件字典的输入输出结构。

import psutil  # 以 PID、创建时刻、二进制和命令行复核原进程与本 job 子进程均已退出。

SCRIPT_PATH = Path(__file__).resolve()  # 固定实际执行终结器源码绝对路径，供运行内快照与摘要使用。
PROJECT_ROOT = SCRIPT_PATH.parents[1]  # 取 ultra_tools 的父目录作为唯一项目分析包根目录。
RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # 限定可封板目标必须是统一运行证据根的直接子目录。
EXPECTED_RUN_PREFIX = "C10_LOAD_MIGRATION_DIAGNOSTIC_"  # 仅允许处理恒总荷载位置迁移诊断族。
EXPECTED_SUBTYPE = "CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_ADAPTIVE_CUTBACK_TO_0_05_PERCENT"  # 冻结本终结器唯一接受的自适应诊断子类型。
EXPECTED_SINGLE_CHANGE = "LS2_NSBMX_200_TO_2000_ONLY"  # 冻结相对 0.5% 固定步基准的唯一工程命令差异。
EXPECTED_LOAD_PATH = "BETA_1_OLD_MCT_LOAD_POSITION_TO_BETA_0_SPATIAL_MASS21_AT_CONSTANT_TOTAL_LOAD"  # 冻结 beta 一到零且总重力不变的载荷路径身份。
EXPECTED_INITIAL_PATH = "MCT_INISTATE_PLUS_FULL_GRAVITY_AT_OLD_BALANCED_POSITION_THEN_CONTINUOUS_POSITION_MIGRATION"  # 冻结初始内力、旧平衡荷载和迁移顺序语义。
EXPECTED_INITIAL_AUDIT = "PENDING_FULL_STATIC_SOLUTION_AND_INDEPENDENT_BALANCE_CHECK"  # 冻结准备态尚未闭合的物理审计声明。
EXPECTED_EQUATION_COUNT = 1234834  # 冻结单层 TYPE72、无辅助节点、无 TYPE73 全桥的独立方程总数。
EXPECTED_LS1_PIVOT = 25.3126539  # 冻结健康 LS1 首次分解的基准正主元，单位沿 MAPDL 方程尺度。
MINIMUM_INCREMENT = 5.0e-7  # NSBMX=2000 对总伪时间 0.001 规定的最小增量，对应迁移比例 0.05%。
MAXIMUM_INCREMENT = 5.0e-6  # NSBMN=200 对总伪时间 0.001 规定的最大增量，对应迁移比例 0.5%。
INCREMENT_TOLERANCE = 1.0e-12  # 比较 APDL 科学计数法步长时允许的绝对浮点解析尾差。
FINAL_STATUS = "STATIC_ADAPTIVE_LOAD_POSITION_MIGRATION_NATURALLY_FAILED_AT_MINIMUM_INCREMENT_NCNV"  # 发布明确失败且不可进入模态的根级终态。
NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"  # 覆盖 MAPDL 整数、小数和科学计数法的有限数词法。
LEDGER_LINE_PATTERN = re.compile(r"^([0-9a-f]{64})\s{2}(.+)$")  # 只接受六十四位小写摘要、双空格和相对路径的账本格式。
EQUATION_PATTERN = re.compile(r"NUMBER OF EQUATIONS\s*=\s*(\d+)", re.IGNORECASE)  # 提取每次直接求解器组装报告的方程总数。
PIVOT_PATTERN = re.compile(rf"Sparse solver minimum pivot\s*=\s*({NUMBER_PATTERN})", re.IGNORECASE)  # 提取每次稀疏分解的有符号最小主元。
LS_COMPLETED_PATTERN = re.compile(r"\*\*\* LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED", re.IGNORECASE)  # 提取被 MAPDL 接受并形成结果集的载荷步和子步。
LS2_EVENT_PATTERN = re.compile(rf"(?P<reject>\*\*\* LOAD STEP\s+2\s+SUBSTEP\s+(?P<reject_substep>\d+)\s+NOT COMPLETED\.\s+CUM ITER\s*=\s*(?P<cum_iter>\d+))|(?P<bisect>\*\*\* BEGIN BISECTION NUMBER\s+(?P<bisect_number>\d+)\s+NEW TIME INCREMENT\s*=\s*(?P<increment>{NUMBER_PATTERN}))", re.IGNORECASE)  # 按原文顺序捕获 LS2 拒绝和随后二分事件。
MNTR_ROW_PATTERN = re.compile(rf"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+({NUMBER_PATTERN})\s+({NUMBER_PATTERN})(?:\s+|$)", re.IGNORECASE)  # 匹配 MNTR 五个整数控制列和两个时间列。


def require(condition: bool, message: str) -> None:  # 接收必须成立的布尔条件和拒绝原因；失败时不发布任何终态。
    if not condition:  # 仅在谱系、进程、监控、日志、数值或发布完整性不闭合时进入。
        raise RuntimeError(message)  # 抛出清晰异常并保持当前运行仍为未封板状态。


def sha256_bytes(payload: bytes) -> str:  # 接收内存字节并返回六十四位小写 SHA-256，供虚拟待发布文件入账。
    return hashlib.sha256(payload).hexdigest()  # 一次性计算已渲染文本字节的不可变内容身份。


def sha256_file(path: Path) -> str:  # 接收普通文件路径并返回完整二进制内容的六十四位小写 SHA-256。
    digest = hashlib.sha256()  # 为当前文件创建独立摘要累加器，禁止用大小或时刻代替内容身份。
    with path.open("rb") as handle:  # 使用只读二进制模式避免编码和换行转换改变摘要。
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):  # 每次读取八 MiB，在大型数据库吞吐和内存峰值间取平衡。
            digest.update(block)  # 按原始字节顺序累加当前数据块。
    return digest.hexdigest()  # 返回可写入标准账本的固定长度摘要。


def read_json(path: Path) -> dict[str, Any]:  # 接收 UTF-8 JSON 路径并返回已经验证为对象的顶层字典。
    require(path.is_file(), f"缺少 JSON 工件：{path}")  # 在解析前拒绝缺失、目录或错误路径。
    payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))  # 以严格 UTF-8 解析完整文档，禁止静默替换证据字节。
    require(isinstance(payload, dict), f"JSON 顶层不是对象：{path}")  # 禁止数组或标量冒充具名机器工件。
    return payload  # 返回通过存在性、编码、语法和顶层类型门的对象。


def render_json(payload: dict[str, Any]) -> str:  # 接收机器对象并返回稳定缩进、保留中文且禁止 NaN 的 JSON 文本。
    return json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 固定两空格缩进和单一末尾 LF 供哈希复核。


def parse_hash_ledger(path: Path, root: Path) -> dict[str, str]:  # 接收准备账本和运行根并返回唯一相对路径到摘要映射。
    require(path.is_file(), f"缺少准备态账本：{path}")  # 无启动前字节谱系时禁止归档自然失败。
    entries: dict[str, str] = {}  # 初始化保持输入行顺序的唯一条目映射。
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()  # 以严格 UTF-8 读取全部账本行。
    require(len(lines) >= 29, f"准备态账本条目不足：{len(lines)}")  # 本版自适应包至少应冻结二十九项准备工件。
    for line_number, line in enumerate(lines, start=1):  # 按真实行号逐项关闭格式、路径、存在性和摘要门。
        match = LEDGER_LINE_PATTERN.fullmatch(line)  # 对完整行应用严格摘要和双空格分隔格式。
        require(match is not None, f"准备账本第 {line_number} 行格式无效")  # 空行、宽松摘要和错误分隔均拒绝。
        relative_text = match.group(2).replace("\\", "/")  # 将平台分隔符统一为 POSIX 形式供唯一比较。
        require(relative_text not in entries, f"准备账本重复路径：{relative_text}")  # 禁止后行覆盖同一文件的先前摘要。
        artifact_path = (root / Path(relative_text)).resolve()  # 把当前相对路径投影到规范运行根。
        require(artifact_path.is_relative_to(root.resolve()), f"准备账本路径越界：{relative_text}")  # 阻断绝对路径和父目录逃逸。
        require(artifact_path.is_file(), f"准备账本工件缺失：{relative_text}")  # 每项冻结输入或 QA 工件必须仍为普通文件。
        require(sha256_file(artifact_path) == match.group(1), f"准备账本工件哈希漂移：{relative_text}")  # 求解前后字节不一致即拒绝封板。
        entries[relative_text] = match.group(1)  # 保存通过全部门禁的唯一条目。
    return entries  # 返回可供启动认领和监控快照三方复核的准备映射。


def argument_value(arguments: list[str], flag: str) -> str:  # 接收启动参数数组和标志并返回其唯一相邻值。
    indexes = [index for index, value in enumerate(arguments) if value.casefold() == flag.casefold()]  # 忽略标志大小写收集全部出现位置。
    require(len(indexes) == 1, f"启动参数 {flag} 出现 {len(indexes)} 次，预期 1")  # 缺失或重复都会导致真实执行路径歧义。
    index = indexes[0]  # 读取已经确认唯一的参数下标。
    require(index + 1 < len(arguments), f"启动参数 {flag} 缺少后继值")  # 防止末尾孤立标志造成越界。
    return arguments[index + 1]  # 返回求解器实际采用的相邻字符串值。


def process_identity_is_alive(identity: dict[str, Any]) -> bool:  # 接收冻结进程身份并判断同一 PID、时刻、二进制和命令行是否仍存活。
    try:  # 目标可能自然退出、拒绝访问、成为僵尸或 PID 已被系统复用。
        process = psutil.Process(int(identity["pid"]))  # 按冻结 PID 取得当前进程对象但不单独据此下结论。
        if abs(float(process.create_time()) - float(identity["create_time_epoch_seconds"])) > 0.001:  # 创建时刻差超过一毫秒表示 PID 已复用。
            return False  # 不把无关的新进程误判为原 MAPDL 包装器。
        if str(Path(process.exe()).resolve()).casefold() != str(Path(str(identity["executable"])).resolve()).casefold():  # 二进制路径变化表示身份不一致。
            return False  # 返回原进程已经消失的语义。
        if [str(value) for value in process.cmdline()] != [str(value) for value in identity["command_line"]]:  # 完整参数数组变化表示不是同一执行身份。
            return False  # 阻断单靠名称或 PID 的误判。
        return True  # 四项身份均一致时确认原求解进程仍存活。
    except (psutil.NoSuchProcess, psutil.ZombieProcess):  # 进程对象已经消失或成为不可执行僵尸时可确认原求解身份不再运行。
        return False  # 返回自然消失语义，后续仍由本 job 子进程扫描和监控终态交叉证明。
    except (psutil.AccessDenied, KeyError, TypeError, ValueError, OSError, RuntimeError) as error:  # 权限或字段异常无法区分存活、复用与证据破损，必须失败关闭。
        raise RuntimeError(f"无法严格复核冻结进程身份：{error}") from error  # 抛出原因为链式异常，禁止把不可读误当已经退出。


def file_is_stable(path: Path, wait_seconds: float = 2.0) -> bool:  # 接收运行原件和等待秒数并判断大小、修改时刻在窗口内不变。
    first = path.stat()  # 读取第一次大小和纳秒级修改时刻。
    time.sleep(wait_seconds)  # 等待两秒覆盖常见退出缓冲刷新窗口，且不用于求解监控。
    second = path.stat()  # 读取第二次文件状态供精确对比。
    return first.st_size == second.st_size and first.st_mtime_ns == second.st_mtime_ns  # 两项均不变才可最终哈希与发布。


def parse_mntr_rows(path: Path) -> list[dict[str, float | int]]:  # 接收原生 MNTR 并返回每个已接受子步的七项控制与时间字段。
    rows: list[dict[str, float | int]] = []  # 初始化保持原生日志顺序的接受子步列表。
    for line in path.read_text(encoding="latin-1", errors="strict").splitlines():  # Latin-1 一一映射字节并逐行扫描，避免页眉本地字符失败。
        match = MNTR_ROW_PATTERN.match(line)  # 尝试识别五个整数和两个浮点前缀的数据行。
        if match is not None:  # 只有完整数值前缀才属于已接受子步，标题和空行忽略。
            row = {"load_step": int(match.group(1)), "substep": int(match.group(2)), "attempt": int(match.group(3)), "iterations": int(match.group(4)), "total_iterations": int(match.group(5)), "increment": float(match.group(6)), "total_time": float(match.group(7))}  # 转换为可审计机器字段。
            require(all(math.isfinite(float(value)) for value in row.values()), f"MNTR 数据行存在非有限值：{line}")  # 禁止 NaN 或无穷进入接受路径结论。
            rows.append(row)  # 保存当前已接受子步，不把失败尝试或二分事件混入。
    return rows  # 返回可与 OUT 完成标志交叉复核的顺序列表。


def parse_ls2_events(output_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:  # 接收完整 OUT 并返回按原文顺序的全部 LS2 事件及二分事件列表。
    events: list[dict[str, Any]] = []  # 初始化拒绝和二分交替序列。
    bisections: list[dict[str, Any]] = []  # 初始化仅含二分编号和新时间增量的子集。
    for match in LS2_EVENT_PATTERN.finditer(output_text):  # 按文本偏移顺序扫描每个完整事件块。
        if match.group("reject") is not None:  # 当前匹配为未完成载荷步事件。
            event = {"kind": "REJECTED", "substep": int(match.group("reject_substep")), "cumulative_iterations": int(match.group("cum_iter")), "text_offset": match.start()}  # 保存子步、累计迭代和原文位置。
        else:  # 当前匹配只能是 BEGIN BISECTION 事件。
            increment = float(match.group("increment"))  # 解析求解器实际选择的新时间增量。
            require(math.isfinite(increment) and increment > 0.0, "LS2 二分增量不是有限正数")  # 阻断破损、零或负步长。
            event = {"kind": "BISECTION", "number": int(match.group("bisect_number")), "increment": increment, "text_offset": match.start()}  # 保存二分编号、真实增量和原文位置。
            bisections.append(event)  # 同步加入二分专用列表供边界验证。
        events.append(event)  # 保持拒绝与二分的完整原文顺序。
    return events, bisections  # 返回可证明全部 LS2 尝试均未接受且最终到达最小增量的两种视图。


def write_new_batch(payloads: dict[Path, str]) -> None:  # 接收全部待发布文本并执行统一预检、同卷暂存、不可覆盖硬链接和安全回滚。
    require(bool(payloads), "批量发布列表为空")  # 禁止无工件调用被误认为封板成功。
    staging_paths = {path: path.with_name(f"{path.name}.codex_staging") for path in payloads}  # 为每个目标构造同目录唯一暂存路径以保证同卷原子操作。
    published_identities: dict[Path, tuple[int, int, int]] = {}  # 保存本调用创建目标的卷号、文件 ID 和大小供异常安全回滚。
    for target_path, staging_path in staging_paths.items():  # 在写出任何字节前统一关闭全部目标与暂存路径门。
        require(target_path.parent.is_dir(), f"最终工件父目录不存在：{target_path.parent}")  # 禁止隐式创建错误目录层级。
        require(not target_path.exists(), f"拒绝覆盖既有最终工件：{target_path}")  # 同一 run 只允许一次失败封板。
        require(not staging_path.exists(), f"发现遗留暂存工件：{staging_path}")  # 防止上次异常内容混入本次发布。
    try:  # 任一暂存或链接异常都进入只清理本调用对象的回滚分支。
        for target_path, rendered_text in payloads.items():  # 先把全部已验证文本写入对应同目录暂存文件。
            staging_path = staging_paths[target_path]  # 取得当前目标唯一暂存路径。
            with staging_path.open("x", encoding="utf-8", newline="\n") as handle:  # 使用排他创建、UTF-8 和 LF 写入完整暂存内容。
                handle.write(rendered_text)  # 一次写出内存中已完成渲染的文本。
        for target_path, staging_path in staging_paths.items():  # 全部暂存成功后按调用顺序逐一原子发布最终名称。
            os.link(staging_path, target_path)  # 目标存在时操作系统拒绝，避免检查与创建间的竞态覆盖。
            published_stat = target_path.stat()  # 取得本调用新建目标的数据对象身份。
            published_identities[target_path] = (int(published_stat.st_dev), int(published_stat.st_ino), int(published_stat.st_size))  # 冻结卷、文件 ID 和大小三元组。
            staging_path.unlink()  # 删除暂存名称并保留指向同一字节对象的最终名称。
    except Exception:  # 捕获任何 I/O 或竞态异常并恢复调用前无最终工件状态。
        for staging_path in staging_paths.values():  # 遍历只属于本次命名规则的尚未发布暂存路径。
            if staging_path.exists():  # 已成功发布的暂存名称已删除，只有残余才进入。
                staging_path.unlink()  # 删除本次未发布碎片而不触碰任何既有结果。
        for target_path, expected_identity in reversed(list(published_identities.items())):  # 逆序处理本调用已创建的部分目标。
            if target_path.is_file():  # 只有目标仍为普通文件时才允许读取身份。
                current_stat = target_path.stat()  # 取得当前路径的数据对象身份以防被外部替换。
                current_identity = (int(current_stat.st_dev), int(current_stat.st_ino), int(current_stat.st_size))  # 构造与发布时同格式的三元组。
                if current_identity == expected_identity:  # 仅当仍指向本调用创建的同一对象时允许删除。
                    target_path.unlink()  # 回滚本次部分发布，避免半套状态被下游误读。
        raise  # 原样重新抛出异常，禁止把回滚后的失败冒充成功。


def build_appended_ledger(run_dir: Path, virtual_texts: dict[Path, str], ledger_path: Path) -> tuple[str, int]:  # 接收运行根、待发布文本和最终账本路径并返回覆盖全部工件的追加账本文本与条目数。
    target_paths = {path.resolve() for path in virtual_texts} | {ledger_path.resolve()}  # 构造尚未存在或将在本批次发布的全部目标集合。
    existing_paths = [path for path in run_dir.rglob("*") if path.is_file() and path.resolve() not in target_paths and not path.name.endswith(".codex_staging")]  # 收集运行内既有普通工件并排除本批次目标与暂存名。
    ledger_entries: dict[str, str] = {}  # 初始化相对路径到内容摘要的完整最终映射。
    for path in existing_paths:  # 对准备、启动、监控和求解原件逐项计算当前真实字节摘要。
        relative_text = path.relative_to(run_dir).as_posix()  # 转换为稳定 POSIX 运行内相对路径。
        require(relative_text not in ledger_entries, f"最终账本既有路径重复：{relative_text}")  # 防止大小写或枚举异常造成歧义覆盖。
        ledger_entries[relative_text] = sha256_file(path)  # 把当前普通文件完整二进制摘要写入映射。
    for path, rendered_text in virtual_texts.items():  # 对尚未发布的终结器快照、审计、状态和报告计算虚拟摘要。
        relative_text = path.resolve().relative_to(run_dir).as_posix()  # 将目标限制并转换为运行内 POSIX 路径。
        require(relative_text not in ledger_entries, f"最终账本虚拟路径与既有工件冲突：{relative_text}")  # 发布前关闭重名和覆盖风险。
        ledger_entries[relative_text] = sha256_bytes(rendered_text.encode("utf-8"))  # 按实际 UTF-8 写出字节预先计算摘要。
    ordered_lines = [f"{ledger_entries[relative_text]}  {relative_text}" for relative_text in sorted(ledger_entries)]  # 按相对路径稳定排序生成标准双空格账本行。
    require(len(ordered_lines) > 29, "失败追加账本未覆盖准备账本之外的运行与终态工件")  # 至少必须比二十九项准备谱系更完整。
    return "\n".join(ordered_lines) + "\n", len(ordered_lines)  # 返回末尾单一 LF 的账本文本和可报告条目数。


def resolve_run(run_dir_value: Path) -> Path:  # 接收用户给定目录并返回通过项目边界与运行族门的规范绝对路径。
    run_dir = run_dir_value.resolve()  # 消除相对段、符号路径和当前目录歧义。
    require(run_dir.is_dir(), f"运行目录不存在：{run_dir}")  # 拒绝缺失或普通文件路径。
    require(run_dir.parent == RUNS_ROOT.resolve(), f"运行目录越出批准 ultra_runs 根：{run_dir}")  # 只允许直接子运行，禁止跨项目写入。
    require(run_dir.name.startswith(EXPECTED_RUN_PREFIX), f"运行目录不属于自适应迁移族：{run_dir.name}")  # 阻断静力、微单元或其他模型线。
    return run_dir  # 返回已通过边界与族名检查的唯一目标。


def validate_source_references(run_dir: Path, manifest: dict[str, Any], prepared_entries: dict[str, str]) -> dict[str, Any]:  # 接收当前运行、清单和准备映射并返回已复算的固定步基准与 K5 授权谱系摘要。
    baseline_relative = str(manifest.get("previous_migration_reference", "")).replace("\\", "/")  # 规范化默认 K5=0 固定 0.5% 输入基准引用路径。
    authorization_relative = str(manifest.get("adaptive_authorization_reference", "")).replace("\\", "/")  # 规范化 K5=1 证伪后续授权引用路径。
    require(baseline_relative == "qa/previous_migration_reference.json" and authorization_relative == "qa/adaptive_authorization_reference.json", "输入基准或后续授权引用路径不符合冻结合同")  # 禁止匿名或跨目录引用。
    require(baseline_relative in prepared_entries and authorization_relative in prepared_entries, "准备账本未冻结输入基准或授权引用 JSON")  # 两份谱系对象必须属于启动前字节身份。
    baseline_reference = read_json(run_dir / Path(baseline_relative))  # 读取默认 K5=0 固定步输入基准身份与五项摘要。
    authorization_reference = read_json(run_dir / Path(authorization_relative))  # 读取 K5=1 同轨失败及批准自适应下一步的五项摘要。
    require(baseline_reference.get("role") == "SINGLE_DIFFERENCE_INPUT_BASELINE" and authorization_reference.get("role") == "FOLLOWUP_AUTHORIZATION_EVIDENCE_NOT_INPUT_BASELINE", "基准和授权引用角色混淆")  # 防止从 K5=1 输入错误派生当前候选。
    require(baseline_reference.get("run_name") == manifest.get("single_difference_input_baseline_run") and authorization_reference.get("run_name") == manifest.get("authorization_evidence_run"), "清单与引用 JSON 的源运行名不一致")  # 关闭双字段运行身份门。
    baseline_run = (RUNS_ROOT / str(baseline_reference["run_name"])).resolve()  # 定位默认 K5=0 固定步源运行。
    authorization_run = (RUNS_ROOT / str(authorization_reference["run_name"])).resolve()  # 定位 K5=1 证伪授权源运行。
    require(baseline_run.parent == RUNS_ROOT.resolve() and baseline_run.is_dir() and authorization_run.parent == RUNS_ROOT.resolve() and authorization_run.is_dir(), "基准或授权源运行越界/缺失")  # 仅允许统一证据根直接子目录。
    baseline_paths = {"root_status_sha256": baseline_run / "C10_static_status.json", "manifest_sha256": baseline_run / "manifest.json", "final_artifact_ledger_sha256": baseline_run / "artifact_hashes.sha256", "main_input_sha256": baseline_run / "solver" / "c10_load_migration_static_main.inp", "runtime_abort_audit_sha256": baseline_run / "qa" / "runtime_abort_audit.json"}  # 建立输入基准五项权威原件映射。
    authorization_paths = {"root_status_sha256": authorization_run / "C10_static_status.json", "manifest_sha256": authorization_run / "manifest.json", "final_artifact_ledger_sha256": authorization_run / "artifact_hashes.sha256", "main_input_sha256": authorization_run / "solver" / "c10_load_migration_static_main.inp", "runtime_abort_audit_sha256": authorization_run / "qa" / "runtime_abort_audit.json"}  # 建立授权运行五项权威原件映射。
    require(all(path.is_file() and sha256_file(path) == str(baseline_reference.get(field)) for field, path in baseline_paths.items()), "输入基准五项原件缺失或摘要漂移")  # 逐项复算状态、清单、账本、主控和失败审计。
    require(all(path.is_file() and sha256_file(path) == str(authorization_reference.get(field)) for field, path in authorization_paths.items()), "授权运行五项原件缺失或摘要漂移")  # 逐项复算 K5 证伪运行关键原件。
    baseline_final_entries = parse_hash_ledger(baseline_paths["final_artifact_ledger_sha256"], baseline_run)  # 复算输入基准最终账本全部当前文件字节。
    authorization_final_entries = parse_hash_ledger(authorization_paths["final_artifact_ledger_sha256"], authorization_run)  # 复算授权运行最终账本全部当前文件字节。
    require(len(baseline_final_entries) == 59 and len(authorization_final_entries) == 59, "输入基准或授权运行最终账本不是五十九项")  # 固定两条已封板源谱系完整规模。
    require(authorization_reference.get("single_difference_observed_effect") == "NO_CHANGE_IN_LS2_FIRST_TWO_NR_STATES_AT_PRINTED_PRECISION" and authorization_reference.get("authorized_next_diagnostic") == "LS2_ADAPTIVE_SUBSTEPS_200_2000_200_ALLOW_0_05_PERCENT_MINIMUM_INCREMENT", "K5 授权未证明同轨无效或未批准当前自适应下一步")  # 固定排除 K5 假设后的唯一授权。
    return {"input_baseline_run": baseline_run.name, "input_baseline_final_ledger_sha256": sha256_file(baseline_paths["final_artifact_ledger_sha256"]), "input_baseline_final_ledger_entry_count": len(baseline_final_entries), "authorization_run": authorization_run.name, "authorization_final_ledger_sha256": sha256_file(authorization_paths["final_artifact_ledger_sha256"]), "authorization_final_ledger_entry_count": len(authorization_final_entries), "authorization_effect": authorization_reference["single_difference_observed_effect"], "authorized_diagnostic": authorization_reference["authorized_next_diagnostic"], "all_external_source_entries_rehashed": True}  # 返回可纳入失败审计的两条外部源谱系摘要。


def validate_monitor_chain(run_dir: Path, manifest: dict[str, Any], launch_claim_path: Path, process_identity_path: Path, prepared_entries: dict[str, str], output_path: Path, error_path: Path, native_monitor_path: Path) -> dict[str, Any]:  # 接收完整运行身份和原件路径并返回由 JSONL 独立复算的自然退出监控摘要。
    claim_path = run_dir / "qa" / "runtime_hard_stop_monitor_claim.json"  # 定位监控器在采样和任何动作前排他创建的认领工件。
    samples_path = run_dir / "qa" / "runtime_hard_stop_monitor_samples.jsonl"  # 定位每十秒刷盘的资源、进程和日志增量流水。
    final_path = run_dir / "qa" / "runtime_hard_stop_monitor_final.json"  # 定位进程树稳定退出后排他创建的监控终态。
    require(claim_path.is_file() and samples_path.is_file() and final_path.is_file(), "缺少监控认领、样本或终态工件")  # 三件缺一即不能证明自然退出。
    claim = read_json(claim_path)  # 读取冻结监控代码、启动链摘要和初始进程绑定。
    final = read_json(final_path)  # 读取资源极值、硬事件、控制器动作和文件稳定性终态。
    sample_lines = [line for line in samples_path.read_text(encoding="utf-8", errors="strict").splitlines() if line.strip()]  # 读取并保留每行 JSON 对象边界。
    require(bool(sample_lines), "监控样本流水为空")  # 至少需要一次真实附着样本。
    samples = [json.loads(line) for line in sample_lines]  # 逐行解析，任一破损 JSON 都直接失败关闭。
    require(all(isinstance(sample, dict) and sample.get("schema_version") == 1 for sample in samples), "监控样本存在非对象或未知 schema")  # 只接受冻结第一版对象记录。
    indexes = [int(sample.get("sample_index", -1)) for sample in samples]  # 提取样本序号供连续性复算。
    available_ram = [int(sample.get("physical_memory_available_bytes", -1)) for sample in samples]  # 提取每轮可用物理内存供最小值复算。
    disk_free = [int(sample.get("disk_free_bytes", -1)) for sample in samples]  # 提取每轮运行盘余量供最小值复算。
    related_rss = [int(sample.get("related_rss_bytes", -1)) for sample in samples]  # 提取本 job 进程合计工作集供峰值复算。
    low_ram_seconds = [float(sample.get("low_ram_continuous_seconds", -1.0)) for sample in samples]  # 提取连续低于一 GiB 计时供六十秒门复算。
    sample_equations = [int(value) for sample in samples for value in sample.get("new_equation_counts", [])]  # 按流水顺序重建监控观察到的全部方程数。
    sample_hard_events = [event for sample in samples for event in sample.get("new_hard_events", [])]  # 按流水顺序重建全部控制器硬事件。
    require(claim.get("schema_version") == 1 and claim.get("status") == "MONITOR_CLAIMED", "监控认领 schema 或状态错误")  # 只接受采样前冻结的第一版认领语义。
    require(claim.get("run_name") == run_dir.name and claim.get("jobname") == manifest.get("jobname"), "监控认领运行或 job 身份错配")  # 关闭跨运行工件复制。
    require(claim.get("runtime_launch_sha256") == sha256_file(run_dir / "runtime_launch.json") and claim.get("runtime_launch_claim_sha256") == sha256_file(launch_claim_path), "监控认领引用的启动链摘要不一致")  # 证明监控附着当前不可覆盖启动链。
    require(claim.get("runtime_process_identity_sha256") == sha256_file(process_identity_path), "监控认领引用的增强进程身份摘要不一致")  # 证明监控绑定当前防 PID 回收身份。
    monitor_relative = str(manifest.get("runtime_monitor_script", "")).replace("\\", "/")  # 规范化清单声明的冻结监控器快照路径。
    require(monitor_relative == "input_snapshot/ultra_c10_adaptive_monitor.py" and monitor_relative in prepared_entries, "准备账本未冻结批准监控器快照")  # 固定运行时监控代码属于启动前谱系。
    require(claim.get("monitor_script_sha256") == manifest.get("runtime_monitor_script_sha256") == prepared_entries[monitor_relative], "监控代码在认领、清单和准备账本间不一致")  # 三方闭合实际执行代码字节身份。
    require(final.get("schema_version") == 1 and final.get("status") == "NATURAL_PROCESS_TREE_EXITED_STABLE_WITHOUT_MONITOR_HARD_STOP", "监控终态不是自然稳定退出且无硬停")  # 控制器中止或完整性阻断绝不能借用本终结器。
    require(final.get("run_name") == run_dir.name and final.get("jobname") == manifest.get("jobname"), "监控终态运行或 job 身份错配")  # 关闭其他运行终态复制。
    require(final.get("monitor_claim_sha256") == sha256_file(claim_path) and final.get("samples_sha256") == sha256_file(samples_path), "监控终态引用的认领或流水摘要不一致")  # 防止终态提交后替换先行证据。
    require(final.get("hard_events") == [] and final.get("controller_abort", {}).get("requested") is False, "监控器记录了硬事件或控制器中止")  # 自然 NCNV 必须完全由 MAPDL 自身结束。
    require(final.get("monitor_block_reason") is None and final.get("final_related_processes") == [], "监控终态仍有阻断或本 job 进程")  # 退出证据必须闭合且进程树清空。
    require(final.get("final_lock_file", {}).get("exists") is False and not any((run_dir / "solver").glob("*.lock")), "监控终态或当前目录仍存在 MAPDL lock")  # 双向证明数据库已关闭。
    require(indexes == list(range(1, len(samples) + 1)) and int(final.get("sample_count", -1)) == len(samples), "监控样本序号或终态计数不能复算")  # 防止删行、重排或伪造样本总数。
    require(all(value > 0 for value in available_ram) and min(available_ram) == int(final.get("minimum_physical_memory_available_bytes", -1)), "监控最小可用内存不能由流水复算")  # 独立复算资源极值。
    require(all(value > 0 for value in disk_free) and min(disk_free) == int(final.get("minimum_disk_free_bytes", -1)), "监控最小磁盘余量不能由流水复算")  # 独立复算磁盘极值。
    require(all(value >= 0 for value in related_rss) and max(related_rss) == int(final.get("maximum_related_rss_bytes", -1)), "监控最大工作集不能由流水复算")  # 独立复算本 job 内存峰值。
    require(all(math.isfinite(value) and 0.0 <= value < 60.0 for value in low_ram_seconds), "监控出现持续六十秒低内存或无效计时")  # 资源硬线不得被普通失败掩盖。
    require(sample_equations == final.get("observed_equation_counts") and final.get("unique_equation_counts") == [EXPECTED_EQUATION_COUNT], "监控方程数流水缺失、漂移或摘要不一致")  # 保持单层拓扑方程秩不变。
    require(sample_hard_events == final.get("hard_events"), "监控硬事件流水与终态摘要不一致")  # 防止样本已有硬事件而终态清空。
    require(int(final.get("minimum_physical_memory_available_bytes", 0)) >= 512 * 1024**2 and int(final.get("minimum_disk_free_bytes", 0)) >= 32 * 1024**3, "监控资源极值越过硬停线却未形成事件")  # 独立复核控制器动作合同。
    final_file_map = {"final_out_file": output_path, "final_err_file": error_path, "final_mntr_file": native_monitor_path}  # 建立监控三项权威文件快照到当前原件映射。
    for field, path in final_file_map.items():  # 逐项核对存在性、大小和纳秒修改时刻均未在监控提交后变化。
        snapshot = final.get(field, {})  # 读取当前终态中的文件快照对象。
        stat = path.stat()  # 取得当前真实原件状态。
        require(snapshot.get("exists") is True and int(snapshot.get("size_bytes", -1)) == stat.st_size and int(snapshot.get("mtime_ns", -1)) == stat.st_mtime_ns, f"监控提交后文件发生变化：{path.name}")  # 关闭尾部追加或替换窗口。
    return {"status": final["status"], "claim_sha256": sha256_file(claim_path), "samples_sha256": sha256_file(samples_path), "final_sha256": sha256_file(final_path), "sample_count": len(samples), "minimum_physical_memory_available_bytes": min(available_ram), "minimum_disk_free_bytes": min(disk_free), "maximum_related_rss_bytes": max(related_rss), "maximum_low_ram_continuous_seconds": max(low_ram_seconds), "observed_equation_counts": sample_equations, "controller_abort_requested": False, "hard_event_count": 0, "files_stable_at_monitor_commit": True}  # 返回全部由原始流水重算的自然退出、资源、方程和动作摘要。


def finalize(run_dir_value: Path) -> Path:  # 接收唯一运行目录并在全部严格门通过后返回新建的失败根状态路径。
    run_dir = resolve_run(run_dir_value)  # 规范化并关闭项目根、直接子目录和运行族边界门。
    manifest_path = run_dir / "manifest.json"  # 定位准备账本冻结的求解身份、输入和许可清单。
    root_status_path = run_dir / "C10_static_status.json"  # 定位准备阶段根状态，必须保持未完成且不允许生产。
    launch_claim_path = run_dir / "runtime_launch_claim.json"  # 定位 Popen 前排他写出的启动权认领。
    launch_path = run_dir / "runtime_launch.json"  # 定位 Popen 后立即写出的最小 PID 启动记录。
    process_identity_path = run_dir / "runtime_process_identity.json"  # 定位 PID、创建时刻、二进制和真实命令行增强身份。
    prepared_ledger_path = run_dir / "artifact_hashes.sha256"  # 定位启动前二十九项不可变字节谱系。
    manifest = read_json(manifest_path)  # 读取并保留准备态 manifest 原件，不在失败封板中覆盖它。
    root_status = read_json(root_status_path)  # 读取并保留准备态根状态原件，不伪造成功字段。
    launch_claim = read_json(launch_claim_path)  # 读取进程创建前冻结的唯一执行权和资源快照。
    launch = read_json(launch_path)  # 读取真实 Popen PID、完整参数和三段启动链摘要。
    process_identity = read_json(process_identity_path)  # 读取防 PID 回收的操作系统进程身份。
    require(manifest.get("schema_version") == 8 and root_status.get("schema_version") == 3, "manifest 或准备态根状态 schema 不是当前冻结版本")  # 拒绝历史固定步包借用本终结器。
    require(manifest.get("run_name") == run_dir.name and root_status.get("run_name") == run_dir.name, "manifest 或准备态根状态运行名不一致")  # 关闭目录复制和改名错配。
    require(manifest.get("jobname") == root_status.get("jobname") == launch.get("jobname") == launch_claim.get("jobname") == process_identity.get("jobname"), "五段工件 jobname 不一致")  # 固定唯一结果文件族身份。
    require(manifest.get("status") == "STATIC_DIAGNOSTIC_PREPARED" and root_status.get("status") == "STATIC_DIAGNOSTIC_PREPARED", "准备态清单或根状态已被覆盖/终结")  # 同一 run 只允许一次不可覆盖封板。
    require(manifest.get("diagnostic_subtype") == EXPECTED_SUBTYPE and root_status.get("diagnostic_subtype") == EXPECTED_SUBTYPE, "运行不是批准的 0.05% 自适应迁移子类型")  # 阻断固定步或 K5 运行。
    require(manifest.get("single_variable_change") == EXPECTED_SINGLE_CHANGE and root_status.get("single_variable_change") == EXPECTED_SINGLE_CHANGE, "运行唯一变量不是 LS2 NSBMX 200→2000")  # 禁止多变量运行进入因果结论。
    require(manifest.get("load_path_mode") == EXPECTED_LOAD_PATH and manifest.get("initial_state_load_path") == EXPECTED_INITIAL_PATH and manifest.get("initial_state_equilibrium_audit") == EXPECTED_INITIAL_AUDIT, "迁移载荷路径或准备态物理审计身份漂移")  # 固定荷载位置而非荷载总量变化。
    require(manifest.get("constraint_topology") == "SINGLE_TYPE72_NO_AUX_NO_TYPE73", "约束拓扑不是单层 TYPE72")  # 阻断旧串联 TYPE72→TYPE73 病态模型。
    require(manifest.get("mpc184_keyopt5_static") == 0 and manifest.get("prestressed_modal_requires_keyopt5_restore_to_zero") is False, "自适应运行未保持默认 TYPE72 KEYOPT(5)=0")  # 保持相对输入基准的唯一差异。
    require(manifest.get("modal_requested") is False and manifest.get("production_claim_allowed") is False and root_status.get("valid_for_production") is False, "准备工件意外允许模态或生产声明")  # 失败封板不能降级任何用途门。
    increment_change = manifest.get("migration_increment_change")  # 读取准备态冻结的 NSUBST 三参数和百分比解释对象。
    require(isinstance(increment_change, dict), "manifest 缺少 migration_increment_change 对象")  # 后续字段检查只接受具名对象。
    require(increment_change.get("nsbstp") == 200 and increment_change.get("nsbmx") == 2000 and increment_change.get("nsbmn") == 200, "manifest NSUBST 三参数不是 200/2000/200")  # 固定初始、最大和最小子步数合同。
    require(math.isclose(float(increment_change.get("new_initial_fraction", -1.0)), 0.005, rel_tol=0.0, abs_tol=0.0) and math.isclose(float(increment_change.get("new_minimum_fraction", -1.0)), 0.0005, rel_tol=0.0, abs_tol=0.0), "manifest 初始或最小迁移比例不是 0.5%/0.05%")  # 防止文字比例和命令分叉。
    prepared_entries = parse_hash_ledger(prepared_ledger_path, run_dir)  # 在读取求解结论前逐项复算全部准备输入字节。
    prepared_ledger_sha256 = sha256_file(prepared_ledger_path)  # 计算准备账本自身摘要供启动与监控三方交叉核对。
    manifest_sha256 = sha256_file(manifest_path)  # 计算受准备账本保护的 manifest 摘要供启动链核对。
    source_reference_audit = validate_source_references(run_dir, manifest, prepared_entries)  # 复算默认 K5 输入基准和 K5=1 授权运行各五十九项完整外部谱系。
    require(launch_claim.get("schema_version") == 1 and launch_claim.get("status") == "LAUNCH_CLAIMED_NOT_YET_STARTED", "启动认领 schema 或状态不符合 Popen 前合同")  # 只接受当前不可覆盖启动器。
    require(launch.get("schema_version") == 1 and launch.get("status") == "RUNNING_DIAGNOSTIC_IDENTITY_CAPTURE_PENDING", "最小启动记录 schema 或状态不符合 Popen 后合同")  # PID 后增强身份必须位于独立工件。
    require(process_identity.get("schema_version") == 1 and process_identity.get("status") == "MAIN_PROCESS_IDENTITY_CAPTURED", "增强进程身份 schema 或状态错误")  # 禁止身份捕获失败运行归档为自然退出。
    require(launch_claim.get("run_name") == run_dir.name and launch.get("run_name") == run_dir.name and process_identity.get("run_name") == run_dir.name, "启动三段链运行名不一致")  # 关闭跨运行启动工件复制。
    require(launch_claim.get("diagnostic_subtype") == EXPECTED_SUBTYPE and launch.get("diagnostic_subtype") == EXPECTED_SUBTYPE, "启动链诊断子类型漂移")  # 启动认领和真实执行必须保持相同诊断身份。
    require(launch_claim.get("single_variable_change") == EXPECTED_SINGLE_CHANGE and launch.get("single_variable_change") == EXPECTED_SINGLE_CHANGE, "启动链唯一变量漂移")  # 证明启动时仍是唯一 NSBMX 差异。
    require(launch_claim.get("manifest_sha256") == manifest_sha256 and launch.get("manifest_sha256") == manifest_sha256, "启动链 manifest 摘要不一致")  # 关闭认领前后清单字节变化。
    require(launch_claim.get("prepared_ledger_sha256") == prepared_ledger_sha256 and launch.get("prepared_ledger_sha256") == prepared_ledger_sha256, "启动链准备账本摘要不一致")  # 关闭认领前后输入谱系变化。
    require(int(launch_claim.get("prepared_ledger_entry_count", -1)) == len(prepared_entries) == int(launch.get("prepared_ledger_entry_count", -1)), "启动链准备账本条目数不一致")  # 防止只核对账本文件而遗漏截断条目。
    require(launch.get("launch_claim_sha256") == sha256_file(launch_claim_path) and process_identity.get("runtime_launch_sha256") == sha256_file(launch_path), "Popen 前认领、最小记录和增强身份摘要链断裂")  # 三段不可覆盖启动链必须连续。
    require(launch_claim.get("prelaunch_resources") == launch.get("prelaunch_resources"), "认领与启动记录的资源快照不一致")  # 防止启动门在 Popen 两侧改写。
    require(launch_claim.get("production_claim_allowed") is False and launch.get("production_claim_allowed") is False, "启动链意外允许生产声明")  # 低内存诊断例外不得升级用途。
    launch_argv = [str(value) for value in manifest.get("launch_argv", [])]  # 从已核对清单恢复完整批准命令数组。
    require(launch_argv == [str(value) for value in launch_claim.get("launch_argv", [])] == [str(value) for value in launch.get("launch_argv", [])] == [str(value) for value in process_identity.get("command_line", [])], "清单、认领、启动和操作系统命令行数组不一致")  # 固定真实执行入口。
    solver_dir = (run_dir / "solver").resolve()  # 定位本 run 唯一 MAPDL 工作目录。
    require(solver_dir.is_dir(), f"缺少 solver 目录：{solver_dir}")  # 在解析参数路径前关闭目录存在门。
    require(launch_argv.count("-b") == 1 and launch_argv.count("-smp") == 1 and argument_value(launch_argv, "-np") == "1", "启动参数不是唯一批处理 SMP1")  # 固定已批准单进程诊断模式。
    require(argument_value(launch_argv, "-j") == str(manifest["jobname"]), "启动 -j 与 manifest 不一致")  # 固定结果文件族名。
    require(Path(argument_value(launch_argv, "-dir")).resolve() == solver_dir, "启动 -dir 未指向本 run solver 目录")  # 阻断跨运行输出污染。
    input_path = Path(argument_value(launch_argv, "-i")).resolve()  # 定位实际传入 MAPDL 的主控输入。
    output_path = Path(argument_value(launch_argv, "-o")).resolve()  # 定位命令行指定的权威 OUT 原件。
    require(input_path == (run_dir / str(manifest.get("main_input"))).resolve() and input_path.parent == solver_dir, "启动主输入与 manifest 或 solver 目录不一致")  # 证明求解确实使用冻结主控。
    require(output_path.parent == solver_dir and output_path.name.casefold() == f"{manifest['jobname']}.out".casefold(), "启动 OUT 不属于本 job")  # 固定权威输出文件。
    mapdl_path = Path(launch_argv[0]).resolve()  # 以 argv 首项定位实际 MAPDL 二进制。
    require(mapdl_path == Path(str(manifest.get("mapdl_executable"))).resolve() and mapdl_path.is_file(), "MAPDL 可执行文件路径漂移或缺失")  # 固定批准版本位置。
    require(sha256_file(mapdl_path) == str(manifest.get("mapdl_executable_sha256")), "MAPDL 可执行文件 SHA-256 漂移")  # 固定实际二进制字节身份。
    input_relative = input_path.relative_to(run_dir).as_posix()  # 形成准备账本内主控相对路径。
    require(input_relative in prepared_entries and prepared_entries[input_relative] == manifest.get("main_input_sha256") == sha256_file(input_path), "主控输入在账本、manifest 和当前字节间不一致")  # 三方关闭输入漂移。
    commands = [line.split("!", maxsplit=1)[0].strip().upper().replace(" ", "") for line in input_path.read_text(encoding="utf-8", errors="strict").splitlines()]  # 去除中文注释并规范化实际 APDL 命令。
    require(commands.count("NSUBST,200,2000,200") == 1 and commands.count("NSUBST,200,200,200") == 0, "实际主控未唯一采用 NSUBST,200,2000,200")  # 固定自适应最小步合同。
    require(commands.count("KEYOPT,72,5,1") == 0 and commands.count("KBC,1") == 1 and commands.count("KBC,0") == 1, "实际主控 K5 或两步 KBC 合同漂移")  # 保持默认 K5 和阶跃/斜坡顺序。
    require(commands.count("/INPUT,APPLY_CONSTANT_TOTAL_LOAD_POSITION_MIGRATION_V1,INP") == 2 and sum(1 for command in commands if command.startswith("CNVTOL,")) == 4, "实际主控迁移 include 或四项 CNVTOL 数量漂移")  # 防止载荷或收敛门被修改。
    require("PERTURB,MODAL" not in commands and not any(command.startswith("MODOPT,") for command in commands), "实际主控包含模态命令")  # 静力自然失败运行绝不能尝试模态。
    require(process_identity.get("pid") == launch.get("main_pid") and str(Path(str(process_identity.get("executable", ""))).resolve()).casefold() == str(mapdl_path).casefold(), "增强进程 PID 或二进制身份与启动记录不一致")  # 关闭 PID 和可执行文件身份门。
    require(not process_identity_is_alive(process_identity), f"原 MAPDL 进程身份仍存活：{process_identity.get('pid')}")  # 求解运行中禁止执行终结器。
    active_job_processes: list[int] = []  # 初始化仍携带本 jobname 和 solver 目录的 ANSYS 进程列表。
    for process in psutil.process_iter(["pid", "name", "cmdline"]):  # 枚举本机进程以覆盖包装器早退但真实 worker 仍存活的情况。
        try:  # 进程可能在枚举期间退出、拒绝访问或成为僵尸。
            process_name = str(process.info.get("name") or "").casefold()  # 读取映像名并归一大小写。
            command_line = " ".join(process.info.get("cmdline") or []).casefold()  # 合并参数供 job 和目录双条件筛选。
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):  # 捕获只读进程瞬态异常。
            continue  # 无法稳定读取的瞬时对象不作为活动证据。
        if process_name.startswith("ansys") and str(manifest["jobname"]).casefold() in command_line and str(solver_dir).casefold() in command_line:  # 仅锁定本 job 本目录的求解器进程。
            active_job_processes.append(int(process.info["pid"]))  # 保存仍活动 PID 供明确拒绝说明。
    require(not active_job_processes, f"仍有本 job 求解器进程活动：{active_job_processes}")  # 包装器和真实 worker 均退出后才可封板。
    error_path = solver_dir / f"{manifest['jobname']}.err"  # 定位本 job 独立 ERR 原件。
    native_monitor_path = solver_dir / f"{manifest['jobname']}.mntr"  # 定位本 job 原生已接受子步 MNTR。
    require(output_path.is_file() and output_path.stat().st_size > 1_000_000, "主 OUT 缺失或异常过小")  # 全桥装配与 LS1/LS2 路径必须产生充分原始输出。
    require(error_path.is_file() and error_path.stat().st_size > 0, "独立 ERR 缺失或为空")  # 原生 NCNV 失败必须留下错误工件。
    require(native_monitor_path.is_file() and native_monitor_path.stat().st_size > 0, "原生 MNTR 缺失或为空")  # LS1 接受事实必须有独立历史文件。
    require(file_is_stable(output_path) and file_is_stable(error_path) and file_is_stable(native_monitor_path), "OUT、ERR 或 MNTR 在稳定检查窗口仍变化")  # 防止退出缓冲尚未刷新就解析。
    monitor_audit = validate_monitor_chain(run_dir, manifest, launch_claim_path, process_identity_path, prepared_entries, output_path, error_path, native_monitor_path)  # 先证明自然稳定退出、无控制器动作和三文件未漂移。
    require(not (solver_dir / f"{manifest['jobname']}.abt").exists(), "发现控制器 .abt 文件，不能归类为 MAPDL 自然 NCNV")  # 进一步排除外部中止文件残留。
    output_text = output_path.read_text(encoding="latin-1", errors="strict")  # 以一一字节映射方式读取完整 OUT，保留数值和英文原生证据。
    error_text = error_path.read_text(encoding="latin-1", errors="strict")  # 以同一策略读取 ERR，避免本地页眉字符替换。
    output_upper = output_text.upper()  # 构造不区分大小写的原生日志门视图。
    error_upper = error_text.upper()  # 构造 ERR 的大写门视图。
    equation_counts = [int(value) for value in EQUATION_PATTERN.findall(output_text)]  # 提取全部装配方程数供秩恒定审计。
    pivots = [float(value) for value in PIVOT_PATTERN.findall(output_text)]  # 提取全部稀疏分解最小主元供正定性审计。
    require(equation_counts and sorted(set(equation_counts)) == [EXPECTED_EQUATION_COUNT], "OUT 方程数缺失、漂移或不是 1,234,834")  # 阻断旧双层约束和运行时拓扑变化。
    require(pivots and all(math.isfinite(value) and value > 0.0 for value in pivots), "OUT 最小主元缺失、非有限或非正")  # 拒绝 small、zero、negative pivot 路径。
    require(math.isclose(pivots[0], EXPECTED_LS1_PIVOT, rel_tol=0.0, abs_tol=1.0e-6), f"LS1 首个正主元与健康基准不一致：{pivots[0]}")  # 证明 LS1 起始分解仍与修复后全桥一致。
    forbidden_fragments = ["*** FATAL ***", "PROBLEM TERMINATED DUE TO A FATAL", "SMALL EQUATION SOLVER PIVOT", "ZERO PIVOT", "NEGATIVE PIVOT", "CNVTOL COMMAND IS IGNORED", "INTERNALLY RESET TO CNVTOL"]  # 冻结不得被普通 NCNV 掩盖的硬失败短语。
    require(not any(fragment in output_upper or fragment in error_upper for fragment in forbidden_fragments), "OUT/ERR 含 FATAL、病态主元或 CNVTOL 被忽略/重置证据")  # 硬事件只能由监控器停止，不能进入自然失败分支。
    completed_steps = [(int(step), int(substep)) for step, substep in LS_COMPLETED_PATTERN.findall(output_text)]  # 提取所有真正接受的载荷步结果集标志。
    require(completed_steps.count((1, 1)) == 1 and not any(step == 2 for step, _ in completed_steps), f"接受子步路径不是仅 LS1/1：{completed_steps}")  # 证明 LS1 接受且 LS2 无可用端点。
    require(">>> SOLUTION CONVERGED AFTER EQUILIBRIUM ITERATION   4" in output_text, "OUT 未证明 LS1 在第 4 次平衡迭代收敛")  # 冻结健康形成态基准的迭代事实。
    mntr_rows = parse_mntr_rows(native_monitor_path)  # 解析独立原生接受子步历史。
    require(len(mntr_rows) == 1, f"MNTR 接受行数量不是仅 LS1 一行：{len(mntr_rows)}")  # 任何 LS2 接受行都改变本失败类型。
    mntr_ls1 = mntr_rows[0]  # 读取唯一接受行供各控制列精确核对。
    require(int(mntr_ls1["load_step"]) == 1 and int(mntr_ls1["substep"]) == 1 and int(mntr_ls1["attempt"]) == 1 and int(mntr_ls1["iterations"]) == 4 and int(mntr_ls1["total_iterations"]) == 4, f"MNTR LS1 控制列不符合 1/1/1/4/4：{mntr_ls1}")  # 证明唯一行确为健康 LS1。
    require(math.isclose(float(mntr_ls1["increment"]), 1.0, rel_tol=0.0, abs_tol=1.0e-12) and math.isclose(float(mntr_ls1["total_time"]), 1.0, rel_tol=0.0, abs_tol=1.0e-12), "MNTR LS1 增量或累计时间不是 1.0")  # 固定旧荷载位置平衡点时刻。
    ls2_events, bisections = parse_ls2_events(output_text)  # 重建所有 LS2 未完成与自动二分的原文顺序。
    require(len(bisections) >= 1 and len(ls2_events) == 2 * len(bisections) + 1, "LS2 事件数量不是拒绝/二分交替且以最终拒绝结束")  # 每次继续都须先拒绝，最后最小步拒绝后不再二分。
    expected_kinds = ["REJECTED" if index % 2 == 0 else "BISECTION" for index in range(len(ls2_events))]  # 构造 R/B/R/B/.../R 的严格路径模板。
    require([str(event["kind"]) for event in ls2_events] == expected_kinds, f"LS2 事件顺序不是严格拒绝—二分交替：{ls2_events}")  # 关闭乱序、遗漏或额外二分。
    rejected_events = [event for event in ls2_events if event["kind"] == "REJECTED"]  # 提取全部未完成尝试供子步和累计迭代审计。
    require(all(int(event["substep"]) == 1 for event in rejected_events), "LS2 拒绝路径出现非第一子步，不能归类为首端点失败")  # 当前诊断预计首个迁移端点始终未接受。
    require([int(event["number"]) for event in bisections] == list(range(1, len(bisections) + 1)), "二分编号不从 1 连续递增")  # 防止日志截断或事件遗漏。
    bisection_increments = [float(event["increment"]) for event in bisections]  # 提取每次实际新时间增量供单调和最小步门。
    require(all(INCREMENT_TOLERANCE < value <= MAXIMUM_INCREMENT + INCREMENT_TOLERANCE for value in bisection_increments), f"二分增量越出 (0,5E-6]：{bisection_increments}")  # 拒绝非法或超最大迁移步长。
    require(all(bisection_increments[index] < bisection_increments[index - 1] for index in range(1, len(bisection_increments))), "二分增量未严格递减")  # 证明 AUTOTS 真正沿失败路径逐次切回。
    require(math.isclose(bisection_increments[-1], MINIMUM_INCREMENT, rel_tol=0.0, abs_tol=INCREMENT_TOLERANCE), f"最终二分未到 5E-7 最小增量：{bisection_increments[-1]}")  # 固定 0.05% 最小迁移比例已经实际尝试。
    require(int(rejected_events[-1]["text_offset"]) > int(bisections[-1]["text_offset"]), "最终拒绝没有发生在最小步二分之后")  # 证明最小步不是只打印而未尝试。
    require(output_upper.count("TERMINATE ANALYSIS IF NOT CONVERGED . . . . . .YES (EXIT)") >= 2, "OUT 未冻结 NCNV=EXIT 的 LS1/LS2 原生求解选项")  # 证明最终退出策略来自 MAPDL 非收敛控制而非外部抢停。
    final_rejection_tail = output_upper[int(rejected_events[-1]["text_offset"]):]  # 截取最终最小步拒绝后的原生终止证据区间。
    native_ncnv_phrases = ["SOLUTION NOT CONVERGED", "SOLUTION DID NOT CONVERGE", "CONVERGENCE FAILURE", "NO CONVERGENCE", "NOT CONVERGED"]  # 列出 MAPDL 版本可能使用的等价原生 NCNV 措辞。
    matched_native_ncnv_phrases = [phrase for phrase in native_ncnv_phrases if phrase in final_rejection_tail]  # 提取最终拒绝之后真实命中的原生非收敛措辞供机器审计。
    require(bool(matched_native_ncnv_phrases), "最终最小步拒绝后缺少 MAPDL 原生非收敛措辞")  # 不允许只凭高残差推断 NCNV。
    native_failure_match = re.search(rf"SOLUTION NOT CONVERGED AT TIME\s+({NUMBER_PATTERN})\s+\(LOAD STEP\s+2\s+SUBSTEP\s+1\)\.", final_rejection_tail, re.IGNORECASE)  # 提取最终错误块明确指向 LS2 首子步的失败伪时间。
    require(native_failure_match is not None, "最终错误块未明确记录 load step 2 substep 1 的 Solution not converged")  # 防止其他阶段错误借用同一普通短语。
    native_failure_time = float(native_failure_match.group(1))  # 把原生失败伪时间转换为可审计有限数。
    require(math.isfinite(native_failure_time) and 1.0 - INCREMENT_TOLERANCE <= native_failure_time <= 1.0 + MAXIMUM_INCREMENT + INCREMENT_TOLERANCE, f"原生 NCNV 伪时间越出 LS2 首迁移端点显示范围：{native_failure_time}")  # 允许页尾低精度把 1.0000005 显示为 1.0，但仍由前述事件偏移严格证明最小步已实际尝试。
    require("*** ERROR ***" in final_rejection_tail or "*** ERROR ***" in error_upper, "最终最小步 NCNV 未形成 MAPDL 原生错误块")  # 普通错误允许自然退出但必须留下原件。
    require(re.search(r"REASON FOR TERMINATION[.\s]*UNCONVERGED SOLUTION", output_upper) is not None, "OUT 缺少 REASON FOR TERMINATION=UNCONVERGED SOLUTION 原生证据")  # 用重启动摘要确认终止原因而不是外部退出。
    require("PROBLEM TERMINATED BY INDICATED ERROR(S) OR BY END OF INPUT DATA" in output_upper and "RUN COMPLETED" in output_upper, "OUT 缺少原生错误终止和批处理自然完成标志")  # 证明 MAPDL 自行完成错误退出而非进程被杀。
    error_summaries = [int(value) for value in re.findall(r"NUMBER OF ERROR\s+MESSAGES ENCOUNTERED\s*=\s*(\d+)", output_text, re.IGNORECASE)]  # 提取页尾唯一错误累计值供普通 NCNV 闭合。
    require(error_summaries == [1], f"OUT 错误摘要不是唯一一个原生 NCNV 错误：{error_summaries}")  # 防止其他错误与 NCNV 混合后仍封板为单一原因。
    gate_path = solver_dir / "c10_gate_status.txt"  # 定位主控 fail-closed 状态文本。
    require(gate_path.is_file() and file_is_stable(gate_path), "缺少或仍变化的 c10_gate_status.txt")  # 失败分支必须形成稳定门禁原件。
    gate_text = gate_path.read_text(encoding="latin-1", errors="strict").upper()  # 读取并规范化门禁状态文本。
    require("STATUS=PASSED" not in gate_text, "APDL 门禁意外记录通过状态")  # 任一成功标志都与原生 NCNV 失败互斥。
    explicit_gate_rejection = "STATUS=REJECTED" in gate_text and "REASON=LS2_LOAD_POSITION_MIGRATION_NOT_CONVERGED" in gate_text  # 判断 NCNV 若返回主控后是否执行了显式拒绝分支。
    native_exit_before_gate_branch = "STATUS=RUNNING" in gate_text and "PHASE=ASSEMBLY" in gate_text  # 判断默认 NCNV=EXIT 是否在 *GET 分支前终止输入并保留启动哨兵。
    require(explicit_gate_rejection != native_exit_before_gate_branch, f"APDL 门禁既非唯一显式 LS2 拒绝，也非 NCNV=EXIT 前置 RUNNING 哨兵：{gate_text.strip()}")  # 只接受两条互斥且可解释的原生失败路径。
    gate_disposition = "EXPLICIT_LS2_REJECT_BRANCH_EXECUTED" if explicit_gate_rejection else "RUNNING_ASSEMBLY_SENTINEL_PRESERVED_BECAUSE_NATIVE_NCNV_EXIT_TERMINATED_INPUT_BEFORE_GATE_BRANCH"  # 冻结门禁文本与默认 NCNV 控制流的关系。
    require(not (solver_dir / "c10_static_energy_mass_reaction.txt").exists(), "失败运行意外产生完整静力能量/质量/反力摘要")  # 防止后处理局部结果被误当完整静力。
    require(not (solver_dir / f"{manifest['jobname']}_eq.db").exists(), "失败运行意外保存平衡端点数据库")  # 没有 beta=0 平衡点就不应存在最终数据库。
    require(not (run_dir / "C10_static_final_status.json").exists(), "运行已存在成功静力终态，拒绝失败封板")  # 成功与失败终态必须互斥。
    return publish_failure(run_dir, manifest, root_status, prepared_entries, prepared_ledger_sha256, manifest_sha256, source_reference_audit, launch, process_identity, monitor_audit, output_path, error_path, native_monitor_path, gate_path, equation_counts, pivots, mntr_ls1, rejected_events, bisections, bisection_increments, matched_native_ncnv_phrases, native_failure_time, gate_disposition)  # 将全部已验证证据交给不可覆盖发布函数。


def publish_failure(run_dir: Path, manifest: dict[str, Any], root_status: dict[str, Any], prepared_entries: dict[str, str], prepared_ledger_sha256: str, manifest_sha256: str, source_reference_audit: dict[str, Any], launch: dict[str, Any], process_identity: dict[str, Any], monitor_audit: dict[str, Any], output_path: Path, error_path: Path, native_monitor_path: Path, gate_path: Path, equation_counts: list[int], pivots: list[float], mntr_ls1: dict[str, float | int], rejected_events: list[dict[str, Any]], bisections: list[dict[str, Any]], bisection_increments: list[float], matched_native_ncnv_phrases: list[str], native_failure_time: float, gate_disposition: str) -> Path:  # 接收全部已通过门禁的证据并发布机器审计、人读报告、源码快照和追加账本。
    qa_dir = run_dir / "qa"  # 定位准备期已存在的运行内 QA 目录，禁止隐式创建新证据根。
    require(qa_dir.is_dir(), f"缺少 QA 目录：{qa_dir}")  # 发布目标父目录必须已由准备包冻结。
    snapshot_path = qa_dir / SCRIPT_PATH.name  # 定位实际执行终结器源码的运行内不可覆盖快照。
    audit_path = qa_dir / "adaptive_natural_failure_audit.json"  # 定位机器可读自然失败完整审计。
    dictionary_path = qa_dir / "adaptive_natural_failure_audit_dictionary.md"  # 定位 JSON 字段、单位和用途边界说明。
    packet_path = run_dir / "adaptive_failure_result_packet.md"  # 定位面向人工复核的失败结果包。
    ledger_path = run_dir / "artifact_hashes_failure_final.sha256"  # 定位保留准备账本并追加运行/终态工件的最终账本。
    final_status_path = run_dir / "C10_static_failure_final_status.json"  # 定位下游首先读取的不可覆盖失败根状态。
    target_paths = [snapshot_path, audit_path, dictionary_path, packet_path, ledger_path, final_status_path]  # 汇总本次唯一允许新增的六个发布目标。
    require(all(not path.exists() for path in target_paths), "至少一个失败封板目标已存在，拒绝重复终结")  # 一次运行只允许一套首次发布证据。
    script_text = SCRIPT_PATH.read_text(encoding="utf-8", errors="strict")  # 读取实际执行源码供运行内快照和摘要闭合。
    script_sha256 = sha256_bytes(script_text.encode("utf-8"))  # 按将要写出的 UTF-8 字节计算终结器身份。
    native_files = {"out": output_path, "err": error_path, "mntr": native_monitor_path, "gate": gate_path}  # 建立四项权威 MAPDL 原件名称到路径映射。
    native_file_records = {name: {"relative_path": path.relative_to(run_dir).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)} for name, path in native_files.items()}  # 为每项原件冻结运行内路径、字节数和完整摘要。
    rejected_iterations = [int(event["cumulative_iterations"]) for event in rejected_events]  # 提取每次失败尝试结束时的累计 Newton 迭代数。
    audit = {"schema_version": 1, "status": FINAL_STATUS, "run_name": run_dir.name, "jobname": manifest["jobname"], "diagnostic_subtype": EXPECTED_SUBTYPE, "single_variable_change": EXPECTED_SINGLE_CHANGE, "finalized_by_script": f"qa/{SCRIPT_PATH.name}", "finalizer_script_sha256": script_sha256, "preparation_chain": {"manifest_sha256": manifest_sha256, "prepared_ledger_path": "artifact_hashes.sha256", "prepared_ledger_sha256": prepared_ledger_sha256, "prepared_ledger_entry_count": len(prepared_entries), "all_prepared_entries_rehashed": True, "prepared_manifest_and_status_preserved_unmodified": True}, "source_references": source_reference_audit, "launch_chain": {"runtime_launch_claim_sha256": sha256_file(run_dir / "runtime_launch_claim.json"), "runtime_launch_sha256": sha256_file(run_dir / "runtime_launch.json"), "runtime_process_identity_sha256": sha256_file(run_dir / "runtime_process_identity.json"), "main_pid": int(launch["main_pid"]), "create_time_epoch_seconds": float(process_identity["create_time_epoch_seconds"]), "exact_executable_and_command_line_verified": True, "main_identity_confirmed_absent": True, "active_job_process_count_after_exit": 0}, "runtime_monitor": monitor_audit, "native_files": native_file_records, "equation_and_pivot": {"expected_equation_count": EXPECTED_EQUATION_COUNT, "observed_equation_counts": equation_counts, "unique_equation_counts": sorted(set(equation_counts)), "minimum_pivots": pivots, "first_ls1_pivot": pivots[0], "minimum_positive_pivot": min(pivots), "all_pivots_finite_and_positive": True, "small_zero_negative_pivot_observed": False}, "ls1": {"accepted": True, "accepted_substep_count": 1, "load_step": int(mntr_ls1["load_step"]), "substep": int(mntr_ls1["substep"]), "attempt": int(mntr_ls1["attempt"]), "equilibrium_iterations": int(mntr_ls1["iterations"]), "total_iterations": int(mntr_ls1["total_iterations"]), "increment": float(mntr_ls1["increment"]), "total_time": float(mntr_ls1["total_time"])}, "ls2": {"accepted_substep_count": 0, "rejected_attempt_count": len(rejected_events), "bisection_count": len(bisections), "event_sequence": [str(event["kind"]) for event in [item for pair in zip(rejected_events[:-1], bisections, strict=True) for item in pair] + [rejected_events[-1]]], "rejected_substeps": [int(event["substep"]) for event in rejected_events], "rejected_cumulative_iterations": rejected_iterations, "final_rejection_text_offset": int(rejected_events[-1]["text_offset"]), "bisection_numbers": [int(event["number"]) for event in bisections], "bisection_increments": bisection_increments, "final_minimum_bisection_text_offset": int(bisections[-1]["text_offset"]), "minimum_allowed_increment": MINIMUM_INCREMENT, "minimum_increment_reached_and_rejected": True, "native_failure_total_time": native_failure_time, "native_failure_load_step": 2, "native_failure_substep": 1, "native_ncnv_exit_option_observed": True, "native_ncnv_phrases_after_final_rejection": matched_native_ncnv_phrases, "native_error_block_observed_after_final_rejection": True, "native_termination_reason": "UNCONVERGED_SOLUTION", "gate_disposition": gate_disposition, "continuous_migration_beta_zero_endpoint_reached": False}, "failure_classification": {"solver_process_exit": "NATURAL_WITHOUT_CONTROLLER_ABORT", "reason": "LS2_FIRST_MIGRATION_ENDPOINT_REMAINED_NONCONVERGENT_AFTER_AUTOTS_CUTBACK_TO_0_05_PERCENT_MINIMUM_INCREMENT", "valid_static_result_obtained": False, "restart_base_state_allowed": False, "modal_execution_attempted": False, "modal_execution_allowed": False, "production_claim_allowed": False, "partial_rst_or_database_allowed_as_final_state": False}, "next_action": "REBUILD_PHYSICAL_INITIAL_EQUILIBRIUM_WITH_SPATIAL_GRAVITY_FORM_FINDING_OR_INITIAL_STRAIN_AND_REVIEW_CONNECTION_BEHAVIOR_BEFORE_ANY_NEW_FULL_BRIDGE_RUN", "appended_ledger": "artifact_hashes_failure_final.sha256"}  # 汇总谱系、自然退出、秩、正主元、LS1、全部 LS2 拒绝/二分和用途禁令。
    audit_text = render_json(audit)  # 在写盘前完成合法 JSON 渲染和非有限数拒绝。
    final_status = {"schema_version": 1, "run_name": run_dir.name, "jobname": manifest["jobname"], "status": FINAL_STATUS, "static_numeric_status": "FAILED_TO_REACH_BETA_ZERO_EQUILIBRIUM", "failure_reason": audit["failure_classification"]["reason"], "ls1_beta_one_old_load_position_equilibrium": "CONVERGED_IN_4_ITERATIONS", "ls2_accepted_substep_count": 0, "ls2_minimum_migration_fraction_attempted": 0.0005, "ls2_minimum_migration_fraction_converged": False, "equation_count": EXPECTED_EQUATION_COUNT, "minimum_positive_pivot": min(pivots), "controller_abort_requested": False, "monitor_hard_event_count": 0, "valid_static_result_obtained": False, "restart_base_state_allowed": False, "modal_status": "BLOCKED_NOT_RUN", "modal_execution_allowed": False, "production_claim_allowed": False, "valid_for_production": False, "prepared_manifest_status_preserved": root_status["status"], "failure_audit": "qa/adaptive_natural_failure_audit.json", "human_report": "adaptive_failure_result_packet.md", "final_appended_ledger": "artifact_hashes_failure_final.sha256", "next_action": audit["next_action"]}  # 提供下游无需解释准备态 manifest 即可识别的明确失败根状态。
    final_status_text = render_json(final_status)  # 在任何发布前完成根状态 JSON 渲染。
    dictionary_text = "# 自适应迁移自然失败审计字段说明\n\n`adaptive_natural_failure_audit.json` 只描述本次失败事实，不修改准备态 `manifest.json` 或 `C10_static_status.json`。力单位为 N，力矩单位为 N·mm，位移单位为 mm；伪时间增量无量纲，`5E-7` 对总迁移时长 `0.001` 表示 0.05% 的荷载位置迁移比例。`ls1.accepted=true` 只证明 beta=1 的旧荷载位置平衡点收敛；`ls2.accepted_substep_count=0` 表示没有任何迁移端点形成可用结果。`minimum_increment_reached_and_rejected=true` 必须同时由 OUT 中最后一次 `BEGIN BISECTION` 的 `5E-7`、其后的 `NOT COMPLETED`、原生非收敛错误块和 MNTR 无 LS2 接受行证明。`controller_abort_requested=false` 由完整监控 JSONL 与终态复算，不代表求解成功。失败运行的 `.rst/.db/.rdb/.ldhi/.rNNN` 即使存在，也不得作为 beta=0 静力端点、重启动基态或预应力模态输入。`production_claim_allowed=false` 为不可放宽用途边界。\n"  # 为无注释 JSON 提供单位、组合证据和禁止用途说明。
    packet_text = f"# C10 自适应荷载位置迁移失败封板\n\n状态：`{FINAL_STATUS}`。这是求解器自然非收敛结论，不是控制器抢停，也不是有效静力结果。\n\n- LS1：beta=1 旧荷载位置在 4 次平衡迭代后接受；MNTR 仅有这一行。\n- LS2：接受子步为 0；共 {len(rejected_events)} 次未完成尝试、{len(bisections)} 次自动二分，真实新增量依次为 {', '.join(f'{value:.8g}' for value in bisection_increments)}。\n- 最小步：最终 `5E-7` 伪时间增量对应 0.05% 迁移；该步实际尝试后仍未收敛，MAPDL 按原生 NCNV=EXIT 路径自然退出。\n- 拓扑数值健康性：全部方程报告均为 {EXPECTED_EQUATION_COUNT:,}；共 {len(pivots)} 个主元报告均为有限正数，最小值 {min(pivots):.9g}；未见 small/zero/negative pivot、FATAL 或 CNVTOL 被忽略/重置。\n- 监控完整性：{monitor_audit['sample_count']} 个连续样本；硬事件 0、控制器中止 0，OUT/ERR/MNTR 和 lock 终态稳定。\n- 结论：没有 beta=0 完整静力端点；禁止把任何部分 RST/数据库作为重启动或预应力模态基态，禁止生产使用。\n- 后续：应回到空间重力下的找形/初始应变与真实连接行为复核，再决定是否授权新的全桥诊断；本封板不授权继续靠放宽收敛准则或更小步长试跑。\n\n机器审计见 `qa/adaptive_natural_failure_audit.json`，全运行追加账本见 `artifact_hashes_failure_final.sha256`。\n"  # 生成工程人员可直接判断失败性质、数值健康性和下一步边界的简明报告。
    virtual_texts = {snapshot_path: script_text, audit_path: audit_text, dictionary_path: dictionary_text, packet_path: packet_text, final_status_path: final_status_text}  # 汇总除最终账本外的五个待发布文本及其准确字节。
    ledger_text, ledger_entry_count = build_appended_ledger(run_dir, virtual_texts, ledger_path)  # 对全部既有原件和待发布文本生成非自引用追加账本。
    publish_payloads = {snapshot_path: script_text, audit_path: audit_text, dictionary_path: dictionary_text, packet_path: packet_text, ledger_path: ledger_text, final_status_path: final_status_text}  # 按根状态最后的顺序构造原子批量发布内容。
    write_new_batch(publish_payloads)  # 统一预检、暂存和不可覆盖发布，异常时安全回滚本批次全部对象。
    require(sha256_file(snapshot_path) == script_sha256 and sha256_file(audit_path) == sha256_bytes(audit_text.encode("utf-8")) and sha256_file(final_status_path) == sha256_bytes(final_status_text.encode("utf-8")), "发布后终结器、审计或根状态摘要与内存渲染不一致")  # 立即复核三项关键发布字节。
    print(json.dumps({"run_dir": str(run_dir), "status": FINAL_STATUS, "prepared_ledger_entry_count": len(prepared_entries), "failure_final_ledger_entry_count": ledger_entry_count, "failure_final_ledger_sha256": sha256_file(ledger_path), "ls1_accepted": True, "ls2_accepted_substep_count": 0, "ls2_rejected_attempt_count": len(rejected_events), "bisection_count": len(bisections), "minimum_increment_reached_and_rejected": True, "controller_abort_requested": False, "modal_execution_allowed": False, "production_claim_allowed": False}, ensure_ascii=False, allow_nan=False))  # 向调用者返回可解析的失败状态、账本规模和用途禁令摘要。
    return final_status_path  # 返回已经原子发布且通过摘要复核的失败根状态路径。


def parse_arguments() -> argparse.Namespace:  # 无业务输入并返回用户显式指定的唯一运行目录参数。
    parser = argparse.ArgumentParser(description="严格封板自然达到 0.05% 最小迁移步仍 NCNV 的 C10 自适应静力失败运行；本脚本不启动或停止求解器。")  # 创建只读验证加不可覆盖发布的命令行解析器。
    parser.add_argument("--run-dir", required=True, type=Path, help="唯一 C10_LOAD_MIGRATION_DIAGNOSTIC 自适应运行目录；禁止使用 latest 或通配符。")  # 强制调用者明确给出目标，避免跨运行误封板。
    return parser.parse_args()  # 返回已由 argparse 完成必填和 Path 类型转换的命名空间。


def main() -> None:  # 无输入和返回值；解析参数、执行严格失败验收并输出最终状态路径。
    arguments = parse_arguments()  # 读取唯一目标运行目录参数。
    final_status_path = finalize(arguments.run_dir)  # 执行准备、启动、监控、日志、数值和发布全链门禁。
    require(final_status_path.is_file(), "失败根状态发布后缺失")  # 对调用链返回路径执行最后存在性防御检查。


if __name__ == "__main__":  # 仅直接运行本文件时进入一次终结流程，导入审查不会访问运行目录或写文件。
    main()  # 执行不可覆盖的自适应自然失败终结器。
