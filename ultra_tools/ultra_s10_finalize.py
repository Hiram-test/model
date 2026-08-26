"""对固定 S10 运行实施只读结果门禁，并在全部通过后事务化写入真实终态、最终 QA 和全 run SHA-256 账本。"""  # 模块永久禁止写入 solver，只更新根状态、lineage、qa、结果包、运行回执和编排器快照。

from __future__ import annotations  # 启用延迟类型注解，避免动态证据容器在导入阶段产生兼容性副作用。

import argparse  # 严格解析零参数 CLI，并由标准 --help 提供唯一允许的参数帮助入口。
import copy  # 深复制 prepare manifest，保留全部来源、物理差异和资源历史字段。
import csv  # 解析 LINK180 两列轴力 CSV 和最终账本标签结构。
import ctypes  # 调用 Windows 内核命名互斥量，保证 finalizer 跨进程独占且进程退出自动释放。
import json  # 读取运行态 JSON，并输出机器 QA、根状态和最终运行回执。
import math  # 拒绝非有限数值并执行频率、能量、质量和反力容差门禁。
import os  # 提供 fsync 与原子 os.replace，避免半写文件成为正式终态。
import re  # 提取 MAPDL 警告、错误、收敛摘要、静力键值、结果集和向量结构。
import subprocess  # 只读查询原主 PID 是否仍存在，不启动任何结构求解。
from ctypes import wintypes  # 为 CreateMutexW、ReleaseMutex 和 CloseHandle 声明 Windows 句柄类型。
from datetime import datetime, timezone  # 生成唯一 UTC 最终化时间。
from pathlib import Path  # 统一处理固定 run、相对账本路径和写入越界门禁。
from typing import Any  # 描述 JSON 动态对象和证据汇总字典。

from ultra_a10_finalize import json_bytes  # 复用已验证的确定性 UTF-8 JSON 渲染函数。
from ultra_a10_finalize import parse_numeric_csv  # 复用无标题纯数值 CSV 的有限数和列数门禁。
from ultra_a10_finalize import read_json  # 复用 UTF-8-sig JSON 顶层对象严格解析函数。
from ultra_a10_finalize import read_mixed_text  # 复用 MAPDL 混合编码文本的 ASCII 安全读取函数。
from ultra_a10_finalize import require  # 复用 fail-closed 布尔门禁函数。
from ultra_a10_finalize import sha256_bytes  # 复用内存字节 SHA-256 函数。
from ultra_a10_finalize import sha256_file  # 复用 8 MiB 流式文件 SHA-256 函数。


SCRIPT_PATH = Path(__file__).resolve()  # 固定当前 S10 finalizer 源码绝对路径。
TOOLS_DIR = SCRIPT_PATH.parent  # ultra_tools 是 finalizer 与通用 helper 所在目录。
HELPER_PATH = TOOLS_DIR / "ultra_a10_finalize.py"  # 记录本脚本实际复用的通用只读函数源码。
PROJECT_ROOT = TOOLS_DIR.parent  # V2.0 项目根目录承载固定 ultra_runs。
RUN_NAME = "S10_SECTION_SHEAR_20260716T050342389124Z"  # 本脚本只允许封板这一 S10 正式运行。
RUN_DIR = PROJECT_ROOT / "ultra_runs" / RUN_NAME  # 指向固定 S10 run。
FINALIZER_MUTEX_NAME = f"Local\\UltraS10Finalize_{RUN_NAME}"  # 使用当前 Windows 登录会话内的固定命名互斥量串行化同一 run 的全部 finalizer。
WINDOWS_ERROR_ALREADY_EXISTS = 183  # CreateMutexW 返回既有命名对象时的 Win32 错误码，表示另一 finalizer 已持有或保留该互斥量。
SOLVER_DIR = RUN_DIR / "solver"  # solver 目录在最终化期间永久只读。
QA_DIR = RUN_DIR / "qa"  # 最终机器 QA 和字段说明写入既有 qa 目录。
LINEAGE_DIR = RUN_DIR / "lineage"  # prepare 与 running 原件归档到既有 lineage 目录。
ORCHESTRATOR_DIR = RUN_DIR / "orchestrator_snapshot"  # finalizer 和 helper 源码快照写入既有编排器快照目录。
STATUS_PATH = RUN_DIR / "S10_status.json"  # 根状态从 prepare 事实更新为真实执行终态。
MANIFEST_PATH = RUN_DIR / "manifest.json"  # 根 manifest 保留历史并补入实际执行和 postrun 字段。
RESULT_PACKET_PATH = RUN_DIR / "result_packet.md"  # 用户入口由不可读 prepare 文本更新为最终结果摘要。
LEDGER_PATH = RUN_DIR / "artifact_hashes.sha256"  # 最终全 run 账本覆盖旧 prepare 账本且只排除自身。
RUNTIME_LAUNCH_PATH = RUN_DIR / "runtime_launch.json"  # 运行回执从 RUNNING_UNFINALIZED 更新为 COMPLETED_FINALIZED。
RUNTIME_STATUS_PATH = RUN_DIR / "runtime_status.md"  # 运行说明更新为完成和 QA 闭合口径。
PREPARE_STATUS_ARCHIVE = LINEAGE_DIR / "S10_status.prepare_original.json"  # 原样归档 prepare 根状态字节。
PREPARE_MANIFEST_ARCHIVE = LINEAGE_DIR / "manifest.prepare_original.json"  # 原样归档 prepare manifest 字节。
PREPARE_RESULT_PACKET_ARCHIVE = LINEAGE_DIR / "result_packet.prepare_original.md"  # 原样归档 prepare 用户说明字节。
PREPARE_LEDGER_ARCHIVE = LINEAGE_DIR / "artifact_hashes.prepare_original.sha256"  # 原样归档 52 项 prepare 账本。
RUNNING_LAUNCH_ARCHIVE = LINEAGE_DIR / "runtime_launch.running_original.json"  # 原样归档启动时运行回执。
RUNNING_STATUS_ARCHIVE = LINEAGE_DIR / "runtime_status.running_original.md"  # 原样归档运行中说明。
POSTRUN_GATE_PATH = QA_DIR / "postrun_gate.json"  # 机器可读最终门禁主入口。
EXTERNAL_COMPLETION_QA_PATH = QA_DIR / "s10_external_completion_qa.json"  # 后续 C10 复用的逐字节同源入口。
WARNING_DISPOSITION_PATH = QA_DIR / "warning_disposition.md"  # 五条主 OUT warning 的逐项工程处置。
EXECUTION_FIELDS_PATH = QA_DIR / "execution_field_dictionary.md"  # JSON/CSV/账本字段、单位和限制说明。
FINALIZER_SNAPSHOT_PATH = ORCHESTRATOR_DIR / "ultra_s10_finalize.py"  # 保存本次实际执行 finalizer 源码。
HELPER_SNAPSHOT_PATH = ORCHESTRATOR_DIR / "ultra_a10_finalize.helper.py"  # 保存本次复用通用 helper 源码。
JOBNAME = "cw_S10_0716t050342_a4"  # 固定 S10 MAPDL 作业名。
MAIN_INPUT_PATH = SOLVER_DIR / "s10_section_shear_main.inp"  # 固定主输入用于来源哈希和执行协议门禁。
MAIN_INPUT_SNAPSHOT_PATH = RUN_DIR / "input_snapshot" / "s10_section_shear_main.inp"  # 固定主输入审阅快照必须与 solver 副本及 manifest 摘要三方一致。
MAIN_OUT_PATH = SOLVER_DIR / "cw_s10_0716t050342_a4.out"  # 绑定磁盘真实小写 s10 文件名，避免 QA 路径与跨平台账本标签大小写失配。
STATIC_TABLE_PATH = SOLVER_DIR / "s10_static_energy_mass_reaction.txt"  # 固定两步静力、质量和反力摘要。
LS1_HISTORY_PATH = SOLVER_DIR / "s10_ls1_energy_history.csv"  # 固定 20 行 LS1 全历程能量表。
TOPOLOGY_PATH = SOLVER_DIR / "s10_topology_counts.txt"  # 固定节点、单元和 TYPE 数量摘要。
MODAL_TABLE_PATH = SOLVER_DIR / "s10_modal_properties.csv"  # 固定 80×15 模态属性表。
MODAL_SET_LIST_PATH = SOLVER_DIR / "s10_modal_set_list.txt"  # 固定 RSTP 80 结果集清单。
MODAL_MANIFEST_PATH = SOLVER_DIR / "s10_modal_export_manifest.txt"  # 固定 requested/available/exported 三项闭合清单。
SENE_PATH = SOLVER_DIR / "s10_section_modal_sene.csv"  # 固定 80×16 六截面能量表。
GATE_STATUS_PATH = SOLVER_DIR / "s10_gate_status.txt"  # solver 原生状态只读证明等待外部 QA。
EQ_DB_PATH = SOLVER_DIR / f"{JOBNAME}_eq.db"  # LS2 平衡 DB 是 LINK180 POSTONLY 只读源。
STATIC_RST_PATH = SOLVER_DIR / f"{JOBNAME}.rst"  # 静力 RST 是 LINK180 POSTONLY 只读源。
MODAL_DB_PATH = SOLVER_DIR / f"{JOBNAME}_modal.db"  # 模态数据库是最终关键结果。
MODAL_RSTP_PATH = SOLVER_DIR / f"{JOBNAME}.rstp"  # 合并 80 阶模态结果是最终关键结果。
MODAL_MODE_PATH = SOLVER_DIR / f"{JOBNAME}.mode"  # 合并特征向量文件是最终关键结果。
FULL_PATH = SOLVER_DIR / f"{JOBNAME}.full"  # 合并矩阵文件用于结果扩展和复核。
RDB_PATH = SOLVER_DIR / f"{JOBNAME}.rdb"  # 初始数据库用于原生重启能力。
LDHI_PATH = SOLVER_DIR / f"{JOBNAME}.ldhi"  # 载荷历史文件用于原生重启能力。
EXPECTED_PREPARE_STATUS = "PREPARED_NOT_STARTED_USER_MEMORY_OVERRIDE"  # 仅允许从用户明确覆盖内存门禁的 prepare 状态首次最终化。
EXPECTED_RUNTIME_STATUS = "RUNNING_UNFINALIZED"  # 启动回执必须仍是运行中未封板历史状态。
FINAL_STATUS = "PASS_WITH_LEGACY_LIMITATIONS"  # 数值门禁通过但保留运动学、尺度、质量参与和物理映射边界。
EXECUTION_STATUS = "EXECUTED"  # MAPDL 主作业已真实完成。
QA_STATUS = "PASSED_FOR_S10_SECTION_SHEAR_TRIAL"  # QA 仅授权本次截面剪切因果试算结果。
EXPECTED_MODES = 80  # 模态属性、结果集、能量和两类向量均固定 80 阶。
EXPECTED_VECTOR_NODE_ROWS = 91_407  # 每份 PRNSOL 文件含 91,407 个实际求解自由度节点。
MIN_VECTOR_BYTES = 1_000_000  # 每份全桥向量文本至少 1 MB，防止空壳文件通过。
EXPECTED_LINK_COUNT = 73_692  # TYPE4 LINK180 固定数量。
EXPECTED_TOPOLOGY = {  # 固定拓扑和元素类型计数，键名与 solver 摘要字段逐字一致。
    "NODE_COUNT": 109_086,  # 全模型冻结节点总数为 109,086 个。
    "ELEMENT_COUNT": 172_994,  # 全模型冻结单元总数为 172,994 个。
    "TYPE4": 73_692,  # TYPE4 LINK180 冻结单元数量为 73,692 个。
    "TYPE6": 48_620,  # TYPE6 冻结单元数量为 48,620 个。
    "TYPE70": 17_679,  # TYPE70 冻结单元数量为 17,679 个，并与六截面元素总数闭合。
    "TYPE71": 33_003,  # TYPE71 冻结单元数量为 33,003 个。
}  # 完成六项拓扑冻结值映射。
EXPECTED_SECTION_COUNTS = [  # 按 SEC61 至 SEC66 的固定顺序保存六组有限梁单元数量。
    2_698,  # SEC61 冻结有限梁单元数量为 2,698 个。
    1_562,  # SEC62 冻结有限梁单元数量为 1,562 个。
    4_011,  # SEC63 冻结有限梁单元数量为 4,011 个。
    1_890,  # SEC64 冻结有限梁单元数量为 1,890 个。
    4_620,  # SEC65 冻结有限梁单元数量为 4,620 个。
    2_898,  # SEC66 冻结有限梁单元数量为 2,898 个。
]  # 完成 SEC61..66 六组冻结数量列表。
EXPECTED_WARNINGS = 5  # 主 OUT 实际为四条分析 warning 加一条摘要后性能 warning。
EXPECTED_SUMMARY_WARNINGS = 4  # MAPDL 退出摘要在性能 warning 之前报告四条。
EXPECTED_PREPARE_LEDGER_ENTRIES = 52  # prepare 账本固定为 52 项且必须在最终化前全部仍匹配。
MASS_TOLERANCE_TONNE = 1.0e-6  # 总质量绝对误差上限为 1e-6 tonne。
REACTION_RELATIVE_TOLERANCE = 1.0e-4  # 竖向反力相对误差上限为 1e-4。
STEN_RATIO_TOLERANCE = 1.0e-2  # LS1 全历程与 LS2 端点稳定化能比例上限为 1%。
SENE_IDENTITY_TOLERANCE = 1.0e-12  # 六截面能量和比例恒等式采用 1e-12 绝对/相对量级容差。
EXPECTED_RESULT_LOAD_STEP = 2  # 静力保持态和 LINK180 审计必须读取载荷步 2。
EXPECTED_RESULT_SUBSTEP = 1  # LS2 保持态固定只有子步 1。
EXPECTED_RESULT_TIME = 1.001  # LS2 保持态的 MAPDL 伪时间固定为 1.001。
NUMERIC_IDENTITY_TOLERANCE = 1.0e-12  # 结果时间、模态恒等式和文本重算采用 1e-12 的双精度容差。
ENERGY_RATIO_IDENTITY_TOLERANCE = 1.0e-20  # STEN/SENE 文本比例复算采用 1e-20 的绝对容差。
ENERGY_ENDPOINT_ABS_TOLERANCE_N_MM = 1.0e-6  # LS1 端点 SENE 文本复核的最小绝对容差为 1e-6 N·mm。
MODAL_SET_FREQUENCY_TOLERANCE_HZ = 1.0e-7  # 模态属性表与 RSTP 文本频率差上限为 1e-7 Hz。
MODAL_BAND_LIMIT_HZ = 0.35  # 固定试算合同要求 80 阶频带越过 0.35 Hz。
EXPECTED_UZ_SUPPORT_COUNT = 464  # 静力摘要冻结的 UZ 支承节点数量为 464 个。
EXPECTED_LS1_HISTORY_ROWS = 20  # LS1 全历程固定包含 20 个连续子步。
LS1_TIME_INCREMENT = 0.05  # LS1 每个连续子步的 MAPDL 伪时间增量固定为 0.05。
EXPECTED_DMP_RANKS = 4  # 主求解固定使用四个 DMP rank，即 rank0 至 rank3。
WORKER_ERR_VERSION_BYTES = 80  # rank1 至 rank3 的干净 ERR 仅含 80 字节版本标识。
HASH_PROGRESS_INTERVAL = 25  # 全量账本每处理 25 个文件输出一次进度。
EXPECTED_DEPENDENCY_COUNT = 11  # prepare manifest 固定登记十一项输入依赖。
MODAL_PROPERTY_COLUMNS = 15  # 模态属性 CSV 每行固定包含 15 列数值。
LS1_HISTORY_COLUMNS = 6  # LS1 能量历史 CSV 每行固定包含 6 列数值。
SENE_TABLE_COLUMNS = 16  # 六截面模态能量 CSV 每行固定包含 16 列数值。
SECTION_COMPONENT_COUNT = 6  # 六截面能量表固定包含 SEC61..66 六个分量。
LINK_FORCE_COLUMNS = 2  # LINK180 原始轴力 CSV 每行固定包含元素号和轴力两列。
BINARY_SUFFIXES = {  # 这些 solver 二进制实施提交前后必须保持大小与 mtime_ns 不变。
    ".db",  # MAPDL 数据库文件后缀。
    ".rst",  # 静力结果文件后缀。
    ".rstp",  # 合并模态结果文件后缀。
    ".rdb",  # MAPDL 重启数据库后缀。
    ".full",  # 完整矩阵文件后缀。
    ".emat",  # 单元矩阵文件后缀。
    ".esav",  # 单元保存文件后缀。
    ".mode",  # 模态特征向量文件后缀。
    ".mlv",  # MAPDL 模态相关二进制后缀。
    ".r001",  # DMP rank1 结果分片后缀。
    ".r002",  # DMP rank2 结果分片后缀。
    ".dsp",  # MAPDL 位移相关二进制后缀。
    ".ldhi",  # MAPDL 载荷历史文件后缀。
}  # 完成受保护二进制后缀集合。
WARNING_FRAGMENTS = [  # 五项字符串按工程处置顺序唯一识别真实 MAPDL warning 消息块。
    "constraint equations may not be valid for elements that undergo large deflections",  # 识别 legacy 约束方程大变形适用性 warning。
    "coefficient ratio exceeds 1.0e8",  # 识别矩阵系数比超过 1E8 的尺度 warning。
    "calculated reference moment convergence value = 7.085126611e-02",  # 识别 LS1 参考力矩收敛尺度 warning。
    "calculated reference moment convergence value = 1.697185674e-03",  # 识别 LS2 参考力矩收敛尺度 warning。
    "elapsed time exceeds the cpu time by 40%",  # 识别正常退出后追加的 elapsed/CPU 性能 warning。
]  # 完成五条规范化 warning 识别片段。


def parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:  # 输入可选参数序列并返回已验证的零业务参数命名空间。
    """仅允许裸运行或标准 --help；任何未知、位置或伪 dry-run 参数均由 argparse 非零拒绝。"""  # 函数说明 CLI 不允许调用方误以为不存在的参数会改变写入语义。
    parser = argparse.ArgumentParser(description=f"严格最终化固定运行 {RUN_NAME}；除 --help 外不接受任何参数。", allow_abbrev=False)  # 构造禁用长参数缩写的标准解析器，避免近似参数被意外接受。
    return parser.parse_args(argv)  # 解析零个业务参数；未知参数由 argparse 自动打印错误并以退出码 2 终止。


def acquire_finalizer_mutex() -> int:  # 无输入并返回当前线程独占持有的 Windows 内核互斥量句柄整数。
    """CreateMutexW 以固定名称跨进程互斥；进程异常退出时内核自动释放，不产生陈旧锁文件。"""  # 函数说明锁的生命周期和崩溃安全边界。
    require(os.name == "nt", "S10 finalizer 独占锁仅支持当前 Windows 执行环境。")  # 脚本依赖 tasklist 和 Win32 互斥量，因此其他平台必须 fail-closed。
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # 加载 Win32 内核库并启用线程局部 last-error 捕获。
    create_mutex = kernel32.CreateMutexW  # 取得创建或打开命名互斥量的 Unicode API。
    create_mutex.argtypes = [  # 声明 CreateMutexW 三个位置参数的 ctypes 类型。
        ctypes.c_void_p,  # 第一个参数是可空安全属性指针。
        wintypes.BOOL,  # 第二个参数是是否请求初始所有权的布尔值。
        wintypes.LPCWSTR,  # 第三个参数是 Unicode 命名互斥量名称。
    ]  # 完成 CreateMutexW 参数类型列表。
    create_mutex.restype = wintypes.HANDLE  # 声明返回值为 Windows 内核对象句柄。
    close_handle = kernel32.CloseHandle  # 取得关闭未拥有或最终释放句柄的 API。
    close_handle.argtypes = [wintypes.HANDLE]  # 声明 CloseHandle 只接收一个内核句柄。
    close_handle.restype = wintypes.BOOL  # 声明 CloseHandle 返回非零表示成功。
    ctypes.set_last_error(0)  # 清空当前线程旧错误码，确保 CreateMutexW 后的判定只反映本次调用。
    raw_handle = create_mutex(None, True, FINALIZER_MUTEX_NAME)  # 创建互斥量并在首次创建时立即把所有权授予当前线程。
    create_error = ctypes.get_last_error()  # 捕获对象创建结果；183 表示同名互斥量已经存在。
    require(bool(raw_handle), f"无法创建 S10 finalizer 互斥量，Win32 错误码={create_error}。")  # 空句柄表示内核锁建立失败，禁止继续读写 run。
    handle = int(raw_handle)  # 把 ctypes 句柄规范化为可跨函数传递的 Python 整数。
    if create_error == WINDOWS_ERROR_ALREADY_EXISTS:  # 同名对象存在时当前线程没有获得初始所有权。
        close_handle(wintypes.HANDLE(handle))  # 关闭本次仅打开的句柄，避免拒绝路径泄漏内核资源。
        raise RuntimeError(f"另一 S10 finalizer 已持有独占互斥量：{FINALIZER_MUTEX_NAME}")  # fail-closed 阻止两个事务并发通过 prepare 起点。
    require(create_error == 0, f"创建 S10 finalizer 互斥量返回异常 Win32 错误码={create_error}。")  # 成功新建时 last-error 必须为零，其他状态不作猜测。
    return handle  # 返回由当前线程持有且必须在最终完成或失败后释放的句柄。


def release_finalizer_mutex(handle: int) -> None:  # 输入当前线程持有的互斥量句柄并释放所有权后关闭内核对象。
    """无论 finalizer 成功还是失败均调用；ReleaseMutex 与 CloseHandle 任一失败都明确报错。"""  # 函数说明锁释放的完整动作。
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # 重新取得带 last-error 支持的 Win32 内核库。
    release_mutex = kernel32.ReleaseMutex  # 取得释放当前线程互斥量所有权的 API。
    release_mutex.argtypes = [wintypes.HANDLE]  # 声明 ReleaseMutex 接收一个内核句柄。
    release_mutex.restype = wintypes.BOOL  # 声明 ReleaseMutex 返回非零表示成功。
    close_handle = kernel32.CloseHandle  # 取得关闭内核句柄的 API。
    close_handle.argtypes = [wintypes.HANDLE]  # 声明 CloseHandle 接收一个内核句柄。
    close_handle.restype = wintypes.BOOL  # 声明 CloseHandle 返回非零表示成功。
    windows_handle = wintypes.HANDLE(handle)  # 把 Python 整数恢复为 Win32 API 所需句柄类型。
    release_ok = bool(release_mutex(windows_handle))  # 释放当前线程从 CreateMutexW 获得的独占所有权。
    release_error = ctypes.get_last_error() if not release_ok else 0  # 仅在释放失败时记录 Win32 错误码。
    close_ok = bool(close_handle(windows_handle))  # 无论释放结果如何都关闭句柄，避免进程继续保留命名对象。
    close_error = ctypes.get_last_error() if not close_ok else 0  # 仅在关闭失败时记录 Win32 错误码。
    require(release_ok and close_ok, f"释放 S10 finalizer 互斥量失败：release_error={release_error}, close_error={close_error}")  # 任一内核资源动作失败均向调用方暴露。


def pid_is_running(pid: int) -> bool:  # 输入 Windows PID 并返回是否仍存在同一活动进程。
    """使用 tasklist 精确 PID 过滤，只读判断原 MAPDL 主 PID 是否已退出。"""  # 函数说明进程门禁。
    command = [  # 构造只查询指定 PID 且输出无标题 CSV 的 tasklist 参数。
        "tasklist",  # 调用 Windows 原生只读进程列表程序。
        "/FI",  # 声明下一项是 tasklist 过滤表达式。
        f"PID eq {pid}",  # 只保留进程号精确等于输入 pid 的记录。
        "/FO",  # 声明下一项是输出格式。
        "CSV",  # 使用可由 csv.reader 稳定解析的 CSV 格式。
        "/NH",  # 禁止输出标题行，避免标题被误判为进程记录。
    ]  # 完成单 PID 查询命令。
    completed = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")  # 执行只读查询并把不可解码字节替换为占位符。
    for row in csv.reader(completed.stdout.splitlines()):  # 逐行解析可能的进程记录。
        if len(row) >= 2 and row[1].strip() == str(pid):  # 第二列精确等于目标 PID 时表示仍活动。
            return True  # 返回活动状态。
    return False  # 未发现精确 PID 时返回已退出。


def safe_run_path(relative_text: str) -> Path:  # 输入账本 POSIX 相对路径并返回固定 run 内规范绝对路径。
    """拒绝绝对路径、空路径、点段和越出 run 的标签。"""  # 函数说明账本路径安全。
    relative = Path(relative_text)  # 将 POSIX 标签转换为本机 Path。
    require(bool(relative.parts) and not relative.is_absolute() and ".." not in relative.parts, f"账本路径不安全：{relative_text}")  # 拒绝绝对和父级点段。
    candidate = (RUN_DIR / relative).resolve(strict=False)  # 规范化固定 run 下候选路径。
    try:  # 尝试表达为 run 内相对路径。
        candidate.relative_to(RUN_DIR.resolve())  # 只有 run 子路径才允许继续。
    except ValueError as exc:  # 越界路径进入明确失败。
        raise RuntimeError(f"账本路径越出 S10 run：{relative_text}") from exc  # 阻止任意文件读取。
    return candidate  # 返回已验证绝对路径。


def validate_hash_ledger(ledger_path: Path, root_dir: Path, expected_entries: int | None = None, exclude_self: bool = True) -> dict[str, Any]:  # ledger_path 是账本文件，root_dir 是标签根目录，expected_entries 为可选精确条目数，exclude_self 控制是否要求除账本自身外全目录闭合。
    """返回账本路径、条目数、冻结摘要和记录映射；严格核对格式、路径、摘要、集合及全窗口元数据稳定性。"""  # 返回对象仅在全部门禁通过后生成。
    require(ledger_path.is_file(), f"哈希账本不存在：{ledger_path}")  # 账本必须存在。
    ledger_before = ledger_path.stat()  # 在读取账本前记录字节数和纳秒修改时间。
    ledger_bytes = ledger_path.read_bytes()  # 一次读取账本原始字节，避免解析内容与返回摘要来自不同版本。
    ledger_after_read = ledger_path.stat()  # 在读取后重新取得账本元数据。
    require((ledger_before.st_size, ledger_before.st_mtime_ns) == (ledger_after_read.st_size, ledger_after_read.st_mtime_ns), f"账本读取期间发生变化：{ledger_path}")  # 账本本身在验证窗口必须稳定。
    initial_actual_metadata: dict[str, tuple[int, int]] = {}  # 初始化按相对标签记录的闭合集合起点元数据。
    if exclude_self:  # 只有全闭合账本才要求根目录全部其他普通文件集合固定。
        for actual_path in root_dir.rglob("*"):  # 在任何逐项哈希前枚举完整普通文件集合。
            if actual_path.is_file() and actual_path != ledger_path:  # 排除账本自身并只记录普通文件。
                actual_stat = actual_path.stat()  # 捕获当前文件的字节数和纳秒修改时间。
                initial_actual_metadata[actual_path.relative_to(root_dir).as_posix()] = (actual_stat.st_size, actual_stat.st_mtime_ns)  # 用稳定 POSIX 标签保存全局起点快照。
    records: dict[str, str] = {}  # 初始化相对路径到摘要映射。
    verified_metadata: dict[Path, tuple[int, int]] = {}  # 保存每个已验证目标在首次读取前的元数据供全程结束复核。
    ledger_text = ledger_bytes.decode("utf-8")  # 按规范无 BOM UTF-8 解码已经冻结的账本字节。
    for line_number, line in enumerate(ledger_text.splitlines(), start=1):  # 逐行解析同一份冻结账本内容。
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)  # 要求小写 SHA-256、双空格和非空标签。
        require(match is not None, f"账本第 {line_number} 行格式非法：{ledger_path}")  # 非规范行立即拒绝。
        digest, relative_text = match.groups()  # 提取摘要和相对路径。
        relative = Path(relative_text)  # 把标签转换为 Path 供安全检查。
        require(not relative.is_absolute() and ".." not in relative.parts and relative_text not in records, f"账本路径不安全或重复：{relative_text}")  # 拒绝绝对、父级和重复标签。
        candidate = (root_dir / relative).resolve(strict=False)  # 解析根目录内候选文件。
        try:  # 尝试确认候选位于根目录。
            candidate.relative_to(root_dir.resolve())  # 只有根目录子文件才合法。
        except ValueError as exc:  # 越界路径进入失败。
            raise RuntimeError(f"账本路径越出根目录：{relative_text}") from exc  # 抛出安全错误。
        require(candidate.is_file(), f"账本文件缺失：{candidate}")  # 每个标签必须指向普通文件。
        candidate_before = candidate.stat()  # 在当前文件哈希前记录字节数和纳秒修改时间。
        candidate_metadata = (candidate_before.st_size, candidate_before.st_mtime_ns)  # 规范化当前文件起点元数据。
        if exclude_self:  # 全闭合账本要求当前标签命中最初枚举的同一文件版本。
            require(initial_actual_metadata.get(relative_text) == candidate_metadata, f"账本文件在全局验证开始后发生变化或路径大小写不一致：{candidate}")  # 拒绝哈希前已经漂移的文件。
        require(sha256_file(candidate) == digest, f"账本摘要不匹配：{candidate}")  # 当前字节必须匹配账本。
        candidate_after = candidate.stat()  # 在当前文件哈希后再次读取元数据。
        require(candidate_metadata == (candidate_after.st_size, candidate_after.st_mtime_ns), f"账本文件哈希期间发生变化：{candidate}")  # 拒绝当前文件读取窗口内的并发写入。
        verified_metadata[candidate] = candidate_metadata  # 保存当前文件版本供全部条目处理结束后的第二次检查。
        records[relative_text] = digest  # 保存已验证记录。
    if expected_entries is not None:  # 调用方提供固定条目数时执行精确比较。
        require(len(records) == expected_entries, f"账本条目数不是 {expected_entries}：{ledger_path}")  # 条目数漂移即拒绝。
    if exclude_self:  # 账本按设计排除自身时执行集合闭合。
        require(set(records) == set(initial_actual_metadata), f"账本集合与初始实际文件集合不闭合：{ledger_path}")  # 拒绝漏登、幽灵记录和标签大小写漂移。
        final_actual_metadata: dict[str, tuple[int, int]] = {}  # 初始化全部条目验证完成后的实际集合快照。
        for actual_path in root_dir.rglob("*"):  # 第二次递归枚举全部普通文件，捕获早先文件哈希后的漂移和新文件。
            if actual_path.is_file() and actual_path != ledger_path:  # 排除账本自身并只记录普通文件。
                actual_stat = actual_path.stat()  # 取得结束时字节数和纳秒修改时间。
                final_actual_metadata[actual_path.relative_to(root_dir).as_posix()] = (actual_stat.st_size, actual_stat.st_mtime_ns)  # 保存结束时稳定 POSIX 标签快照。
        require(final_actual_metadata == initial_actual_metadata, f"账本全局验证期间文件集合或元数据发生变化：{ledger_path}")  # 拒绝新增、删除以及早先已哈希文件的后续漂移。
    else:  # prepare 子集账本不要求覆盖执行后新增文件，但其已登记目标仍必须全程稳定。
        for candidate, candidate_metadata in verified_metadata.items():  # 逐项复核每个已哈希文件在全部账本处理结束后仍是同一版本。
            candidate_final = candidate.stat()  # 取得当前已登记文件的结束元数据。
            require(candidate_metadata == (candidate_final.st_size, candidate_final.st_mtime_ns), f"子集账本验证期间文件在哈希后发生变化：{candidate}")  # 拒绝早先已验证目标的后续漂移。
    ledger_final = ledger_path.stat()  # 在全部目标检查结束后再次取得账本元数据。
    require((ledger_before.st_size, ledger_before.st_mtime_ns) == (ledger_final.st_size, ledger_final.st_mtime_ns) and ledger_path.read_bytes() == ledger_bytes, f"账本在全局验证结束前发生变化：{ledger_path}")  # 账本元数据和完整字节必须保持冻结。
    result = {  # 构造同一冻结账本的身份和记录映射。
        "path": ledger_path.relative_to(RUN_DIR).as_posix() if RUN_DIR.resolve() in ledger_path.resolve().parents else str(ledger_path),  # 账本位于固定 run 内时返回 POSIX 相对路径，否则返回调用方路径文本。
        "entry_count": len(records),  # 已通过格式、路径和摘要验证的账本条目总数。
        "sha256": sha256_bytes(ledger_bytes),  # 本次冻结账本原始字节的 SHA-256。
        "records": records,  # 相对路径标签到已验证摘要的完整映射。
    }  # 完成账本验证结果对象。
    return result  # 返回账本验证结果。


def solver_binary_metadata() -> dict[str, tuple[int, int]]:  # 无输入并返回 solver 二进制相对路径到大小和 mtime_ns 的映射。
    """只读 stat 所有固定二进制后缀，用于证明 finalizer 没有触碰求解结果。"""  # 函数说明保护范围。
    result: dict[str, tuple[int, int]] = {}  # 初始化元数据映射。
    for path in sorted((candidate for candidate in SOLVER_DIR.iterdir() if candidate.is_file() and candidate.suffix.lower() in BINARY_SUFFIXES), key=lambda candidate: candidate.name.lower()):  # 稳定枚举 solver 二进制。
        stat = path.stat()  # 读取大小和纳秒修改时间。
        result[path.name] = (stat.st_size, stat.st_mtime_ns)  # 保存轻量身份。
    require(bool(result), "solver 未发现受保护二进制。")  # 空集合表示路径或后缀契约失效。
    return result  # 返回元数据映射。


def parse_key_values(path: Path) -> dict[str, float]:  # 输入 MAPDL 键值摘要并返回所有有限浮点字段。
    """支持一行多个 KEY=VALUE，固定使用 ASCII 键并拒绝非有限数值。"""  # 函数说明解析口径。
    text = read_mixed_text(path).upper()  # 读取并统一键大小写。
    pairs = re.findall(r"([A-Z][A-Z0-9_]*)=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:E[+-]?\d+)?)", text)  # 提取科学计数法键值。
    values = {key: float(value) for key, value in pairs}  # 转换为浮点映射。
    require(all(math.isfinite(value) for value in values.values()), f"键值摘要含非有限数：{path}")  # 拒绝 NaN 和无穷。
    return values  # 返回完整键值映射。


def validate_prepare_roots() -> dict[str, Any]:  # 无输入并返回 prepare/running 原件和身份。
    """只允许从唯一 prepare+running 状态首次最终化，并先验证 52 项 prepare 账本未漂移。"""  # 函数说明一次性起点。
    require(RUN_DIR.is_dir() and SOLVER_DIR.is_dir() and QA_DIR.is_dir() and LINEAGE_DIR.is_dir() and ORCHESTRATOR_DIR.is_dir(), "S10 run 结构不完整。")  # 五个固定目录必须齐全。
    status_bytes = STATUS_PATH.read_bytes()  # 捕获 prepare 根状态原始字节。
    manifest_bytes = MANIFEST_PATH.read_bytes()  # 捕获 prepare manifest 原始字节。
    result_packet_bytes = RESULT_PACKET_PATH.read_bytes()  # 捕获 prepare 结果说明原始字节。
    prepare_ledger_bytes = LEDGER_PATH.read_bytes()  # 捕获 52 项 prepare 账本原始字节。
    runtime_launch_bytes = RUNTIME_LAUNCH_PATH.read_bytes()  # 捕获启动时运行回执原始字节。
    runtime_status_bytes = RUNTIME_STATUS_PATH.read_bytes()  # 捕获运行中说明原始字节。
    status = read_json(STATUS_PATH)  # 解析 prepare 根状态。
    manifest = read_json(MANIFEST_PATH)  # 解析 prepare manifest。
    runtime_launch = read_json(RUNTIME_LAUNCH_PATH)  # 解析运行回执。
    require(status.get("run_name") == RUN_NAME and manifest.get("run_name") == RUN_NAME and runtime_launch.get("run_name") == RUN_NAME, "根文件 run 身份不一致。")  # 三份机器文件必须绑定固定 run。
    require(status.get("jobname") == JOBNAME and manifest.get("jobname") == JOBNAME and runtime_launch.get("jobname") == JOBNAME, "根文件 jobname 不一致。")  # 三份机器文件必须绑定固定作业。
    require(status.get("status") == EXPECTED_PREPARE_STATUS and manifest.get("status") == EXPECTED_PREPARE_STATUS, "根状态不是允许的一次性 prepare 起点。")  # 拒绝重复最终化或错误 run。
    require(status.get("execution_attempted") is False and status.get("mapdl_started") is False and manifest.get("prepare_only") is True and manifest.get("mapdl_started") is False, "prepare 未执行事实不成立。")  # prepare 原件必须仍声明未执行。
    require(runtime_launch.get("status") == EXPECTED_RUNTIME_STATUS and runtime_launch.get("artifact_ledger_pending_finalization") is True, "运行回执不是待最终化状态。")  # 运行回执必须等待账本封板。
    main_pid = int(runtime_launch.get("main_pid", 0))  # 读取原 MAPDL 主 PID。
    require(main_pid > 0 and not pid_is_running(main_pid), f"原 MAPDL 主 PID 仍活动：{main_pid}")  # 主进程必须已经退出。
    prepare_ledger = validate_hash_ledger(LEDGER_PATH, RUN_DIR, EXPECTED_PREPARE_LEDGER_ENTRIES, exclude_self=False)  # 逐项复算 prepare 账本。
    require(set(prepare_ledger["records"]).issubset({path.relative_to(RUN_DIR).as_posix() for path in RUN_DIR.rglob("*") if path.is_file()}), "prepare 账本存在幽灵记录。")  # 52 项必须仍存在。
    new_targets = (  # 枚举首次最终化才允许创建且不得预先存在的十二个目标。
        PREPARE_STATUS_ARCHIVE,  # prepare 根状态原件归档目标。
        PREPARE_MANIFEST_ARCHIVE,  # prepare manifest 原件归档目标。
        PREPARE_RESULT_PACKET_ARCHIVE,  # prepare 用户结果说明原件归档目标。
        PREPARE_LEDGER_ARCHIVE,  # prepare 52 项账本原件归档目标。
        RUNNING_LAUNCH_ARCHIVE,  # running 启动回执原件归档目标。
        RUNNING_STATUS_ARCHIVE,  # running 状态说明原件归档目标。
        POSTRUN_GATE_PATH,  # 最终机器门禁主入口目标。
        EXTERNAL_COMPLETION_QA_PATH,  # 外部完成 QA 同源入口目标。
        WARNING_DISPOSITION_PATH,  # 五条 warning 工程处置文档目标。
        EXECUTION_FIELDS_PATH,  # 不可注释机器字段说明文档目标。
        FINALIZER_SNAPSHOT_PATH,  # 当前 finalizer 源码快照目标。
        HELPER_SNAPSHOT_PATH,  # 当前通用 helper 源码快照目标。
    )  # 完成首次创建目标元组。
    for path in new_targets:  # 逐个检查新目标不存在。
        require(not path.exists(), f"最终化新目标已存在，拒绝覆盖：{path}")  # 任一既有目标都表示状态不确定。
    lock_files = sorted(path for path in SOLVER_DIR.glob("*.lock") if path.is_file())  # 枚举 MAPDL 锁文件。
    stale_locks: list[dict[str, Any]] = []  # 初始化允许保留的退出后零字节锁记录。
    for lock_path in lock_files:  # 逐个核对锁文件只能是已退出作业的零字节残留。
        require(lock_path.name == f"{JOBNAME}.lock" and lock_path.stat().st_size == 0 and lock_path.stat().st_mtime_ns <= MAIN_OUT_PATH.stat().st_mtime_ns, f"发现活动或未知锁文件：{lock_path}")  # 非固定零字节旧锁即拒绝。
        stale_lock = {  # 构造已确认进程退出后的零字节残留锁记录。
            "path": lock_path.relative_to(RUN_DIR).as_posix(),  # 残留锁在固定 run 内的 POSIX 相对路径。
            "length_bytes": 0,  # 文件长度必须严格为零字节。
            "classification": "STALE_ZERO_BYTE_LOCK_AFTER_CONFIRMED_PROCESS_EXIT",  # 分类表示主 PID 已退出且该锁不代表活动求解。
        }  # 完成单个残留锁记录。
        stale_locks.append(stale_lock)  # 保存已验证残留锁记录。
    prepare_ledger_summary = {key: value for key, value in prepare_ledger.items() if key != "records"}  # 删除大记录映射，仅保留 prepare 账本身份摘要。
    result = {  # 构造事务和最终 QA 所需的全部 prepare/running 起点证据。
        "status_bytes": status_bytes,  # prepare 根状态原始字节。
        "manifest_bytes": manifest_bytes,  # prepare manifest 原始字节。
        "result_packet_bytes": result_packet_bytes,  # prepare 用户结果说明原始字节。
        "prepare_ledger_bytes": prepare_ledger_bytes,  # prepare 52 项账本原始字节。
        "runtime_launch_bytes": runtime_launch_bytes,  # running 启动回执原始字节。
        "runtime_status_bytes": runtime_status_bytes,  # running 状态说明原始字节。
        "status": status,  # 已解析 prepare 根状态对象。
        "manifest": manifest,  # 已解析 prepare manifest 对象。
        "runtime_launch": runtime_launch,  # 已解析 running 启动回执对象。
        "status_sha256": sha256_bytes(status_bytes),  # prepare 根状态原始字节摘要。
        "manifest_sha256": sha256_bytes(manifest_bytes),  # prepare manifest 原始字节摘要。
        "result_packet_sha256": sha256_bytes(result_packet_bytes),  # prepare 用户结果说明原始字节摘要。
        "prepare_ledger_sha256": sha256_bytes(prepare_ledger_bytes),  # prepare 账本原始字节摘要。
        "runtime_launch_sha256": sha256_bytes(runtime_launch_bytes),  # running 启动回执原始字节摘要。
        "runtime_status_sha256": sha256_bytes(runtime_status_bytes),  # running 状态说明原始字节摘要。
        "prepare_ledger": prepare_ledger_summary,  # 不含逐文件 records 的 prepare 账本身份摘要。
        "stale_locks": stale_locks,  # 已验证可接受的零字节残留锁列表。
    }  # 完成 prepare/running 起点证据对象。
    return result  # 返回全部起点证据。


def validate_link180_qa() -> dict[str, Any]:  # 无输入并返回最新 S10 LINK180 POSTONLY 正式证据。
    """只接受 schema v2 原子发布包，并直接复算实测子步、全诊断、轴力、生成器谱系和源完整性。"""  # 函数说明强化后的硬前提。
    candidates = sorted(path for path in RUN_DIR.glob("S10_LINK180_POSTONLY_*") if path.is_dir())  # 枚举 run 内正式 LINK180 审计目录。
    require(bool(candidates), "缺少 S10 LINK180 POSTONLY 审计。")  # 缺失即阻断最终化。
    audit_dir = candidates[-1]  # 选择字典序最新审计目录。
    qa_path = audit_dir / "qa_summary.json"  # 固定机器 QA 路径。
    qa = read_json(qa_path)  # 解析机器 QA。
    require(qa.get("schema_version") == 2 and qa.get("audit_id") == audit_dir.name, "S10 LINK180 QA 不是绑定正式目录的 schema v2。")  # 新版机器契约和正式目录身份必须一致。
    require(qa.get("status") == "PASSED" and qa.get("gate_passed") is True and qa.get("publication_mode") == "HIDDEN_STAGING_ATOMIC_RENAME", "S10 LINK180 QA 未通过原子发布门禁。")  # 顶层状态、门禁和发布协议必须同时成立。
    execution = qa.get("execution")  # 提取执行对象。
    result_set = qa.get("result_set")  # 提取结果集对象。
    force = qa.get("link180_axial_force")  # 提取轴力对象。
    source = qa.get("source_integrity")  # 提取源完整性对象。
    orchestrator = qa.get("orchestrator")  # 提取包内生成器源码快照谱系对象。
    qa_objects = (  # 按固定顺序汇总五个必须为字典的正式 QA 子对象。
        execution,  # LINK180 执行诊断对象。
        result_set,  # 实测结果集身份对象。
        force,  # LINK180 轴力覆盖和极值对象。
        source,  # DB/RST 源完整性对象。
        orchestrator,  # 生成器源码快照谱系对象。
    )  # 完成五个正式 QA 子对象元组。
    require(all(isinstance(value, dict) for value in qa_objects), "S10 LINK180 QA 结构不完整。")  # 五个正式对象必须齐全。
    require(execution.get("mode") == "POST1_ONLY_SMP1" and execution.get("mapdl_exit_code") == 0 and execution.get("processes") == 1, "S10 LINK180 POSTONLY 执行模式或退出码异常。")  # 执行必须是固定 SMP1 且零退出。
    require(execution.get("input_forbidden_command_count") == 0 and execution.get("input_allowlist_exact_match") is True and execution.get("uncommented_executable_line_count") == 0 and execution.get("non_chinese_comment_line_count") == 0, "S10 LINK180 APDL strict allowlist 或中文注释门禁失败。")  # 输入活动行、顺序和注释必须完整闭合。
    require(execution.get("mapdl_warning_count") == 0 and execution.get("mapdl_error_count") == 0 and execution.get("mapdl_fatal_count") == 0 and execution.get("negative_pivot_count") == 0 and execution.get("zero_pivot_count") == 0, "S10 LINK180 POSTONLY 存在 warning/error/fatal/pivot。")  # OUT 与 ERR 合并硬诊断必须全零。
    require(execution.get("summary_warning_counts") == [0] and execution.get("summary_error_counts") == [0] and execution.get("exit_without_saving_confirmed") is True, "S10 LINK180 退出摘要或 NOSAVE 门禁失败。")  # 退出摘要必须各唯一零值且确认无保存退出。
    require(int(result_set.get("load_step", -1)) == EXPECTED_RESULT_LOAD_STEP and int(result_set.get("substep", -1)) == EXPECTED_RESULT_SUBSTEP and abs(float(result_set.get("time", math.nan)) - EXPECTED_RESULT_TIME) <= NUMERIC_IDENTITY_TOLERANCE, "S10 LINK180 结果集不是 LS2/1/time=1.001。")  # 结果集载荷步、子步和伪时间必须匹配冻结常量。
    force_count_keys = (  # 定义五项必须共同等于 73,692 的 LINK180 覆盖数量字段。
        "expected_count",  # 冻结期望 LINK180 数量。
        "actual_count",  # MAPDL 实际选择 LINK180 数量。
        "written_count",  # MAPDL 实际写出轴力记录数量。
        "csv_row_count",  # Python 解析的 CSV 有效行数。
        "unique_element_count",  # Python 解析的唯一元素号数量。
    )  # 完成五项覆盖数量字段元组。
    for key in force_count_keys:  # 五项覆盖数量必须全部为 73,692。
        require(int(force.get(key, -1)) == EXPECTED_LINK_COUNT, f"S10 LINK180 {key} 不是 {EXPECTED_LINK_COUNT}。")  # 当前数量不闭合即拒绝。
    require(int(force.get("duplicate_element_count", -1)) == 0 and int(force.get("invalid_numeric_line_count", -1)) == 0 and int(force.get("nonpositive_count", -1)) == 0 and float(force.get("minimum_force_n", 0.0)) > 0.0, "S10 LINK180 存在重复、非法或非正轴力。")  # 原始数据必须全正且无坏记录。
    require(source.get("source_integrity_passed") is True, "S10 LINK180 未证明源完整性。")  # QA 摘要必须声明源不变。
    package_ledger = validate_hash_ledger(audit_dir / "artifact_hashes.sha256", audit_dir, expected_entries=None, exclude_self=True)  # 独立复算审计包自身账本。
    snapshot_name = str(orchestrator.get("snapshot_path", ""))  # 读取包内生成器源码快照文件名。
    require(Path(snapshot_name).name == snapshot_name and snapshot_name.endswith(".py"), "S10 LINK180 生成器快照路径不安全。")  # 快照必须是包内单一 Python 文件名。
    snapshot_hash = str(orchestrator.get("sha256", "")).lower()  # 读取生成器声明的规范小写 SHA-256。
    require(re.fullmatch(r"[0-9a-f]{64}", snapshot_hash) is not None, "S10 LINK180 生成器快照 SHA-256 非法。")  # 摘要必须是完整 64 位十六进制。
    snapshot_path = audit_dir / snapshot_name  # 把生成器快照绑定到正式审计目录。
    require(sha256_file(snapshot_path) == snapshot_hash and package_ledger["records"].get(snapshot_name) == snapshot_hash, "S10 LINK180 生成器快照与包账本不一致。")  # 快照当前字节、QA 声明和包账本必须三方闭合。
    csv_name = str(force.get("csv_path", ""))  # 读取安全 CSV 文件名。
    require(Path(csv_name).name == csv_name and csv_name.endswith(".csv"), "S10 LINK180 CSV 路径不安全。")  # 禁止路径逃逸。
    csv_path = audit_dir / csv_name  # 绑定 CSV 到正式审计目录。
    rows = parse_numeric_csv(csv_path, LINK_FORCE_COLUMNS)  # 直接解析 73,692 行元素号与轴力两列数值。
    require(len(rows) == EXPECTED_LINK_COUNT and all(row[0].is_integer() for row in rows), "S10 LINK180 CSV 行数或元素号非法。")  # 行数和元素号必须闭合。
    element_ids = [int(row[0]) for row in rows]  # 提取整数元素号。
    forces = [row[1] for row in rows]  # 提取轴力。
    require(len(set(element_ids)) == EXPECTED_LINK_COUNT and all(value > 0.0 for value in forces), "S10 LINK180 原始 CSV 含重复元素或非正轴力。")  # 逐行证明全正和唯一。
    minimum_force = min(forces)  # 直接从原始 CSV 复算最小轴力，单位 N。
    maximum_force = max(forces)  # 直接从原始 CSV 复算最大轴力，单位 N。
    minimum_element_id = element_ids[forces.index(minimum_force)]  # 取得首次达到最小轴力的唯一元素号。
    maximum_element_id = element_ids[forces.index(maximum_force)]  # 取得首次达到最大轴力的唯一元素号。
    require(minimum_force == float(force["minimum_force_n"]) and maximum_force == float(force["maximum_force_n"]), "S10 LINK180 CSV 极值与 QA 摘要不一致。")  # 两个轴力极值必须由原始表精确复现。
    require(minimum_element_id == int(force.get("minimum_element_id", -1)) and maximum_element_id == int(force.get("maximum_element_id", -1)), "S10 LINK180 CSV 极值元素号与 QA 摘要不一致。")  # 两个极值对应元素号必须精确复现。
    summary_path = audit_dir / "s10_link180_summary.txt"  # 固定 MAPDL 机器摘要路径。
    summary_values = parse_key_values(summary_path)  # 直接解析 MAPDL 写出的数量、极值和结果集身份。
    summary_required = {  # 定义新版 LINK180 摘要全部必需字段。
        "ACTUAL_COUNT",  # MAPDL 实际选中的 TYPE4 LINK180 数量。
        "WRITTEN_COUNT",  # MAPDL 实际写入轴力 CSV 的记录数量。
        "NONPOSITIVE_COUNT",  # 轴力小于或等于零的记录数量。
        "GATE_PASS",  # MAPDL 内部数量与正轴力联合门禁值。
        "MIN_FORCE_N",  # 最小轴力，单位 N。
        "MIN_ELEMENT_ID",  # 最小轴力对应元素号。
        "MAX_FORCE_N",  # 最大轴力，单位 N。
        "MAX_ELEMENT_ID",  # 最大轴力对应元素号。
        "RESULT_LOAD_STEP",  # 实测结果集载荷步编号。
        "RESULT_SUBSTEP",  # 实测结果集子步编号。
        "RESULT_TIME",  # 实测结果集 MAPDL 伪时间。
    }  # 完成十一项摘要必需字段集合。
    require(summary_required.issubset(summary_values), f"S10 LINK180 摘要缺字段：{sorted(summary_required - set(summary_values))}")  # 缺任一实测字段即拒绝。
    require(int(summary_values["ACTUAL_COUNT"]) == EXPECTED_LINK_COUNT and int(summary_values["WRITTEN_COUNT"]) == EXPECTED_LINK_COUNT and int(summary_values["NONPOSITIVE_COUNT"]) == 0 and int(summary_values["GATE_PASS"]) == 1, "S10 LINK180 MAPDL 数量或内部门禁摘要不闭合。")  # MAPDL 原生数量和正轴力门禁必须通过。
    require(int(summary_values["RESULT_LOAD_STEP"]) == EXPECTED_RESULT_LOAD_STEP and int(summary_values["RESULT_SUBSTEP"]) == EXPECTED_RESULT_SUBSTEP and abs(summary_values["RESULT_TIME"] - EXPECTED_RESULT_TIME) <= NUMERIC_IDENTITY_TOLERANCE, "S10 LINK180 MAPDL 摘要不是实测 LS2/substep1/time=1.001。")  # 不接受 QA 层硬编码结果集身份。
    require(summary_values["MIN_FORCE_N"] == minimum_force and summary_values["MAX_FORCE_N"] == maximum_force and int(summary_values["MIN_ELEMENT_ID"]) == minimum_element_id and int(summary_values["MAX_ELEMENT_ID"]) == maximum_element_id, "S10 LINK180 MAPDL 摘要极值与原始 CSV 不一致。")  # MAPDL 摘要和 Python 深度解析必须四项闭合。
    postflight_name = str(source.get("postflight_path", ""))  # 读取安全 postflight 文件名。
    require(Path(postflight_name).name == postflight_name and postflight_name.endswith(".json"), "S10 LINK180 postflight 路径不安全。")  # 禁止路径逃逸。
    postflight_path = audit_dir / postflight_name  # 绑定 postflight 到正式目录。
    postflight = read_json(postflight_path)  # 解析前后源身份记录。
    require(postflight.get("schema_version") == 2 and postflight.get("audit_id") == audit_dir.name, "S10 LINK180 postflight 不是绑定正式目录的 schema v2。")  # 执行后对象必须属于同一新版原子发布包。
    require(postflight.get("source_integrity_passed") is True and postflight.get("exit_without_saving_confirmed") is True and postflight.get("active_mapdl_process_count_after") == 0, "S10 LINK180 postflight 未证明只读退出。")  # 源不变、NOSAVE 和无残留进程必须成立。
    records = postflight.get("files")  # 提取两个源记录。
    require(isinstance(records, list) and len(records) == 2, "S10 LINK180 postflight 不是 DB/RST 两项。")  # 只允许两个固定源。
    current_sources: dict[str, dict[str, Any]] = {}  # 初始化当前源身份对象。
    expected_paths = {  # 固定 LINK180 postflight 源角色到当前 S10 源路径的映射。
        "equilibrium_database": EQ_DB_PATH,  # 平衡数据库角色绑定 LS2 平衡 DB。
        "static_result": STATIC_RST_PATH,  # 静力结果角色绑定合并静力 RST。
    }  # 完成两个只读源角色映射。
    for record in records:  # 逐项复核前后对象和当前文件。
        require(isinstance(record, dict) and record.get("role") in expected_paths, "S10 LINK180 postflight 源角色非法。")  # 每项必须是固定角色。
        role = str(record["role"])  # 读取已验证角色。
        before = record.get("before")  # 读取执行前身份。
        after = record.get("after")  # 读取执行后身份。
        require(isinstance(before, dict) and isinstance(after, dict) and before == after, f"S10 LINK180 {role} 前后身份不一致。")  # 前后对象必须逐字段相同。
        unchanged_keys = (  # 定义单个源文件必须全部为真的四项不变字段。
            "length_unchanged",  # 文件完整字节数前后不变。
            "creation_time_unchanged",  # Windows 创建时间前后不变。
            "last_write_time_unchanged",  # 最后修改时间前后不变。
            "sha256_unchanged",  # 完整原始字节摘要前后不变。
        )  # 完成源文件不变字段元组。
        require(all(record.get(key) is True for key in unchanged_keys), f"S10 LINK180 {role} 不变布尔未全通过。")  # 四项不变标志必须全真。
        path = expected_paths[role]  # 绑定当前固定源路径。
        current_hash = sha256_file(path)  # 当前时点重新计算源摘要。
        require(current_hash == str(after.get("sha256", "")).lower() and path.stat().st_size == int(after.get("length_bytes", -1)), f"S10 LINK180 {role} 当前内容已漂移。")  # 当前源必须继续匹配 postflight。
        current_sources[role] = {  # 保存当前时点的只读源身份。
            "path": path.relative_to(RUN_DIR).as_posix(),  # 源文件在固定 run 内的 POSIX 相对路径。
            "length_bytes": path.stat().st_size,  # 源文件当前完整字节数。
            "sha256": current_hash,  # 源文件当前完整原始字节 SHA-256。
        }  # 完成当前源身份记录。
    out_path = audit_dir / "s10_link180_post.out"  # 固定 POSTONLY OUT。
    err_path = audit_dir / "s10_link180_post.err"  # 固定 POSTONLY ERR。
    out_text = read_mixed_text(out_path)  # 读取 OUT 直接复核。
    err_text = read_mixed_text(err_path)  # 读取 ERR 直接复核。
    diagnostic_text = out_text + "\n" + err_text  # 合并 OUT 与 ERR 形成与生成器一致的统一诊断口径。
    warning_count = len(re.findall(r"(?im)^\s*\*{3}\s+WARNING\s+\*{3}(?:\s|$)", diagnostic_text))  # 统计合并 warning 标题。
    error_count = len(re.findall(r"(?im)^\s*\*{3}\s+ERROR\s+\*{3}(?:\s|$)", diagnostic_text))  # 统计合并 error 标题。
    fatal_count = len(re.findall(r"(?im)^\s*\*{3}\s+FATAL(?:\s+\*{3})?(?:\s|$)", diagnostic_text))  # 统计合并 fatal 标题。
    negative_pivot_count = len(re.findall(r"(?i)\bnegative\s+pivots?\b", diagnostic_text))  # 统计合并 negative pivot 单复数短语。
    zero_pivot_count = len(re.findall(r"(?i)\bzero\s+pivots?\b", diagnostic_text))  # 统计合并 zero pivot 单复数短语。
    summary_warnings = [int(value) for value in re.findall(r"(?im)^\s*NUMBER OF WARNING MESSAGES ENCOUNTERED=\s*(\d+)\s*$", out_text)]  # 直接提取 OUT 退出摘要 warning 列表。
    summary_errors = [int(value) for value in re.findall(r"(?im)^\s*NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*(\d+)\s*$", out_text)]  # 直接提取 OUT 退出摘要 error 列表。
    diagnostic_counts = (  # 按固定顺序汇总 OUT/ERR 五类硬诊断数量。
        warning_count,  # warning 标题数量。
        error_count,  # error 标题数量。
        fatal_count,  # fatal 标题数量。
        negative_pivot_count,  # negative pivot 短语数量。
        zero_pivot_count,  # zero pivot 短语数量。
    )  # 完成五类硬诊断计数元组。
    expected_zero_diagnostics = (  # 定义五类硬诊断共同要求的零值目标。
        0,  # warning 目标数量为零。
        0,  # error 目标数量为零。
        0,  # fatal 目标数量为零。
        0,  # negative pivot 目标数量为零。
        0,  # zero pivot 目标数量为零。
    )  # 完成五项零诊断目标元组。
    require(diagnostic_counts == expected_zero_diagnostics, "S10 LINK180 OUT/ERR 不是零 warning/error/fatal/pivot。")  # 两份原生诊断必须全干净。
    require(summary_warnings == [0] and summary_errors == [0], "S10 LINK180 OUT 退出摘要不是唯一 0 warning/0 error。")  # 退出摘要必须各出现一次且为零。
    require("EXIT MAPDL WITHOUT SAVING DATABASE" in out_text and "RUN COMPLETED" in out_text, "S10 LINK180 OUT 未确认 NOSAVE 正常完成。")  # 直接确认退出语义。
    require(sha256_file(out_path) == str(execution.get("out_sha256", "")).lower() and sha256_file(err_path) == str(execution.get("err_sha256", "")).lower() and err_path.stat().st_size == int(execution.get("err_length_bytes", -1)), "S10 LINK180 OUT/ERR 身份与 QA 执行对象不一致。")  # 原生诊断文件必须匹配机器 QA 声明。
    return {  # 返回最终化所需新版 LINK180 统一证据。
        "status": "PASSED",  # 表示新版审计包全部硬门禁已通过。
        "audit_dir": audit_dir.relative_to(RUN_DIR).as_posix(),  # 正式 LINK180 审计目录的 run 内相对路径。
        "qa_path": qa_path.relative_to(RUN_DIR).as_posix(),  # 机器 QA 文件的 run 内相对路径。
        "qa_sha256": sha256_file(qa_path),  # 机器 QA 完整原始字节摘要。
        "package_ledger": {key: value for key, value in package_ledger.items() if key != "records"},  # 不含大 records 映射的独立审计包账本摘要。
        "actual_count": EXPECTED_LINK_COUNT,  # 已由原始 CSV 和机器摘要共同证明的 LINK180 数量。
        "nonpositive_count": 0,  # 已由原始 CSV 证明的非正轴力数量。
        "minimum_force_n": minimum_force,  # 原始 CSV 最小轴力，单位 N。
        "minimum_element_id": minimum_element_id,  # 最小轴力对应 LINK180 元素号。
        "maximum_force_n": maximum_force,  # 原始 CSV 最大轴力，单位 N。
        "maximum_element_id": maximum_element_id,  # 最大轴力对应 LINK180 元素号。
        "csv_path": csv_path.relative_to(RUN_DIR).as_posix(),  # 原始轴力 CSV 的 run 内相对路径。
        "csv_sha256": sha256_file(csv_path),  # 原始轴力 CSV 完整摘要。
        "summary_path": summary_path.relative_to(RUN_DIR).as_posix(),  # MAPDL 机器摘要的 run 内相对路径。
        "summary_sha256": sha256_file(summary_path),  # MAPDL 机器摘要完整摘要。
        "postflight_path": postflight_path.relative_to(RUN_DIR).as_posix(),  # 源完整性 postflight 的 run 内相对路径。
        "postflight_sha256": sha256_file(postflight_path),  # postflight 完整摘要。
        "orchestrator_snapshot_path": snapshot_path.relative_to(RUN_DIR).as_posix(),  # 包内真实生成器源码快照相对路径。
        "orchestrator_snapshot_sha256": snapshot_hash,  # 生成器源码快照已验证摘要。
        "current_sources": current_sources,  # finalizer 当前时点重新计算的 DB/RST 身份。
        "execution": execution,  # LINK180 QA 中已验证的执行诊断对象。
        "result_set": result_set,  # LINK180 QA 中已验证的实测结果集身份。
    }  # 完成新版 LINK180 证据对象。


def validate_main_out() -> dict[str, Any]:  # 无输入并返回主 OUT、ERR 和四个 stat 的直接执行证据。
    """要求 5 个预期 warning、0 error/fatal/pivot、80 特征值、RUN COMPLETED 和四 rank 到 Mode 80。"""  # 函数说明主执行门禁。
    text = read_mixed_text(MAIN_OUT_PATH)  # 读取唯一权威主 OUT。
    lower = text.lower()  # 统一大小写用于固定片段识别。
    error_pattern = r"(?im)^\s*\*{3}\s+ERROR\s+\*{3}(?:\s|$)"  # 允许标题空白差异但要求三个星号、独立 ERROR 单词和完整标题边界。
    fatal_pattern = r"(?im)^\s*\*{3}\s+FATAL(?:\s+\*{3})?(?:\s|$)"  # 同时兼容 MAPDL 带或不带尾部三星号的 FATAL 标题。
    negative_pivot_pattern = r"(?i)\bnegative\s+pivots?\b"  # 只匹配 negative pivot/pivots 独立词组，不误判 maximum/minimum pivot 正常统计。
    zero_pivot_pattern = r"(?i)\bzero\s+pivots?\b"  # 只匹配 zero pivot/pivots 独立词组并兼容复数。
    warning_markers = len(re.findall(r"(?m)^\s*\*\*\* WARNING \*\*\*", text))  # 统计实际 warning 标题。
    error_markers = len(re.findall(error_pattern, text))  # 用稳健完整标题规则统计主 OUT error。
    fatal_markers = len(re.findall(fatal_pattern, text))  # 用稳健完整标题规则统计主 OUT fatal。
    negative_pivot_markers = len(re.findall(negative_pivot_pattern, text))  # 统计主 OUT negative pivot 单复数诊断词组。
    zero_pivot_markers = len(re.findall(zero_pivot_pattern, text))  # 统计主 OUT zero pivot 单复数诊断词组。
    summary_warnings = [int(value) for value in re.findall(r"NUMBER OF WARNING MESSAGES ENCOUNTERED=\s*(\d+)", text)]  # 提取退出摘要 warning 数。
    summary_errors = [int(value) for value in re.findall(r"NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*(\d+)", text)]  # 提取退出摘要 error 数。
    require(warning_markers == EXPECTED_WARNINGS and summary_warnings == [EXPECTED_SUMMARY_WARNINGS], "S10 主 OUT warning 计数口径不闭合。")  # 五条实际与四条摘要必须同时成立。
    require(error_markers == 0 and fatal_markers == 0 and summary_errors == [0], "S10 主 OUT 存在 ERROR/FATAL 或摘要错误数非零。")  # 所有硬错误必须为零。
    require("run completed" in lower and "80 eigenvalues converged" in lower and "exit mapdl without saving database" in lower, "S10 主 OUT 缺少完成、80 特征值或 NOSAVE 标记。")  # 三项完成标记必须存在。
    require(negative_pivot_markers == 0 and zero_pivot_markers == 0, "S10 主 OUT 出现负主元或零主元。")  # 矩阵主元硬失败单复数词组必须为零。
    records: list[dict[str, Any]] = []  # 初始化五条 warning 机器处置记录。
    dispositions = [  # 按 WARNING_FRAGMENTS 的冻结顺序定义五条工程处置文本。
        "保留为 legacy 约束方程大变形适用性限制；由两步静力收敛、LINK180 全正和 80 阶模态共同约束。",  # W1 约束方程大变形 warning 的适用性处置。
        "保留为矩阵尺度病态限制；本次无负/零主元、两步收敛且 80 个特征值全部收敛。",  # W2 高系数比 warning 的尺度处置。
        "LS1 参考力矩低于内部阈值仅影响收敛参考尺度；后续完整 20 子步收敛且全历程 STEN/SENE 通过。",  # W3 LS1 参考力矩 warning 的数值处置。
        "LS2 参考力矩低于内部阈值仅影响收敛参考尺度；保持步收敛、time=1.001 且反力质量闭合。",  # W4 LS2 参考力矩 warning 的数值处置。
        "elapsed/CPU 40% 属资源性能提示；发生在 0 error 正常退出之后，不改变数值结果。",  # W5 elapsed/CPU warning 的性能处置。
    ]  # 完成五条固定处置列表。
    lines = text.splitlines()  # 按原始行顺序保存 OUT，以便从 warning 标题提取被 MAPDL 自动换行的完整消息块。
    warning_blocks: list[dict[str, Any]] = []  # 初始化 warning 标题行、原始块和规范化块的映射列表。
    for line_index, line in enumerate(lines):  # 逐行扫描真实的 MAPDL warning 标题，而不在输入回显或普通说明中做全文片段计数。
        if re.fullmatch(r"\s*\*\*\* WARNING \*\*\*.*", line) is None:  # 非 warning 标题行不建立消息块。
            continue  # 继续检查下一行，确保只处理五个真实诊断标题。
        block_lines = [line]  # 当前 warning 块首先包含带 elapsed/time 的标题行。
        for following_line in lines[line_index + 1 :]:  # 从标题下一行开始收集同一 warning 的自动换行正文。
            if not following_line.strip():  # MAPDL 使用空行终止当前 warning 正文。
                break  # 在空行处停止，避免把后续 NOTE、求解输出或另一个 warning 并入本块。
            block_lines.append(following_line)  # 保存当前非空正文行，使跨行句子能够稳定识别。
        normalized_block = re.sub(r"\s+", " ", " ".join(block_lines)).strip().lower()  # 把 MAPDL 的列宽换行和多空格统一为单空格并忽略大小写。
        warning_blocks.append({  # 保存当前 warning 块供唯一语义匹配和机器 QA 追溯。
            "out_line": line_index + 1,  # MAPDL OUT 中一基 warning 标题行号。
            "normalized": normalized_block,  # 已统一空白和大小写的完整 warning 正文。
            "raw_lines": block_lines,  # 保留标题和自动换行正文的原始行列表。
        })  # 完成当前 warning 块记录并追加到顺序列表。
    require(len(warning_blocks) == EXPECTED_WARNINGS, "S10 主 OUT warning 块数量与标题计数不一致。")  # 规范化消息块数量必须仍为五条。
    for index, fragment in enumerate(WARNING_FRAGMENTS):  # 按冻结工程语义顺序识别五条 warning。
        matching_blocks = [block for block in warning_blocks if fragment in block["normalized"]]  # 仅在真实 warning 块内匹配可跨行规范化片段。
        require(len(matching_blocks) == 1, f"S10 warning 识别片段未唯一命中真实消息块：{fragment}")  # 每个预期语义必须唯一对应一个真实 warning。
        matched_block = matching_blocks[0]  # 提取已经证明唯一的 warning 块。
        records.append({  # 保存当前 warning 的识别证据和工程处置。
            "warning_id": f"W{index + 1}",  # 按冻结顺序生成 W1 至 W5 标识。
            "out_line": matched_block["out_line"],  # 当前 warning 在主 OUT 中的一基标题行号。
            "recognition_fragment": fragment,  # 唯一命中当前消息块的规范化语义片段。
            "disposition": dispositions[index],  # 与识别顺序一一对应的工程处置文本。
            "status": "DISPOSED",  # 表示当前 warning 已纳入最终工程判断。
            "contributes_legacy_limitation": index in (0, 1),  # 仅 W1 和 W2 形成最终 legacy 限制。
        })  # 完成当前 warning 处置记录。
    err_records: list[dict[str, Any]] = []  # 初始化四 rank ERR 记录。
    for rank in range(EXPECTED_DMP_RANKS):  # 固定检查四个 DMP rank，即 rank0 至 rank3。
        path = SOLVER_DIR / f"{JOBNAME}_{rank}.err"  # 构造固定 ERR 路径。
        err_text = read_mixed_text(path)  # 读取当前 ERR。
        warnings = len(re.findall(r"(?m)^\s*\*\*\* WARNING \*\*\*", err_text))  # 统计 ERR warning。
        errors = len(re.findall(error_pattern, err_text))  # 使用与主 OUT 相同的稳健完整标题规则统计 ERR error。
        fatals = len(re.findall(fatal_pattern, err_text))  # 独立统计每个 rank ERR 的 FATAL 标题。
        negative_pivots = len(re.findall(negative_pivot_pattern, err_text))  # 独立统计每个 rank ERR 的 negative pivot 单复数词组。
        zero_pivots = len(re.findall(zero_pivot_pattern, err_text))  # 独立统计每个 rank ERR 的 zero pivot 单复数词组。
        require(errors == 0 and fatals == 0 and negative_pivots == 0 and zero_pivots == 0 and warnings == (EXPECTED_WARNINGS if rank == 0 else 0), f"S10 rank{rank} ERR 诊断计数异常。")  # rank0 只允许五 warning，其余硬诊断及 worker warning 必须为零。
        require(rank == 0 or path.stat().st_size == WORKER_ERR_VERSION_BYTES, f"S10 rank{rank} ERR 不是 80 字节版本标识。")  # worker ERR 必须仅包含冻结长度的干净版本行。
        err_records.append({  # 保存当前 rank ERR 身份和全部硬诊断计数。
            "path": path.relative_to(RUN_DIR).as_posix(),  # ERR 文件在固定 run 内的相对路径。
            "length_bytes": path.stat().st_size,  # ERR 文件完整字节数。
            "sha256": sha256_file(path),  # ERR 文件完整原始字节摘要。
            "warning_count": warnings,  # 当前 ERR 中 warning 标题数量。
            "error_count": errors,  # 当前 ERR 中 error 标题数量。
            "fatal_count": fatals,  # 当前 ERR 中 fatal 标题数量。
            "negative_pivot_count": negative_pivots,  # 当前 ERR 中 negative pivot 短语数量。
            "zero_pivot_count": zero_pivots,  # 当前 ERR 中 zero pivot 短语数量。
        })  # 完成当前 rank ERR 记录。
    stat_records: list[dict[str, Any]] = []  # 初始化四 rank stat 终态记录。
    for rank in range(EXPECTED_DMP_RANKS):  # 固定检查四个 DMP rank。
        path = SOLVER_DIR / f"{JOBNAME}_{rank}.stat"  # 构造固定 stat 路径。
        stat_text = read_mixed_text(path)  # 读取最终 stat。
        require(re.search(r"Cum\. Iter\.=\s*80\b", stat_text) is not None and "Element Output" in stat_text, f"S10 rank{rank} stat 未闭合到 Mode 80。")  # stat 必须结束于第 80 阶结果输出。
        stat_records.append({  # 保存当前 rank stat 身份和 Mode 80 完成结论。
            "path": path.relative_to(RUN_DIR).as_posix(),  # stat 文件在固定 run 内的相对路径。
            "length_bytes": path.stat().st_size,  # stat 文件完整字节数。
            "sha256": sha256_file(path),  # stat 文件完整原始字节摘要。
            "mode_80_completed": True,  # 当前 stat 已通过第 80 阶 Element Output 终态门禁。
        })  # 完成当前 rank stat 记录。
    return {  # 返回主 OUT 与四 ERR 全部硬诊断均为零的完整执行证据。
        "path": MAIN_OUT_PATH.relative_to(RUN_DIR).as_posix(),  # 主 OUT 在固定 run 内的相对路径。
        "length_bytes": MAIN_OUT_PATH.stat().st_size,  # 主 OUT 完整字节数。
        "sha256": sha256_file(MAIN_OUT_PATH),  # 主 OUT 完整原始字节摘要。
        "warning_markers": warning_markers,  # 主 OUT 实际 warning 标题总数。
        "summary_warning_count": summary_warnings[0],  # MAPDL 退出摘要记录的 warning 数量。
        "tail_warning_after_summary_count": warning_markers - summary_warnings[0],  # 退出摘要之后追加的性能 warning 数量。
        "error_count": error_markers,  # 主 OUT error 标题数量。
        "fatal_count": fatal_markers,  # 主 OUT fatal 标题数量。
        "negative_pivot_count": negative_pivot_markers,  # 主 OUT negative pivot 短语数量。
        "zero_pivot_count": zero_pivot_markers,  # 主 OUT zero pivot 短语数量。
        "run_completed": True,  # 主 OUT 已出现正常完成和 NOSAVE 标记。
        "eigenvalues_converged": EXPECTED_MODES,  # 主 OUT 已证明全部 80 个特征值收敛。
        "records": records,  # 五条 warning 的逐项识别和工程处置记录。
        "err_files": err_records,  # 四个 DMP rank ERR 的身份和诊断计数。
        "stat_files": stat_records,  # 四个 DMP rank stat 的身份和 Mode 80 完成记录。
    }  # 完成主执行证据对象。


def validate_static() -> dict[str, Any]:  # 无输入并返回两步静力、LS1 全历程、质量和反力门禁。
    """要求 20 行连续历史、STEN 峰值闭合、LS1/LS2 收敛和质量反力误差通过。"""  # 函数说明静力范围。
    values = parse_key_values(STATIC_TABLE_PATH)  # 解析静力摘要。
    required_keys = {  # 定义两步静力、能量、质量和反力摘要全部必需字段。
        "LS1_CNVG",  # LS1 收敛布尔数值。
        "LS2_CNVG",  # LS2 收敛布尔数值。
        "LS2",  # 最终静力载荷步编号。
        "TIME2",  # LS2 最终伪时间。
        "SENE1",  # LS1 端点应变能，单位 N·mm。
        "STEN1",  # LS1 端点稳定化能，单位 N·mm。
        "RATIO1",  # LS1 端点稳定化能绝对比例。
        "STATIC_NSET",  # 静力结果集总数。
        "LS1_HISTORY_COUNT",  # LS1 全历程记录数。
        "PEAK_SUBSTEP",  # LS1 稳定化能比例峰值子步。
        "PEAK_TIME",  # LS1 稳定化能比例峰值伪时间。
        "LS1_HISTORY_PEAK_ABS_STEN_OVER_SENE",  # LS1 全历程稳定化能绝对比例峰值。
        "SENE2",  # LS2 端点应变能，单位 N·mm。
        "STEN2",  # LS2 端点稳定化能，单位 N·mm。
        "RATIO2",  # LS2 端点稳定化能绝对比例。
        "MASS",  # 模型实际总质量，单位 tonne。
        "EXPECTED",  # 冻结期望总质量，单位 tonne。
        "ABS_ERROR",  # 实际与期望总质量绝对误差，单位 tonne。
        "UZ",  # UZ 支承节点数量。
        "RF_EXPECTED",  # 期望竖向总反力，单位 N。
        "RF_ACTUAL",  # 实际竖向总反力，单位 N。
        "RF_ERROR",  # 竖向总反力绝对误差，单位 N。
        "RF_RELATIVE_ERROR",  # 竖向总反力相对误差，无量纲。
    }  # 完成二十三项静力摘要必需字段集合。
    require(required_keys.issubset(values), f"S10 静力摘要缺字段：{sorted(required_keys - set(values))}")  # 缺任一字段即拒绝。
    require(int(values["LS1_CNVG"]) == 1 and int(values["LS2_CNVG"]) == 1 and int(values["LS2"]) == EXPECTED_RESULT_LOAD_STEP and abs(values["TIME2"] - EXPECTED_RESULT_TIME) <= NUMERIC_IDENTITY_TOLERANCE, "S10 LS1/LS2 收敛或结果集身份失败。")  # 两步收敛且 LS2 载荷步和伪时间必须匹配冻结常量。
    require(values["SENE1"] > 0.0 and values["SENE2"] > 0.0 and abs(values["RATIO1"]) <= STEN_RATIO_TOLERANCE and abs(values["RATIO2"]) <= STEN_RATIO_TOLERANCE, "S10 静力端点能量门禁失败。")  # 端点能量必须正且稳定化比例低。
    require(values["ABS_ERROR"] <= MASS_TOLERANCE_TONNE and int(values["UZ"]) == EXPECTED_UZ_SUPPORT_COUNT and values["RF_RELATIVE_ERROR"] <= REACTION_RELATIVE_TOLERANCE, "S10 质量、支承或反力门禁失败。")  # 质量误差、464 个 UZ 支承和反力相对误差必须闭合。
    history = parse_numeric_csv(LS1_HISTORY_PATH, LS1_HISTORY_COLUMNS)  # 解析每行六列的 LS1 全历程。
    expected_history_count = int(values["LS1_HISTORY_COUNT"])  # 读取摘要声明的历史行数。
    require(len(history) == expected_history_count == EXPECTED_LS1_HISTORY_ROWS and int(values["STATIC_NSET"]) == expected_history_count + 1, "S10 LS1 历史行数或静力结果集数量不闭合。")  # 20 个 LS1 子步加 LS2 端点应为 21 个结果集。
    for index, row in enumerate(history, start=1):  # 逐行核对载荷步、子步、时间和比例恒等式。
        require(int(row[0]) == 1 and int(row[1]) == index and abs(row[2] - index * LS1_TIME_INCREMENT) <= NUMERIC_IDENTITY_TOLERANCE, f"S10 LS1 历史第 {index} 行身份不连续。")  # 子步必须连续且伪时间按每步 0.05 递增。
        require(row[3] > 0.0 and abs(row[5] - abs(row[4] / row[3])) <= ENERGY_RATIO_IDENTITY_TOLERANCE, f"S10 LS1 历史第 {index} 行能量比例不闭合。")  # 逐行重算 STEN/SENE 并应用 1e-20 绝对容差。
    require(abs(history[-1][3] - values["SENE1"]) <= max(ENERGY_ENDPOINT_ABS_TOLERANCE_N_MM, abs(values["SENE1"]) * NUMERIC_IDENTITY_TOLERANCE) and abs(history[-1][4] - values["STEN1"]) <= ENERGY_RATIO_IDENTITY_TOLERANCE, "S10 LS1 历史末行与端点摘要不一致。")  # 末行必须在固定绝对/相对容差内等于 LS1 端点。
    peak_index = max(range(len(history)), key=lambda position: abs(history[position][5]))  # 查找全历程峰值行。
    peak_ratio = abs(history[peak_index][5])  # 读取复算峰值。
    require(peak_ratio <= STEN_RATIO_TOLERANCE and abs(peak_ratio - values["LS1_HISTORY_PEAK_ABS_STEN_OVER_SENE"]) <= ENERGY_RATIO_IDENTITY_TOLERANCE, "S10 LS1 全历程 STEN 峰值不闭合或超限。")  # 峰值必须与摘要在 1e-20 内一致且低于 1%。
    require(int(values["PEAK_SUBSTEP"]) == peak_index + 1 and abs(values["PEAK_TIME"] - history[peak_index][2]) <= NUMERIC_IDENTITY_TOLERANCE, "S10 LS1 峰值子步或时间与历史不一致。")  # 峰值子步和伪时间必须在 1e-12 内闭合。
    return {  # 返回带单位的两步静力、全历程、质量和反力结果。
        "ls1_converged": True,  # LS1 已通过收敛门禁。
        "ls2_converged": True,  # LS2 已通过收敛门禁。
        "ls2_load_step": EXPECTED_RESULT_LOAD_STEP,  # LS2 冻结载荷步编号。
        "ls2_time": values["TIME2"],  # LS2 实测 MAPDL 伪时间。
        "ls1_sene_n_mm": values["SENE1"],  # LS1 端点应变能，单位 N·mm。
        "ls1_sten_n_mm": values["STEN1"],  # LS1 端点稳定化能，单位 N·mm。
        "ls1_abs_sten_over_sene": abs(values["RATIO1"]),  # LS1 端点稳定化能绝对比例。
        "ls2_sene_n_mm": values["SENE2"],  # LS2 端点应变能，单位 N·mm。
        "ls2_sten_n_mm": values["STEN2"],  # LS2 端点稳定化能，单位 N·mm。
        "ls2_abs_sten_over_sene": abs(values["RATIO2"]),  # LS2 端点稳定化能绝对比例。
        "ls1_history_rows": len(history),  # LS1 全历程有效记录行数。
        "ls1_history_peak_substep": peak_index + 1,  # 稳定化能比例峰值的一基子步号。
        "ls1_history_peak_time": history[peak_index][2],  # 稳定化能比例峰值伪时间。
        "ls1_history_peak_abs_sten_over_sene": peak_ratio,  # LS1 全历程稳定化能绝对比例峰值。
        "mass_actual_tonne": values["MASS"],  # 模型实际总质量，单位 tonne。
        "mass_expected_tonne": values["EXPECTED"],  # 冻结期望总质量，单位 tonne。
        "mass_abs_error_tonne": values["ABS_ERROR"],  # 总质量绝对误差，单位 tonne。
        "uz_support_count": int(values["UZ"]),  # 实测 UZ 支承节点数量。
        "reaction_expected_n": values["RF_EXPECTED"],  # 期望竖向总反力，单位 N。
        "reaction_actual_n": values["RF_ACTUAL"],  # 实际竖向总反力，单位 N。
        "reaction_abs_error_n": values["RF_ERROR"],  # 竖向总反力绝对误差，单位 N。
        "reaction_relative_error": values["RF_RELATIVE_ERROR"],  # 竖向总反力相对误差。
        "ls2_sene_relative_change_from_ls1": abs(values["SENE2"] - values["SENE1"]) / values["SENE1"],  # LS2 相对 LS1 的应变能变化比例。
        "source_path": STATIC_TABLE_PATH.relative_to(RUN_DIR).as_posix(),  # 静力摘要源文件相对路径。
        "source_sha256": sha256_file(STATIC_TABLE_PATH),  # 静力摘要源文件完整摘要。
        "history_path": LS1_HISTORY_PATH.relative_to(RUN_DIR).as_posix(),  # LS1 全历程 CSV 相对路径。
        "history_sha256": sha256_file(LS1_HISTORY_PATH),  # LS1 全历程 CSV 完整摘要。
    }  # 完成静力结果对象。


def validate_topology() -> dict[str, Any]:  # 无输入并返回固定拓扑数量门禁。
    """节点、单元及 TYPE4/6/70/71 必须与 prepare 冻结值逐项相等。"""  # 函数说明拓扑不变量。
    values = parse_key_values(TOPOLOGY_PATH)  # 解析拓扑摘要。
    for key, expected in EXPECTED_TOPOLOGY.items():  # 逐项比较六个冻结数量。
        require(int(values.get(key, -1)) == expected, f"S10 拓扑 {key} 不是 {expected}。")  # 数量漂移即拒绝。
    return {  # 返回固定拓扑数量及其来源身份。
        "status": "PASSED",  # 六项冻结拓扑数量已全部通过。
        "counts": EXPECTED_TOPOLOGY,  # 节点、单元和 TYPE4/6/70/71 冻结数量映射。
        "source_path": TOPOLOGY_PATH.relative_to(RUN_DIR).as_posix(),  # 拓扑摘要源文件相对路径。
        "source_sha256": sha256_file(TOPOLOGY_PATH),  # 拓扑摘要源文件完整摘要。
    }  # 完成拓扑证据对象。


def validate_vector_files(kind: str) -> dict[str, Any]:  # kind 约定传入 displacement 或 rotation，并返回对应 80 份向量结构摘要。
    """displacement 绑定 all_nodes 位移文件，rotation 绑定 rotations 转角文件；调用方只允许使用这两个类别。"""  # 函数说明参数取值、文件映射和返回范围。
    suffix = "all_nodes" if kind == "displacement" else "rotations"  # 绑定类别到文件名后缀。
    expected_header = "PRINT U    NODAL SOLUTION PER NODE" if kind == "displacement" else "PRINT ROT  NODAL SOLUTION PER NODE"  # 绑定类别到 MAPDL 标题。
    paths = sorted(SOLVER_DIR.glob(f"mode_*_{suffix}.txt"))  # 稳定枚举当前类别向量文件。
    require(len(paths) == EXPECTED_MODES, f"S10 {kind} 向量文件数不是 {EXPECTED_MODES}。")  # 数量必须为 80。
    sizes: list[int] = []  # 初始化文件大小列表。
    for mode_index, path in enumerate(paths, start=1):  # 按文件名顺序逐份深度解析。
        require(path.name == f"mode_{mode_index:02d}_{suffix}.txt" and path.stat().st_size >= MIN_VECTOR_BYTES, f"S10 {kind} 向量名称或大小异常：{path.name}")  # 文件名和最小大小必须闭合。
        result_rows = 0  # 初始化当前文件数值节点行计数。
        header_found = False  # 初始化类别标题标志。
        substep_found = False  # 初始化阶次标志。
        maximum_found = False  # 初始化最大值尾部标志。
        forbidden_found = False  # 初始化非法诊断文本标志。
        with path.open("r", encoding="utf-8", errors="replace") as stream:  # 逐行读取当前 7.5 MB 向量文件。
            for line in stream:  # 扫描全部头部、数据行和尾部。
                upper = line.upper()  # 统一 ASCII 大小写供固定文本识别。
                header_found = header_found or expected_header in upper  # 识别位移或转角标题。
                substep_found = substep_found or re.search(rf"SUBSTEP=\s*{mode_index}\b", upper) is not None  # 识别文件内阶次。
                maximum_found = maximum_found or "MAXIMUM ABSOLUTE VALUES" in upper  # 识别完整尾部。
                forbidden_tokens = (  # 定义向量文本中禁止出现的四类非有限或硬诊断标记。
                    "NAN",  # 禁止非数 NaN 标记。
                    "INFINITY",  # 禁止无穷值标记。
                    "*** ERROR ***",  # 禁止 MAPDL error 标题。
                    "*** FATAL",  # 禁止 MAPDL fatal 标题及其带尾星号变体。
                )  # 完成禁止文本标记元组。
                forbidden_found = forbidden_found or any(token in upper for token in forbidden_tokens)  # 识别非有限或硬诊断。
                if re.match(r"^\s*\d+\s+[+\-0-9.]", line):  # 节点结果行以整数节点号和数值开头。
                    result_rows += 1  # 增加结果节点行计数。
        require(header_found and substep_found and maximum_found and not forbidden_found, f"S10 {kind} 向量结构不完整：{path.name}")  # 四项结构门禁必须通过。
        require(result_rows == EXPECTED_VECTOR_NODE_ROWS, f"S10 {kind} {path.name} 结果节点数不是 {EXPECTED_VECTOR_NODE_ROWS}。")  # 每份文件必须含 91407 个求解节点。
        sizes.append(path.stat().st_size)  # 保存文件大小范围。
    return {  # 返回当前位移或转角类别的向量结构摘要。
        "count": len(paths),  # 当前类别实际向量文件数量。
        "result_rows_per_file": EXPECTED_VECTOR_NODE_ROWS,  # 每份向量文件固定求解节点行数。
        "minimum_bytes": min(sizes),  # 当前类别单文件最小字节数。
        "maximum_bytes": max(sizes),  # 当前类别单文件最大字节数。
        "topology_node_count": EXPECTED_TOPOLOGY["NODE_COUNT"],  # 全模型冻结拓扑节点总数。
        "direction_node_gap": EXPECTED_TOPOLOGY["NODE_COUNT"] - EXPECTED_VECTOR_NODE_ROWS,  # 拓扑节点与有自由度结果节点的数量差。
        "direction_node_gap_equals_type70_count": EXPECTED_TOPOLOGY["NODE_COUNT"] - EXPECTED_VECTOR_NODE_ROWS == EXPECTED_TOPOLOGY["TYPE70"],  # 节点差是否恰等于 TYPE70 方向节点数。
        "pattern": f"solver/mode_01..80_{suffix}.txt",  # 当前类别八十份文件的用户可读路径模式。
    }  # 完成向量结构摘要。


def validate_modal(static: dict[str, Any]) -> dict[str, Any]:  # static 必须含 mass_actual_tonne，并返回 80 阶模态、结果集、向量和有效质量摘要。
    """不硬编码频带内阶数，只要求 80 阶完整、频率严格递增且第 80 阶超过冻结的 0.35 Hz。"""  # 函数说明输入约束、模态门禁和返回范围。
    rows = parse_numeric_csv(MODAL_TABLE_PATH, MODAL_PROPERTY_COLUMNS)  # 解析每行十五列的 80 阶模态属性。
    require(len(rows) == EXPECTED_MODES, "S10 模态属性行数不是 80。")  # 属性表必须 80 行。
    frequencies = [row[1] for row in rows]  # 提取频率序列。
    require(all(int(row[0]) == index for index, row in enumerate(rows, start=1)), "S10 模态属性阶次不是 1..80。")  # 阶次必须连续。
    require(all(row[2] > 0.0 for row in rows) and all(value > 0.0 for value in frequencies) and all(left < right for left, right in zip(frequencies, frequencies[1:])), "S10 广义质量或频率非正/不递增。")  # 广义质量正且频率严格递增。
    maximum_effm_residual = 0.0  # 初始化 EFFM=PFACT² 最大相对残差。
    for row in rows:  # 逐阶复核六方向参与因子和有效质量。
        for offset in range(SECTION_COMPONENT_COUNT):  # 六个平动/转动方向逐项比较。
            expected_effm = row[3 + offset] ** 2  # 由参与因子平方重算有效质量。
            actual_effm = row[9 + offset]  # 读取输出有效质量。
            require(actual_effm >= 0.0, "S10 模态有效质量出现负值。")  # 有效质量不得为负。
            residual = abs(actual_effm - expected_effm) / max(1.0, abs(actual_effm), abs(expected_effm))  # 计算尺度稳定相对残差。
            maximum_effm_residual = max(maximum_effm_residual, residual)  # 更新全表最大残差。
    require(maximum_effm_residual <= NUMERIC_IDENTITY_TOLERANCE, "S10 模态 EFFM 与 PFACT² 不闭合。")  # 双精度恒等式残差必须不超过 1e-12。
    manifest_text = read_mixed_text(MODAL_MANIFEST_PATH)  # 读取导出清单。
    manifest_values = [int(round(float(value))) for value in re.findall(r"(?:REQUESTED|AVAILABLE|EXPORTED)=\s*([0-9.]+)", manifest_text.upper())]  # 提取三项阶数。
    require(manifest_values == [EXPECTED_MODES, EXPECTED_MODES, EXPECTED_MODES], "S10 模态 requested/available/exported 不全为 80。")  # 三项闭合。
    set_rows = re.findall(r"(?m)^\s*(\d+)\s+([0-9.+\-Ee]+)\s+1\s+(\d+)\s+(\d+)\s*$", read_mixed_text(MODAL_SET_LIST_PATH))  # 解析 RSTP 结果集索引。
    require(len(set_rows) == EXPECTED_MODES, "S10 RSTP 结果集数不是 80。")  # set list 必须 80 行。
    set_frequencies: list[float] = []  # 初始化结果集频率列表。
    for expected_index, raw in enumerate(set_rows, start=1):  # 逐行核对 SET、SUBSTEP 和累计序号。
        set_number, frequency_text, substep, cumulative = raw  # 分别解包结果集号、频率文本、子步号和累计结果集序号四个字段。
        require(int(set_number) == expected_index and int(substep) == expected_index and int(cumulative) == expected_index, "S10 RSTP 结果集编号不连续。")  # 三个编号必须均为 1..80。
        set_frequencies.append(float(frequency_text))  # 保存结果集频率。
    maximum_set_frequency_error = max(abs(left - right) for left, right in zip(frequencies, set_frequencies))  # 计算属性表与 set list 最大频率差。
    require(maximum_set_frequency_error <= MODAL_SET_FREQUENCY_TOLERANCE_HZ, "S10 模态属性与 RSTP set list 频率不一致。")  # 两份文本频率必须在 1e-7 Hz 容差内一致。
    displacement = validate_vector_files("displacement")  # 深度核对 80 份位移向量。
    rotation = validate_vector_files("rotation")  # 深度核对 80 份转角向量。
    in_band_count = sum(1 for value in frequencies if value <= MODAL_BAND_LIMIT_HZ)  # 统计冻结 0.35 Hz 频带以内实际阶数。
    require(frequencies[-1] > MODAL_BAND_LIMIT_HZ and 0 < in_band_count < EXPECTED_MODES, "S10 80 阶频带未证明越过 0.35 Hz。")  # 证明 80 阶结果无 0.35 Hz 截断。
    gaps = [frequencies[index + 1] - frequencies[index] for index in range(len(frequencies) - 1)]  # 计算相邻频差。
    minimum_gap_index = min(range(len(gaps)), key=gaps.__getitem__)  # 查找最小频差对应的前一阶。
    translational_columns = (  # 固定模态属性表中 X、Y、Z 三个平动有效质量列索引。
        9,  # X 向有效质量位于零基第 9 列。
        10,  # Y 向有效质量位于零基第 10 列。
        11,  # Z 向有效质量位于零基第 11 列。
    )  # 完成三向平动有效质量列索引。
    translational_ratios = [sum(row[column] for row in rows) / static["mass_actual_tonne"] for column in translational_columns]  # 计算 X/Y/Z 80 阶累计有效质量比例。
    effective_mass_ratios = {  # 构造 X、Y、Z 三向八十阶累计有效质量比例。
        "x": translational_ratios[0],  # X 向累计有效质量占总质量比例。
        "y": translational_ratios[1],  # Y 向累计有效质量占总质量比例。
        "z": translational_ratios[2],  # Z 向累计有效质量占总质量比例。
    }  # 完成三向有效质量比例对象。
    return {  # 返回完整模态属性、结果集、向量和有效质量摘要。
        "property_rows": len(rows),  # 模态属性表有效行数。
        "property_columns": MODAL_PROPERTY_COLUMNS,  # 模态属性表固定列数。
        "frequency_first_hz": frequencies[0],  # 第一阶频率，单位 Hz。
        "frequency_last_hz": frequencies[-1],  # 第八十阶频率，单位 Hz。
        "frequency_strictly_increasing": True,  # 全部频率已证明严格递增。
        "frequency_0_to_0_35_hz_count": in_band_count,  # 小于或等于 0.35 Hz 的实际阶数。
        "first_mode_above_0_35_hz": in_band_count + 1,  # 首个超过 0.35 Hz 的一基阶次。
        "first_frequency_above_0_35_hz": frequencies[in_band_count],  # 首个超过 0.35 Hz 的频率。
        "minimum_adjacent_gap_hz": gaps[minimum_gap_index],  # 全部相邻频差中的最小值，单位 Hz。
        "minimum_gap_mode_pair": [minimum_gap_index + 1, minimum_gap_index + 2],  # 最小相邻频差对应的两个一基阶次。
        "generalized_mass_minimum": min(row[2] for row in rows),  # 八十阶广义质量最小值。
        "generalized_mass_maximum": max(row[2] for row in rows),  # 八十阶广义质量最大值。
        "maximum_effm_equals_pfact_squared_residual": maximum_effm_residual,  # EFFM=PFACT² 恒等式全表最大相对残差。
        "effective_mass_ratio_80_modes": effective_mass_ratios,  # X/Y/Z 三向八十阶累计有效质量比例。
        "mass_participation_90_percent_requirement_in_contract": False,  # 固定 S10 合同未设置 90% 质量参与硬门槛。
        "set_count": len(set_rows),  # RSTP 结果集有效记录数量。
        "maximum_property_vs_set_frequency_error_hz": maximum_set_frequency_error,  # 属性表与 set list 最大频率差，单位 Hz。
        "requested": EXPECTED_MODES,  # 模态导出清单请求阶数。
        "available": EXPECTED_MODES,  # 模态导出清单可用阶数。
        "exported": EXPECTED_MODES,  # 模态导出清单实际导出阶数。
        "displacement_vectors": displacement,  # 八十份全节点位移向量结构摘要。
        "rotation_vectors": rotation,  # 八十份全节点转角向量结构摘要。
        "properties_path": MODAL_TABLE_PATH.relative_to(RUN_DIR).as_posix(),  # 模态属性 CSV 相对路径。
        "properties_sha256": sha256_file(MODAL_TABLE_PATH),  # 模态属性 CSV 完整摘要。
        "set_list_path": MODAL_SET_LIST_PATH.relative_to(RUN_DIR).as_posix(),  # RSTP 结果集清单相对路径。
        "set_list_sha256": sha256_file(MODAL_SET_LIST_PATH),  # RSTP 结果集清单完整摘要。
        "export_manifest_path": MODAL_MANIFEST_PATH.relative_to(RUN_DIR).as_posix(),  # 模态导出清单相对路径。
        "export_manifest_sha256": sha256_file(MODAL_MANIFEST_PATH),  # 模态导出清单完整摘要。
    }  # 完成模态结果摘要对象。


def validate_sene() -> dict[str, Any]:  # 无输入并返回 80×16 六截面模态能量门禁。
    """总能量必须正、六组分量非负、比例闭区间且三类恒等式在 1e-12 内闭合。"""  # 函数说明能量门禁。
    rows = parse_numeric_csv(SENE_PATH, SENE_TABLE_COLUMNS)  # 解析每行十六列的八十阶纯数值表。
    require(len(rows) == EXPECTED_MODES and all(int(row[0]) == index for index, row in enumerate(rows, start=1)), "S10 SENE 行数或阶次不是 1..80。")  # 行数和阶次必须闭合。
    ratio_values: list[float] = []  # 初始化 480 个分量比例列表。
    maximum_component_ratio_error = 0.0  # 初始化逐分量比例恒等式误差。
    maximum_sum_error = 0.0  # 初始化六分量求和误差。
    maximum_sum_ratio_error = 0.0  # 初始化六分量总比例误差。
    for row in rows:  # 逐阶复核总能量、六组分量和比例。
        total = row[1]  # 读取全模型总 SENE。
        components = row[2:8]  # 读取 SEC61..66 六组 SENE。
        ratios = row[8:14]  # 读取六组占比。
        six_sum = row[14]  # 读取六组能量和。
        six_ratio = row[15]  # 读取六组能量和占比。
        require(total > 0.0 and all(value >= 0.0 for value in components), "S10 SENE 出现非正总能量或负分量能量。")  # 能量物理门禁。
        require(all(-SENE_IDENTITY_TOLERANCE <= value <= 1.0 + SENE_IDENTITY_TOLERANCE for value in ratios) and -SENE_IDENTITY_TOLERANCE <= six_ratio <= 1.0 + SENE_IDENTITY_TOLERANCE, "S10 SENE 比例越出 [0,1]。")  # 比例必须在闭区间。
        for component, ratio in zip(components, ratios):  # 逐分量复算占比。
            maximum_component_ratio_error = max(maximum_component_ratio_error, abs(component / total - ratio))  # 更新分量比例最大误差。
        maximum_sum_error = max(maximum_sum_error, abs(sum(components) - six_sum))  # 更新六分量和绝对误差。
        maximum_sum_ratio_error = max(maximum_sum_ratio_error, abs(six_sum / total - six_ratio))  # 更新总比例误差。
        ratio_values.extend(ratios)  # 汇总比例范围。
    require(maximum_component_ratio_error <= SENE_IDENTITY_TOLERANCE and maximum_sum_error <= SENE_IDENTITY_TOLERANCE and maximum_sum_ratio_error <= SENE_IDENTITY_TOLERANCE, "S10 SENE 恒等式误差超过 1e-12。")  # 三类恒等式必须通过。
    return {  # 返回完整六截面模态能量摘要。
        "status": "PASSED",  # 八十阶能量物理与恒等式门禁已全部通过。
        "rows": len(rows),  # 六截面模态能量表有效行数。
        "columns": SENE_TABLE_COLUMNS,  # 六截面模态能量表固定列数。
        "component_count": SECTION_COMPONENT_COUNT,  # SEC61..66 固定分量数量。
        "component_counts": EXPECTED_SECTION_COUNTS,  # SEC61..66 六组冻结元素数量。
        "component_total": sum(EXPECTED_SECTION_COUNTS),  # 六组冻结元素数量合计。
        "component_total_equals_type70": sum(EXPECTED_SECTION_COUNTS) == EXPECTED_TOPOLOGY["TYPE70"],  # 六组元素总数是否等于 TYPE70 冻结数量。
        "total_sene_min_n_mm": min(row[1] for row in rows),  # 八十阶全模型总 SENE 最小值，单位 N·mm。
        "total_sene_max_n_mm": max(row[1] for row in rows),  # 八十阶全模型总 SENE 最大值，单位 N·mm。
        "component_ratio_min": min(ratio_values),  # 六组逐分量占比的全表最小值。
        "component_ratio_max": max(ratio_values),  # 六组逐分量占比的全表最大值。
        "six_component_sum_ratio_min": min(row[15] for row in rows),  # 六分量总占比的八十阶最小值。
        "six_component_sum_ratio_max": max(row[15] for row in rows),  # 六分量总占比的八十阶最大值。
        "maximum_component_ratio_error": maximum_component_ratio_error,  # 逐分量占比恒等式最大误差。
        "maximum_component_sum_abs_error_n_mm": maximum_sum_error,  # 六分量能量和恒等式最大绝对误差，单位 N·mm。
        "maximum_sum_ratio_error": maximum_sum_ratio_error,  # 六分量总占比恒等式最大误差。
        "source_path": SENE_PATH.relative_to(RUN_DIR).as_posix(),  # 六截面模态能量 CSV 相对路径。
        "source_sha256": sha256_file(SENE_PATH),  # 六截面模态能量 CSV 完整摘要。
    }  # 完成六截面模态能量对象。


def validate_dependencies(prepare: dict[str, Any]) -> dict[str, Any]:  # prepare 必须含已验证 manifest，并返回主输入和十一项依赖的当前双副本身份。
    """重新计算 input_snapshot 与 solver 双副本；返回对象证明主输入和 SEC61..66 等依赖保持 prepare 哈希。"""  # 函数说明参数约束、来源门禁和返回语义。
    manifest = prepare["manifest"]  # 提取 prepare manifest。
    expected_main_hash = str(manifest.get("main_input_sha256", "")).lower()  # 读取 prepare manifest 冻结的主输入摘要并规范化大小写。
    require(re.fullmatch(r"[0-9a-f]{64}", expected_main_hash) is not None, "S10 prepare manifest 主输入 SHA-256 非法。")  # 主输入历史摘要必须是完整小写十六进制值。
    main_solver_hash = sha256_file(MAIN_INPUT_PATH)  # 重算 solver 实际执行主输入摘要。
    main_snapshot_hash = sha256_file(MAIN_INPUT_SNAPSHOT_PATH)  # 重算 input_snapshot 审阅主输入摘要。
    require(main_solver_hash == expected_main_hash and main_snapshot_hash == expected_main_hash and main_solver_hash == main_snapshot_hash, "S10 主输入 solver、input_snapshot 与 prepare manifest 三方不一致。")  # 两份主输入必须逐字节同源且共同匹配冻结摘要。
    dependencies = manifest.get("dependencies")  # 提取 11 项依赖。
    require(isinstance(dependencies, list) and len(dependencies) == EXPECTED_DEPENDENCY_COUNT, "S10 prepare manifest 依赖数不是 11。")  # 依赖图必须包含冻结的十一项记录。
    records: list[dict[str, Any]] = []  # 初始化当前依赖身份记录。
    seen_basenames: set[str] = set()  # 初始化依赖文件名唯一性集合，防止同一依赖重复十一遍冒充完整图。
    seen_orders: set[int] = set()  # 初始化依赖顺序唯一性集合，确保执行顺序精确覆盖 1..11。
    for item in dependencies:  # 逐项复算 input_snapshot 和 solver 副本。
        require(isinstance(item, dict), "S10 依赖记录不是对象。")  # 每项必须具名字段。
        basename = str(item.get("basename", ""))  # 读取安全 basename。
        require(Path(basename).name == basename and basename, "S10 依赖 basename 不安全。")  # 禁止路径逃逸。
        require(basename not in seen_basenames, f"S10 依赖 basename 重复：{basename}")  # 同一文件不得重复占用多个依赖槽位。
        seen_basenames.add(basename)  # 登记当前已验证唯一文件名。
        raw_order = item.get("order")  # 读取 JSON 中未经截断转换的依赖顺序字段。
        require(isinstance(raw_order, int) and not isinstance(raw_order, bool), f"S10 依赖 order 不是整数：{basename}")  # 拒绝浮点截断和布尔值冒充整数顺序。
        order = int(raw_order)  # 保存已证明为真正整数的顺序值。
        require(order not in seen_orders, f"S10 依赖 order 重复：{order}")  # 每个执行顺序只能出现一次。
        seen_orders.add(order)  # 登记当前唯一顺序。
        snapshot_path = RUN_DIR / "input_snapshot" / basename  # 绑定审阅快照。
        solver_path = SOLVER_DIR / basename  # 绑定执行副本。
        snapshot_hash = sha256_file(snapshot_path)  # 重算快照摘要。
        solver_hash = sha256_file(solver_path)  # 重算执行副本摘要。
        require(snapshot_hash == str(item.get("s10_input_snapshot_sha256", "")).lower() and solver_hash == str(item.get("s10_solver_sha256", "")).lower() and snapshot_hash == solver_hash, f"S10 依赖双副本当前哈希漂移或彼此不一致：{basename}")  # 两套副本必须共同匹配 prepare 记录且逐字节同源。
        records.append({  # 保存当前依赖双副本身份和同源结论。
            "order": order,  # prepare manifest 冻结的执行顺序。
            "basename": basename,  # 不含目录的安全依赖文件名。
            "role": item.get("role"),  # prepare manifest 记录的依赖工程角色。
            "input_snapshot_sha256": snapshot_hash,  # input_snapshot 审阅副本完整摘要。
            "solver_sha256": solver_hash,  # solver 实际执行副本完整摘要。
            "matches_prepare_manifest": True,  # 两份当前摘要均已匹配 prepare manifest。
            "copies_identical": True,  # input_snapshot 与 solver 两份副本逐字节同源。
        })  # 完成当前依赖身份记录。
    require(seen_orders == set(range(1, EXPECTED_DEPENDENCY_COUNT + 1)), f"S10 依赖 order 未连续覆盖 1..11：{sorted(seen_orders)}")  # 十一项执行顺序必须无缺口完整闭合。
    return {  # 返回主输入双路径、双摘要及十一项来源完整性证据。
        "status": "PASSED",  # 主输入和全部依赖双副本已通过。
        "main_input_solver_path": MAIN_INPUT_PATH.relative_to(RUN_DIR).as_posix(),  # solver 实际执行主输入相对路径。
        "main_input_solver_sha256": main_solver_hash,  # solver 主输入完整摘要。
        "main_input_snapshot_path": MAIN_INPUT_SNAPSHOT_PATH.relative_to(RUN_DIR).as_posix(),  # input_snapshot 主输入相对路径。
        "main_input_snapshot_sha256": main_snapshot_hash,  # input_snapshot 主输入完整摘要。
        "main_input_copies_identical": True,  # 两份主输入已证明逐字节同源。
        "main_input_path": MAIN_INPUT_PATH.relative_to(RUN_DIR).as_posix(),  # 兼容既有消费者的主输入相对路径字段。
        "main_input_sha256": main_solver_hash,  # 兼容既有消费者的主输入摘要字段。
        "dependency_count": len(records),  # 已验证依赖记录数量。
        "dependency_orders": sorted(seen_orders),  # 已验证连续覆盖 1..11 的顺序列表。
        "dependencies": records,  # 十一项依赖双副本身份记录。
    }  # 完成来源完整性证据对象。


def validate_critical_results() -> dict[str, Any]:  # 无输入并返回八类关键二进制当前身份。
    """平衡 DB、静力 RST、模态 DB/RSTP/MODE/FULL、RDB 和 LDHI 均须唯一非空。"""  # 函数说明关键结果充分条件。
    paths = [  # 固定八个必须存在且非空的关键二进制结果。
        EQ_DB_PATH,  # LS2 平衡数据库。
        STATIC_RST_PATH,  # 合并静力结果文件。
        MODAL_DB_PATH,  # 模态数据库。
        MODAL_RSTP_PATH,  # 合并八十阶模态结果文件。
        MODAL_MODE_PATH,  # 合并模态特征向量文件。
        FULL_PATH,  # 合并完整矩阵文件。
        RDB_PATH,  # 原生重启数据库。
        LDHI_PATH,  # 原生载荷历史文件。
    ]  # 完成八个关键二进制路径列表。
    records: list[dict[str, Any]] = []  # 初始化关键结果记录。
    for path in paths:  # 逐文件检查存在、非空和当前摘要。
        require(path.is_file() and path.stat().st_size > 0, f"S10 关键结果缺失或为空：{path}")  # 非空是硬门禁。
        records.append({  # 保存当前关键结果文件身份。
            "path": path.relative_to(RUN_DIR).as_posix(),  # 关键文件在固定 run 内的相对路径。
            "length_bytes": path.stat().st_size,  # 关键文件完整字节数。
            "sha256": sha256_file(path),  # 关键文件完整原始字节摘要。
        })  # 完成当前关键结果身份记录。
    return {  # 返回八类关键结果摘要。
        "status": "PASSED",  # 八个关键二进制均已存在、非空并完成哈希。
        "critical_file_count": len(records),  # 已验证关键文件数量。
        "files": records,  # 八个关键文件的路径、字节数和摘要记录。
    }  # 完成关键结果摘要对象。


def collect_evidence() -> dict[str, Any]:  # 无输入并返回全部只读门禁证据。
    """先验证 prepare 与 LINK180，再读取主结果；本阶段绝不写 run 文件。"""  # 函数说明零写入证据阶段。
    prepare = validate_prepare_roots()  # 固定 prepare/running 原件和 52 项账本。
    link180 = validate_link180_qa()  # 关闭 S10 自身 LINK180 正轴力硬门禁。
    binary_before = solver_binary_metadata()  # 记录证据收集前 solver 二进制元数据。
    main_out = validate_main_out()  # 核对主 OUT、ERR、stat 和完成标记。
    static = validate_static()  # 核对两步静力和 LS1 全历程。
    topology = validate_topology()  # 核对冻结拓扑。
    modal = validate_modal(static)  # 核对 80 阶、结果集、向量和有效质量。
    sene = validate_sene()  # 核对 80×16 六截面能量。
    dependencies = validate_dependencies(prepare)  # 核对主输入和 11 项依赖。
    critical = validate_critical_results()  # 核对八类关键二进制。
    gate_text = read_mixed_text(GATE_STATUS_PATH).strip()  # 读取 solver 原生外部 QA 状态。
    require(gate_text == "STATUS=SOLVER_EXPORT_COMPLETED PHASE=EXTERNAL_QA_REQUIRED", "S10 solver gate 原生状态不符合预期。")  # 原始状态必须证明导出完成且等待本 finalizer。
    binary_after = solver_binary_metadata()  # 记录全部只读门禁后的二进制元数据。
    require(binary_after == binary_before, "S10 只读证据收集期间 solver 二进制元数据发生变化。")  # 并发写入即拒绝。
    return {  # 返回全部只读门禁形成的完整证据汇总。
        "prepare": prepare,  # prepare/running 起点原件、摘要和锁文件证据。
        "link180": link180,  # S10 LINK180 POST1-only 正轴力与源完整性证据。
        "binary_metadata": binary_before,  # 证据收集前后保持一致的 solver 二进制元数据。
        "main_out": main_out,  # 主 OUT、四 ERR 和四 stat 执行证据。
        "static": static,  # 两步静力、LS1 全历程、质量和反力证据。
        "topology": topology,  # 冻结拓扑数量证据。
        "modal": modal,  # 八十阶模态属性、结果集、向量和有效质量证据。
        "sene": sene,  # 八十阶六截面模态能量证据。
        "dependencies": dependencies,  # 主输入和十一项依赖双副本来源证据。
        "critical_results": critical,  # 八个关键二进制结果身份。
        "solver_gate_status": gate_text,  # solver 原生等待外部 QA 状态文本。
        "finalizer_sha256": sha256_file(SCRIPT_PATH),  # 当前实际 finalizer 源码摘要。
        "helper_sha256": sha256_file(HELPER_PATH),  # 当前实际通用 helper 源码摘要。
    }  # 完成全部证据汇总对象。


def documented_limitations(evidence: dict[str, Any]) -> list[dict[str, str]]:  # 输入证据并返回固定结论范围边界。
    """限制不否定本次 S10 因果试算数值闭合，但禁止把它冒充生产模型或严格 MAC 对齐。"""  # 函数说明终态语义。
    modal = evidence["modal"]  # 提取模态摘要供动态数值说明。
    limitations = [  # 按稳定顺序构造五项最终结论范围限制。
        {  # 第一项保留 legacy 约束方程大变形适用性边界。
            "id": "LEGACY_CONSTRAINT_EQUATION_LARGE_DEFLECTION",  # 机器稳定标识对应 W1。
            "description": "legacy 约束方程在大变形下的适用性 warning 仍存在；本次未改变连接运动学。",  # 说明本次试算没有消除既有运动学边界。
        },  # 完成第一项限制。
        {  # 第二项保留矩阵高系数比尺度边界。
            "id": "HIGH_COEFFICIENT_RATIO",  # 机器稳定标识对应 W2。
            "description": "矩阵系数比超过 1E8；虽无负/零主元且全部收敛，仍保留尺度病态边界。",  # 说明收敛不等于尺度风险消失。
        },  # 完成第二项限制。
        {  # 第三项披露八十阶累计有效质量范围。
            "id": "EFFECTIVE_MASS_X_80_BELOW_90_PERCENT",  # 机器稳定标识对应未采用的 90% 外部标准。
            "description": f"固定 80 阶合同未设置 90% 有效质量门槛；当前 X/Y/Z 累计比例分别为 {modal['effective_mass_ratio_80_modes']['x']:.6%}/{modal['effective_mass_ratio_80_modes']['y']:.6%}/{modal['effective_mass_ratio_80_modes']['z']:.6%}，若另行采用 90% 标准则不满足。",  # 动态写入三向累计比例并明确合同边界。
        },  # 完成第三项限制。
        {  # 第四项要求近重根跨模型比较使用子空间方法。
            "id": "NEAR_REPEATED_MODE_SUBSPACE",  # 机器稳定标识对应最小相邻频差风险。
            "description": f"最小相邻频差为 {modal['minimum_adjacent_gap_hz']:.16g} Hz，对应 {modal['minimum_gap_mode_pair'][0]}–{modal['minimum_gap_mode_pair'][1]} 阶；跨模型比较应按近重根子空间处理。",  # 动态写入最小频差和对应阶次。
        },  # 完成第四项限制。
        {  # 第五项维持严格报告 MAC 和目标物理映射的硬源证阻断。
            "id": "STRICT_REPORT_MAC_SOURCE_UNAVAILABLE",  # 机器稳定标识对应原始全节点双精度向量缺失。
            "description": "用户确认报告原始全节点双精度模态向量无法取得；严格 MAC 与 14 目标一一物理映射保持 HARD_SOURCE_EVIDENCE_BLOCK，不得按频率或阶次强配。",  # 明确禁止无源证的阶次强配。
        },  # 完成第五项限制。
    ]  # 完成稳定顺序的五项限制列表。
    return limitations  # 返回最终结论范围限制。


def make_warning_markdown(evidence: dict[str, Any]) -> str:  # 输入证据并返回五条 warning 的逐项处置 Markdown。
    """每条记录给出 OUT 行号、识别片段、处置和是否形成 legacy 限制。"""  # 函数说明文档覆盖。
    lines = [  # 构造 warning 处置 Markdown 的标题和计数说明。
        "# S10 主 OUT 警告逐项处置",  # 文档一级标题。
        "",  # 标题后的 Markdown 空行。
        "主 OUT 实际出现 5 个 `*** WARNING ***` 标记；退出摘要先记录 4 条，摘要之后追加 1 条 elapsed/CPU 性能 warning。两种计数口径一致，未处置警告数为 0。",  # 解释实际标题数与退出摘要数的差异。
        "",  # 计数说明后的 Markdown 空行。
    ]  # 完成文档起始行。
    titles = [  # 定义与五条 warning 顺序一一对应的可读标题。
        "约束方程与大变形",  # W1 可读标题。
        "矩阵系数比超过 1E8",  # W2 可读标题。
        "LS1 参考力矩阈值",  # W3 可读标题。
        "LS2 参考力矩阈值",  # W4 可读标题。
        "退出后资源性能提示",  # W5 可读标题。
    ]  # 完成五条可读标题列表。
    for index, record in enumerate(evidence["main_out"]["records"]):  # 按主 OUT 原顺序写出五个小节。
        lines.extend([  # 写入当前机器 warning 记录对应的 Markdown 小节。
            f"## W{index + 1}：{titles[index]}",  # 当前 warning 二级标题。
            "",  # 二级标题后的 Markdown 空行。
            f"- OUT 行：{record['out_line']}。",  # 当前 warning 在主 OUT 中的一基标题行号。
            f"- 识别片段：`{record['recognition_fragment']}`。",  # 当前 warning 的唯一规范化识别片段。
            f"- 处置：{record['disposition']}",  # 当前 warning 工程处置文本。
            f"- 状态：`DISPOSED`；形成 legacy 限制：`{str(record['contributes_legacy_limitation']).lower()}`。",  # 当前 warning 处置状态和限制贡献布尔值。
            "",  # 当前 warning 小节后的 Markdown 空行。
        ])  # 完成当前 warning 小节。
    lines.extend([  # 追加五条 warning 的最终状态口径。
        "## 终态口径",  # 最终状态说明二级标题。
        "",  # 二级标题后的 Markdown 空行。
        "五条 warning 均不构成本次数值门禁失败；W1/W2 保留为工程适用性边界，W3/W4 已由后续收敛和完整能量门禁处置，W5 仅反映资源性能。根状态因此采用 `PASS_WITH_LEGACY_LIMITATIONS`。",  # 解释为何最终状态是带 legacy 限制的通过。
        "",  # 文档末尾保留一个空行。
    ])  # 完成最终状态口径。
    return "\n".join(lines)  # 返回末尾含 LF 的 Markdown。


def make_field_dictionary() -> str:  # 无输入并返回最终 JSON、CSV、状态和账本字段说明。
    """不可注释机器格式的用途、单位、布尔含义和结论范围集中记录在相邻 Markdown。"""  # 函数说明配套文档角色。
    lines = [  # 逐行构造固定字段字典，保证每个 Markdown 字面行都有中文源码说明。
        "# S10 最终执行字段字典\n",  # 文档一级标题。
        "\n",  # 一级标题后的空行。
        "## 状态\n",  # 状态字段说明二级标题。
        "\n",  # 状态标题后的空行。
        "- `execution_status=EXECUTED`：DMP4 / INTELMPI 主作业已真实完成。\n",  # 解释执行状态字段。
        "- `qa_status=PASSED_FOR_S10_SECTION_SHEAR_TRIAL`：本次 SEC61..66 剪切因果试算的数值与完整性门禁通过。\n",  # 解释 QA 状态字段。
        "- `valid_for_s10_section_shear_trial=true`：结果可用于本次单变量试算判断。\n",  # 解释试算用途授权布尔值。
        "- `valid_for_production_model=false`：S10 是因果变体，不自动替代生产模型。\n",  # 解释生产模型用途布尔值。
        "- `next_action=NONE_FOR_THIS_RUN`：本 run 不需要再次启动。\n",  # 解释当前 run 后续动作字段。
        "- `pipeline_next_action=REBUILD_C10_FROM_FINAL_S10_BOUNDARY`：后续纯连接 C10 必须从本次最终边界重新准备。\n",  # 解释流水线后续动作字段。
        "\n",  # 状态章节后的空行。
        "## 数值单位\n",  # 数值单位二级标题。
        "\n",  # 单位标题后的空行。
        "- 静力 SENE/STEN：N·mm。\n",  # 说明静力能量字段单位。
        "- 质量：tonne。\n",  # 说明质量字段单位。
        "- 反力和 LINK180 轴力：N。\n",  # 说明反力与轴力字段单位。
        "- 频率：Hz。\n",  # 说明频率字段单位。
        "- 有效质量比例、SENE 比例和误差比例：无量纲。\n",  # 说明各类比例字段无量纲。
        "\n",  # 单位章节后的空行。
        "## 模态与向量\n",  # 模态与向量二级标题。
        "\n",  # 模态标题后的空行。
        "- `modal.property_rows=80`、`set_count=80`、`requested/available/exported=80` 共同证明 80 阶闭合。\n",  # 解释八十阶闭合字段组合。
        "- 两类向量各 80 份，每份含 91,407 个实际求解自由度节点。\n",  # 解释向量文件数量和每份节点行数。
        "- 拓扑节点与向量节点差 17,679，恰等于 TYPE70 第三方向节点数；这些方向节点没有独立求解自由度，不属于漏导出。\n",  # 解释节点数量差的物理来源。
        "- 固定 80 阶合同没有设置 90% 累计有效质量硬门槛；实际 X/Y/Z 比例只作为范围限制报告。\n",  # 解释有效质量比例的合同边界。
        "\n",  # 模态章节后的空行。
        "## 六截面 SENE\n",  # 六截面能量二级标题。
        "\n",  # 六截面标题后的空行。
        "- `s10_section_modal_sene.csv` 每行 16 列：阶次、全模型 SENE、SEC61..66 六组 SENE、六组占比、六组和、六组和占比。\n",  # 解释十六列 CSV 布局。
        "- 总 SENE 必须正，分量 SENE 非负，比例在 `[0,1]`，三类恒等式误差不超过 `1E-12`。\n",  # 解释能量物理与恒等式门禁。
        "\n",  # 六截面章节后的空行。
        "## LINK180 POSTONLY\n",  # LINK180 审计二级标题。
        "\n",  # LINK180 标题后的空行。
        "- S10 不能复用 A10 轴力结论；`S10_LINK180_POSTONLY_*/qa_summary.json` 直接读取 S10 的 LS2/time=1.001。\n",  # 解释轴力证据必须来自本次 S10。
        "- 73,692 个 TYPE4 元素必须全部唯一且轴力严格为正。\n",  # 解释 LINK180 覆盖和正轴力硬门禁。
        "- 平衡 DB 和静力 RST 在 POST1-only 前后以及 finalizer 当前时点的 SHA-256 必须一致。\n",  # 解释只读源完整性门禁。
        "\n",  # LINK180 章节后的空行。
        "## 谱系与账本\n",  # 谱系与账本二级标题。
        "\n",  # 谱系标题后的空行。
        "- prepare 根状态、manifest、结果说明、52 项 prepare 账本和 running 回执均原样归档到 `lineage/`。\n",  # 解释准备期和运行中原件归档范围。
        "- `solver/` 在 finalizer 中永久只读；二进制大小和 `mtime_ns` 在证据收集、写入和全账本哈希前后必须一致。\n",  # 解释 solver 只读与二进制竞态门禁。
        "- `artifact_hashes.sha256` 覆盖 run 下除自身外全部普通文件，包括 solver 原生文件、160 份向量、LINK180 审计包、最终 QA、lineage 和编排器快照。\n",  # 解释最终账本覆盖范围。
        "- 账本按设计排除自身，避免自引用悖论；`launch_command.txt` 仅作为 prepare-time 历史命令证据。\n",  # 解释自排除设计与历史命令角色。
        "\n",  # 谱系章节后的空行。
        "## 结论范围\n",  # 结论范围二级标题。
        "\n",  # 结论标题后的空行。
        "- 报告原始全节点双精度模态向量不可得，严格 MAC 维持 `HARD_SOURCE_EVIDENCE_BLOCK`。\n",  # 解释严格 MAC 硬源证阻断。
        "- 近重根模态跨模型比较必须采用子空间方法，不能按阶次强配。\n",  # 解释近重根跨模型比较约束。
    ]  # 完成字段字典全部 Markdown 行。
    return "".join(lines)  # 按原顺序无分隔拼接并保留原有末尾 LF。


def build_postrun_gate(evidence: dict[str, Any], generated_utc: str) -> dict[str, Any]:  # 输入全证据和 UTC 时间并返回机器门禁对象。
    """对象只在全部硬门禁已通过后构造，checks 均为可由原始文件复现的真值。"""  # 函数说明构造时序。
    checks = {  # 汇总全部已经由原始证据复现的硬门禁真值。
        "main_out_run_completed": True,  # 主 OUT 已证明 RUN COMPLETED 和 NOSAVE。
        "main_out_zero_errors_and_fatals": True,  # 主 OUT 与四 ERR 的 error/fatal 均为零。
        "main_out_zero_negative_and_zero_pivots": True,  # 主 OUT 与四 ERR 的负/零主元诊断均为零。
        "all_five_warnings_disposed": True,  # 五条预期 warning 均已唯一识别并逐项处置。
        "four_rank_stats_mode_80": True,  # 四个 DMP rank stat 均闭合到 Mode 80。
        "ls1_and_ls2_converged": True,  # 两个静力载荷步均已收敛。
        "ls1_history_20_rows_and_peak_passed": True,  # LS1 二十行全历程及峰值门禁已通过。
        "mass_and_reaction_closed": True,  # 总质量与竖向反力误差均在冻结容差内。
        "topology_counts_match": True,  # 节点、单元及 TYPE 数量均匹配冻结拓扑。
        "modal_properties_and_sets_80": True,  # 模态属性和 RSTP 结果集均完整覆盖八十阶。
        "modal_vectors_80_plus_80_structurally_complete": True,  # 八十份位移和八十份转角向量结构完整。
        "sene_80_by_16_passed": True,  # 八十乘十六六截面能量表全部门禁通过。
        "link180_73692_all_positive": True,  # 73,692 个 LINK180 全覆盖且轴力严格为正。
        "link180_postonly_sources_current": True,  # LINK180 POST1-only 源 DB/RST 前后及当前身份一致。
        "prepare_ledger_52_entries_current": True,  # prepare 52 项账本当前仍逐项匹配。
        "eleven_dependencies_current": True,  # 主输入及十一项依赖双副本当前仍同源。
        "critical_results_nonempty_and_hashed": True,  # 八个关键二进制均非空并完成哈希。
        "solver_binary_metadata_unchanged": True,  # 全部只读证据收集前后 solver 二进制元数据不变。
    }  # 完成全部硬门禁真值对象。
    return {  # 返回完整机器门禁及全部可追溯证据入口。
        "schema_version": 1,  # 最终 postrun gate 机器契约版本为第一版。
        "run_id": "S10_SECTION_SHEAR",  # 固定试算类型标识。
        "run_name": RUN_NAME,  # 固定正式运行目录名。
        "jobname": JOBNAME,  # 固定 MAPDL 作业名。
        "generated_utc": generated_utc,  # 统一最终化 UTC 时间。
        "execution_status": EXECUTION_STATUS,  # 主 MAPDL 作业真实执行状态。
        "qa_status": QA_STATUS,  # 本次 S10 截面剪切试算 QA 状态。
        "gate_status": "PASSED",  # 全部硬门禁通过后的机器状态。
        "final_status": FINAL_STATUS,  # 带 legacy 限制的最终状态。
        "valid_for_s10_section_shear_trial": True,  # 授权本次单变量截面剪切试算用途。
        "valid_for_production_model": False,  # 明确不自动替代生产模型。
        "checks": checks,  # 全部可由原始文件复现的硬门禁真值。
        "main_out": evidence["main_out"],  # 主 OUT、四 ERR 和四 stat 证据。
        "static": evidence["static"],  # 两步静力、质量和反力证据。
        "topology": evidence["topology"],  # 冻结拓扑数量证据。
        "modal": evidence["modal"],  # 八十阶模态与向量证据。
        "section_modal_sene": evidence["sene"],  # 六截面模态能量证据。
        "link180": evidence["link180"],  # LINK180 正轴力与源完整性证据。
        "dependencies": evidence["dependencies"],  # 主输入和十一项依赖来源证据。
        "critical_results": evidence["critical_results"],  # 八个关键二进制身份。
        "solver_gate_original": {  # 保存 solver 原生等待外部 QA 状态的来源身份。
            "path": GATE_STATUS_PATH.relative_to(RUN_DIR).as_posix(),  # solver gate 相对路径。
            "value": evidence["solver_gate_status"],  # solver gate 原始状态文本。
            "sha256": sha256_file(GATE_STATUS_PATH),  # solver gate 完整摘要。
        },  # 完成 solver 原生状态身份。
        "prepare_lineage": {  # 保存 prepare 与 running 六份原件的归档路径和原始摘要。
            "status_archive": PREPARE_STATUS_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # prepare 根状态归档相对路径。
            "status_original_sha256": evidence["prepare"]["status_sha256"],  # prepare 根状态原始摘要。
            "manifest_archive": PREPARE_MANIFEST_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # prepare manifest 归档相对路径。
            "manifest_original_sha256": evidence["prepare"]["manifest_sha256"],  # prepare manifest 原始摘要。
            "result_packet_archive": PREPARE_RESULT_PACKET_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # prepare 结果说明归档相对路径。
            "result_packet_original_sha256": evidence["prepare"]["result_packet_sha256"],  # prepare 结果说明原始摘要。
            "prepare_ledger_archive": PREPARE_LEDGER_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # prepare 账本归档相对路径。
            "prepare_ledger_original_sha256": evidence["prepare"]["prepare_ledger_sha256"],  # prepare 账本原始摘要。
            "running_launch_archive": RUNNING_LAUNCH_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # running 启动回执归档相对路径。
            "running_launch_original_sha256": evidence["prepare"]["runtime_launch_sha256"],  # running 启动回执原始摘要。
            "running_status_archive": RUNNING_STATUS_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # running 状态说明归档相对路径。
            "running_status_original_sha256": evidence["prepare"]["runtime_status_sha256"],  # running 状态说明原始摘要。
        },  # 完成 prepare/running 谱系对象。
        "execution_policy": {  # 记录真实主作业并行和资源门禁策略。
            "parallel_mode": "DMP",  # 主作业采用分布式内存并行。
            "processes": EXPECTED_DMP_RANKS,  # 主作业固定使用四个 DMP rank。
            "mpi": "INTELMPI",  # 主作业固定使用 Intel MPI。
            "memory_gate_overridden_by_user": True,  # 用户明确覆盖准备期内存门禁。
            "disk_gate_passed_at_launch": True,  # 启动时磁盘门禁已通过。
        },  # 完成执行策略对象。
        "stale_lock_files": evidence["prepare"]["stale_locks"],  # 已确认主进程退出后的零字节残留锁列表。
        "documented_limitations": documented_limitations(evidence),  # 五项最终结论范围限制。
        "target_physical_mapping_status": "HARD_SOURCE_EVIDENCE_BLOCK",  # 目标一一物理映射维持硬源证阻断。
        "hard_order_target_pairing_claimed": False,  # 明确未按频率或阶次强制配对目标。
        "next_action": "NONE_FOR_THIS_RUN",  # 当前 run 不需要再次启动或修复。
        "pipeline_next_action": "REBUILD_C10_FROM_FINAL_S10_BOUNDARY",  # 后续 C10 必须从最终 S10 边界重建。
        "artifact_ledger": {  # 描述最终全 run 账本路径和覆盖策略。
            "path": LEDGER_PATH.relative_to(RUN_DIR).as_posix(),  # 最终账本相对路径。
            "coverage": "ALL_REGULAR_FILES_UNDER_RUN_EXCEPT_LEDGER_ITSELF",  # 账本覆盖除自身外全部普通文件。
            "self_excluded": True,  # 账本按设计排除自身避免自引用。
        },  # 完成最终账本说明对象。
        "orchestrator_integrity": {  # 绑定实际 finalizer 和 helper 的源码摘要及快照。
            "finalizer_sha256": evidence["finalizer_sha256"],  # 当前实际 finalizer 源码摘要。
            "helper_sha256": evidence["helper_sha256"],  # 当前实际通用 helper 源码摘要。
            "finalizer_snapshot": FINALIZER_SNAPSHOT_PATH.relative_to(RUN_DIR).as_posix(),  # finalizer 包内快照相对路径。
            "helper_snapshot": HELPER_SNAPSHOT_PATH.relative_to(RUN_DIR).as_posix(),  # helper 包内快照相对路径。
        },  # 完成编排器源码完整性对象。
    }  # 完成 postrun gate 机器对象。


def build_status(evidence: dict[str, Any], generated_utc: str) -> dict[str, Any]:  # 输入证据和时间并返回新的根 S10_status。
    """深复制 prepare 根状态以保留父 run、物理变更、请求阶数和创建时间，再覆盖真实终态字段。"""  # 函数说明历史身份保留和终态更新边界。
    status = copy.deepcopy(evidence["prepare"]["status"])  # 保留 parent_run、effective_input_parent、physical_change_family、changed_section_count、modes_requested 和 created_at_utc 等准备期身份。
    status.update({  # 覆盖所有执行与 QA 终态，同时不删除 prepare 中未冲突的稳定身份字段。
        "schema_version": 2,  # 根状态执行终态契约版本升级为第二版。
        "run_id": "S10_SECTION_SHEAR",  # 固定试算类型标识。
        "run_name": RUN_NAME,  # 固定正式运行目录名。
        "jobname": JOBNAME,  # 固定 MAPDL 作业名。
        "model_line": "A30_AXES_PLUS_ASEC_SHEAR_ONLY",  # 固定模型线表示仅改变截面剪切属性。
        "status": FINAL_STATUS,  # 带 legacy 限制的最终状态。
        "execution_status": EXECUTION_STATUS,  # 主 MAPDL 作业真实执行状态。
        "qa_status": QA_STATUS,  # 本次 S10 截面剪切试算 QA 状态。
        "prepare_status": EXPECTED_PREPARE_STATUS,  # 首次最终化前允许的 prepare 历史状态。
        "prepare_gate_passed": True,  # prepare 起点和 52 项账本已通过。
        "execution_attempted": True,  # 主作业确已尝试执行。
        "process_started": True,  # 外部 MAPDL 进程确已启动。
        "mapdl_started": True,  # MAPDL 主作业确已开始。
        "postrun_gate_passed": True,  # 外部最终门禁已通过。
        "valid_for_s10_section_shear_trial": True,  # 授权本次单变量试算用途。
        "valid_for_production_model": False,  # 明确不自动替代生产模型。
        "memory_gate_overridden_by_user": True,  # 用户明确覆盖准备期内存门禁。
        "main_out_warning_markers": EXPECTED_WARNINGS,  # 主 OUT 实际五条 warning 标题数量。
        "main_out_errors": 0,  # 主 OUT error 标题数量为零。
        "negative_pivot_count": 0,  # 主 OUT 负主元诊断数量为零。
        "zero_pivot_count": 0,  # 主 OUT 零主元诊断数量为零。
        "modes_available": EXPECTED_MODES,  # 可用模态阶数为八十。
        "modes_exported": EXPECTED_MODES,  # 已导出模态阶数为八十。
        "displacement_vector_files": EXPECTED_MODES,  # 位移向量文件数量为八十。
        "rotation_vector_files": EXPECTED_MODES,  # 转角向量文件数量为八十。
        "sene_status": "PASSED_80_BY_16",  # 六截面八十乘十六能量表门禁状态。
        "link180_status": "PASSED_73692_ALL_POSITIVE",  # 73,692 个 LINK180 全正轴力门禁状态。
        "strict_mac_status": "HARD_SOURCE_EVIDENCE_BLOCK",  # 严格报告 MAC 维持硬源证阻断。
        "target_physical_mapping_closed": False,  # 十四目标一一物理映射尚未闭合。
        "documented_limitations": documented_limitations(evidence),  # 五项最终结论范围限制。
        "finalized_utc": generated_utc,  # 统一最终化 UTC 时间。
        "next_action": "NONE_FOR_THIS_RUN",  # 当前 run 不需要再次启动或修复。
        "pipeline_next_action": "REBUILD_C10_FROM_FINAL_S10_BOUNDARY",  # 后续 C10 必须从最终 S10 边界重建。
        "prepare_lineage": {  # 保存三份 prepare 核心原件归档入口。
            "status": PREPARE_STATUS_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # prepare 根状态归档相对路径。
            "manifest": PREPARE_MANIFEST_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # prepare manifest 归档相对路径。
            "artifact_ledger": PREPARE_LEDGER_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # prepare 52 项账本归档相对路径。
        },  # 完成 prepare 核心谱系入口。
        "postrun_gate": POSTRUN_GATE_PATH.relative_to(RUN_DIR).as_posix(),  # 最终机器门禁相对路径。
        "external_completion_qa": EXTERNAL_COMPLETION_QA_PATH.relative_to(RUN_DIR).as_posix(),  # 外部完成 QA 同源入口相对路径。
    })  # 完成根状态终态字段覆盖。
    return status  # 返回兼具完整准备谱系和真实执行结论的根状态。


def build_manifest(evidence: dict[str, Any], generated_utc: str) -> dict[str, Any]:  # 输入证据和时间并返回保留历史字段的新 manifest。
    """深复制 prepare manifest，更新执行事实并把资源快照明确标为 prepare-time 历史。"""  # 函数说明历史保留。
    manifest = copy.deepcopy(evidence["prepare"]["manifest"])  # 深复制 prepare manifest。
    manifest["schema_version"] = 2  # 根 manifest 升级为执行终态字段契约。
    manifest["status"] = FINAL_STATUS  # 更新最终状态。
    manifest["execution_status"] = EXECUTION_STATUS  # 记录真实执行。
    manifest["qa_status"] = QA_STATUS  # 记录试算 QA 通过。
    manifest["next_action"] = "NONE_FOR_THIS_RUN"  # 本 run 不再等待启动。
    manifest["pipeline_next_action"] = "REBUILD_C10_FROM_FINAL_S10_BOUNDARY"  # 记录后续 C10 动作。
    manifest["prepare_only"] = False  # 当前根 manifest 不再是 prepare-only。
    manifest["mapdl_execution_attempted"] = True  # 主作业确已尝试。
    manifest["process_started"] = True  # 外部 MAPDL 进程确已启动。
    manifest["mapdl_started"] = True  # 与根状态一致。
    manifest["valid_for_s10_section_shear_trial"] = True  # 授权本次因果试算用途。
    manifest["valid_for_production_model"] = False  # 不自动替代生产模型。
    manifest["prepare_state_archived"] = {  # 记录 prepare 核心原件归档位置和原始摘要。
        "status_path": PREPARE_STATUS_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # prepare 根状态归档相对路径。
        "status_sha256": evidence["prepare"]["status_sha256"],  # prepare 根状态原始摘要。
        "manifest_path": PREPARE_MANIFEST_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # prepare manifest 归档相对路径。
        "manifest_sha256": evidence["prepare"]["manifest_sha256"],  # prepare manifest 原始摘要。
        "result_packet_path": PREPARE_RESULT_PACKET_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # prepare 结果说明归档相对路径。
        "result_packet_sha256": evidence["prepare"]["result_packet_sha256"],  # prepare 结果说明原始摘要。
        "artifact_ledger_path": PREPARE_LEDGER_ARCHIVE.relative_to(RUN_DIR).as_posix(),  # prepare 52 项账本归档相对路径。
        "artifact_ledger_sha256": evidence["prepare"]["prepare_ledger_sha256"],  # prepare 账本原始摘要。
    }  # 完成 prepare 原件归档对象。
    manifest["actual_execution"] = {  # 补入真实 MAPDL 主作业执行摘要。
        "status": EXECUTION_STATUS,  # 主作业真实执行状态。
        "parallel_mode": "DMP",  # 主作业采用分布式内存并行。
        "processes": EXPECTED_DMP_RANKS,  # 主作业固定使用四个 DMP rank。
        "mpi": "INTELMPI",  # 主作业固定使用 Intel MPI。
        "main_out": MAIN_OUT_PATH.relative_to(RUN_DIR).as_posix(),  # 主 OUT 相对路径。
        "main_out_sha256": evidence["main_out"]["sha256"],  # 主 OUT 已验证摘要。
        "warning_markers": EXPECTED_WARNINGS,  # 主 OUT 实际 warning 标题数量。
        "summary_warning_count": EXPECTED_SUMMARY_WARNINGS,  # MAPDL 退出摘要 warning 数量。
        "errors": 0,  # 主 OUT error 标题数量。
        "fatals": 0,  # 主 OUT fatal 标题数量。
        "negative_pivots": 0,  # 主 OUT negative pivot 数量。
        "zero_pivots": 0,  # 主 OUT zero pivot 数量。
        "finalized_utc": generated_utc,  # 统一最终化 UTC 时间。
    }  # 完成真实执行摘要。
    manifest["postrun_finalization"] = {  # 补入最终 QA、限制、账本和源码快照入口。
        "gate_status": "PASSED",  # 外部最终门禁状态。
        "final_status": FINAL_STATUS,  # 带 legacy 限制的最终状态。
        "qa_status": QA_STATUS,  # 本次 S10 截面剪切试算 QA 状态。
        "postrun_gate": POSTRUN_GATE_PATH.relative_to(RUN_DIR).as_posix(),  # 最终机器门禁相对路径。
        "external_completion_qa": EXTERNAL_COMPLETION_QA_PATH.relative_to(RUN_DIR).as_posix(),  # 外部完成 QA 同源入口相对路径。
        "warning_disposition": WARNING_DISPOSITION_PATH.relative_to(RUN_DIR).as_posix(),  # 五条 warning 处置文档相对路径。
        "field_dictionary": EXECUTION_FIELDS_PATH.relative_to(RUN_DIR).as_posix(),  # 机器字段说明文档相对路径。
        "link180_qa": evidence["link180"]["qa_path"],  # S10 LINK180 机器 QA 相对路径。
        "modal_properties": EXPECTED_MODES,  # 已验证模态属性阶数。
        "displacement_vectors": EXPECTED_MODES,  # 已验证位移向量文件数量。
        "rotation_vectors": EXPECTED_MODES,  # 已验证转角向量文件数量。
        "section_sene_rows": EXPECTED_MODES,  # 已验证六截面能量表行数。
        "hard_order_target_pairing_claimed": False,  # 明确未按频率或阶次强配目标。
        "target_physical_mapping_status": "HARD_SOURCE_EVIDENCE_BLOCK",  # 目标一一物理映射维持硬源证阻断。
        "artifact_ledger": LEDGER_PATH.relative_to(RUN_DIR).as_posix(),  # 最终全 run 账本相对路径。
        "artifact_ledger_self_excluded": True,  # 最终账本按设计排除自身。
        "finalizer_snapshot": FINALIZER_SNAPSHOT_PATH.relative_to(RUN_DIR).as_posix(),  # finalizer 源码快照相对路径。
        "finalizer_sha256": evidence["finalizer_sha256"],  # 当前实际 finalizer 源码摘要。
        "helper_snapshot": HELPER_SNAPSHOT_PATH.relative_to(RUN_DIR).as_posix(),  # helper 源码快照相对路径。
        "helper_sha256": evidence["helper_sha256"],  # 当前实际 helper 源码摘要。
    }  # 完成 postrun finalization 对象。
    manifest["documented_limitations"] = documented_limitations(evidence)  # 在顶层直接披露结论边界。
    resources = manifest.get("resources")  # 读取 prepare 资源对象。
    if isinstance(resources, dict):  # 仅在资源对象结构合法时更新历史角色。
        for value in resources.values():  # 遍历 memory、disk 和其他资源项。
            if isinstance(value, dict):  # 仅对字典资源项写历史角色。
                value["snapshot_role"] = "PREPARE_TIME_HISTORICAL_ONLY"  # 防止把准备瞬间资源误当最终状态。
                if "execution_attempted" in value:  # 仅在原字段存在时更新执行事实。
                    value["execution_attempted"] = True  # 记录外部执行已经发生。
    return manifest  # 返回保留全部准备审计的新 manifest。


def build_runtime_launch(evidence: dict[str, Any], generated_utc: str) -> dict[str, Any]:  # 输入证据和时间并返回完成态运行回执。
    """保留启动字段并补入正常退出、QA 和账本待完成后的终态。"""  # 函数说明运行回执更新。
    runtime = copy.deepcopy(evidence["prepare"]["runtime_launch"])  # 深复制启动时回执。
    runtime["status"] = "COMPLETED_FINALIZED"  # 更新运行生命周期终态。
    runtime["completed_at_utc"] = generated_utc  # 记录最终化时间。
    runtime["mapdl_exit_status"] = "RUN_COMPLETED_ZERO_ERRORS"  # 记录 MAPDL 正常退出。
    runtime["warning_markers"] = EXPECTED_WARNINGS  # 记录五条已处置 warning。
    runtime["error_markers"] = 0  # 记录零错误。
    runtime["modes_available"] = EXPECTED_MODES  # 记录 80 阶可用。
    runtime["modes_exported"] = EXPECTED_MODES  # 记录 80 阶导出。
    runtime["link180_nonpositive_count"] = 0  # 记录 LINK180 全正。
    runtime["artifact_ledger_pending_finalization"] = False  # 最终账本将在同一事务最后写入。
    runtime["postrun_gate_passed"] = True  # 记录外部 QA 通过。
    runtime["postrun_gate"] = POSTRUN_GATE_PATH.relative_to(RUN_DIR).as_posix()  # 绑定机器门禁入口。
    return runtime  # 返回完成态运行回执。


def make_runtime_status(generated_utc: str) -> str:  # 输入最终化时间并返回用户可读运行终态说明。
    """运行说明区分主求解完成、外部 QA、LINK180 和最终账本状态。"""  # 函数说明文档用途。
    lines = [  # 逐行构造运行终态 Markdown，保持原文本和末尾 LF 不变。
        "# S10 运行终态\n",  # 文档一级标题。
        "\n",  # 一级标题后的空行。
        "- 状态：`COMPLETED_FINALIZED`。\n",  # 说明运行生命周期终态。
        f"- 作业：`{JOBNAME}`，DMP4 / INTELMPI。\n",  # 说明固定作业名和并行配置。
        "- 主求解：`RUN COMPLETED`，5 条 warning 已处置，0 error、0 fatal、0 negative/zero pivot。\n",  # 汇总主求解完成和诊断计数。
        "- 静力：LS1/LS2 收敛，20 条 LS1 全历程能量、质量和反力门禁通过。\n",  # 汇总静力门禁。
        "- 模态：80 个特征值、80 个结果集、80 份位移向量、80 份转角向量全部闭合。\n",  # 汇总模态和向量闭合。
        "- 六截面能量：80×16 CSV 数值和恒等式门禁通过。\n",  # 汇总六截面能量门禁。
        "- LINK180：S10 自身 POST1-only 复核 73,692 个元素全部正拉力，源 DB/RST 前后不变。\n",  # 汇总 LINK180 轴力和源完整性。
        "- 适用范围：本次截面剪切因果试算可用；不自动替代生产模型。\n",  # 说明结果适用范围。
        "- 严格 MAC：报告原始全节点向量不可得，维持 `HARD_SOURCE_EVIDENCE_BLOCK`。\n",  # 说明严格 MAC 硬源证阻断。
        f"- 最终化时间：`{generated_utc}`。\n",  # 写入统一最终化 UTC 时间。
    ]  # 完成运行终态 Markdown 行。
    return "".join(lines)  # 返回与原多行字符串逐字节等价且带末尾 LF 的文本。


def make_result_packet(evidence: dict[str, Any], generated_utc: str) -> str:  # 输入证据和时间并返回最终用户结果包。
    """以结论优先方式汇总执行、静力、模态、能量、轴力和限制。"""  # 函数说明用户入口。
    static = evidence["static"]  # 提取静力摘要。
    modal = evidence["modal"]  # 提取模态摘要。
    link180 = evidence["link180"]  # 提取轴力摘要。
    lines = [  # 逐行构造最终用户结果包，保持原文本、动态格式和末尾 LF 不变。
        "# S10 截面剪切单变量正式执行结果\n",  # 文档一级标题。
        "\n",  # 一级标题后的空行。
        f"- 最终状态：`{FINAL_STATUS}`；QA：`{QA_STATUS}`；最终化时间：`{generated_utc}`。\n",  # 汇总最终状态、QA 和统一时间。
        "- MAPDL：DMP4 / INTELMPI 已真实完成；主 OUT 为 0 ERROR、0 FATAL、0 negative/zero pivot。\n",  # 汇总主作业执行与硬诊断。
        "- warning：实际 5 条，摘要计 4 条且退出后追加 1 条性能 warning；全部已在 `qa/warning_disposition.md` 处置。\n",  # 解释 warning 双计数口径和处置入口。
        f"- 静力：LS1/LS2 均收敛；质量绝对误差 {static['mass_abs_error_tonne']:.16g} tonne；反力相对误差 {static['reaction_relative_error']:.16g}。\n",  # 写入质量和反力实测误差。
        f"- LS1 全历程：20 个连续子步；峰值 `|STEN/SENE|={static['ls1_history_peak_abs_sten_over_sene']:.16g}`。\n",  # 写入 LS1 全历程稳定化能比例峰值。
        f"- 模态：80 行属性、80 个 RSTP 结果集、80 份位移向量和 80 份转角向量；频率范围 {modal['frequency_first_hz']:.16g}–{modal['frequency_last_hz']:.16g} Hz。\n",  # 写入八十阶频率范围和完整性。
        f"- 有效质量：80 阶累计 X/Y/Z 比例为 {modal['effective_mass_ratio_80_modes']['x']:.6%}/{modal['effective_mass_ratio_80_modes']['y']:.6%}/{modal['effective_mass_ratio_80_modes']['z']:.6%}；固定 80 阶合同未设置 90% 硬门槛。\n",  # 写入三向累计有效质量比例及合同边界。
        "- 六截面 SENE：80×16 表通过；六组元素合计 17,679，与 TYPE70 完全一致。\n",  # 汇总六截面能量和元素数量闭合。
        f"- LINK180：{link180['actual_count']} 个 TYPE4 全覆盖，非正轴力 0，最小轴力 {link180['minimum_force_n']:.16g} N。\n",  # 写入 LINK180 覆盖数量和最小轴力。
        "- 源完整性：LINK180 POST1-only 前后及 finalizer 当前时点的平衡 DB/RST SHA-256 一致。\n",  # 汇总 LINK180 源完整性。
        "- prepare 与 running 原件：状态、manifest、结果说明、52 项账本和启动回执已原样归档到 `lineage/`。\n",  # 汇总准备期和运行中原件归档。
        "- 最终全 run 账本：`artifact_hashes.sha256` 覆盖除自身外全部普通文件。\n",  # 说明最终账本覆盖范围。
        "\n",  # 结果摘要与限制章节之间的空行。
        "## 适用范围和限制\n",  # 适用范围和限制二级标题。
        "\n",  # 二级标题后的空行。
        "1. S10 是 SEC61..66 截面剪切属性单变量因果试算，可用于本次试算判断，但不自动替代生产模型。\n",  # 第一项说明试算用途边界。
        "2. legacy 约束方程大变形 warning 与矩阵系数比超过 1E8 的尺度边界仍保留。\n",  # 第二项说明既有工程限制。
        f"3. 最小相邻频差为 {modal['minimum_adjacent_gap_hz']:.16g} Hz，对应 {modal['minimum_gap_mode_pair'][0]}–{modal['minimum_gap_mode_pair'][1]} 阶；跨模型比较必须采用近重根子空间方法。\n",  # 第三项写入近重根频差和阶次。
        "4. 报告原始全节点双精度模态向量不可得，严格 MAC 和 14 目标一一物理映射维持硬源证阻断，不得按频率或阶次强配。\n",  # 第四项说明严格 MAC 与目标映射阻断。
        "\n",  # 限制列表与权威入口之间的空行。
        "权威机器结论见 `qa/s10_external_completion_qa.json`；字段说明见 `qa/execution_field_dictionary.md`。\n",  # 指向权威机器结论和字段说明。
    ]  # 完成最终用户结果包全部 Markdown 行。
    return "".join(lines)  # 返回与原多行 f 字符串逐字节等价且带末尾 LF 的文本。


def atomic_write(path: Path, payload: bytes, allowed_targets: set[Path]) -> None:  # path 是目标文件，payload 是完整待写字节，allowed_targets 是精确白名单；成功无返回。
    """目标必须位于白名单和非 solver 的真实 run 路径；同目录临时文件 fsync 后原子 replace。"""  # 函数说明三个参数约束、写入副作用和 None 返回语义。
    require(path in allowed_targets, f"写目标不在 finalizer 白名单：{path}")  # 禁止任意 run 内路径写入。
    resolved_parent = path.parent.resolve()  # 规范化目标父目录。
    try:  # 尝试证明目标父目录经符号链接或 junction 解析后仍位于固定 run。
        resolved_parent.relative_to(RUN_DIR.resolve())  # 只有真实落点位于 run 内才允许继续。
    except ValueError as exc:  # 父目录重解析到 run 外时进入明确拒绝。
        raise RuntimeError(f"写目标父目录越出固定 S10 run：{path}") from exc  # 防止 qa、lineage 或快照目录 junction 把写入重定向到外部路径。
    require(not (resolved_parent == SOLVER_DIR.resolve() or SOLVER_DIR.resolve() in resolved_parent.parents), f"禁止写入 solver：{path}")  # solver 永久只读。
    temp_path = path.with_name(f".{path.name}.ultra_s10_finalize_{os.getpid()}.tmp")  # 在同目录构造当前 PID 唯一临时文件。
    require(not temp_path.exists(), f"原子写临时文件已存在：{temp_path}")  # 防止覆盖未知残留。
    try:  # 确保异常时清理本函数临时文件。
        with temp_path.open("xb") as stream:  # 排他创建临时文件。
            stream.write(payload)  # 写出完整字节。
            stream.flush()  # 刷新 Python 缓冲区。
            os.fsync(stream.fileno())  # 请求操作系统持久化当前文件。
        os.replace(temp_path, path)  # 同卷原子替换目标。
    finally:  # 无论成功失败都检查临时残留。
        if temp_path.exists():  # replace 失败时临时文件可能仍存在。
            temp_path.unlink()  # 仅删除当前 PID 固定命名临时文件。


def build_full_ledger(status_payload_override: bytes) -> tuple[bytes, int]:  # 输入尚未发布的最终 STATUS 完整字节并返回全 run 账本字节和条目数。
    """递归哈希除账本自身外全部文件；STATUS 使用最终 payload 摘要，并以前后全集元数据快照拒绝竞态。"""  # 函数说明状态最后提交与账本稳定性协议。
    require(isinstance(status_payload_override, bytes) and bool(status_payload_override), "最终 STATUS override 必须是非空完整字节。")  # 防止空或错误类型 payload 进入权威账本。
    temp_files = sorted(path for path in RUN_DIR.rglob("*.tmp") if path.is_file())  # 枚举任何事务临时文件。
    require(not temp_files, f"构建最终账本前发现临时文件：{temp_files}")  # 临时文件不得进入正式集合。
    files = sorted((path for path in RUN_DIR.rglob("*") if path.is_file() and path != LEDGER_PATH), key=lambda path: path.relative_to(RUN_DIR).as_posix())  # 按 POSIX 相对路径稳定枚举。
    require(bool(files), "S10 run 没有可哈希文件。")  # 空 run 不允许封板。
    require(STATUS_PATH in files, "S10 根 STATUS 不在最终账本实际文件集合。")  # 状态最后发布仍要求同一路径已存在 prepare 原件并占据账本标签。
    initial_metadata: dict[Path, tuple[int, int]] = {}  # 初始化全部实文件在任何哈希开始前的大小和纳秒修改时间快照。
    for path in files:  # 先于逐文件哈希冻结全集元数据，避免后处理较晚文件时接受已经漂移的新版本。
        initial_stat = path.stat()  # 取得当前普通文件元数据。
        initial_metadata[path] = (initial_stat.st_size, initial_stat.st_mtime_ns)  # 保存当前文件起点版本。
    entries: list[str] = []  # 初始化账本行列表。
    print(f"S10 finalize: 开始哈希 {len(files)} 个文件，账本按设计只排除自身。", flush=True)  # 报告长哈希阶段。
    for index, path in enumerate(files, start=1):  # 逐文件流式哈希。
        before = path.stat()  # 记录哈希前大小和修改时间。
        require(initial_metadata[path] == (before.st_size, before.st_mtime_ns), f"最终账本文件在轮到哈希前已变化：{path}")  # 拒绝初始快照后、当前哈希前的漂移。
        digest = sha256_bytes(status_payload_override) if path == STATUS_PATH else sha256_file(path)  # STATUS 记录尚未发布的最终字节摘要，其他文件直接哈希当前只读内容。
        after = path.stat()  # 记录哈希后元数据。
        require(initial_metadata[path] == (after.st_size, after.st_mtime_ns), f"最终账本哈希期间文件变化：{path}")  # 当前文件哈希前后及相对全集起点必须完全稳定。
        relative = path.relative_to(RUN_DIR).as_posix()  # 生成稳定 POSIX 相对标签。
        require(not relative.startswith("/") and ".." not in Path(relative).parts, f"最终账本相对路径不安全：{relative}")  # 防止绝对或父级标签。
        entries.append(f"{digest}  {relative}")  # 保存规范双空格分隔行。
        if index % HASH_PROGRESS_INTERVAL == 0 or index == len(files):  # 每处理 25 个文件或到达最后一个文件时报告进度。
            print(f"S10 finalize: 哈希进度 {index}/{len(files)}。", flush=True)  # 保持长阶段可观测。
    require(len({line.split("  ", 1)[1] for line in entries}) == len(entries), "最终账本出现重复标签。")  # 标签必须唯一。
    final_files = sorted((path for path in RUN_DIR.rglob("*") if path.is_file() and path != LEDGER_PATH), key=lambda path: path.relative_to(RUN_DIR).as_posix())  # 全部哈希结束后重新枚举集合以捕获新增、删除或路径替换。
    require(final_files == files, "最终账本哈希期间实际文件集合发生变化。")  # 文件对象和稳定排序列表必须与起点逐项相同。
    final_metadata: dict[Path, tuple[int, int]] = {}  # 初始化全部实文件在哈希结束后的第二份元数据快照。
    for path in final_files:  # 逐项复核早先已经哈希的文件没有在后续长窗口内再次变化。
        final_stat = path.stat()  # 取得结束时大小和纳秒修改时间。
        final_metadata[path] = (final_stat.st_size, final_stat.st_mtime_ns)  # 保存结束时文件版本。
    require(final_metadata == initial_metadata, "最终账本哈希全程结束时文件大小或 mtime_ns 集合已漂移。")  # 拒绝早先文件哈希后的并发写入和同路径替换。
    return ("\n".join(entries) + "\n").encode("utf-8"), len(entries)  # 返回末尾含 LF 的账本字节和条目数。


def rollback(originals: dict[Path, bytes | None], written_paths: list[Path], allowed_targets: set[Path]) -> list[str]:  # 输入原始字节、实际成功写入顺序和白名单，并返回全部恢复错误说明。
    """只逆序恢复实际写过的目标；每项 best-effort 继续，最后由调用方聚合报告而不掩盖其余恢复机会。"""  # 函数说明可靠回滚顺序和错误策略。
    errors: list[str] = []  # 初始化不立即中断的恢复错误集合。
    restored: set[Path] = set()  # 初始化已处理路径集合，防止意外重复写入记录导致二次恢复。
    for path in reversed(written_paths):  # 严格按真实提交顺序的反序恢复，而不是依赖 set 的非确定顺序。
        if path in restored:  # 重复路径只恢复一次，保持最初事务前字节。
            continue  # 跳过已经处理的同一路径。
        restored.add(path)  # 登记当前路径已经进入恢复流程。
        try:  # 单项恢复失败不得阻止其余目标继续尝试。
            original = originals[path]  # 读取事务开始前捕获的完整原始字节或不存在标记。
            if original is None:  # None 表示事务前目标不存在。
                if path.exists():  # 仅当本事务已创建且当前仍存在时删除。
                    path.unlink()  # 删除白名单新建文件，使目录恢复到事务前集合。
                require(not path.exists(), f"回滚后新目标仍存在：{path}")  # 复核删除结果而不默认为成功。
            else:  # 既有目标必须恢复完整原始字节。
                atomic_write(path, original, allowed_targets)  # 使用同一原子写协议恢复旧字节。
                require(path.read_bytes() == original, f"回滚后原始字节不一致：{path}")  # 逐字节复核恢复结果。
        except Exception as exc:  # 捕获当前目标的任何删除、写入或复核错误。
            errors.append(f"{path}: {exc}")  # 保存路径级错误并继续恢复更早目标。
    return errors  # 返回全部恢复失败，空列表表示所有实际写入均已恢复。


def validate_already_finalized() -> dict[str, Any]:  # 无输入并对已发布 FINAL_STATUS 实施零 run 写入的严格幂等复核。
    """验证根状态、manifest、runtime、双 QA 和全量账本；全部一致时返回 ALREADY_FINALIZED_VERIFIED。"""  # 函数说明成功重入的只读契约。
    status = read_json(STATUS_PATH)  # 读取已发布根状态作为幂等提交标记。
    manifest = read_json(MANIFEST_PATH)  # 读取已完成根 manifest。
    runtime = read_json(RUNTIME_LAUNCH_PATH)  # 读取已完成运行回执。
    require(status.get("run_name") == RUN_NAME and status.get("jobname") == JOBNAME and status.get("status") == FINAL_STATUS, "已最终化根状态身份或 FINAL_STATUS 不一致。")  # 根提交标记必须绑定固定 run 和作业。
    require(status.get("execution_status") == EXECUTION_STATUS and status.get("qa_status") == QA_STATUS and status.get("postrun_gate_passed") is True, "已最终化根状态执行或 QA 字段不闭合。")  # 根状态必须仍声明真实执行和门禁通过。
    require(manifest.get("run_name") == RUN_NAME and manifest.get("jobname") == JOBNAME and manifest.get("status") == FINAL_STATUS, "已最终化 manifest 身份或状态不一致。")  # manifest 必须绑定同一固定 run。
    require(manifest.get("execution_status") == EXECUTION_STATUS and manifest.get("qa_status") == QA_STATUS and manifest.get("prepare_only") is False and manifest.get("mapdl_started") is True, "已最终化 manifest 执行事实不闭合。")  # manifest 不得退回 prepare 或未执行语义。
    require(runtime.get("run_name") == RUN_NAME and runtime.get("jobname") == JOBNAME and runtime.get("status") == "COMPLETED_FINALIZED", "已最终化 runtime 回执身份或状态不一致。")  # 运行回执必须是同一作业的完成态。
    require(runtime.get("artifact_ledger_pending_finalization") is False and runtime.get("postrun_gate_passed") is True, "已最终化 runtime 仍声称账本待完成或 QA 未通过。")  # 完成态不得保留待封板标志。
    postrun_bytes = POSTRUN_GATE_PATH.read_bytes()  # 读取机器门禁主入口完整字节。
    external_bytes = EXTERNAL_COMPLETION_QA_PATH.read_bytes()  # 读取外部完成 QA 完整字节。
    require(postrun_bytes == external_bytes, "已最终化双机器 QA 入口不再逐字节一致。")  # 两个权威入口必须继续同源。
    postrun = read_json(POSTRUN_GATE_PATH)  # 解析机器门禁对象供身份和状态复核。
    require(postrun.get("run_name") == RUN_NAME and postrun.get("jobname") == JOBNAME and postrun.get("gate_status") == "PASSED" and postrun.get("final_status") == FINAL_STATUS, "已最终化机器 QA 身份或门禁状态不一致。")  # QA 必须仍是固定 run 的正式通过结论。
    ledger = validate_hash_ledger(LEDGER_PATH, RUN_DIR, expected_entries=None, exclude_self=True)  # 对全 run 除账本自身外每个文件逐项重算并实施全局稳定性复核。
    actual_file_count = sum(1 for path in RUN_DIR.rglob("*") if path.is_file())  # 统计当前 run 下包括账本自身的全部普通文件。
    require(ledger["entry_count"] == actual_file_count - 1, "已最终化账本条目数不等于当前普通文件总数减一。")  # 明确复核自排除账本的闭合计数。
    return {  # 返回可供重入调用方识别的零写入成功摘要。
        "status": "ALREADY_FINALIZED_VERIFIED",  # 表示既有终态已完成严格幂等复核且未重写 run。
        "final_status": FINAL_STATUS,  # 既有根状态的最终结论。
        "execution_status": EXECUTION_STATUS,  # 既有主作业真实执行状态。
        "qa_status": QA_STATUS,  # 既有 S10 截面剪切试算 QA 状态。
        "postrun_gate": str(POSTRUN_GATE_PATH),  # 最终机器门禁绝对路径文本。
        "external_completion_qa": str(EXTERNAL_COMPLETION_QA_PATH),  # 外部完成 QA 绝对路径文本。
        "artifact_ledger": str(LEDGER_PATH),  # 最终全 run 账本绝对路径文本。
        "artifact_ledger_entries": ledger["entry_count"],  # 已严格复核的账本条目数量。
        "artifact_ledger_sha256": ledger["sha256"],  # 已严格复核的账本完整摘要。
    }  # 完成幂等成功摘要。


def commit_finalization(evidence: dict[str, Any]) -> dict[str, Any]:  # evidence 必须是 collect_evidence 的全部通过结果，并返回已提交终态摘要。
    """先写除 STATUS 外产物，以最终 STATUS override 建账本，再原子发布 STATUS；失败回滚，成功返回严格复核摘要。"""  # 函数说明参数约束、状态最后提交、回滚和返回语义。
    generated_utc = datetime.now(timezone.utc).isoformat()  # 生成统一最终化时间。
    postrun_gate = build_postrun_gate(evidence, generated_utc)  # 构造机器门禁。
    final_status_payload = json_bytes(build_status(evidence, generated_utc))  # 在内存生成最后发布的根 STATUS 完整字节，供账本 override 和 commit marker 共用。
    outputs: dict[Path, bytes] = {}  # 初始化 STATUS 之前的固定输出映射。
    outputs[PREPARE_STATUS_ARCHIVE] = evidence["prepare"]["status_bytes"]  # 原样归档 prepare 状态。
    outputs[PREPARE_MANIFEST_ARCHIVE] = evidence["prepare"]["manifest_bytes"]  # 原样归档 prepare manifest。
    outputs[PREPARE_RESULT_PACKET_ARCHIVE] = evidence["prepare"]["result_packet_bytes"]  # 原样归档 prepare 结果说明。
    outputs[PREPARE_LEDGER_ARCHIVE] = evidence["prepare"]["prepare_ledger_bytes"]  # 原样归档 52 项 prepare 账本。
    outputs[RUNNING_LAUNCH_ARCHIVE] = evidence["prepare"]["runtime_launch_bytes"]  # 原样归档启动回执。
    outputs[RUNNING_STATUS_ARCHIVE] = evidence["prepare"]["runtime_status_bytes"]  # 原样归档运行中说明。
    outputs[FINALIZER_SNAPSHOT_PATH] = SCRIPT_PATH.read_bytes()  # 原样快照当前 finalizer。
    outputs[HELPER_SNAPSHOT_PATH] = HELPER_PATH.read_bytes()  # 原样快照实际复用 helper。
    outputs[WARNING_DISPOSITION_PATH] = make_warning_markdown(evidence).encode("utf-8")  # 写五条 warning 处置。
    outputs[EXECUTION_FIELDS_PATH] = make_field_dictionary().encode("utf-8")  # 写字段说明。
    outputs[POSTRUN_GATE_PATH] = json_bytes(postrun_gate)  # 写机器门禁。
    outputs[EXTERNAL_COMPLETION_QA_PATH] = json_bytes(postrun_gate)  # 写逐字节同源外部完成 QA。
    outputs[RESULT_PACKET_PATH] = make_result_packet(evidence, generated_utc).encode("utf-8")  # 更新用户结果包。
    outputs[RUNTIME_LAUNCH_PATH] = json_bytes(build_runtime_launch(evidence, generated_utc))  # 更新完成态运行回执。
    outputs[RUNTIME_STATUS_PATH] = make_runtime_status(generated_utc).encode("utf-8")  # 更新运行状态说明。
    outputs[MANIFEST_PATH] = json_bytes(build_manifest(evidence, generated_utc))  # 更新根 manifest。
    target_order = list(outputs) + [  # 明确记录非状态产物之后的两个最终提交目标。
        LEDGER_PATH,  # 倒数第二步原子发布最终全 run 账本。
        STATUS_PATH,  # 最后一步原子发布根 STATUS commit marker。
    ]  # 完成非状态产物、账本和最后 STATUS 的确定提交顺序。
    allowed_targets = set(target_order)  # 构造精确写目标白名单。
    originals = {path: path.read_bytes() if path.exists() else None for path in target_order}  # 按确定顺序捕获事务前完整字节供回滚。
    written_paths: list[Path] = []  # 初始化实际已经成功原子替换的目标顺序。
    try:  # 包裹全部写入、复核和账本阶段。
        for path, payload in outputs.items():  # 按 lineage、快照、QA、运行回执和 manifest 顺序提交，但暂不发布根 STATUS。
            atomic_write(path, payload, allowed_targets)  # 原子写入白名单目标。
            written_paths.append(path)  # 在任何后续复核前登记真实已写目标，确保异常时能够恢复。
            require(path.read_bytes() == payload, f"落盘字节复核失败：{path}")  # 立即逐字节读回验证。
        require(sha256_file(PREPARE_STATUS_ARCHIVE) == evidence["prepare"]["status_sha256"], "prepare 状态归档哈希不闭合。")  # 核对状态原件。
        require(sha256_file(PREPARE_MANIFEST_ARCHIVE) == evidence["prepare"]["manifest_sha256"], "prepare manifest 归档哈希不闭合。")  # 核对 manifest 原件。
        require(sha256_file(PREPARE_RESULT_PACKET_ARCHIVE) == evidence["prepare"]["result_packet_sha256"], "prepare 结果说明归档哈希不闭合。")  # 核对结果说明原件。
        require(sha256_file(PREPARE_LEDGER_ARCHIVE) == evidence["prepare"]["prepare_ledger_sha256"], "prepare 账本归档哈希不闭合。")  # 核对 prepare 账本原件。
        require(sha256_file(RUNNING_LAUNCH_ARCHIVE) == evidence["prepare"]["runtime_launch_sha256"], "running 回执归档哈希不闭合。")  # 核对运行回执原件。
        require(sha256_file(RUNNING_STATUS_ARCHIVE) == evidence["prepare"]["runtime_status_sha256"], "running 说明归档哈希不闭合。")  # 核对运行说明原件。
        require(sha256_file(FINALIZER_SNAPSHOT_PATH) == evidence["finalizer_sha256"] and sha256_file(HELPER_SNAPSHOT_PATH) == evidence["helper_sha256"], "finalizer 或 helper 快照哈希不闭合。")  # 核对执行源码快照。
        require(POSTRUN_GATE_PATH.read_bytes() == EXTERNAL_COMPLETION_QA_PATH.read_bytes(), "双机器 QA 入口未逐字节一致。")  # 两个入口必须同源。
        require(solver_binary_metadata() == evidence["binary_metadata"], "STATUS 发布前 solver 二进制元数据变化。")  # 非状态产物写入期间 solver 隔离必须成立。
        ledger_payload, ledger_entries = build_full_ledger(final_status_payload)  # 在其他产物稳定后，以尚未发布的最终 STATUS 字节构建全 run 账本。
        atomic_write(LEDGER_PATH, ledger_payload, allowed_targets)  # 在根 STATUS 仍为 prepare 提交标记时原子替换旧账本。
        written_paths.append(LEDGER_PATH)  # 登记账本已实际写入，后续异常必须恢复 52 项旧账本。
        require(LEDGER_PATH.read_bytes() == ledger_payload and len(LEDGER_PATH.read_text(encoding="utf-8").splitlines()) == ledger_entries, "最终账本落盘字节或行数不一致。")  # 账本自身必须闭合。
        atomic_write(STATUS_PATH, final_status_payload, allowed_targets)  # 最后原子发布根 STATUS，使其成为账本和全部非状态产物均已落盘后的唯一 run 内 commit marker。
        written_paths.append(STATUS_PATH)  # 登记最后提交标记已写入，严格复核失败时仍可恢复 prepare 状态。
        require(STATUS_PATH.read_bytes() == final_status_payload, "最终 STATUS commit marker 落盘字节不一致。")  # 立即逐字节复核最后发布内容。
        strict_ledger = validate_hash_ledger(LEDGER_PATH, RUN_DIR, expected_entries=ledger_entries, exclude_self=True)  # STATUS 发布后按账本逐项重算全部文件并执行全局稳定性复核。
        actual_file_count = sum(1 for path in RUN_DIR.rglob("*") if path.is_file())  # 统计当前包含账本自身的全部普通文件。
        require(strict_ledger["entry_count"] == actual_file_count - 1, "最终账本条目数不等于当前普通文件总数减一。")  # 明确证明自排除账本的数量闭合。
        status_relative = STATUS_PATH.relative_to(RUN_DIR).as_posix()  # 取得根 STATUS 在账本中的规范 POSIX 标签。
        require(strict_ledger["records"].get(status_relative) == sha256_bytes(final_status_payload), "最终账本中的 STATUS 摘要与 commit marker 字节不一致。")  # 账本必须精确承诺最后发布的状态字节。
        require(solver_binary_metadata() == evidence["binary_metadata"], "最终 STATUS 与严格账本复核后 solver 二进制元数据变化。")  # 20+ GiB 双重读取期间不得有外部写入。
    except Exception as commit_exc:  # 任一写入、哈希、竞态或复核异常进入按实际写入顺序的整体回滚。
        rollback_errors = rollback(originals, written_paths, allowed_targets)  # best-effort 恢复所有实际写入目标并收集而非首错中断。
        if rollback_errors:  # 任一目标恢复失败时必须同时保留原提交失败和全部回滚失败信息。
            raise RuntimeError(f"S10 finalization 失败且回滚不完整；提交错误={commit_exc}；回滚错误={' | '.join(rollback_errors)}") from commit_exc  # 抛出聚合错误，禁止宣称已完整回滚。
        raise  # 全部恢复成功时保留原始提交异常及其 traceback。
    return {  # 返回已通过最后 STATUS 发布和严格账本复核的成功摘要。
        "status": FINAL_STATUS,  # 带 legacy 限制的最终状态。
        "execution_status": EXECUTION_STATUS,  # 主 MAPDL 作业真实执行状态。
        "qa_status": QA_STATUS,  # 本次 S10 截面剪切试算 QA 状态。
        "generated_utc": generated_utc,  # 统一最终化 UTC 时间。
        "postrun_gate": str(POSTRUN_GATE_PATH),  # 最终机器门禁绝对路径文本。
        "external_completion_qa": str(EXTERNAL_COMPLETION_QA_PATH),  # 外部完成 QA 绝对路径文本。
        "artifact_ledger": str(LEDGER_PATH),  # 最终全 run 账本绝对路径文本。
        "artifact_ledger_entries": ledger_entries,  # 最终账本条目数量。
        "artifact_ledger_sha256": strict_ledger["sha256"],  # STATUS 发布后严格复核的账本摘要。
        "commit_marker": str(STATUS_PATH),  # 最后原子发布的根 STATUS 路径文本。
        "solver_binary_metadata_count": len(evidence["binary_metadata"]),  # 受保护 solver 二进制文件数量。
        "link180_minimum_force_n": evidence["link180"]["minimum_force_n"],  # LINK180 原始 CSV 最小轴力，单位 N。
    }  # 完成首次最终化成功摘要。


def main(argv: list[str] | None = None) -> int:  # 输入可选 CLI 参数序列并返回零表示新最终化或幂等验证成功、二表示失败。
    """先严格解析零参数 CLI，再持有内核互斥量完成幂等复核或一次性最终化。"""  # 函数说明 CLI、独占锁和双成功路径。
    parse_cli_args(argv)  # 在取得任何锁或读取重文件前拒绝全部未知、位置或伪模式参数，并保留标准 --help。
    try:  # 捕获互斥量、幂等复核、门禁、写入和账本异常。
        mutex_handle = acquire_finalizer_mutex()  # 在 collect_evidence 或已完成复核前取得同一 run 的跨进程独占所有权。
        try:  # 保证成功、门禁失败和提交失败都释放内核互斥量。
            current_status = read_json(STATUS_PATH)  # 在锁内读取根提交标记，决定执行幂等只读路径还是首次最终化路径。
            if current_status.get("status") == FINAL_STATUS:  # 已发布正式终态时禁止重写任何 run 文件。
                result = validate_already_finalized()  # 严格复核根文件、双 QA 和全量账本后返回幂等成功。
            else:  # 非最终状态只能按唯一 prepare 起点执行完整首次最终化。
                evidence = collect_evidence()  # 在独占锁保护下执行零 run 写入证据阶段。
                result = commit_finalization(evidence)  # 仅在全部通过后执行 STATUS 最后发布事务。
        finally:  # 无论内部路径成功或抛出异常都释放当前线程持有的内核互斥量。
            release_finalizer_mutex(mutex_handle)  # 释放所有权并关闭句柄；进程崩溃时 Windows 亦会自动回收。
    except Exception as exc:  # 任一失败进入统一非零路径。
        print(f"S10 finalize FAILED: {exc}", flush=True)  # 输出具体失败原因且不伪造完成。
        return 2  # 返回非零表示最终化未成功或已完整回滚。
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)  # 成功时以中文直写和两空格缩进输出与磁盘一致的机器摘要。
    return 0  # 返回零表示真实终态和全账本完整封板。


if __name__ == "__main__":  # 仅直接运行脚本时进入最终化，导入模块不会读写大文件。
    raise SystemExit(main())  # 把明确退出码交给操作系统和调用方。
