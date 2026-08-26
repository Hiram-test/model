"""在旧空 ABT 控制器自然超时封板后，以追加式证据链提交有效 nonlinear ABT 并只读等待 MAPDL 自然退出。"""  # 本工具绝不覆盖旧工件，也不调用任何主动进程处置接口。

from __future__ import annotations  # 启用延迟注解，避免运行期解析复杂类型产生额外依赖。

import argparse  # 解析唯一运行目录、旧终态摘要和离线自测开关。
import ast  # 离线复核源码中不存在禁止的主动进程动作调用。
import hashlib  # 计算工具、旧工件、动作载荷和运行证据的 SHA-256。
import importlib.util  # 在固定摘要门后加载旧工具的只读验证函数，避免复制已复审逻辑。
import json  # 严格解析和稳定生成机器审计工件。
import math  # 验证投影秒数和数值字段均为有限值。
import os  # 对计划、回执、终态和有效 ABT 执行显式 fsync。
import re  # 校验调用者提供的旧终态摘要为六十四位小写十六进制。
import time  # 使用单调时钟执行有界自然退出和监控终态等待。
from datetime import datetime, timezone  # 生成不受本地时区影响的 UTC 审计时刻。
from pathlib import Path  # 解析运行边界、旧工件、恢复工件和求解器路径。
from types import ModuleType  # 标注通过固定摘要门加载的旧只读验证模块。
from typing import Any  # 标注机器 JSON、旧验证上下文和运行快照的异构字段。

import psutil  # 只读复核旧控制器已经退出和当前 ANSYS 精确进程身份。


SCRIPT_PATH = Path(__file__).resolve()  # 固定本恢复工具绝对路径供自摘要和工件追溯。
TOOLS_DIR = SCRIPT_PATH.parent  # 固定 ultra_tools 目录供定位旧停机工具。
PROJECT_ROOT = TOOLS_DIR.parent  # 固定附件工程根，禁止跨项目恢复。
RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # 固定批准运行根，禁止 latest、通配符和任意目录。
PRIOR_TOOL_PATH = TOOLS_DIR / "ultra_c10_diagnostic_sufficiency_stop.py"  # 定位已执行但错误创建空 ABT 的旧工具。
PRIOR_TOOL_SHA256 = "5d8b17fe76a66cebe67ad1a2f3e6f681bb0e0453f830a666528861c624e92828"  # 固定旧工具已复审版本摘要，防止借用其他实现。
EXPECTED_RUN_NAME = "C10_LOAD_MIGRATION_DIAGNOSTIC_20260801T234415577134Z"  # 固定本次事故恢复唯一运行名，禁止跨运行复用。
EXPECTED_JOBNAME = "cw_C10madp_0801t234415577134_d1"  # 固定 MAPDL 唯一 jobname，避免向其他求解任务投递 ABT。
PRIOR_CLAIM_SHA256 = "72b99894cbc0a7b6e39e0971b8ac680c5a1ee41a19ffeeb893deae24874c8cb7"  # 固定旧机器认领实际六十四位摘要，关闭认领替换风险。
PRIOR_CONTROLLER_PID = 14676  # 固定旧 Python 控制器 PID，仅用于证明原身份已退出而不发送信号。
PRIOR_CONTROLLER_CREATE_TIME = 1785635322.9114935  # 固定旧 Python 控制器创建时刻，单位为 Unix 秒，用于防 PID 回收误判。
PRIOR_CONTROLLER_EXECUTABLE = Path(r"C:\Users\asus\AppData\Local\Programs\Python\Python312\python.exe")  # 固定旧控制器映像绝对路径供三元身份复核。
PRIOR_WRAPPER_PID = 472  # 固定旧 PowerShell 包装器 PID，要求其也已自然退出后才允许接管。
PRIOR_WRAPPER_CREATE_TIME = 1785635322.4987512  # 固定旧包装器创建时刻，单位为 Unix 秒，用于防 PID 回收误判。
PRIOR_WRAPPER_EXECUTABLE = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")  # 固定旧包装器映像绝对路径供三元身份复核。
PRIOR_TIMEOUT_STATUS = "OPERATOR_SUFFICIENCY_STOP_REQUESTED_EXIT_NOT_CONFIRMED_TIMEOUT_NO_FORCE"  # 只接受旧工具自然完成一千八百秒无强制动作封板。
PRIOR_TIMEOUT_BLOCK_REASON = "PROCESS_TREE_OR_FILES_NOT_STABLE_WITHIN_1800_SECONDS_NO_FORCE_ACTION_TAKEN"  # 固定旧终态应声明的超时原因。
PRIOR_EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()  # 固定旧错误空 ABT 的零字节摘要供事故事实闭合。
NATIVE_ABORT_PAYLOAD = b"nonlinear\n"  # 按 MAPDL 2026 R1 合同固定第一列 lowercase nonlinear 加单一 LF。
NATIVE_ABORT_PAYLOAD_LENGTH = 10  # 固定有效载荷字节数为九个 ASCII 字母加一个 LF。
NATIVE_ABORT_PAYLOAD_SHA256 = "efc0d415f2fa6a5bea29d619ed2c58fb6ee8285e68bf671673dc2c56e43f8703"  # 固定有效十字节载荷的 SHA-256。
NATIVE_ABORT_PAYLOAD_HEX = "6e6f6e6c696e6561720a"  # 固定有效十字节载荷的十六进制表示供人工复核。
POLL_INTERVAL_SECONDS = 5.0  # 每五秒只读轮询一次，避免高频争用求解器运行文件。
EXIT_CONFIRMATION_TIMEOUT_SECONDS = 3600.0  # 最多等待六十分钟供 MAPDL 原生中止、保存重启动数据并自然退出。
POST_EXIT_MONITOR_TIMEOUT_SECONDS = 180.0  # 进程退出后最多等待三分钟取得冻结监控器完整终态。
MINIMUM_INCREMENT = 5.0e-7  # 固定已证明可接受的 LS2 最小迁移增量，无量纲载荷时间。
FULL_MIGRATION_TIME = 1.0e-3  # 固定 LS2 全部迁移目标时间，无量纲载荷时间。
SUFFICIENCY_HORIZON_SECONDS = 604800.0  # 固定七天阈值，单位为秒，用于阻断缺少运行充分性的恢复动作。
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")  # 固定六十四位小写十六进制摘要语法。
FORBIDDEN_PROCESS_CALL_NAMES = {"kill", "terminate", "send_signal", "killpg", "taskkill"}  # 固定源码中禁止出现的主动进程动作调用名。
EXPECTED_OPERATOR_ABORT_MONITOR_EVENT_KINDS: frozenset[str] = frozenset()  # 当前冻结监控器只把 FATAL、坏主元、CNVTOL 失效、方程漂移和资源越线列为硬事件，没有任何可归为正常 operator abort 的事件类别。
FROZEN_MONITOR_INVALID_ABORT_PREFIX = "C10_ADAPTIVE_MONITOR_HARD_STOP "  # 披露冻结监控器独立硬停分支写入的首行前缀，该前缀不符合 MAPDL 要求的 nonlinear 第一列合同。


def require(condition: bool, message: str) -> None:  # 接收布尔条件和中文原因；条件失败时立即阻断恢复且不隐式修正。
    if not condition:  # 仅在审计门未通过时进入失败关闭分支。
        raise RuntimeError(message)  # 抛出包含具体证据门的异常并保持旧运行工件不变。


def utc_now() -> str:  # 无输入并返回带 UTC 偏移的 ISO-8601 审计时刻。
    return datetime.now(timezone.utc).isoformat()  # 用显式 UTC 避免本地时区和夏令时歧义。


def sha256_file(path: Path) -> str:  # 接收普通文件并返回流式 SHA-256；不以写模式访问目标。
    digest = hashlib.sha256()  # 初始化独立 SHA-256 状态供当前文件使用。
    with path.open("rb") as handle:  # 以只读二进制模式避免编码和换行转换。
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):  # 每次读取一 MiB，兼顾大 OUT 与内存占用。
            digest.update(chunk)  # 按原始字节顺序累积摘要，绝不重排或规范化。
    return digest.hexdigest()  # 返回六十四位小写十六进制摘要。


def read_json(path: Path) -> dict[str, Any]:  # 接收 JSON 文件并返回严格 UTF-8 顶层对象。
    require(path.is_file(), f"缺少机器工件：{path}")  # 缺失权威工件时禁止恢复。
    payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))  # 严格读取完整 UTF-8 正文并解析 JSON。
    require(isinstance(payload, dict), f"机器工件顶层不是对象：{path}")  # 阻断数组、标量或空值冒充对象。
    return payload  # 返回已验证顶层类型的机器对象。


def render_json(payload: dict[str, Any]) -> str:  # 接收机器对象并返回稳定、保留中文且禁止 NaN 的 JSON 文本。
    return json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"  # 固定两空格缩进和末尾单一 LF。


def write_text_exclusive(path: Path, text_value: str) -> None:  # 接收目标和文本并执行不可覆盖 UTF-8/LF 写入及磁盘同步。
    require(path.parent.is_dir(), f"排他工件父目录不存在：{path.parent}")  # 禁止隐式创建错误目录层级。
    with path.open("x", encoding="utf-8", newline="\n") as handle:  # 使用操作系统排他创建语义阻断重复恢复者。
        handle.write(text_value)  # 一次写入内存中已完成渲染的完整文本。
        handle.flush()  # 刷新 Python 缓冲以使后续动作前工件可见。
        os.fsync(handle.fileno())  # 请求操作系统把追加式审计工件同步到磁盘。


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:  # 接收目标和对象并排他写出稳定机器 JSON。
    write_text_exclusive(path, render_json(payload))  # 复用不可覆盖、UTF-8、LF 和 fsync 合同。


def exact_frozen_process_present(pid: int, create_time: float, executable: Path) -> bool:  # 接收 PID、创建时刻和映像并只读判断冻结旧身份是否仍存活。
    try:  # 目标可能已经自然退出、成为僵尸或 PID 被其他进程回收。
        process = psutil.Process(pid)  # 按冻结 PID 取得当前进程对象但不单凭 PID 作结论。
        current_create_time = float(process.create_time())  # 读取当前进程创建时刻供防回收比较。
        current_executable = Path(process.exe()).resolve()  # 读取当前映像绝对路径供身份闭合。
        return abs(current_create_time - create_time) <= 1.0e-6 and str(current_executable).casefold() == str(executable.resolve()).casefold()  # 仅三元身份完全一致时认定旧进程仍存活。
    except (psutil.NoSuchProcess, psutil.ZombieProcess):  # 原 PID 已退出或成为不可执行僵尸时视为旧身份不存在。
        return False  # 返回旧控制器已经离开当前进程表的事实。
    except (psutil.AccessDenied, OSError, RuntimeError, ValueError) as error:  # 权限或字段异常无法证明安全接管条件。
        raise RuntimeError(f"无法只读复核旧控制器身份 PID={pid}：{error}") from error  # 失败关闭且不创建任何 ABT。


def require_prior_controller_chain_absent() -> None:  # 无输入；要求旧 Python 控制器与其 PowerShell 包装器精确身份都已自然离开。
    require(not exact_frozen_process_present(PRIOR_CONTROLLER_PID, PRIOR_CONTROLLER_CREATE_TIME, PRIOR_CONTROLLER_EXECUTABLE), "旧 Python 控制器 PID 14676 仍存活，禁止并发接管")  # 阻断旧控制器仍可能写 final 或误归因外部 ABT 的竞态。
    require(not exact_frozen_process_present(PRIOR_WRAPPER_PID, PRIOR_WRAPPER_CREATE_TIME, PRIOR_WRAPPER_EXECUTABLE), "旧 PowerShell 包装器 PID 472 仍存活，禁止并发接管")  # 阻断包装器仍可能重启或报告旧流程的竞态。


def load_prior_validation_module() -> ModuleType:  # 无输入并在摘要门通过后返回旧工具的只读验证模块。
    require(PRIOR_TOOL_PATH.is_file(), f"缺少旧停机工具：{PRIOR_TOOL_PATH}")  # 缺失旧实现时无法解释旧 claim 和 final。
    require(sha256_file(PRIOR_TOOL_PATH) == PRIOR_TOOL_SHA256, "旧停机工具摘要漂移，拒绝复用其只读验证逻辑")  # 只加载已复审的确定字节版本。
    specification = importlib.util.spec_from_file_location("ultra_c10_prior_stop_read_only", PRIOR_TOOL_PATH)  # 从固定绝对路径构造隔离模块规范。
    require(specification is not None and specification.loader is not None, "无法构造旧停机工具只读模块规范")  # 阻断缺失加载器或无效路径。
    module = importlib.util.module_from_spec(specification)  # 创建不污染普通导入名空间的隔离模块对象。
    specification.loader.exec_module(module)  # 执行旧模块定义；其 main guard 保证导入不写运行工件。
    return module  # 返回可复用 validate_decision、related_processes 和监控终态审计函数的固定模块。


def resolve_run(run_dir_value: Path) -> Path:  # 接收用户路径并返回通过工程边界和唯一运行名门的规范绝对目录。
    run_dir = run_dir_value.resolve()  # 消除相对段、当前目录和符号路径歧义。
    require(run_dir.is_dir(), f"运行目录不存在：{run_dir}")  # 阻断缺失或普通文件路径。
    require(run_dir.parent == RUNS_ROOT.resolve(), f"运行目录越出批准 ultra_runs 根：{run_dir}")  # 只允许证据根直接子运行。
    require(run_dir.name == EXPECTED_RUN_NAME, f"恢复工具仅批准唯一运行 {EXPECTED_RUN_NAME}，实际为 {run_dir.name}")  # 阻断跨运行复用事故工具。
    return run_dir  # 返回已通过边界与唯一身份检查的目标。


def validate_prior_timeout_final(prior_final: dict[str, Any], prior_final_path: Path) -> None:  # 接收旧终态对象和路径并验证自然超时、空载荷事实和绝无强制动作。
    require(prior_final.get("schema_version") == 1 and prior_final.get("status") == PRIOR_TIMEOUT_STATUS, "旧操作员终态不是批准的一千八百秒超时状态")  # 只接受旧控制器自身完成的超时封板。
    require(prior_final.get("run_name") == EXPECTED_RUN_NAME and prior_final.get("jobname") == EXPECTED_JOBNAME, "旧操作员终态 run/job 身份不一致")  # 阻断跨运行终态复制。
    wait_seconds = float(prior_final.get("wait_seconds", -1.0))  # 读取旧控制器实际单调等待时长，单位为秒。
    require(math.isfinite(wait_seconds) and wait_seconds >= 1795.0, f"旧操作员终态等待不足一千八百秒容差：{wait_seconds}")  # 允许五秒轮询边界但拒绝提前伪封板。
    require(prior_final.get("exact_process_tree_exit_confirmed") is False, "旧终态意外声明求解器进程树已经退出")  # 恢复仅针对旧空 ABT 未生效且 ANSYS 仍运行的情形。
    require(prior_final.get("native_abort_created_exclusively") is True, "旧终态未记录空 ABT 的排他创建事实")  # 闭合旧工具确实进入错误动作分支。
    require(prior_final.get("native_abort_initial_sha256") == PRIOR_EMPTY_PAYLOAD_SHA256, "旧终态未如实记录零字节 ABT 摘要")  # 固定事故根因为空载荷而非其他内容。
    require(prior_final.get("native_abort_exists_at_finalization") is False, "旧空 ABT 在旧终态封板时仍存在，禁止叠加有效 ABT")  # 要求旧错误控制文件已不存在。
    require(prior_final.get("block_reason") == PRIOR_TIMEOUT_BLOCK_REASON, "旧终态超时原因不符合批准恢复分支")  # 关闭异常、监控不净或文件审计失败分支。
    require(prior_final.get("operator_tool_process_terminate_api_called") is False and prior_final.get("operator_tool_process_kill_api_called") is False and prior_final.get("operator_tool_forced_process_action_allowed") is False, "旧终态未证明绝无主动进程处置")  # 禁止在不明强制动作后接管。
    require(prior_final_path.stat().st_size > 0, "旧操作员终态为空文件")  # 阻断零字节占位冒充完成封板。


def validate_recovery_context(run_dir_value: Path, expected_prior_final_sha256: str) -> dict[str, Any]:  # 接收运行路径和外部冻结旧终态摘要并返回全部恢复门通过后的上下文。
    require(SHA256_PATTERN.fullmatch(expected_prior_final_sha256) is not None, "--expected-prior-final-sha256 必须是六十四位小写十六进制")  # 要求调用者在旧控制器退出后显式冻结终态字节。
    run_dir = resolve_run(run_dir_value)  # 固定唯一事故运行绝对路径。
    require_prior_controller_chain_absent()  # 在读取旧 final 和写任何恢复工件前证明旧控制链已退出。
    prior_module = load_prior_validation_module()  # 加载已固定摘要的旧只读决策验证模块。
    context = prior_module.validate_decision(run_dir)  # 复用已复审门严格重验准备账本、启动链、进程、监控、MNTR 和七天投影。
    require(context.get("jobname") == EXPECTED_JOBNAME and context["manifest"].get("jobname") == EXPECTED_JOBNAME, "只读验证上下文 jobname 不一致")  # 再次固定唯一 MAPDL 文件族。
    prior_claim_path = run_dir / "qa" / "runtime_operator_stop_claim.json"  # 定位旧错误工具先行机器认领。
    prior_final_path = run_dir / "qa" / "runtime_operator_stop_final.json"  # 定位旧控制器自然超时终态。
    require(sha256_file(prior_claim_path) == PRIOR_CLAIM_SHA256, "旧操作员认领摘要不等于事故冻结值")  # 阻断认领被替换或手工修订。
    prior_claim = read_json(prior_claim_path)  # 解析旧认领供工具、run/job 和错误动作路径闭合。
    require(prior_claim.get("schema_version") == 2 and prior_claim.get("status") == "OPERATOR_SUFFICIENCY_STOP_CLAIMED_BEFORE_NATIVE_ABORT", "旧操作员认领状态不符合事故分支")  # 只接受已知旧工具认领版本。
    require(prior_claim.get("run_name") == EXPECTED_RUN_NAME and prior_claim.get("jobname") == EXPECTED_JOBNAME, "旧操作员认领 run/job 身份不一致")  # 阻断跨运行认领复制。
    require(prior_claim.get("tool_sha256") == PRIOR_TOOL_SHA256, "旧操作员认领未引用冻结旧工具摘要")  # 关闭旧动作实现字节谱系。
    require(prior_claim.get("native_abort_path_planned") == f"solver/{EXPECTED_JOBNAME}.abt", "旧操作员认领 ABT 目标不一致")  # 固定事故控制文件路径。
    require(sha256_file(prior_final_path) == expected_prior_final_sha256, "旧操作员终态摘要与调用者冻结值不一致")  # 要求旧 final 字节在接管前由调用者二次确认。
    prior_final = read_json(prior_final_path)  # 解析旧终态供自然超时和无强制动作门使用。
    validate_prior_timeout_final(prior_final, prior_final_path)  # 验证旧空 ABT 超时事故的唯一允许恢复状态。
    abort_path = context["solver_dir"] / f"{EXPECTED_JOBNAME}.abt"  # 定位将由恢复工具排他创建的有效 MAPDL 控制文件。
    require(not abort_path.exists(), "旧或外部 ABT 当前仍存在，禁止覆盖或叠加恢复动作")  # 不删除、不截断也不接管既有控制文件。
    require(not context["monitor_final_path"].exists(), "冻结监控器已提交终态，当前 ANSYS 不再允许恢复投递")  # 仅在同一进程树仍运行时动作。
    recovery_paths = {"claim": run_dir / "qa" / "runtime_operator_stop_recovery_claim.json", "explanation": run_dir / "qa" / "runtime_operator_stop_recovery_claim.md", "plan": run_dir / "qa" / "runtime_operator_stop_recovery_action_plan.json", "executed": run_dir / "qa" / "runtime_operator_stop_recovery_action_executed.json", "final": run_dir / "qa" / "runtime_operator_stop_recovery_final.json"}  # 固定五个追加式恢复工件且全部位于既有 QA 目录。
    require(all(not path.exists() for path in recovery_paths.values()), "恢复 claim、说明、计划、执行回执或 final 已存在，禁止重复运行")  # 排他阻断第二恢复者和历史工件覆盖。
    ls2_rows = list(context.get("ls2_rows", []))  # 读取旧验证模块已解析并审核的全部 LS2 自然接受行。
    require(len(ls2_rows) >= 2, f"MNTR 已接受 LS2 最小步不足两个：{len(ls2_rows)}")  # 本恢复只授权至少两个实测最小步的门 A。
    require(all(abs(float(row["increment"]) - MINIMUM_INCREMENT) <= 1.0e-12 for row in ls2_rows[-2:]), "MNTR 最近两个 LS2 接受行不是 5E-7 最小增量")  # 固定实测速率的步长合同。
    require(int(ls2_rows[-1]["substep"]) == int(ls2_rows[-2]["substep"]) + 1, "MNTR 最近两个 LS2 接受子步不连续")  # 防止跨缺失或重编号状态借用耗时。
    measured_seconds = float(ls2_rows[-1]["elapsed_seconds"]) - float(ls2_rows[-2]["elapsed_seconds"])  # 计算最近两个完整自然接受行的真实时间差。
    accepted_migration = sum(float(row["increment"]) for row in ls2_rows)  # 累计所有已接受 LS2 增量供剩余最小步计算。
    remaining_steps = int(math.ceil(max(0.0, FULL_MIGRATION_TIME - accepted_migration) / MINIMUM_INCREMENT - 1.0e-12))  # 用向上取整得到尚需最小步数并容纳浮点尾差。
    projected_seconds = measured_seconds * float(remaining_steps)  # 用最近完整实测周期线性投影全部剩余最小步。
    require(measured_seconds > 0.0 and remaining_steps > 0 and math.isfinite(projected_seconds) and projected_seconds > SUFFICIENCY_HORIZON_SECONDS, f"当前 MNTR 七天充分性门未通过：{projected_seconds:.3f} 秒")  # 只有继续运行严格超过七天才允许恢复停机。
    frozen_monitor_relative = str(context["manifest"].get("runtime_monitor_script", "")).replace("\\", "/")  # 读取 manifest 冻结监控器相对路径并统一分隔符。
    frozen_monitor_path = (run_dir / Path(frozen_monitor_relative)).resolve()  # 将相对路径投影到唯一运行根供只读源码事实复核。
    require(frozen_monitor_path.is_relative_to(run_dir) and frozen_monitor_path.is_file(), "冻结监控器路径越界或缺失")  # 阻断跨运行脚本引用。
    frozen_monitor_source = frozen_monitor_path.read_text(encoding="utf-8", errors="strict")  # 严格读取冻结监控器源码供非法 ABT 首行证据核对。
    require(FROZEN_MONITOR_INVALID_ABORT_PREFIX in frozen_monitor_source and "def request_native_abort" in frozen_monitor_source, "冻结监控器源码不包含已披露的非法 ABT 分支，拒绝套用本事故恢复说明")  # 确保风险披露由当前冻结字节直接支持。
    context.update({"prior_module": prior_module, "prior_claim_path": prior_claim_path, "prior_final_path": prior_final_path, "prior_claim_sha256": PRIOR_CLAIM_SHA256, "prior_final_sha256": expected_prior_final_sha256, "prior_final": prior_final, "abort_path": abort_path, "recovery_paths": recovery_paths, "recovery_tool_sha256": sha256_file(SCRIPT_PATH), "measured_recovery_seconds_per_minimum_step": measured_seconds, "remaining_recovery_minimum_steps": remaining_steps, "projected_recovery_remaining_seconds": projected_seconds, "frozen_monitor_path": frozen_monitor_path, "frozen_monitor_sha256": sha256_file(frozen_monitor_path)})  # 合并旧证据、固定动作目标、工具摘要、门 A 数学量和冻结监控器 P0 字节证据。
    return context  # 返回可供追加式认领、动作前复核、有效 ABT 和终态闭环使用的上下文。


def identity_set(module: ModuleType, records: list[dict[str, Any]]) -> set[tuple[int, float, str, tuple[str, ...]]]:  # 接收旧模块与进程记录并返回可比较的防 PID 回收身份集合。
    return {module.record_identity_tuple(record) for record in records}  # 复用冻结旧模块的 PID、创建时刻、映像和命令行四元合同。


def dynamic_recheck_before_valid_abort(context: dict[str, Any]) -> tuple[bool, str | None]:  # 接收初始上下文并在有效 ABT 前复核所有动态证据是否仍处同一状态。
    try:  # 任一读取、摘要、进程或监控异常都必须失败关闭且不创建 ABT。
        require_prior_controller_chain_absent()  # 再次证明旧控制链未在认领期间复活或仍未退出。
        require(sha256_file(context["prior_claim_path"]) == context["prior_claim_sha256"], "旧 claim 在恢复认领后发生漂移")  # 关闭旧认领竞态修改。
        require(sha256_file(context["prior_final_path"]) == context["prior_final_sha256"], "旧 final 在恢复认领后发生漂移")  # 关闭旧终态竞态修改。
        require(not context["abort_path"].exists(), "有效 ABT 动作前目标路径已被其他主体创建")  # 不覆盖任何外部或迟到控制文件。
        require(not context["monitor_final_path"].exists(), "有效 ABT 动作前冻结监控终态已经出现")  # 阻断与自然退出或硬事件竞争。
        monitor_clean, monitor_reason = context["prior_module"].monitor_still_clean_before_abort(context)  # 复用旧模块检查完整 JSONL 仍无硬事件和终态。
        require(monitor_clean, f"有效 ABT 动作前监控状态不干净：{monitor_reason}")  # 把控制权留给冻结监控器。
        require(context["prior_module"].snapshot_file(context["mntr_path"]) == context["mntr_snapshot"], "恢复认领期间 MNTR 大小或时刻变化")  # 防止新增接受行使投影依据跨状态。
        require(sha256_file(context["mntr_path"]) == context["mntr_sha256"], "恢复认领期间 MNTR 字节摘要变化")  # 以字节摘要补充大小/时刻门。
        current_related = context["prior_module"].related_processes(context["jobname"], context["solver_dir"], context["identity"])  # 再次只读取得同一 job 的精确 ANSYS 进程集合。
        require(identity_set(context["prior_module"], current_related) == identity_set(context["prior_module"], context["current_related"]), "恢复认领期间精确 ANSYS 进程集合变化")  # 阻断进程消失、新增或 PID 身份变化。
        return True, None  # 返回全部动态门仍与初始决策一致。
    except (OSError, RuntimeError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:  # 收敛全部可预期只读复核失败。
        return False, str(error)  # 返回明确无动作原因供追加式 final 封板。


def artifact_audit(path: Path) -> dict[str, Any]:  # 接收可能尚不存在的恢复工件并返回存在性、大小和可选摘要。
    if not path.is_file():  # 工件缺失时不尝试读取或哈希。
        return {"path": path.name, "exists": False, "size_bytes": 0, "sha256": None}  # 用固定字段表达缺失状态。
    return {"path": path.name, "exists": True, "size_bytes": int(path.stat().st_size), "sha256": sha256_file(path)}  # 对存在工件记录真实大小和字节摘要。


def validate_monitor_final_for_operator_abort(context: dict[str, Any], abort_created_at_utc: str) -> tuple[dict[str, Any], str | None]:  # 接收恢复上下文和有效 ABT 时刻并显式区分预期 operator abort 签名与未预期硬错误。
    audit, base_dirty_reason = context["prior_module"].validate_monitor_final(context)  # 先复用旧模块闭合 schema、run/job、样本数、序号、SHA、进程和 lock。
    hard_events_value = audit.get("hard_events")  # 读取完整监控硬事件对象而不假定字段合法。
    hard_events = hard_events_value if isinstance(hard_events_value, list) else []  # 仅列表进入逐项分类，错型由基础审计原因保留。
    try:  # 有效 ABT 时刻必须是带时区 ISO-8601，供事件前后关系严格判断。
        abort_created_time = datetime.fromisoformat(abort_created_at_utc)  # 解析执行回执所用真实创建时刻。
        require(abort_created_time.tzinfo is not None, "有效 ABT 创建时刻缺少时区")  # 阻断本地无偏移时刻参与分类。
    except (TypeError, ValueError, RuntimeError) as error:  # 收敛错型、语法或无时区异常。
        raise RuntimeError(f"无法解析有效 ABT 创建时刻：{error}") from error  # 失败关闭监控终态分类。
    expected_events: list[dict[str, Any]] = []  # 初始化仅允许发生在有效 ABT 之后且类别明确批准的预期事件。
    unexpected_events: list[dict[str, Any]] = []  # 初始化全部错误类别、早于动作、错型或无时刻事件。
    for event in hard_events:  # 逐项分类冻结监控器记录的所有硬事件而不丢弃原对象。
        kind = str(event.get("kind", "")) if isinstance(event, dict) else ""  # 从合法对象读取事件类别，错型使用空类别。
        detected_text = event.get("detected_at_utc") if isinstance(event, dict) else None  # 读取检测时刻供动作前后门。
        try:  # 每个事件时刻必须带时区且能与 ABT 时刻比较。
            detected_time = datetime.fromisoformat(str(detected_text))  # 解析事件检测 ISO-8601 文本。
            event_after_abort = detected_time.tzinfo is not None and detected_time >= abort_created_time  # 只有有效 ABT 后事件才可能是预期签名。
        except (TypeError, ValueError):  # 缺失或损坏时刻不能被宽松归为预期事件。
            event_after_abort = False  # 将不可解析事件保留为未预期硬错误。
        if kind in EXPECTED_OPERATOR_ABORT_MONITOR_EVENT_KINDS and event_after_abort:  # 同时满足批准类别和动作后时序才进入预期集合。
            expected_events.append(event)  # 保留完整原事件供 final 审查。
        else:  # 当前冻结监控器没有批准的 operator abort 类别，因此真实硬事件均进入此分支。
            unexpected_events.append(event if isinstance(event, dict) else {"invalid_event_value": event})  # 保留错型或未预期事件而不静默丢弃。
    controller_abort = audit.get("controller_abort")  # 读取冻结监控器自己的动作记录供独立处置边界复核。
    controller_requested = isinstance(controller_abort, dict) and controller_abort.get("requested") is True  # 明确判断监控器是否请求过它自己的 ABT。
    process_disposition = controller_abort.get("process_disposition") if isinstance(controller_abort, dict) else None  # 读取可能包含正常终止或强制结束 PID 的处置对象。
    terminate_sent = process_disposition.get("terminate_sent_pids", []) if isinstance(process_disposition, dict) else []  # 提取监控器正常终止动作 PID 列表。
    kill_sent = process_disposition.get("kill_sent_pids", []) if isinstance(process_disposition, dict) else []  # 提取监控器强制结束动作 PID 列表。
    audit["operator_abort_event_classification"] = {"effective_abort_created_at_utc": abort_created_at_utc, "approved_expected_event_kinds_for_this_frozen_monitor": sorted(EXPECTED_OPERATOR_ABORT_MONITOR_EVENT_KINDS), "expected_operator_abort_events": expected_events, "unexpected_hard_events": unexpected_events, "all_pre_action_samples_required_clean": True, "generic_abort_or_terminated_text_is_not_a_frozen_monitor_hard_event": True}  # 显式披露当前监控规则没有正常 abort 硬事件类且所有真实硬事件均需单独审查。
    audit["frozen_monitor_independent_abort_contract_risk"] = {"request_native_abort_first_line_prefix": FROZEN_MONITOR_INVALID_ABORT_PREFIX, "mapdl_required_first_line_column_one": "nonlinear", "native_abort_payload_contract_valid": False, "recovery_tool_invoked_frozen_monitor_abort_function": False, "monitor_controller_abort_requested": controller_requested, "monitor_terminate_sent_pids": terminate_sent, "monitor_kill_sent_pids": kill_sent}  # 披露冻结监控器 P0，但明确本恢复工具只提交 operator ABT。
    reasons: list[str] = []  # 初始化 operator abort 专项监控不干净原因列表。
    if base_dirty_reason is not None:  # 基础审计已发现状态、字段、样本、进程、lock 或硬事件问题时保留原原因。
        reasons.append(base_dirty_reason)  # 不因 operator abort 背景覆盖旧模块的完整性判断。
    if unexpected_events:  # 当前冻结监控器记录的任一真实硬事件都不是批准的正常 operator abort 签名。
        reasons.append("UNEXPECTED_HARD_EVENTS_AFTER_OR_BEFORE_OPERATOR_ABORT")  # 显式区分未预期硬错误与正常退出文本。
    if controller_requested or terminate_sent or kill_sent:  # 监控器若请求自己的错误 ABT 或采取进程处置则禁止恢复成功。
        reasons.append("FROZEN_MONITOR_REQUESTED_ABORT_OR_SENT_PROCESS_DISPOSITION")  # 披露潜在退化到正常终止或强制结束的独立控制动作。
    return audit, None if not reasons else ";".join(dict.fromkeys(reasons))  # 返回完整分类审计和去重后的可选不干净原因。


def write_recovery_final(context: dict[str, Any], status: str, block_reason: str | None, abort_created: bool, abort_created_at_utc: str | None, payload_written: bool, payload_synced: bool, readback_matches: bool, exit_confirmed: bool, wait_seconds: float, poll_count: int, stable_state: Any, monitor_audit: dict[str, Any] | None) -> Path:  # 接收动作与退出证据并排他写出唯一恢复终态。
    paths = context["recovery_paths"]  # 读取五个固定恢复工件路径映射。
    final = {"schema_version": 1, "status": status, "run_name": EXPECTED_RUN_NAME, "jobname": EXPECTED_JOBNAME, "finalized_at_utc": utc_now(), "recovery_tool_path": str(SCRIPT_PATH), "recovery_tool_sha256": context["recovery_tool_sha256"], "prior_tool_path": str(PRIOR_TOOL_PATH), "prior_tool_sha256": PRIOR_TOOL_SHA256, "prior_operator_claim_sha256": context["prior_claim_sha256"], "prior_operator_final_sha256": context["prior_final_sha256"], "prior_controller_pid": PRIOR_CONTROLLER_PID, "prior_controller_exact_identity_absent_before_recovery": True, "recovery_claim": artifact_audit(paths["claim"]), "recovery_explanation": artifact_audit(paths["explanation"]), "recovery_action_plan": artifact_audit(paths["plan"]), "recovery_action_executed": artifact_audit(paths["executed"]), "native_abort_path": context["abort_path"].relative_to(context["run_dir"]).as_posix(), "native_abort_payload_text": NATIVE_ABORT_PAYLOAD.decode("ascii"), "native_abort_payload_length_bytes": NATIVE_ABORT_PAYLOAD_LENGTH, "native_abort_payload_hex": NATIVE_ABORT_PAYLOAD_HEX, "native_abort_payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "native_abort_created_exclusively": abort_created, "native_abort_created_at_utc": abort_created_at_utc, "native_abort_payload_written_fully": payload_written, "native_abort_flush_and_fsync_completed": payload_synced, "native_abort_readback_matches_contract": readback_matches, "native_abort_exists_at_finalization": context["abort_path"].is_file(), "exact_process_tree_exit_confirmed": exit_confirmed, "wait_seconds": wait_seconds, "poll_interval_seconds": POLL_INTERVAL_SECONDS, "poll_count": poll_count, "exit_confirmation_timeout_seconds": EXIT_CONFIRMATION_TIMEOUT_SECONDS, "final_out_file": None if stable_state is None else stable_state[0], "final_err_file": None if stable_state is None else stable_state[1], "final_mntr_file": None if stable_state is None else stable_state[2], "final_lock_file": None if stable_state is None else stable_state[3], "frozen_monitor_final": monitor_audit, "frozen_monitor_path": context["frozen_monitor_path"].relative_to(context["run_dir"]).as_posix(), "frozen_monitor_sha256": context["frozen_monitor_sha256"], "frozen_monitor_native_abort_payload_contract_valid": False, "frozen_monitor_invalid_abort_first_line_prefix": FROZEN_MONITOR_INVALID_ABORT_PREFIX, "recovery_tool_called_frozen_monitor_abort_function": False, "block_reason": block_reason, "causal_native_abort_acknowledgement_proven_by_process_exit_alone": False, "operator_tool_process_terminate_api_called": False, "operator_tool_process_kill_api_called": False, "operator_tool_process_send_signal_api_called": False, "operator_tool_forced_process_action_allowed": False, "valid_static_result_obtained": False, "modal_execution_allowed": False, "production_claim_allowed": False}  # 汇总旧链、双回执、精确载荷、动作结果、冻结监控器已知 P0 字节证据、自然退出和用途禁令且不把进程退出误当因果证明。
    write_json_exclusive(paths["final"], final)  # 排他提交唯一恢复终态，禁止覆盖或重复操作者改写。
    return paths["final"]  # 返回已同步磁盘的恢复终态路径。


def request_valid_native_abort_recovery(run_dir_value: Path, expected_prior_final_sha256: str) -> Path:  # 接收唯一运行和旧终态摘要，提交有效 ABT 并返回追加式恢复终态路径。
    context = validate_recovery_context(run_dir_value, expected_prior_final_sha256)  # 在任何恢复写入前完成旧链、当前运行、监控、进程、MNTR 和七天门。
    paths = context["recovery_paths"]  # 读取固定追加式 claim、说明、计划、执行和 final 路径。
    planned_at_utc = utc_now()  # 冻结恢复计划形成时刻且明确早于有效 ABT 创建。
    claim = {"schema_version": 1, "status": "OPERATOR_STOP_RECOVERY_CLAIMED_BEFORE_VALID_NATIVE_ABORT", "run_name": EXPECTED_RUN_NAME, "jobname": EXPECTED_JOBNAME, "claimed_at_utc": planned_at_utc, "recovery_tool_path": str(SCRIPT_PATH), "recovery_tool_sha256": context["recovery_tool_sha256"], "prior_tool_sha256": PRIOR_TOOL_SHA256, "prior_operator_claim_path": context["prior_claim_path"].relative_to(context["run_dir"]).as_posix(), "prior_operator_claim_sha256": context["prior_claim_sha256"], "prior_operator_final_path": context["prior_final_path"].relative_to(context["run_dir"]).as_posix(), "prior_operator_final_sha256": context["prior_final_sha256"], "prior_controller_pid": PRIOR_CONTROLLER_PID, "prior_controller_create_time_epoch_seconds": PRIOR_CONTROLLER_CREATE_TIME, "prior_controller_exact_identity_absent": True, "prepared_ledger_sha256": context["prepared_ledger_sha256"], "prepared_ledger_entry_count": context["prepared_entry_count"], "runtime_launch_claim_sha256": sha256_file(context["launch_claim_path"]), "runtime_launch_sha256": sha256_file(context["launch_path"]), "runtime_process_identity_sha256": sha256_file(context["identity_path"]), "runtime_monitor_claim_sha256": sha256_file(context["monitor_claim_path"]), "runtime_monitor_samples_sha256_at_recovery_decision": context["monitor_samples_sha256_at_decision"], "runtime_monitor_sample_count_at_recovery_decision": context["monitor_sample_count"], "mntr_sha256_at_recovery_decision": context["mntr_sha256"], "accepted_ls2_substep_count": len(context["ls2_rows"]), "latest_two_ls2_rows": context["latest_two"], "measured_seconds_per_minimum_step": context["measured_recovery_seconds_per_minimum_step"], "remaining_minimum_step_count": context["remaining_recovery_minimum_steps"], "projected_remaining_seconds": context["projected_recovery_remaining_seconds"], "projection_strictly_exceeds_seven_days": True, "native_abort_target_path": context["abort_path"].relative_to(context["run_dir"]).as_posix(), "native_abort_payload_text_planned": NATIVE_ABORT_PAYLOAD.decode("ascii"), "native_abort_payload_length_bytes_planned": NATIVE_ABORT_PAYLOAD_LENGTH, "native_abort_payload_hex_planned": NATIVE_ABORT_PAYLOAD_HEX, "native_abort_payload_sha256_planned": NATIVE_ABORT_PAYLOAD_SHA256, "native_abort_created_at_claim_time": False, "frozen_monitor_path": context["frozen_monitor_path"].relative_to(context["run_dir"]).as_posix(), "frozen_monitor_sha256": context["frozen_monitor_sha256"], "frozen_monitor_native_abort_payload_contract_valid": False, "frozen_monitor_invalid_abort_first_line_prefix": FROZEN_MONITOR_INVALID_ABORT_PREFIX, "recovery_tool_will_not_invoke_frozen_monitor_abort_function": True, "all_monitor_hard_events_before_valid_abort_required_empty": True, "post_action_monitor_events_require_explicit_expected_vs_unexpected_classification": True, "operator_tool_forced_process_action_allowed": False, "modal_execution_allowed": False, "production_claim_allowed": False}  # 冻结恢复授权、旧链摘要、当前充分性、精确有效载荷和冻结监控器已知 P0 字节证据，且不伪称已创建。
    write_json_exclusive(paths["claim"], claim)  # 第一步排他写出恢复机器认领并同步磁盘。
    explanation = f"# C10 有效 nonlinear ABT 追加式恢复认领\n\n旧工具 `{PRIOR_TOOL_PATH.name}` 创建了零字节 ABT；该载荷不满足 MAPDL 非线性干净终止合同。旧控制器 PID `{PRIOR_CONTROLLER_PID}` 及包装器已退出，旧超时 final 摘要为 `{context['prior_final_sha256']}`，旧 claim 摘要为 `{context['prior_claim_sha256']}`。\n\n本恢复只针对 `{EXPECTED_RUN_NAME}` / `{EXPECTED_JOBNAME}`。在再次核对同一进程树、无硬事件、MNTR 至少两个 `5E-7` 接受步且剩余投影严格超过七天后，工具将排他创建 `{context['abort_path'].name}`，精确写入十字节 ASCII `nonlinear\\n`；计划回执明确写在动作前，执行回执只在写入、flush、fsync 和读回一致后形成。工具绝不调用任何主动结束或强制结束进程的接口，部分结果禁止用于模态和生产。\n"  # 生成人工可核对的事故事实、恢复边界、十字节合同和绝不强杀说明。
    try:  # 说明或计划写入失败时必须形成无有效 ABT 的追加式终态。
        write_text_exclusive(paths["explanation"], explanation)  # 第二步排他写出相邻中文说明并同步磁盘。
        plan = {"schema_version": 1, "status": "OPERATOR_STOP_RECOVERY_NATIVE_ABORT_PLANNED_NOT_CREATED", "run_name": EXPECTED_RUN_NAME, "jobname": EXPECTED_JOBNAME, "planned_at_utc": planned_at_utc, "recovery_tool_sha256": context["recovery_tool_sha256"], "prior_operator_claim_sha256": context["prior_claim_sha256"], "prior_operator_final_sha256": context["prior_final_sha256"], "recovery_claim_sha256": sha256_file(paths["claim"]), "native_abort_target_path": context["abort_path"].relative_to(context["run_dir"]).as_posix(), "payload_text": NATIVE_ABORT_PAYLOAD.decode("ascii"), "payload_length_bytes": NATIVE_ABORT_PAYLOAD_LENGTH, "payload_hex": NATIVE_ABORT_PAYLOAD_HEX, "payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "exclusive_create_planned": True, "native_abort_created": False, "payload_written": False, "flush_and_fsync_completed": False, "readback_matches": False, "operator_tool_forced_process_action_allowed": False}  # 第三步只记录精确动作计划，字段明确表示尚未创建、写入或同步。
        write_json_exclusive(paths["plan"], plan)  # 排他提交动作前计划回执并同步磁盘。
    except (OSError, RuntimeError, UnicodeError, ValueError) as error:  # 捕获 claim 后说明或计划的排他写入和同步异常。
        return write_recovery_final(context, "OPERATOR_STOP_RECOVERY_NO_VALID_ABORT_EXPLANATION_OR_PLAN_FAILED", f"RECOVERY_EXPLANATION_OR_PLAN_WRITE_FAILED:{error}", False, None, False, False, False, False, 0.0, 0, None, None)  # 如实封板无有效 ABT、无强杀状态。
    recheck_clean, recheck_reason = dynamic_recheck_before_valid_abort(context)  # 在两份先行工件和计划回执后再次闭合全部动态证据。
    if not recheck_clean:  # 任一动态状态变化时停止在无动作分支。
        return write_recovery_final(context, "OPERATOR_STOP_RECOVERY_NO_VALID_ABORT_DYNAMIC_RECHECK_FAILED", f"PRE_VALID_ABORT_RECHECK_FAILED:{recheck_reason}", False, None, False, False, False, False, 0.0, 0, None, None)  # 排他封板且不创建 ABT。
    abort_created = False  # 初始化尚未取得 ABT 排他创建权的事实。
    abort_created_at_utc: str | None = None  # 初始化尚无真实 ABT 创建时刻。
    payload_written = False  # 初始化十字节载荷尚未完整写入。
    payload_synced = False  # 初始化 flush 和 fsync 尚未完成。
    readback_matches = False  # 初始化同一文件句柄读回尚未证明一致。
    action_error: str | None = None  # 保存可能发生的创建、写入、同步、读回或执行回执异常。
    try:  # 有效 ABT 排他动作中的任一异常都必须被记录且绝不转为进程强制处置。
        with context["abort_path"].open("x+b") as abort_handle:  # 排他创建可读写二进制 ABT，禁止覆盖任何迟到外部文件。
            abort_created = True  # 文件对象排他创建成功后立即冻结真实动作事实。
            abort_created_at_utc = utc_now()  # 记录真实创建成功时刻而不是复核或计划时刻。
            written_count = abort_handle.write(NATIVE_ABORT_PAYLOAD)  # 精确写入 ASCII nonlinear 加单一 LF 的十字节载荷。
            require(written_count == NATIVE_ABORT_PAYLOAD_LENGTH, f"有效 ABT 写入字节数错误：{written_count}")  # 阻断短写或意外长度。
            payload_written = True  # 仅在返回字节数恰为十时标记完整写入。
            abort_handle.flush()  # 刷新 Python 缓冲，使操作系统看到全部十字节。
            os.fsync(abort_handle.fileno())  # 请求操作系统把有效控制载荷同步到磁盘。
            payload_synced = True  # 仅在 flush 和 fsync 都返回后标记同步完成。
            abort_handle.seek(0, os.SEEK_SET)  # 回到文件起点供同一句柄逐字节读回。
            readback = abort_handle.read()  # 在关闭文件前读取完整载荷供实际字节合同复核。
            readback_matches = readback == NATIVE_ABORT_PAYLOAD and len(readback) == NATIVE_ABORT_PAYLOAD_LENGTH and hashlib.sha256(readback).hexdigest() == NATIVE_ABORT_PAYLOAD_SHA256  # 同时核对内容、长度和摘要。
            require(readback_matches, "有效 ABT 同句柄读回不满足十字节 nonlinear 合同")  # 读回不一致时不发布执行成功回执。
            executed = {"schema_version": 1, "status": "OPERATOR_STOP_RECOVERY_NATIVE_ABORT_CREATED_AND_SYNCED", "run_name": EXPECTED_RUN_NAME, "jobname": EXPECTED_JOBNAME, "created_at_utc": abort_created_at_utc, "executed_receipt_written_at_utc": utc_now(), "recovery_tool_sha256": context["recovery_tool_sha256"], "prior_operator_claim_sha256": context["prior_claim_sha256"], "prior_operator_final_sha256": context["prior_final_sha256"], "recovery_claim_sha256": sha256_file(paths["claim"]), "recovery_action_plan_sha256": sha256_file(paths["plan"]), "native_abort_target_path": context["abort_path"].relative_to(context["run_dir"]).as_posix(), "payload_text": NATIVE_ABORT_PAYLOAD.decode("ascii"), "payload_length_bytes": len(readback), "payload_hex": readback.hex(), "payload_sha256": hashlib.sha256(readback).hexdigest(), "exclusive_create_succeeded": True, "payload_written_fully": payload_written, "flush_and_fsync_completed": payload_synced, "readback_matches_contract": readback_matches, "abort_path_visible_while_creator_handle_open": context["abort_path"].is_file(), "operator_tool_forced_process_action_allowed": False}  # 仅在真实排他创建、十字节写入、磁盘同步和读回一致后形成已执行回执。
            write_json_exclusive(paths["executed"], executed)  # 在 ABT 创建者句柄仍打开时排他同步执行回执，缩小控制文件被消费后的证据空窗。
    except (OSError, RuntimeError, UnicodeError, ValueError) as error:  # 捕获排他创建、短写、同步、读回或执行回执失败。
        action_error = str(error)  # 保存真实动作阶段异常供等待后终态解释。
    if not abort_created:  # 排他创建本身失败时没有任何原生停机动作可等待。
        return write_recovery_final(context, "OPERATOR_STOP_RECOVERY_VALID_ABORT_NOT_CREATED_NO_FORCE", f"VALID_NATIVE_ABORT_CREATE_FAILED:{action_error}", False, None, payload_written, payload_synced, readback_matches, False, 0.0, 0, None, None)  # 排他封板且绝不尝试覆盖或强杀。
    wait_started = time.monotonic()  # 记录有效 ABT 创建后的自然退出等待单调起点。
    previous_terminal_state: Any = None  # 初始化连续稳定文件比较基准为空。
    stable_empty_samples = 0  # 初始化进程空、无 lock 且文件稳定的连续轮数。
    poll_count = 0  # 初始化 ABT 后只读轮询次数。
    stable_state: Any = None  # 初始化尚未确认的最终 OUT、ERR、MNTR 和 lock 快照。
    wait_audit_error: str | None = None  # 保存 ABT 后只读审计可能发生的异常。
    while time.monotonic() - wait_started < EXIT_CONFIRMATION_TIMEOUT_SECONDS:  # 在固定六十分钟内等待 MAPDL 响应有效 ABT 并自行退出。
        poll_count += 1  # 为本轮只读检查分配连续计数。
        try:  # 进程或运行文件读取异常不能转成主动进程动作。
            remaining_related = context["prior_module"].related_processes(context["jobname"], context["solver_dir"], context["identity"])  # 取得仍存活的本 job 精确 ANSYS 进程集合。
            current_state = context["prior_module"].file_triplet_state(context)  # 取得 OUT、ERR、MNTR 和 lock 当前快照。
        except (OSError, RuntimeError, KeyError, TypeError, ValueError) as error:  # 收敛 ABT 后只读身份或文件审计异常。
            wait_audit_error = str(error)  # 保存异常并停止轮询，绝不调用任何进程动作接口。
            break  # 进入追加式异常终态封板。
        no_lock = current_state[3]["exists"] is False  # 只有 MAPDL 已移除 lock 才可能确认数据库关闭。
        terminal_files_exist = all(bool(snapshot["exists"]) for snapshot in current_state[:3])  # OUT、ERR 和 MNTR 三项权威运行原件必须保留。
        files_unchanged = previous_terminal_state is not None and current_state[:3] == previous_terminal_state[:3]  # 连续两轮大小和时刻相同才算稳定。
        if not remaining_related and no_lock and terminal_files_exist:  # 进程树空、无 lock 且三项原件存在时进入退出候选。
            stable_empty_samples = stable_empty_samples + 1 if files_unchanged else 1  # 文件未变则延续计数，否则重建第一轮候选。
        else:  # 任一进程、lock 或文件状态未闭合时继续等待。
            stable_empty_samples = 0  # 重置连续稳定计数，禁止单点退出误判。
        previous_terminal_state = current_state  # 保存本轮状态供下一轮比较。
        if stable_empty_samples >= 2:  # 两轮连续满足进程空、无 lock 和文件不变时确认自然退出。
            stable_state = current_state  # 冻结最终文件状态供恢复 final 使用。
            break  # 结束自然退出轮询并进入监控终态闭环。
        time.sleep(POLL_INTERVAL_SECONDS)  # 等待五秒再只读检查，不调用任何进程动作接口。
    wait_seconds = time.monotonic() - wait_started  # 计算有效 ABT 后已等待的真实单调时长。
    if wait_audit_error is not None:  # ABT 已创建但退出审计发生异常时如实封板。
        return write_recovery_final(context, "OPERATOR_STOP_RECOVERY_VALID_ABORT_REQUESTED_EXIT_AUDIT_FAILED_NO_FORCE", f"POST_VALID_ABORT_READ_ONLY_AUDIT_FAILED:{wait_audit_error};ACTION_ERROR:{action_error}", True, abort_created_at_utc, payload_written, payload_synced, readback_matches, False, wait_seconds, poll_count, previous_terminal_state, None)  # 记录动作与绝不强杀边界。
    if stable_state is None:  # 六十分钟内未同时取得进程空、无 lock 和文件稳定证据。
        return write_recovery_final(context, "OPERATOR_STOP_RECOVERY_VALID_ABORT_REQUESTED_EXIT_NOT_CONFIRMED_TIMEOUT_NO_FORCE", f"PROCESS_TREE_OR_FILES_NOT_STABLE_WITHIN_3600_SECONDS_NO_FORCE;ACTION_ERROR:{action_error}", True, abort_created_at_utc, payload_written, payload_synced, readback_matches, False, wait_seconds, poll_count, previous_terminal_state, None)  # 如实封板有效请求已提交但退出未确认。
    monitor_wait_started = time.monotonic()  # 记录进程退出后等待冻结监控器终态的单调起点。
    monitor_audit: dict[str, Any] | None = None  # 初始化尚未取得的完整监控终态摘要。
    monitor_dirty_reason: str | None = None  # 初始化尚未发现的不干净监控原因。
    monitor_read_error: str | None = None  # 保存等待期最后一次半写、字段或哈希异常。
    while time.monotonic() - monitor_wait_started < POST_EXIT_MONITOR_TIMEOUT_SECONDS:  # 最多等待三分钟跨过监控器终态写入窗口。
        if context["monitor_final_path"].is_file():  # 文件出现后仍需完整字段和流水哈希审计。
            try:  # 半写或字段异常允许有界重试而不触发进程动作。
                monitor_audit, monitor_dirty_reason = validate_monitor_final_for_operator_abort(context, str(abort_created_at_utc))  # 闭合基础终态并显式区分预期 operator abort 签名、未预期硬错误和监控器独立处置。
                break  # 取得完整对象后结束等待，无论干净与否都如实封板。
            except (OSError, RuntimeError, UnicodeError, json.JSONDecodeError, AttributeError, KeyError, TypeError, ValueError) as error:  # 收敛半写、错型和摘要异常。
                monitor_read_error = str(error)  # 保留最后异常供超时终态解释。
        time.sleep(POLL_INTERVAL_SECONDS)  # 每五秒只读重试且绝不发送进程信号。
    if monitor_audit is None:  # 三分钟内未取得完整可审计监控终态。
        reason = "MONITOR_FINAL_MISSING_AFTER_180_SECONDS" if monitor_read_error is None else f"MONITOR_FINAL_UNREADABLE_AFTER_180_SECONDS:{monitor_read_error}"  # 区分从未出现和持续不可读。
        return write_recovery_final(context, "OPERATOR_STOP_RECOVERY_VALID_ABORT_EXITED_MONITOR_FINAL_MISSING_NO_FORCE", f"{reason};ACTION_ERROR:{action_error}", True, abort_created_at_utc, payload_written, payload_synced, readback_matches, True, wait_seconds, poll_count, stable_state, None)  # 保留已退出事实但不声称完整闭环。
    if monitor_dirty_reason is not None:  # 硬事件、监控器动作、lock、进程或流水任一不干净时禁止成功状态。
        return write_recovery_final(context, "OPERATOR_STOP_RECOVERY_VALID_ABORT_EXITED_MONITOR_FINAL_NOT_CLEAN_NO_FORCE", f"{monitor_dirty_reason};ACTION_ERROR:{action_error}", True, abort_created_at_utc, payload_written, payload_synced, readback_matches, True, wait_seconds, poll_count, stable_state, monitor_audit)  # 保留完整不干净证据且不强杀。
    if action_error is not None or not paths["executed"].is_file():  # 动作已可能生效但执行回执未完整闭合时禁止发布干净成功状态。
        return write_recovery_final(context, "OPERATOR_STOP_RECOVERY_VALID_ABORT_EXITED_ACTION_RECEIPT_INCOMPLETE_NO_FORCE", f"ACTION_EXECUTED_RECEIPT_INCOMPLETE:{action_error}", True, abort_created_at_utc, payload_written, payload_synced, readback_matches, True, wait_seconds, poll_count, stable_state, monitor_audit)  # 如实保留退出与回执缺口。
    return write_recovery_final(context, "OPERATOR_STOP_RECOVERY_VALID_NATIVE_ABORT_REQUESTED_PROCESS_TREE_EXITED_STABLE", None, True, abort_created_at_utc, payload_written, payload_synced, readback_matches, True, wait_seconds, poll_count, stable_state, monitor_audit)  # 仅在双回执、有效载荷、自然退出和监控终态全部干净时发布恢复成功。


def call_name(call: ast.Call) -> str | None:  # 接收 AST 调用节点并返回简单函数名或属性名供离线禁用动作审计。
    if isinstance(call.func, ast.Name):  # 直接函数调用由名称节点表示。
        return call.func.id  # 返回直接调用名称。
    if isinstance(call.func, ast.Attribute):  # 对象方法调用由属性节点表示。
        return call.func.attr  # 返回末级方法名供 kill 等禁令匹配。
    return None  # 复杂动态调用不提供简单名称但仍由人工源码审计覆盖。


def run_offline_self_tests() -> dict[str, Any]:  # 无运行目录输入并返回不写任何项目工件的离线合同测试摘要。
    require(SHA256_PATTERN.fullmatch(PRIOR_TOOL_SHA256) is not None, "离线测试失败：旧工具固定摘要不是六十四位小写十六进制")  # 防止人工抄录时漏字节却直到真实恢复才被发现。
    require(SHA256_PATTERN.fullmatch(PRIOR_CLAIM_SHA256) is not None, "离线测试失败：旧 claim 固定摘要不是六十四位小写十六进制")  # 防止事故认领摘要少位、多位或含非十六进制字符。
    require(SHA256_PATTERN.fullmatch(NATIVE_ABORT_PAYLOAD_SHA256) is not None, "离线测试失败：有效 ABT 固定摘要不是六十四位小写十六进制")  # 防止动作载荷摘要文本本身损坏。
    require(sha256_file(PRIOR_TOOL_PATH) == PRIOR_TOOL_SHA256, "离线测试失败：旧工具现场摘要与固定值不一致")  # 在不访问当前运行主流程的前提下现场复算旧工具字节。
    require(len(NATIVE_ABORT_PAYLOAD) == NATIVE_ABORT_PAYLOAD_LENGTH, "离线测试失败：有效 ABT 长度不是十字节")  # 验证九字母加 LF 的长度合同。
    require(NATIVE_ABORT_PAYLOAD.hex() == NATIVE_ABORT_PAYLOAD_HEX, "离线测试失败：有效 ABT 十六进制漂移")  # 验证精确 ASCII 字节序列。
    require(hashlib.sha256(NATIVE_ABORT_PAYLOAD).hexdigest() == NATIVE_ABORT_PAYLOAD_SHA256, "离线测试失败：有效 ABT SHA-256 漂移")  # 验证固定载荷摘要。
    prior_module = load_prior_validation_module()  # 只读加载旧决策模块供合成 MNTR 数学门测试。
    synthetic_rows = [{"load_step": 1, "substep": 1, "attempt": 1, "iterations": 4, "total_iterations": 4, "increment": 1.0, "total_time_printed": 1.0, "elapsed_seconds": 300.0}, {"load_step": 2, "substep": 1, "attempt": 4, "iterations": 29, "total_iterations": 48, "increment": MINIMUM_INCREMENT, "total_time_printed": 1.0, "elapsed_seconds": 3700.0}, {"load_step": 2, "substep": 2, "attempt": 1, "iterations": 45, "total_iterations": 93, "increment": MINIMUM_INCREMENT, "total_time_printed": 1.0, "elapsed_seconds": 6600.0}]  # 构造两个连续最小步且剩余投影超过七天的门 A 样本。
    synthetic_result = prior_module.evaluate_mntr_sufficiency(synthetic_rows)  # 复用旧模块验证合成门 A 投影。
    require(synthetic_result["sufficiency_branch"] == "A_TWO_ACCEPTED_MINIMUM_STEPS" and float(synthetic_result["projected_remaining_seconds"]) > SUFFICIENCY_HORIZON_SECONDS, "离线测试失败：门 A 合成样本未通过七天投影")  # 确认恢复依赖的数学门仍成立。
    source_text = SCRIPT_PATH.read_text(encoding="utf-8", errors="strict")  # 严格读取本工具源码供 AST 与逐行注释自审计。
    syntax_tree = ast.parse(source_text, filename=str(SCRIPT_PATH))  # 解析完整源码以确认 Python 语法合法。
    forbidden_calls = sorted({name for node in ast.walk(syntax_tree) if isinstance(node, ast.Call) for name in [call_name(node)] if name in FORBIDDEN_PROCESS_CALL_NAMES})  # 收集全部被禁止的主动进程动作调用名。
    require(not forbidden_calls, f"离线测试失败：发现禁止的主动进程动作调用 {forbidden_calls}")  # 源码出现任一 kill、terminate 或 send_signal 即失败。
    uncommented_lines = [index for index, line in enumerate(source_text.splitlines(), start=1) if line.strip() and "#" not in line]  # 收集所有非空且缺少相邻注释标记的物理源码行。
    require(not uncommented_lines, f"离线测试失败：存在缺少逐行中文注释的源码行 {uncommented_lines[:20]}")  # 强制每一行有效代码都带注释。
    non_chinese_comment_lines = [index for index, line in enumerate(source_text.splitlines(), start=1) if "#" in line and re.search(r"[\u4e00-\u9fff]", line.split("#", 1)[1]) is None]  # 收集注释段不含中文字符的物理行。
    require(not non_chinese_comment_lines, f"离线测试失败：存在不含中文的注释行 {non_chinese_comment_lines[:20]}")  # 落实默认中文逐行注释合同。
    return {"status": "OFFLINE_SELF_TESTS_PASSED", "tool_sha256": sha256_file(SCRIPT_PATH), "native_abort_payload_length_bytes": NATIVE_ABORT_PAYLOAD_LENGTH, "native_abort_payload_sha256": NATIVE_ABORT_PAYLOAD_SHA256, "synthetic_projected_remaining_seconds": synthetic_result["projected_remaining_seconds"], "forbidden_process_calls": forbidden_calls, "uncommented_line_count": len(uncommented_lines), "non_chinese_comment_line_count": len(non_chinese_comment_lines), "current_run_writes_performed": False}  # 返回可机器解析且明确未写当前运行的自测摘要。


def parse_arguments() -> argparse.Namespace:  # 无业务输入并返回命令行恢复或离线自测参数。
    parser = argparse.ArgumentParser(description="旧空 ABT 控制器自然超时后，以追加式双回执写入有效 nonlinear ABT；绝不主动结束或强制结束 ANSYS 进程。")  # 创建事故专用命令行解析器。
    parser.add_argument("--run-dir", type=Path, help=f"唯一批准运行目录，名称必须为 {EXPECTED_RUN_NAME}。")  # 接收显式运行目录且禁止 latest 和通配符。
    parser.add_argument("--expected-prior-final-sha256", help="旧 runtime_operator_stop_final.json 的外部冻结 SHA-256。")  # 强制调用者在旧控制器退出后确认旧终态字节。
    parser.add_argument("--self-test", action="store_true", help="仅执行载荷、数学、AST 和逐行中文注释离线自测，不访问运行主流程。")  # 提供绝不写当前 run 的验证入口。
    return parser.parse_args()  # 返回已完成基本类型转换的命名空间。


def main() -> None:  # 无返回值；执行离线自测或唯一事故运行的追加式有效 ABT 恢复。
    arguments = parse_arguments()  # 读取运行路径、旧 final 摘要和离线开关。
    if arguments.self_test:  # 离线模式不得进入运行验证或写工件路径。
        print(json.dumps(run_offline_self_tests(), ensure_ascii=False, allow_nan=False))  # 输出可解析自测结果并结束。
        return  # 明确阻断后续运行主流程。
    require(arguments.run_dir is not None, "恢复模式必须提供 --run-dir")  # 阻断未指定唯一事故运行。
    require(isinstance(arguments.expected_prior_final_sha256, str), "恢复模式必须提供 --expected-prior-final-sha256")  # 阻断未冻结旧终态摘要。
    final_path = request_valid_native_abort_recovery(arguments.run_dir, arguments.expected_prior_final_sha256)  # 执行全链验证、双回执、有效 ABT 和自然退出等待。
    final = read_json(final_path)  # 读取刚刚排他写出的恢复终态供标准输出摘要。
    print(json.dumps({"run_dir": str(arguments.run_dir.resolve()), "status": final["status"], "recovery_final": str(final_path), "exact_process_tree_exit_confirmed": final["exact_process_tree_exit_confirmed"], "operator_tool_process_terminate_api_called": False, "operator_tool_process_kill_api_called": False, "operator_tool_process_send_signal_api_called": False, "modal_execution_allowed": False, "production_claim_allowed": False}, ensure_ascii=False, allow_nan=False))  # 输出明确无强杀、无模态和无生产边界的机器摘要。


if __name__ == "__main__":  # 仅直接执行本文件时进入离线自测或事故恢复流程。
    main()  # 执行严格命令行入口；导入审查不会访问当前 run 或写任何工件。
