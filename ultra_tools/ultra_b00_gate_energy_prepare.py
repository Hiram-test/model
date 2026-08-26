"""只为既有 B00 基线准备 GATE_BOTTOM_E 模态应变能只读后处理包，绝不启动 MAPDL。"""  # 模块说明明确本工具只有封板职责，不包含任何求解器执行路径。
from __future__ import annotations  # 启用延迟类型注解，避免运行时解析复合类型产生额外依赖。
import ctypes  # 仅调用 Windows 内存状态接口，用于记录未来后处理所需的资源快照。
import hashlib  # 仅以流式方式计算源二进制和准备产物的 SHA-256 摘要。
import json  # 仅读取 B00 清单并写出不支持注释的机器可读封板文件。
import re  # 仅解析 B00 导出计数、MAPDL 汇总和静态禁用命令。
import secrets  # 仅生成两字节随机后缀，防止同一微秒下的准备目录发生名称碰撞。
import shutil  # 仅查询目标卷剩余空间，不复制、移动或删除任何 B00 文件。
from datetime import datetime, timezone  # 仅生成带微秒的 UTC 唯一准备标识和审计时间。
from pathlib import Path  # 统一处理 Windows 绝对路径、独立目录和不可覆盖文件检查。
from typing import Any  # 为 JSON 动态对象提供明确但不过度收窄的类型标注。

SCRIPT_PATH = Path(__file__).resolve()  # 当前脚本绝对路径用于 lineage 快照和自身哈希封板。
TOOLS_DIR = SCRIPT_PATH.parent  # ultra_tools 目录用于定位项目根目录，禁止通过当前工作目录猜测。
PROJECT_ROOT = TOOLS_DIR.parent  # V2.0 项目根目录用于定位唯一 ultra_runs 父目录。
ULTRA_RUNS_ROOT = PROJECT_ROOT / "ultra_runs"  # 所有 Ultra 独立运行目录的固定父目录。
BASELINE_RUN_NAME = "B00_LEGACY_COMPLETE_20260715T111105670409Z"  # 用户指定且不可自动漂移的 B00 基线目录名。
BASELINE_RUN = ULTRA_RUNS_ROOT / BASELINE_RUN_NAME  # 既有 B00 基线根目录只允许读取，不允许写入。
BASELINE_SOLVER = BASELINE_RUN / "solver"  # 既有求解器产物目录承载 modal.db、RSTP 和 MODE 文件族。
BASE_JOB_STEM = "cw_B00_0715t111105_ca"  # B00 二进制共同文件名前缀必须与原 manifest 完全一致。
BASE_MODAL_DB_STEM = f"{BASE_JOB_STEM}_modal"  # 已保存模态数据库的无扩展名文件干用于 RESUME。
BASE_MODAL_DB = BASELINE_SOLVER / f"{BASE_MODAL_DB_STEM}.db"  # 包含完整模型和 GATE_BOTTOM_E 组件的只读数据库。
BASE_RSTP = BASELINE_SOLVER / f"{BASE_JOB_STEM}.rstp"  # 线性扰动模态结果主文件用于 POST1 的 FILE 命令。
BASE_MODE = BASELINE_SOLVER / f"{BASE_JOB_STEM}.mode"  # 与 RSTP 同前缀的 MODE 伴随文件必须同时保留可读。
BASE_MANIFEST = BASELINE_RUN / "manifest.json"  # 原始 B00 机器清单用于校验 jobname、版本和可执行文件。
BASE_EXPORT_MANIFEST = BASELINE_SOLVER / "b00_modal_export_manifest.txt"  # 原始请求、可用、导出阶数闭合证据。
BASE_GATE_STATUS = BASELINE_SOLVER / "b00_gate_status.txt"  # 原始求解与导出完成状态只读证据。
BASE_MODAL_OUT = BASELINE_SOLVER / f"{BASE_JOB_STEM}_modal_resume.out"  # 原始模态续算输出用于零 ERROR 静态门禁。
BASE_MODAL_SOURCE = BASELINE_SOLVER / "b00_legacy_complete_modal_resume_source.inp"  # 原始模态控制顺序的静态审计源。
BASE_COMPONENT_SOURCE = BASELINE_SOLVER / "apply_finite_gates_and_passages_v2.inp"  # GATE_BOTTOM_E 组件定义与数量证据。
MAPDL_EXE = Path(r"D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe")  # 未来命令固定指向 B00 已审计的 MAPDL v261。
MAPDL_SHA256 = "6c6327f6b906db8e6dd498bd38c97685d7e3e4acf52fccbf243b2dff7ed7af1b"  # MAPDL v261 可执行文件的封板摘要。
EXPECTED_MODE_COUNT = 59  # B00 在 0 至 0.35 Hz 内实际导出 59 阶，运行时结果集数必须完全一致。
EXPECTED_GATE_ELEMENT_COUNT = 2698  # GATE_BOTTOM_E 的 H175 下横梁单元封板数量来自原构件生成清单。
EXPECTED_MAPDL_VERSION = "2026 R1 / v261"  # 仅接受原 B00 manifest 记录的求解器版本口径。
RUN_PREFIX = "B00_GATE_ENERGY_PREPARED"  # 新准备目录前缀与 B00 主求解目录明确隔离。
JOB_PREFIX = "cw_B00GE"  # 新 MAPDL jobname 前缀不复用 BASE_JOB_STEM，避免任何同名输出。
PROCESS_COUNT = 1  # 只读 POST1 固定单进程 SMP，避免生成或改写 B00 的 DMP 分区文件。
MINIMUM_MEMORY_BYTES = 4 * 1024**3  # 未来运行最低可用物理内存门槛为 4 GiB，覆盖数据库与单列 ETABLE。
COMFORTABLE_MEMORY_BYTES = 6 * 1024**3  # 未来运行舒适可用物理内存参考为 6 GiB，给 MAPDL 运行库留余量。
MINIMUM_DISK_BYTES = 2 * 1024**3  # 独立输出卷最低剩余空间门槛为 2 GiB，不含零复制源二进制。
EXPECTED_OUTPUT_BYTES_MAX = 100 * 1024**2  # CSV、OUT、LOG 和状态文本预计合计不超过 100 MiB。
HASH_CHUNK_BYTES = 8 * 1024**2  # 源二进制按 8 MiB 分块读取，限制哈希过程的瞬时内存占用。
CROSSCHECK_RELATIVE_TOLERANCE = 1.0e-6  # PRENERGY 与 ETABLE/SSUM 的相对闭合容差取一百万分之一。
RATIO_PERCENTAGE_POINT_TOLERANCE = 1.0e-6  # 两条通道的组件百分比容差取 1E-6 个百分点。
EXPECTED_BINARY_SPECS: dict[str, tuple[int, str]] = {  # 固定全部主文件与四个 DMP 分区伴随文件的封板尺寸和摘要。
    "cw_B00_0715t111105_ca.mode": (635371520, "848f5b786e6a71c57991f1de2aa013e20ee3ed3230866feef38a37a1ea3f2cd7"),  # 主 MODE 文件用于保持原模态伴随数据完整。
    "cw_B00_0715t111105_ca.rstp": (672071680, "7c009f60822ec42daf0825033550edd84ef2ec25172fcbc8f516356d4a0fa31a"),  # 主 RSTP 文件承载 59 阶线性扰动结果集。
    "cw_B00_0715t111105_ca0.mode": (231211008, "8c1c8b04a935b508b95d24cbeb10406fc1fa0754f18abc560e1d5f1471c44f7c"),  # 第零 DMP 分区 MODE 伴随文件必须保留。
    "cw_B00_0715t111105_ca0.rstp": (244187136, "6423db2370e90c89f785e13f1a9790293f4e942121994dbe80645cb921798a07"),  # 第零 DMP 分区 RSTP 伴随文件必须保留。
    "cw_B00_0715t111105_ca1.mode": (230686720, "59fb35c17755d7538a2731f13fc29cc6b1186dbd7f5c4c7ddc5716f3beac3f2d"),  # 第一 DMP 分区 MODE 伴随文件必须保留。
    "cw_B00_0715t111105_ca1.rstp": (242417664, "c66e65cd15facaccad37e0f811ef134cb0d4fcefc9b9ca1d3a2ea2f8e5299740"),  # 第一 DMP 分区 RSTP 伴随文件必须保留。
    "cw_B00_0715t111105_ca2.mode": (237305856, "7cabb982b468cc5640f0b42c44439f2c9463d6c231cdeaddcd1f6bc816fb2f44"),  # 第二 DMP 分区 MODE 伴随文件必须保留。
    "cw_B00_0715t111105_ca2.rstp": (249036800, "156c6647690a3d6a43fe3fcf9397800685d8f97f56e7bf9b208ba465d6f281f5"),  # 第二 DMP 分区 RSTP 伴随文件必须保留。
    "cw_B00_0715t111105_ca3.mode": (270991360, "72aed0a7cbc2a9bd1e24c1a1316131240cf3b877c0a89bcbe94bd46563de277d"),  # 第三 DMP 分区 MODE 伴随文件必须保留。
    "cw_B00_0715t111105_ca3.rstp": (283639808, "ba50444329e27a4b2e64069c1fd753ad340c0ce4096433052f4e9135da4a50f1"),  # 第三 DMP 分区 RSTP 伴随文件必须保留。
    "cw_B00_0715t111105_ca_modal.db": (241631232, "ca11c4b3115086ff7df61d5a4f47f1ca5b771fce90dbe08e1d89aa50848e97f3"),  # 完成 59 阶导出后保存的模态数据库用于只读 RESUME。
}  # 结束不可漂移的源二进制封板字典。


class MemoryStatusEx(ctypes.Structure):  # 映射 Windows MEMORYSTATUSEX 结构以只读查询物理内存。
    """保存 Windows 全局内存状态；字段单位均为字节，负载字段单位为百分比。"""  # 类说明给出输入来源和字段单位约束。

    _fields_ = [  # 字段顺序严格匹配 Win32 MEMORYSTATUSEX ABI，禁止调整顺序。
        ("dwLength", ctypes.c_ulong),  # 结构体自身字节长度由调用前显式填写。
        ("dwMemoryLoad", ctypes.c_ulong),  # 当前物理内存占用率范围为 0 至 100。
        ("ullTotalPhys", ctypes.c_ulonglong),  # 系统物理内存总量，单位为字节。
        ("ullAvailPhys", ctypes.c_ulonglong),  # 当前可用物理内存，单位为字节。
        ("ullTotalPageFile", ctypes.c_ulonglong),  # 系统页面文件总量，单位为字节。
        ("ullAvailPageFile", ctypes.c_ulonglong),  # 当前可用页面文件，单位为字节。
        ("ullTotalVirtual", ctypes.c_ulonglong),  # 当前进程虚拟地址空间总量，单位为字节。
        ("ullAvailVirtual", ctypes.c_ulonglong),  # 当前进程可用虚拟地址空间，单位为字节。
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),  # 扩展虚拟地址空间，常规 64 位进程通常为零。
    ]  # 结束 Windows 结构字段定义。


def require(condition: bool, message: str) -> None:  # 将所有静态门禁统一为带明确原因的失败异常。
    """条件为假时抛出 RuntimeError；成功时无输出、无写入并返回 None。"""  # 函数说明包含输入、输出和失败约束。
    if not condition:  # 只有静态事实不满足时才进入拒绝分支。
        raise RuntimeError(message)  # 立即拒绝准备，防止生成看似可运行但来源不闭合的目录。


def sha256_file(path: Path) -> str:  # 流式读取任意文件并返回小写六十四位 SHA-256 十六进制摘要。
    """读取 path 的全部字节但不修改文件；返回 SHA-256 字符串。"""  # 函数说明明确输入、输出和只读约束。
    digest = hashlib.sha256()  # 创建新的 SHA-256 累加器，避免跨文件复用状态。
    with path.open("rb") as handle:  # 以二进制只读模式打开源文件，禁止产生时间戳之外的内容变更。
        while True:  # 循环直到读取到空字节串，适配数百 MiB 的二进制文件。
            chunk = handle.read(HASH_CHUNK_BYTES)  # 每次最多读取 8 MiB，避免一次载入整个二进制。
            if not chunk:  # 空字节串表示已到文件末尾。
                break  # 结束读取循环并进入摘要输出。
            digest.update(chunk)  # 将当前分块按原始顺序加入 SHA-256 累加器。
    return digest.hexdigest()  # 返回固定六十四位小写摘要供封板比较和清单记录。


def write_new_text(path: Path, content: str) -> None:  # 仅创建不存在的 UTF-8 文本文件并拒绝覆盖。
    """把 content 写入新文件 path；若目标已存在则失败。"""  # 函数说明明确不可覆盖语义和无返回值。
    require(not path.exists(), f"拒绝覆盖既有文件：{path}")  # 在任何写入前执行存在性门禁。
    path.write_text(content, encoding="utf-8", newline="\n")  # 使用 UTF-8 与 LF 写入便于 APDL 和审计工具稳定读取。


def write_new_json(path: Path, payload: Any) -> None:  # 将动态对象序列化为新 JSON 文件并拒绝覆盖。
    """把 payload 以 UTF-8 缩进 JSON 写入 path；JSON 本身不插入非法注释。"""  # 函数说明遵守 JSON 无注释约束。
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"  # 保留中文并添加末尾换行形成稳定文本。
    write_new_text(path, content)  # 复用不可覆盖写入门禁完成实际文件创建。


def load_json(path: Path) -> dict[str, Any]:  # 读取并校验根对象为字典的 UTF-8 JSON 文件。
    """读取 path 并返回 JSON 对象；根值不是对象时拒绝。"""  # 函数说明明确返回类型和结构约束。
    payload = json.loads(path.read_text(encoding="utf-8"))  # 只读解析现有清单，不对源文件回写格式。
    require(isinstance(payload, dict), f"JSON 根值不是对象：{path}")  # 防止列表或标量被误当作 manifest。
    return payload  # 返回已通过根类型门禁的动态字典。


def memory_snapshot() -> dict[str, Any]:  # 查询准备时 Windows 内存并计算未来运行门槛布尔值。
    """返回物理内存快照和 4/6 GiB 门槛；查询失败时抛出 OSError。"""  # 函数说明给出输出字段来源和失败语义。
    status = MemoryStatusEx()  # 分配零初始化的 Win32 结构体实例。
    status.dwLength = ctypes.sizeof(MemoryStatusEx)  # 按 API 要求写入结构体字节长度。
    success = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))  # 调用只读系统接口填充内存状态。
    if not success:  # Windows 接口返回零表示查询失败。
        raise ctypes.WinError()  # 抛出包含系统错误码的异常，避免伪造资源快照。
    available = int(status.ullAvailPhys)  # 将可用物理内存转换为普通整数以便 JSON 序列化。
    return {  # 返回同时含原始量、门槛和非执行事实的机器可读对象。
        "total_physical_bytes": int(status.ullTotalPhys),  # 记录系统物理内存总量，单位为字节。
        "available_physical_bytes": available,  # 记录准备瞬间可用物理内存，单位为字节。
        "memory_load_percent": int(status.dwMemoryLoad),  # 记录准备瞬间内存占用率，单位为百分比。
        "minimum_available_memory_bytes": MINIMUM_MEMORY_BYTES,  # 固定未来运行最低门槛为 4 GiB。
        "comfortable_available_memory_bytes": COMFORTABLE_MEMORY_BYTES,  # 固定未来运行舒适参考为 6 GiB。
        "minimum_ready": available >= MINIMUM_MEMORY_BYTES,  # 判断准备瞬间是否达到最低内存门槛。
        "comfortable_ready": available >= COMFORTABLE_MEMORY_BYTES,  # 判断准备瞬间是否达到舒适内存参考。
        "execution_attempted": False,  # 明确资源查询没有也不会触发 MAPDL。
    }  # 结束内存快照对象。


def disk_snapshot() -> dict[str, Any]:  # 查询 ultra_runs 所在卷空间并计算未来运行门槛布尔值。
    """返回目标卷字节级空间快照；仅查询，不创建大型副本。"""  # 函数说明明确输入锚点和只读语义。
    usage = shutil.disk_usage(ULTRA_RUNS_ROOT)  # 读取独立运行目录所在卷的总量、已用量和余量。
    return {  # 返回资源门槛和零复制策略的机器可读对象。
        "volume_anchor": str(ULTRA_RUNS_ROOT.resolve()),  # 记录空间查询锚点的绝对路径。
        "total_bytes": int(usage.total),  # 记录目标卷总容量，单位为字节。
        "used_bytes": int(usage.used),  # 记录准备瞬间已用空间，单位为字节。
        "free_bytes": int(usage.free),  # 记录准备瞬间剩余空间，单位为字节。
        "minimum_free_bytes": MINIMUM_DISK_BYTES,  # 固定未来运行最低剩余空间为 2 GiB。
        "minimum_ready": int(usage.free) >= MINIMUM_DISK_BYTES,  # 判断准备瞬间是否达到磁盘门槛。
        "expected_output_bytes_max": EXPECTED_OUTPUT_BYTES_MAX,  # 记录预计小文本输出上限为 100 MiB。
        "source_binary_copy_bytes": 0,  # 明确采用绝对路径只读引用，不复制约 2.75 GiB 源二进制。
        "execution_attempted": False,  # 明确空间查询没有也不会触发 MAPDL。
    }  # 结束磁盘快照对象。


def validate_baseline() -> tuple[dict[str, Any], dict[str, tuple[int, int]]]:  # 完成 B00 文本、二进制和哈希的只读静态门禁。
    """返回源审计记录和文件状态快照；任何不一致均在创建新目录前拒绝。"""  # 函数说明明确输出和 fail-closed 顺序。
    require(BASELINE_RUN.is_dir(), f"缺少固定 B00 基线目录：{BASELINE_RUN}")  # 禁止回退到相似或最新目录。
    require(BASELINE_SOLVER.is_dir(), f"缺少固定 B00 solver 目录：{BASELINE_SOLVER}")  # 要求二进制位于原始封板层级。
    required_text_files = [BASE_MANIFEST, BASE_EXPORT_MANIFEST, BASE_GATE_STATUS, BASE_MODAL_OUT, BASE_MODAL_SOURCE, BASE_COMPONENT_SOURCE]  # 汇总全部静态文本证据。
    for path in required_text_files:  # 逐项验证文本证据存在且为普通文件。
        require(path.is_file(), f"缺少 B00 静态证据：{path}")  # 任一缺失都拒绝生成启动命令。
    manifest = load_json(BASE_MANIFEST)  # 读取 B00 原 manifest 以验证 jobname、版本和可执行文件摘要。
    require(manifest.get("jobname") == BASE_JOB_STEM, "B00 manifest 的 jobname 与固定前缀不一致")  # 防止结果文件族错配。
    require(manifest.get("mapdl_version") == EXPECTED_MAPDL_VERSION, "B00 manifest 的 MAPDL 版本不是 v261")  # 防止跨版本误读。
    require(Path(str(manifest.get("mapdl_executable"))).resolve() == MAPDL_EXE.resolve(), "B00 manifest 的 MAPDL 路径不一致")  # 固定未来解析器路径。
    require(manifest.get("mapdl_executable_sha256") == MAPDL_SHA256, "B00 manifest 的 MAPDL 摘要不一致")  # 固定未来解析器字节身份。
    export_text = BASE_EXPORT_MANIFEST.read_text(encoding="utf-8", errors="strict")  # 严格 UTF-8 读取原导出计数证据。
    exported_match = re.search(r"EXPORTED=\s*([0-9]+)", export_text)  # 提取实际导出阶数，不依赖空格宽度。
    require(exported_match is not None, "B00 模态导出清单缺少 EXPORTED 字段")  # 字段缺失时无法闭合结果集数量。
    exported_count = int(exported_match.group(1))  # 将十进制导出阶数字段转换为整数。
    require(exported_count == EXPECTED_MODE_COUNT, f"B00 实际导出阶数不是 {EXPECTED_MODE_COUNT}")  # 固定本次逐阶循环规模。
    gate_text = BASE_GATE_STATUS.read_text(encoding="utf-8", errors="strict")  # 严格读取原完成状态文本。
    require("STATUS=SOLVER_EXPORT_COMPLETED" in gate_text, "B00 gate 状态未达到 SOLVER_EXPORT_COMPLETED")  # 只允许使用完成导出的基线。
    out_text = BASE_MODAL_OUT.read_text(encoding="utf-8", errors="replace")  # 容忍 MAPDL 本地编码字符但保留 ASCII 汇总字段。
    error_match = re.search(r"NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*([0-9]+)", out_text)  # 提取 MAPDL 汇总 ERROR 计数。
    require(error_match is not None and int(error_match.group(1)) == 0, "B00 模态续算输出不是零 ERROR")  # 拒绝含求解器错误的结果来源。
    modal_source_text = BASE_MODAL_SOURCE.read_text(encoding="utf-8", errors="strict")  # 读取原模态控制源以静态核对展开和输出顺序。
    require("MXPAND,80,,,YES" in modal_source_text, "B00 源未启用 MXPAND 的 Elcalc=YES")  # BEAM188 SENE 至少要求展开时计算单元结果。
    require("OUTRES,ALL,NONE" in modal_source_text, "B00 源缺少已知的 ALL,NONE 输出控制")  # 固定已识别的能量可用性风险事实。
    require("OUTRES,NSOL,ALL" in modal_source_text, "B00 源缺少 59 阶节点结果输出控制")  # 确认 RSTP 的节点模态来源。
    require(f"SAVE,{BASE_MODAL_DB_STEM},db" in modal_source_text, "B00 源未保存固定 modal.db")  # 确认恢复数据库与结果文件同源。
    last_all_none = modal_source_text.rfind("OUTRES,ALL,NONE")  # 定位最后一次关闭全部结果记录的控制命令。
    explicit_veng_after_all_none = modal_source_text.find("OUTRES,VENG", last_all_none) >= 0  # 判断关闭全部后是否重新显式开启元素能量。
    component_text = BASE_COMPONENT_SOURCE.read_text(encoding="utf-8", errors="strict")  # 读取构件输入确认组件类型与封板数量。
    require(f"组件 GATE_BOTTOM_E: ELEM 数量={EXPECTED_GATE_ELEMENT_COUNT}" in component_text, "GATE_BOTTOM_E 注释数量与封板值不一致")  # 固定 2698 根下横梁。
    require("CM,GATE_BOTTOM_E,ELEM" in component_text, "GATE_BOTTOM_E 不是显式 ELEM 组件")  # PRENERGY 只支持元素组件。
    require(MAPDL_EXE.is_file(), f"缺少未来命令指定的 MAPDL v261：{MAPDL_EXE}")  # 只检查存在性，不执行程序。
    actual_mapdl_hash = sha256_file(MAPDL_EXE)  # 只读计算可执行文件摘要以防路径内容漂移。
    require(actual_mapdl_hash == MAPDL_SHA256, "MAPDL v261 可执行文件摘要与 B00 封板值不一致")  # 字节不一致时不生成命令。
    binary_records: list[dict[str, Any]] = []  # 收集全部源二进制的字节、摘要和只读引用策略。
    stat_records: dict[str, tuple[int, int]] = {}  # 保存哈希前文件大小与纳秒修改时间供最终无变更复核。
    for file_name, (expected_bytes, expected_sha256) in EXPECTED_BINARY_SPECS.items():  # 按固定字典逐一核验主文件和 DMP 伴随文件。
        path = BASELINE_SOLVER / file_name  # 在唯一 B00 solver 目录下解析当前二进制绝对路径。
        require(path.is_file(), f"缺少 B00 源二进制：{path}")  # 任一主或分区伴随文件缺失都拒绝准备。
        before = path.stat()  # 记录哈希前的大小和修改时间，不改变文件属性。
        require(before.st_size == expected_bytes, f"B00 源二进制字节数漂移：{file_name}")  # 尺寸漂移时避免无意义的后处理尝试。
        actual_sha256 = sha256_file(path)  # 流式只读计算当前二进制完整摘要。
        require(actual_sha256 == expected_sha256, f"B00 源二进制 SHA-256 漂移：{file_name}")  # 摘要不一致时拒绝生成命令。
        after = path.stat()  # 记录哈希后状态以证明读取过程没有改写源文件。
        require((after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns), f"哈希期间源二进制发生变化：{file_name}")  # 并发变化也按失败处理。
        stat_records[file_name] = (before.st_size, before.st_mtime_ns)  # 保存最终准备结束时再次核验所需的状态。
        binary_records.append({"file_name": file_name, "absolute_path": str(path.resolve()), "bytes": expected_bytes, "sha256": actual_sha256, "reference_mode": "READ_ONLY_ABSOLUTE_PATH", "copied": False})  # 记录零复制只读来源。
    source_audit = {  # 汇总可直接写入 manifest 和静态门禁的来源事实。
        "baseline_run": str(BASELINE_RUN.resolve()),  # 记录用户指定 B00 基线绝对路径。
        "baseline_job_stem": BASE_JOB_STEM,  # 记录 RSTP/MODE 文件族的共同前缀。
        "exported_mode_count": exported_count,  # 记录原导出清单闭合的 59 阶。
        "gate_component": "GATE_BOTTOM_E",  # 记录唯一目标元素组件名称。
        "gate_component_type": "ELEM",  # 记录 PRENERGY 支持的元素组件类型。
        "gate_component_element_count": EXPECTED_GATE_ELEMENT_COUNT,  # 记录静态来源中的 2698 个单元。
        "mxpand_elcalc_yes": True,  # 记录原求解启用了单元结果计算。
        "explicit_veng_after_final_all_none": explicit_veng_after_all_none,  # 记录原 RSTP 是否在关闭全部后重新请求 VENG。
        "sene_runtime_risk": "HIGH_IF_EXPLICIT_VENG_IS_FALSE",  # 明确静态证据不能保证 RSTP 含 SENE，运行时必须 fail-closed。
        "mapdl_executable_sha256": actual_mapdl_hash,  # 记录未来解析器的实际封板摘要。
        "source_binaries": binary_records,  # 记录全部十一项数据库、主文件和分区伴随文件。
        "source_binary_copy_policy": "NO_COPY_NO_MOVE_NO_DELETE_NO_ATTRIBUTE_CHANGE",  # 明确保护 B00 的零复制策略。
    }  # 结束来源审计对象。
    return source_audit, stat_records  # 返回静态事实和最终不变性复核所需状态。


def verify_source_stats_unchanged(stat_records: dict[str, tuple[int, int]]) -> None:  # 准备结束前复核所有 B00 二进制未被改写。
    """比较当前大小和修改时间与 validate_baseline 快照；无返回值。"""  # 函数说明给出输入含义和失败约束。
    for file_name, expected_state in stat_records.items():  # 遍历所有已封板源二进制状态。
        path = BASELINE_SOLVER / file_name  # 重新解析固定 B00 solver 下的当前文件路径。
        current = path.stat()  # 只读获取当前大小和纳秒修改时间。
        require((current.st_size, current.st_mtime_ns) == expected_state, f"准备期间 B00 源二进制发生变化：{file_name}")  # 任一变化都拒绝封板成功。


def build_apdl(csv_stem: str, status_stem: str) -> str:  # 生成仅含 RESUME、POST1 和文本导出的 APDL 输入。
    """返回只读逐阶 SENE 双通道后处理 APDL；不含 SOLU、SOLVE 或 SAVE。"""  # 函数说明明确输出和绝对禁用命令。
    db_stem = str((BASELINE_SOLVER / BASE_MODAL_DB_STEM).resolve())  # 构造 RESUME 使用的 modal.db 绝对无扩展名路径。
    result_stem = str((BASELINE_SOLVER / BASE_JOB_STEM).resolve())  # 构造 FILE 使用的 RSTP/MODE 共同绝对无扩展名路径。
    lines = [  # 每条 APDL 命令均由紧邻中文注释说明用途、条件和预期结果。
        "! 本输入只读恢复既有 B00 modal.db 并读取同前缀 RSTP/MODE；严禁求解、保存或覆盖 B00。",  # 声明整个 APDL 文件的边界与保护策略。
        "/BATCH",  # 固定批处理模式，避免任何交互式选择或隐式人工操作。
        "! 在独立 jobname 和独立工作目录中写入唯一 RUNNING 状态；该文件不位于 B00 基线。",  # 说明初始状态文件的路径隔离事实。
        f"/OUTPUT,{status_stem},txt",  # 打开本准备包唯一状态文件并覆盖尚不存在的新文件。
        "! 写入只表示已进入后处理的状态，不表示能量记录可用或工程判定通过。",  # 说明 RUNNING 状态的非完成语义。
        "/COM,STATUS=RUNNING PHASE=READ_ONLY_POST1",  # 记录只读后处理开始阶段供异常中断审计。
        "! 恢复 MAPDL 主输出，使后续警告、PRENERGY 和 SSUM 均留在唯一 OUT 中。",  # 说明输出通道切回主 OUT 的目的。
        "/OUTPUT",  # 关闭状态重定向并恢复命令行指定的唯一主输出。
        "! 以绝对路径恢复完成 59 阶导出后保存的模型数据库；本输入从不执行 SAVE。",  # 说明数据库输入、来源和不可写约束。
        f"RESUME,'{db_stem}','db'",  # 只读载入包含组件与模型定义的 modal.db。
        "! 进入通用后处理器；本输入不进入 SOLUTION 处理器。",  # 说明处理器边界和禁止求解事实。
        "/POST1",  # 进入 POST1 以读取既有线性扰动结果集。
        "! 显式指定 B00 线性扰动结果主文件；同目录同前缀 MODE 与分区伴随文件保持原位。",  # 说明 RSTP/MODE 配对规则。
        f"FILE,'{result_stem}','rstp'",  # 将既有 RSTP 设为当前只读结果文件。
        "! 激活最后一个真实结果集，以便读取总结果集数并验证文件可访问。",  # 说明 SET,LAST 的运行时探测目的。
        "SET,LAST",  # 读取最后一阶模态结果，不产生求解或数据库保存。
        "! 从当前 RSTP 读取实际结果集总数，必须与原导出清单的 59 阶闭合。",  # 说明 NSET 的来源和硬约束。
        "*GET,B00_NSET,ACTIVE,0,SET,NSET",  # 将当前结果文件总集合数存入标量参数。
        "! 从恢复数据库读取 GATE_BOTTOM_E 组件类型；元素组件的官方类型码必须为 2。",  # 说明组件类型门禁和官方码值。
        "*GET,B00_CTYPE,COMP,GATE_BOTTOM_E,TYPE",  # 读取组件类型以拒绝节点组件或缺失组件。
        "! 恢复全部节点和单元选择，防止 modal.db 保存时的最后选择集影响组件计数。",  # 说明选择集归一化的必要性。
        "ALLSEL,ALL",  # 恢复完整模型选择集。
        "! 仅选择 GATE_BOTTOM_E 元素组件，运行时确认数据库中真实保存的成员数量。",  # 说明组件选择的目的和作用域。
        "CMSEL,S,GATE_BOTTOM_E,ELEM",  # 选择全部 2698 个目标下横梁单元。
        "! 读取当前选择集的元素数量，必须与生成器封板值 2698 完全一致。",  # 说明组件数量硬门禁。
        "*GET,B00_GCNT,ELEM,0,COUNT",  # 将目标组件实际元素数存入标量参数。
        "! 恢复全部选择，以便后续总 SENE 统计覆盖整个模型。",  # 说明门禁后恢复选择集的原因。
        "ALLSEL,ALL",  # 恢复完整模型单元和节点。
        "! 以位掩码累计前置门禁错误：1=组件类型，2=组件数量，4=结果集数量。",  # 说明错误码每一位的含义和用途。
        "B00_PREERR=0",  # 初始化前置门禁错误码为零。
        "! 组件类型不是元素类型码 2 时设置错误位 1。",  # 说明第一个前置分支条件。
        "*IF,B00_CTYPE,NE,2,THEN",  # 检查 GATE_BOTTOM_E 是否为 ELEM 组件。
        "! 累加组件类型错误位，保留其他错误以便一次输出完整位掩码。",  # 说明分支内赋值目的。
        "B00_PREERR=B00_PREERR+1",  # 设置错误位 1。
        "! 结束组件类型门禁分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭组件类型条件结构。
        f"! 组件数量不是 {EXPECTED_GATE_ELEMENT_COUNT} 时设置错误位 2。",  # 说明第二个前置分支条件和封板值。
        f"*IF,B00_GCNT,NE,{EXPECTED_GATE_ELEMENT_COUNT},THEN",  # 检查数据库组件成员数是否为 2698。
        "! 累加组件数量错误位。",  # 说明分支内赋值目的。
        "B00_PREERR=B00_PREERR+2",  # 设置错误位 2。
        "! 结束组件数量门禁分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭组件数量条件结构。
        f"! RSTP 结果集数量不是 {EXPECTED_MODE_COUNT} 时设置错误位 4。",  # 说明第三个前置分支条件和封板阶数。
        f"*IF,B00_NSET,NE,{EXPECTED_MODE_COUNT},THEN",  # 检查结果文件是否恰有 59 阶。
        "! 累加结果集数量错误位。",  # 说明分支内赋值目的。
        "B00_PREERR=B00_PREERR+4",  # 设置错误位 4。
        "! 结束结果集数量门禁分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭结果集数量条件结构。
        "! 任一前置错误存在时写出错误码、实际阶数、组件类型和数量，然后无保存退出。",  # 说明 fail-closed 总分支语义。
        "*IF,B00_PREERR,GT,0,THEN",  # 仅在前置错误位掩码非零时进入拒绝路径。
        "! 打开本准备包唯一状态文件并覆盖 RUNNING 状态。",  # 说明拒绝状态写入位置和覆盖范围。
        f"/OUTPUT,{status_stem},txt",  # 将拒绝状态写入独立输出目录内的唯一文件。
        "! 下一条 VWRITE 与紧随其后的 Fortran 格式行共同写入前置拒绝证据，中间不得插入注释。",  # 同时说明两行语法约束和字段含义。
        "*VWRITE,B00_PREERR,B00_NSET,B00_CTYPE,B00_GCNT",  # 输出错误位掩码及三个实际门禁量。
        "('STATUS=REJECTED REASON=PRECHECK_BITMASK CODE=',F8.0,', NSET=',F8.0,', CTYPE=',F8.0,', GATE_COUNT=',F12.0)",  # 使用定宽整数格式形成可解析拒绝行。
        "! 恢复主输出以保留正常退出摘要。",  # 说明输出通道恢复目的。
        "/OUTPUT",  # 关闭状态重定向并恢复唯一主 OUT。
        "! 离开 POST1，不保存内存中的 SET、选择集或 ETABLE 状态。",  # 说明退出处理器且不修改数据库。
        "FINISH",  # 返回 Begin 层级。
        "! 以前置门禁失败状态退出，NOSAVE 明确禁止写回 modal.db。",  # 说明退出参数的保护作用。
        "/EXIT,NOSAVE",  # 终止未来批处理且不保存任何数据库。
        "! 结束前置门禁失败分支；通过时继续逐阶双通道能量提取。",  # 说明控制流合流位置。
        "*ENDIF",  # 关闭前置拒绝条件结构。
        "! 打开唯一 CSV，所有 PRENERGY 和 SSUM 打印仍留在主 OUT，避免污染结构化数据。",  # 说明 *CFOPEN 与主输出的分工。
        f"*CFOPEN,{csv_stem},csv",  # 创建独立输出目录内唯一 CSV 数据文件。
        "! 下一条无参数 VWRITE 与紧随格式行写入十二列字段名，中间不得插入注释。",  # 同时说明表头语法约束和列数。
        "*VWRITE",  # 触发纯字面量 CSV 表头写入。
        "('mode_index,load_step,substep,frequency_hz,total_sene_prenergy,gate_sene_prenergy,gate_percent_prenergy,total_sene_etable,gate_sene_etable,gate_percent_etable,total_relative_delta,gate_relative_delta')",  # 固定列名和顺序供外部 QA 解析。
        f"! 从第 1 阶循环到固定的第 {EXPECTED_MODE_COUNT} 阶，每阶都执行两条独立能量通道。",  # 说明循环范围、单位和任务目的。
        f"*DO,B00_I,1,{EXPECTED_MODE_COUNT}",  # 开始 59 阶逐阶循环，步长默认为 1。
        "! 显式读取载荷步 1 的当前模态子步，拒绝依赖前一轮 SET 状态。",  # 说明每阶 SET 的确定性。
        "SET,1,B00_I",  # 激活当前模态结果集。
        "! 读取当前 SET 的实际载荷步号供 CSV 闭合。",  # 说明载荷步元数据来源。
        "*GET,B00_LS,ACTIVE,0,SET,LSTP",  # 获取当前实际载荷步号。
        "! 读取当前 SET 的实际子步号供 CSV 闭合。",  # 说明子步元数据来源。
        "*GET,B00_SB,ACTIVE,0,SET,SBST",  # 获取当前实际子步号。
        "! 读取当前模态频率，单位为 Hz。",  # 说明频率单位和来源。
        "*GET,B00_FREQ,ACTIVE,0,SET,FREQ",  # 获取当前结果集频率。
        "! 恢复全部选择后调用官方 PRENERGY 总模型 SENE。",  # 说明官方总能量通道必须覆盖全模型。
        "ALLSEL,ALL",  # 归一化当前选择集为完整模型。
        "! 计算并打印当前阶全模型势能或刚度能；若 RSTP 未存 VENG，运行时门禁将拒绝零值。",  # 说明 PRENERGY 输入和已知风险。
        "PRENERGY,SENE",  # 生成官方总 SENE 缓存供随后 *GET 读取。
        "! 从最近一次无组件 PRENERGY 读取第一种能量的全模型总值。",  # 说明 TOTE 的调用前提和能量序号。
        "*GET,B00_TPR,PRENERGY,0,TOTE,1",  # 获取官方总 SENE。
        "! 调用官方 PRENERGY 计算 GATE_BOTTOM_E 元素组件的 SENE 和百分比。",  # 说明组件通道输入与输出。
        "PRENERGY,SENE,GATE_BOTTOM_E",  # 生成官方组件能量缓存。
        "! 从最近一次组件 PRENERGY 读取第一个组件、第一种能量的绝对值。",  # 说明 ENG 的两个序号含义。
        "*GET,B00_GPR,PRENERGY,1,ENG,1",  # 获取官方组件 SENE。
        "! 从最近一次组件 PRENERGY 读取第一个组件、第一种能量的百分数。",  # 说明 PENG 返回单位为百分比而非小数比。
        "*GET,B00_PPR,PRENERGY,1,PENG,1",  # 获取官方组件 SENE 百分比。
        "! 清除上一阶元素表，确保当前 SET 的 SENE 不复用旧结果。",  # 说明逐阶重建 ETABLE 的必要性。
        "ETABLE,ERAS",  # 删除内存中的全部旧 ETABLE 列。
        "! 将当前阶每个已选单元的单值刚度能写入名为 B00SENE 的元素表列。",  # 说明 ETABLE 标签、项目和单值语义。
        "ETABLE,B00SENE,SENE",  # 构造独立于 PRENERGY 的单元能量通道。
        "! 在全部元素选择下汇总 B00SENE 列，得到 ETABLE 通道的全模型总 SENE。",  # 说明第一个 SSUM 的选择范围。
        "SSUM",  # 汇总当前完整选择集的元素表列。
        "! 从最近一次 SSUM 读取 B00SENE 列的全模型总和。",  # 说明 *GET 依赖最近 SSUM 缓存。
        "*GET,B00_TET,SSUM,0,ITEM,B00SENE",  # 获取 ETABLE 通道全模型总 SENE。
        "! 仅选择 GATE_BOTTOM_E 元素组件，使下一次 SSUM 只覆盖 2698 个目标单元。",  # 说明组件和总量使用同一元素表列以减少口径差异。
        "CMSEL,S,GATE_BOTTOM_E,ELEM",  # 激活目标组件元素选择集。
        "! 在组件选择下汇总同一 B00SENE 列，得到 ETABLE 通道的组件 SENE。",  # 说明第二个 SSUM 的选择范围。
        "SSUM",  # 汇总当前目标组件选择集的元素表列。
        "! 从最近一次 SSUM 读取 B00SENE 列的组件总和。",  # 说明组件 *GET 的缓存来源。
        "*GET,B00_GET,SSUM,0,ITEM,B00SENE",  # 获取 ETABLE 通道组件 SENE。
        "! 恢复全部选择，防止当前组件选择泄漏到下一阶 PRENERGY 总量。",  # 说明循环尾部选择集复位的重要性。
        "ALLSEL,ALL",  # 恢复完整模型选择集。
        "! 先复制官方总 SENE 作为闭合差分母；非正值将在后续设置错误位。",  # 说明安全分母的来源和失效处理。
        "B00_TDEN=B00_TPR",  # 初始化官方总量安全分母。
        "! 官方总 SENE 不大于零时把安全分母临时设为 1，避免在写出 REJECTED 前发生除零。",  # 说明临时值只服务诊断计算且不掩盖错误。
        "*IF,B00_TDEN,LE,0.0,THEN",  # 检查官方总量分母是否可用于除法。
        "! 使用无量纲临时值 1 继续形成诊断量；后续错误位 1 仍会强制拒绝。",  # 说明临时分母的数值和约束。
        "B00_TDEN=1.0",  # 设置防除零临时分母。
        "! 结束官方总量安全分母分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭官方总量分母条件结构。
        "! 再复制 ETABLE 总 SENE 作为组件百分比的分母；非正值将在后续设置错误位。",  # 说明第二个安全分母的来源和失效处理。
        "B00_EDEN=B00_TET",  # 初始化 ETABLE 总量安全分母。
        "! ETABLE 总 SENE 不大于零时把安全分母临时设为 1，避免组件比例除零。",  # 说明临时值不改变 fail-closed 结论。
        "*IF,B00_EDEN,LE,0.0,THEN",  # 检查 ETABLE 总量分母是否可用于除法。
        "! 使用无量纲临时值 1 继续形成诊断量；后续错误位 2 仍会强制拒绝。",  # 说明临时分母的数值和约束。
        "B00_EDEN=1.0",  # 设置防除零临时分母。
        "! 结束 ETABLE 总量安全分母分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭 ETABLE 总量分母条件结构。
        "! 以 ETABLE 安全总量计算组件百分比，单位为百分数。",  # 说明分母、分子和 100 倍换算。
        "B00_PET=100.0*B00_GET/B00_EDEN",  # 计算独立通道的组件 SENE 百分比。
        "! 计算两条总量通道的相对差，以官方安全总量为分母。",  # 说明相对差归一化口径。
        "B00_TREL=ABS(B00_TET-B00_TPR)/B00_TDEN",  # 计算全模型总 SENE 相对闭合差。
        "! 计算两条组件通道的差并用官方安全总量归一化，兼容极小组件能量。",  # 说明组件差不用组件自身作分母的原因。
        "B00_GREL=ABS(B00_GET-B00_GPR)/B00_TDEN",  # 计算组件 SENE 的全局相对闭合差。
        "! 计算两条组件百分比的绝对百分点差。",  # 说明比例差单位为百分点。
        "B00_PREL=ABS(B00_PET-B00_PPR)",  # 计算百分比闭合差。
        "! 以位掩码累计当前阶错误：1/2=总量非正，4/8=组件负值，16/32=比例越界，64/128/256=双通道不闭合。",  # 说明所有运行时错误位。
        "B00_ERR=0",  # 初始化当前阶错误码为零。
        "! 官方总 SENE 不大于零时设置错误位 1，通常表示 RSTP 未保存 VENG/SENE。",  # 说明最关键的能量可用性门禁。
        "*IF,B00_TPR,LE,0.0,THEN",  # 检查官方总能量是否为严格正值。
        "! 累加官方总量无效错误位。",  # 说明分支内赋值目的。
        "B00_ERR=B00_ERR+1",  # 设置错误位 1。
        "! 结束官方总量门禁分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭官方总量条件结构。
        "! ETABLE 总 SENE 不大于零时设置错误位 2。",  # 说明独立通道能量可用性门禁。
        "*IF,B00_TET,LE,0.0,THEN",  # 检查 ETABLE 总能量是否为严格正值。
        "! 累加 ETABLE 总量无效错误位。",  # 说明分支内赋值目的。
        "B00_ERR=B00_ERR+2",  # 设置错误位 2。
        "! 结束 ETABLE 总量门禁分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭 ETABLE 总量条件结构。
        "! 官方组件 SENE 为负时设置错误位 4；零值允许进入比例与闭合检查。",  # 说明组件能量非负约束。
        "*IF,B00_GPR,LT,0.0,THEN",  # 检查官方组件能量下界。
        "! 累加官方组件负值错误位。",  # 说明分支内赋值目的。
        "B00_ERR=B00_ERR+4",  # 设置错误位 4。
        "! 结束官方组件能量门禁分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭官方组件能量条件结构。
        "! ETABLE 组件 SENE 为负时设置错误位 8。",  # 说明独立组件通道的非负约束。
        "*IF,B00_GET,LT,0.0,THEN",  # 检查 ETABLE 组件能量下界。
        "! 累加 ETABLE 组件负值错误位。",  # 说明分支内赋值目的。
        "B00_ERR=B00_ERR+8",  # 设置错误位 8。
        "! 结束 ETABLE 组件能量门禁分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭 ETABLE 组件能量条件结构。
        "! 官方组件百分比小于零或大于 100 时分别设置错误位 16。",  # 说明百分比物理范围。
        "*IF,B00_PPR,LT,0.0,THEN",  # 检查官方百分比下界。
        "! 累加官方比例越界错误位。",  # 说明分支内赋值目的。
        "B00_ERR=B00_ERR+16",  # 设置错误位 16。
        "! 结束官方比例下界分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭官方比例下界条件结构。
        "! 官方组件百分比大于 100 时复用错误位 16。",  # 说明上界与下界共用错误类别。
        "*IF,B00_PPR,GT,100.0,THEN",  # 检查官方百分比上界。
        "! 累加官方比例越界错误位。",  # 说明分支内赋值目的。
        "B00_ERR=B00_ERR+16",  # 设置错误位 16。
        "! 结束官方比例上界分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭官方比例上界条件结构。
        "! ETABLE 组件百分比小于零或大于 100 时使用错误位 32。",  # 说明独立比例物理范围。
        "*IF,B00_PET,LT,0.0,THEN",  # 检查 ETABLE 百分比下界。
        "! 累加 ETABLE 比例越界错误位。",  # 说明分支内赋值目的。
        "B00_ERR=B00_ERR+32",  # 设置错误位 32。
        "! 结束 ETABLE 比例下界分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭 ETABLE 比例下界条件结构。
        "! ETABLE 组件百分比大于 100 时复用错误位 32。",  # 说明上界与下界共用错误类别。
        "*IF,B00_PET,GT,100.0,THEN",  # 检查 ETABLE 百分比上界。
        "! 累加 ETABLE 比例越界错误位。",  # 说明分支内赋值目的。
        "B00_ERR=B00_ERR+32",  # 设置错误位 32。
        "! 结束 ETABLE 比例上界分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭 ETABLE 比例上界条件结构。
        f"! 全模型双通道相对差大于 {CROSSCHECK_RELATIVE_TOLERANCE:.1E} 时设置错误位 64。",  # 说明总量闭合容差和错误位。
        f"*IF,B00_TREL,GT,{CROSSCHECK_RELATIVE_TOLERANCE:.1E},THEN",  # 检查总量双通道闭合。
        "! 累加总量不闭合错误位。",  # 说明分支内赋值目的。
        "B00_ERR=B00_ERR+64",  # 设置错误位 64。
        "! 结束总量闭合分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭总量闭合条件结构。
        f"! 组件双通道差占全模型总量比例大于 {CROSSCHECK_RELATIVE_TOLERANCE:.1E} 时设置错误位 128。",  # 说明组件闭合容差和归一化。
        f"*IF,B00_GREL,GT,{CROSSCHECK_RELATIVE_TOLERANCE:.1E},THEN",  # 检查组件双通道闭合。
        "! 累加组件不闭合错误位。",  # 说明分支内赋值目的。
        "B00_ERR=B00_ERR+128",  # 设置错误位 128。
        "! 结束组件闭合分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭组件闭合条件结构。
        f"! 两条百分比通道相差超过 {RATIO_PERCENTAGE_POINT_TOLERANCE:.1E} 个百分点时设置错误位 256。",  # 说明比例闭合容差和错误位。
        f"*IF,B00_PREL,GT,{RATIO_PERCENTAGE_POINT_TOLERANCE:.1E},THEN",  # 检查百分比双通道闭合。
        "! 累加比例不闭合错误位。",  # 说明分支内赋值目的。
        "B00_ERR=B00_ERR+256",  # 设置错误位 256。
        "! 结束比例闭合分支。",  # 说明结构结束位置。
        "*ENDIF",  # 关闭比例闭合条件结构。
        "! 当前阶任一错误存在时关闭 CSV、写出阶号和九项诊断量并 NOSAVE 退出。",  # 说明逐阶 fail-closed 行为。
        "*IF,B00_ERR,GT,0,THEN",  # 仅在当前阶错误位掩码非零时进入拒绝路径。
        "! 关闭结构化 CSV，确保已通过的前序阶完整落盘。",  # 说明拒绝前关闭文件的目的。
        "*CFCLOS",  # 关闭当前 CSV 命令文件句柄。
        "! 打开唯一状态文件并覆盖 RUNNING 状态。",  # 说明拒绝状态写入位置和覆盖范围。
        f"/OUTPUT,{status_stem},txt",  # 将逐阶拒绝状态写入独立输出目录。
        "! 下一条 VWRITE 与紧随格式行写出错误码、阶号、频率和能量诊断，中间不得插入注释。",  # 同时说明语法约束和字段含义。
        "*VWRITE,B00_ERR,B00_I,B00_FREQ,B00_TPR,B00_TET,B00_GPR,B00_GET,B00_PPR,B00_PET,B00_TREL,B00_GREL,B00_PREL",  # 输出十二项运行时拒绝证据。
        "('STATUS=REJECTED REASON=MODE_ENERGY_GATE CODE=',F8.0,', MODE=',F8.0,', FREQ_HZ=',E24.16,', TOTAL_PRENERGY=',E24.16,', TOTAL_ETABLE=',E24.16,', GATE_PRENERGY=',E24.16,', GATE_ETABLE=',E24.16,', PCT_PRENERGY=',E24.16,', PCT_ETABLE=',E24.16,', TOTAL_REL=',E24.16,', GATE_REL=',E24.16,', PCT_DELTA=',E24.16)",  # 使用双精度科学计数格式保留诊断精度。
        "! 恢复主输出，使退出摘要和求解器错误计数留在唯一 OUT。",  # 说明输出通道恢复目的。
        "/OUTPUT",  # 关闭状态重定向并恢复主 OUT。
        "! 清除内存 ETABLE，避免拒绝退出时保留无意义工作状态。",  # 说明内存清理目的且不涉及源文件。
        "ETABLE,ERAS",  # 清除元素表列。
        "! 离开 POST1，不保存当前 SET 或选择状态。",  # 说明处理器退出语义。
        "FINISH",  # 返回 Begin 层级。
        "! 以 NOSAVE 终止，保证 modal.db、RSTP 和 MODE 不被写回。",  # 说明退出保护作用。
        "/EXIT,NOSAVE",  # 终止未来批处理且不保存数据库。
        "! 结束当前阶拒绝分支；通过时继续写入 CSV。",  # 说明控制流合流位置。
        "*ENDIF",  # 关闭逐阶拒绝条件结构。
        "! 下一条 VWRITE 与紧随格式行写入当前阶十二列数值，中间不得插入注释。",  # 同时说明 CSV 行语法约束和列数。
        "*VWRITE,B00_I,B00_LS,B00_SB,B00_FREQ,B00_TPR,B00_GPR,B00_PPR,B00_TET,B00_GET,B00_PET,B00_TREL,B00_GREL",  # 写入当前阶闭合后的结构化结果。
        "(F8.0,2(',',F8.0),9(',',E24.16))",  # 使用三个整数列和九个 E24.16 浮点列形成纯数值 CSV。
        "! 结束当前阶循环并进入下一阶，直至 59 阶全部通过。",  # 说明循环结构结束位置和完成条件。
        "*ENDDO",  # 关闭逐阶模态循环。
        "! 关闭完成的 CSV，确保全部 59 行和表头落盘。",  # 说明成功路径的文件关闭操作。
        "*CFCLOS",  # 关闭 CSV 命令文件句柄。
        "! 清除最后一阶 ETABLE 并恢复全部选择，保持退出前内存状态整洁。",  # 说明内存清理与选择复位。
        "ETABLE,ERAS",  # 删除最后一阶元素表列。
        "! 恢复全部节点和单元选择。",  # 说明选择集复位作用。
        "ALLSEL,ALL",  # 恢复完整模型选择集。
        "! 打开唯一状态文件并覆盖 RUNNING，只有全部 59 阶通过才执行此段。",  # 说明完成状态的严格前置条件。
        f"/OUTPUT,{status_stem},txt",  # 将完成状态写入独立输出目录。
        "! 下一条 VWRITE 与紧随格式行写出完成阶数和组件数量，中间不得插入注释。",  # 同时说明完成证据语法约束。
        "*VWRITE,B00_NSET,B00_GCNT",  # 输出结果集数和组件单元数两个闭合量。
        "('STATUS=COMPLETED GATE=ALL_MODES_DUAL_SENE_CLOSED MODES=',F8.0,', GATE_ELEMENT_COUNT=',F12.0)",  # 形成唯一可机器解析的完成行。
        "! 恢复主输出，使正常退出和最终错误计数留在唯一 OUT。",  # 说明输出通道恢复目的。
        "/OUTPUT",  # 关闭状态重定向并恢复主 OUT。
        "! 离开 POST1，所有结果已写入独立文本而内存数据库从未保存。",  # 说明成功路径处理器退出语义。
        "FINISH",  # 返回 Begin 层级。
        "! 正常结束只读后处理；NOSAVE 是保护 B00 二进制的最终硬约束。",  # 说明最终退出参数的作用。
        "/EXIT,NOSAVE",  # 终止未来批处理且绝不写回数据库。
    ]  # 结束只读 APDL 行集合。
    return "\n".join(lines) + "\n"  # 以 LF 和末尾换行形成稳定、可哈希的 APDL 文本。


def static_gate_apdl(apdl_text: str) -> dict[str, Any]:  # 静态验证生成 APDL 只含允许的后处理路径。
    """返回命令计数和布尔门禁；出现求解、保存或覆盖命令时拒绝。"""  # 函数说明明确输入、输出和失败条件。
    forbidden_pattern = re.compile(r"(?im)^\s*(?:/SOLU\b|SOLVE(?:\s*,|\s*$)|ANTYPE(?:\s*,|\s*$)|SAVE(?:\s*,|\s*$)|RESWRITE(?:\s*,|\s*$)|RSTCREATE(?:\s*,|\s*$)|EXPASS(?:\s*,|\s*$)|MODOPT(?:\s*,|\s*$)|MXPAND(?:\s*,|\s*$)|/DELETE\b|/COPY\b|/RENAME\b)")  # 匹配所有被禁止的执行、保存和文件变更命令行。
    forbidden_matches = [match.group(0).strip() for match in forbidden_pattern.finditer(apdl_text)]  # 收集实际命中项便于失败诊断。
    require(not forbidden_matches, f"生成 APDL 含禁用命令：{forbidden_matches}")  # 任一禁用命令都拒绝封板。
    required_fragments = ["RESUME,", "/POST1", "FILE,", "SET,1,B00_I", "PRENERGY,SENE", "PRENERGY,SENE,GATE_BOTTOM_E", "ETABLE,B00SENE,SENE", "SSUM", "CMSEL,S,GATE_BOTTOM_E,ELEM", "*GET,B00_TPR,PRENERGY,0,TOTE,1", "*GET,B00_GPR,PRENERGY,1,ENG,1", "*GET,B00_PPR,PRENERGY,1,PENG,1", "*GET,B00_TET,SSUM,0,ITEM,B00SENE", "*GET,B00_GET,SSUM,0,ITEM,B00SENE", "/EXIT,NOSAVE"]  # 列出双通道和只读退出所需的关键片段。
    missing_fragments = [fragment for fragment in required_fragments if fragment not in apdl_text]  # 收集任何缺失的必要片段。
    require(not missing_fragments, f"生成 APDL 缺少必要片段：{missing_fragments}")  # 必要后处理步骤不完整时拒绝封板。
    require(BASE_JOB_STEM in apdl_text, "生成 APDL 未绑定固定 B00 结果文件前缀")  # 防止读取错误结果族。
    require(BASE_MODAL_DB_STEM in apdl_text, "生成 APDL 未绑定固定 B00 modal.db")  # 防止恢复错误数据库。
    return {  # 返回可封板的静态命令计数和保护事实。
        "passed": True,  # 表示所有静态 APDL 门禁通过。
        "forbidden_command_matches": forbidden_matches,  # 应为空列表，便于机器复核。
        "resume_command_count": len(re.findall(r"(?im)^\s*RESUME,", apdl_text)),  # 记录只读数据库恢复命令数量。
        "post1_command_count": len(re.findall(r"(?im)^\s*/POST1\s*$", apdl_text)),  # 记录 POST1 入口数量。
        "file_rstp_command_count": len(re.findall(r"(?im)^\s*FILE,.*,'rstp'\s*$", apdl_text)),  # 记录 RSTP 文件绑定数量。
        "prenergy_command_count": len(re.findall(r"(?im)^\s*PRENERGY,SENE", apdl_text)),  # 记录官方总量和组件量命令数量。
        "etable_sene_command_count": len(re.findall(r"(?im)^\s*ETABLE,B00SENE,SENE\s*$", apdl_text)),  # 记录独立元素能量通道数量。
        "ssum_command_count": len(re.findall(r"(?im)^\s*SSUM\s*$", apdl_text)),  # 记录全模型与组件 SSUM 命令数量。
        "exit_nosave_count": len(re.findall(r"(?im)^\s*/EXIT,NOSAVE\s*$", apdl_text)),  # 记录所有成功和失败路径的无保存退出数量。
        "contains_solution_processor": False,  # 明确静态扫描未发现 SOLUTION 入口。
        "contains_solve": False,  # 明确静态扫描未发现 SOLVE。
        "contains_save": False,  # 明确静态扫描未发现 SAVE。
        "mapdl_execution_attempted": False,  # 明确静态验证没有启动 MAPDL。
    }  # 结束 APDL 静态门禁对象。


def powershell_quote(value: str) -> str:  # 将参数转换为 PowerShell 单引号字面量而不执行。
    """返回可复制到 PowerShell 的单个安全字面量；输入中的单引号按规则加倍。"""  # 函数说明明确输入、输出和非执行语义。
    return "'" + value.replace("'", "''") + "'"  # 使用 PowerShell 单引号转义规则生成纯文本参数。


def build_launch_command(argv: list[str], main_output: Path) -> str:  # 生成证据性未来命令文本而不调用进程 API。
    """返回带状态头和 PowerShell 命令的文本；绝不执行 argv。"""  # 函数说明明确输入、输出和安全边界。
    command = "& " + " ".join(powershell_quote(item) for item in argv)  # 将固定 argv 转成可人工复核的 PowerShell 命令行。
    lines = [  # 以键值头部记录非执行状态、保护策略和预期主输出。
        "STATUS=PREPARED_NOT_STARTED",  # 表示只完成输入与命令封板。
        "MAPDL_EXECUTION_ATTEMPTED=false",  # 明确本工具从未启动 MAPDL。
        "PROCESS_STARTED=false",  # 明确本工具从未创建任何外部进程。
        "BASELINE_ACCESS_POLICY=READ_ONLY_ABSOLUTE_PATH",  # 明确 B00 二进制只通过绝对路径读取。
        "BASELINE_MUTATION_POLICY=NO_COPY_NO_MOVE_NO_DELETE_NO_SAVE",  # 明确不复制、不移动、不删除、不保存回 B00。
        "RESOURCE_POLICY=RECHECK_4_GIB_MEMORY_AND_2_GIB_DISK_BEFORE_MANUAL_LAUNCH",  # 规定人工启动前重查资源门槛。
        f"EXPECTED_UNIQUE_MAIN_OUTPUT={main_output.resolve()}",  # 记录唯一且不在 B00 中的未来 OUT 路径。
        "FUTURE_SMP1_COMMAND_BEGIN",  # 标记未来命令起始边界。
        command,  # 写入只供人工审核和未来显式执行的单进程命令。
        "FUTURE_SMP1_COMMAND_END",  # 标记未来命令结束边界。
        "THIS_FILE_WAS_NOT_EXECUTED_BY_ULTRA_B00_GATE_ENERGY_PREPARE",  # 再次声明本文件仅为证据。
    ]  # 结束启动命令文本行。
    return "\n".join(lines) + "\n"  # 以 LF 和末尾换行形成稳定文本。


def build_readme(run_name: str, input_name: str, csv_name: str, status_name: str, main_output_name: str, source_audit: dict[str, Any]) -> str:  # 生成人工可读门禁与完成判据。
    """返回准备包 README；逐项解释 JSON 配置、资源和运行时 fail-closed 规则。"""  # 函数说明满足 JSON 配套说明要求。
    explicit_veng = source_audit["explicit_veng_after_final_all_none"]  # 提取已识别的 VENG 静态风险布尔值用于说明。
    lines = [  # 组织简洁但完整的人工审计说明。
        "# B00 GATE_BOTTOM_E 模态应变能只读后处理准备包",  # 文档标题明确对象和只读性质。
        "",  # 空行分隔标题与正文以满足 Markdown 渲染规则。
        f"准备目录：{run_name}。本工具只生成输入、独立输出目录和未来 launch_command；没有启动 MAPDL。",  # 说明目录和当前执行状态。
        "",  # 空行分隔段落。
        "## 静态门禁",  # 静态门禁章节标题。
        "",  # 空行分隔标题与列表。
        f"- 基线固定为 {BASELINE_RUN.resolve()}，不按最新目录漂移。",  # 说明固定来源路径。
        f"- modal.db、主 RSTP/MODE 及四个 DMP 分区伴随文件共 {len(EXPECTED_BINARY_SPECS)} 项逐字节校验尺寸与 SHA-256。",  # 说明完整二进制门禁范围。
        f"- 原导出清单必须闭合为 {EXPECTED_MODE_COUNT} 阶，GATE_BOTTOM_E 必须为 ELEM 组件且静态数量为 {EXPECTED_GATE_ELEMENT_COUNT}。",  # 说明阶数与组件门禁。
        "- 生成 APDL 必须含 RESUME、POST1、FILE/RSTP、逐阶 SET、PRENERGY 和 ETABLE/SSUM；不得含 SOLU、SOLVE、ANTYPE、SAVE、RESWRITE、RSTCREATE、EXPASS、MODOPT、MXPAND 或文件删除/复制/改名命令。",  # 说明允许与禁止命令边界。
        "- 新 jobname、主 OUT、CSV 和状态文件均含唯一 UTC 标识且位于独立 output 目录，不与 B00 文件同名。",  # 说明不可覆盖门禁。
        "- 源二进制不复制、不移动、不删除、不改属性；准备结束前再次比较其字节数和纳秒修改时间。",  # 说明源保护复核。
        "",  # 空行分隔章节。
        "## 已知静态风险",  # 风险章节标题。
        "",  # 空行分隔标题与正文。
        f"原模态输入在 MXPAND,80,,,YES 后执行 OUTRES,ALL,NONE，再只执行 OUTRES,NSOL,ALL；在最后一次 ALL,NONE 后显式 VENG={explicit_veng}。因此现有 RSTP 是否真正含 SENE 不能由静态检查宣称成功。",  # 说明高风险的直接证据和结论边界。
        "若运行时 PRENERGY 或 ETABLE/SSUM 得到非正总 SENE，状态必须为 REJECTED；不得从位移文件臆造组件能量。若确实缺少 VENG，下一轮模态求解应在 ALL,NONE 后显式增加 OUTRES,VENG,ALL，并重新生成 RSTP。",  # 说明缺记录时的唯一合规处置。
        "",  # 空行分隔章节。
        "## 预期资源",  # 资源章节标题。
        "",  # 空行分隔标题与列表。
        f"- MAPDL v261，SMP 单进程 {PROCESS_COUNT} 个；不使用 DMP 分区写出。",  # 说明运行模式与进程数。
        f"- 最低可用物理内存 {MINIMUM_MEMORY_BYTES / 1024**3:.0f} GiB，舒适参考 {COMFORTABLE_MEMORY_BYTES / 1024**3:.0f} GiB。",  # 说明内存门槛和单位。
        f"- 独立输出卷最低剩余空间 {MINIMUM_DISK_BYTES / 1024**3:.0f} GiB；源二进制零复制，预计文本输出不超过 {EXPECTED_OUTPUT_BYTES_MAX / 1024**2:.0f} MiB。",  # 说明磁盘门槛与零复制影响。
        f"- 逐阶处理 {EXPECTED_MODE_COUNT} 个结果集，每阶扫描全模型单元一次并扫描 GATE_BOTTOM_E 选择集；实际耗时取决于 RSTP 缓存和存储速度。",  # 说明主要计算负载和不承诺固定时长。
        "",  # 空行分隔章节。
        "## 实际运行时完成判据",  # 完成判据章节标题。
        "",  # 空行分隔标题与列表。
        f"- 唯一主输出 {main_output_name} 的 MAPDL 汇总 ERROR 必须为 0；WARNING 必须逐条人工复核。",  # 说明主 OUT 判据。
        f"- 唯一状态文件 {status_name} 必须且只能以 STATUS=COMPLETED 开头，并记录 MODES={EXPECTED_MODE_COUNT} 与 GATE_ELEMENT_COUNT={EXPECTED_GATE_ELEMENT_COUNT}。",  # 说明状态文件判据。
        f"- 唯一 CSV {csv_name} 必须恰有 1 行表头和 {EXPECTED_MODE_COUNT} 行数据，mode_index 连续为 1 至 {EXPECTED_MODE_COUNT}，频率严格递增。",  # 说明结构化数据行数和序列判据。
        "- 每阶两条总 SENE 均严格为正、两条组件 SENE 均非负、两条组件比例均在 0 至 100%。",  # 说明物理范围判据。
        f"- PRENERGY 与 ETABLE/SSUM 的总量相对差及组件差除以总量均不得超过 {CROSSCHECK_RELATIVE_TOLERANCE:.1E}，比例差不得超过 {RATIO_PERCENTAGE_POINT_TOLERANCE:.1E} 个百分点。",  # 说明双通道数值闭合判据。
        "- 运行前后重新计算全部十一项 B00 源二进制 SHA-256，必须与 input/source_binary_manifest.json 完全一致；任何变化都判失败。",  # 说明运行后的源保护判据。
        "",  # 空行分隔章节。
        "## 文件角色",  # 文件角色章节标题。
        "",  # 空行分隔标题与列表。
        f"- input/{input_name}：唯一只读 APDL 输入。",  # 说明 APDL 文件用途。
        "- input/source_binary_manifest.json：十一项 B00 二进制的绝对路径、字节数和摘要；JSON 字段逐项由本 README 说明。",  # 说明 JSON 配套文档作用。
        "- qa/static_gate.json：静态命令计数、禁用命令扫描和资源快照；JSON 字段逐项由静态门禁与预期资源章节说明。",  # 说明静态 QA 文件用途。
        "- launch_command.txt：未来人工启动命令证据，当前状态固定为 PREPARED_NOT_STARTED。",  # 说明命令文件用途和当前状态。
        "",  # 空行分隔章节。
        "## 官方语法依据",  # 官方依据章节标题。
        "",  # 空行分隔标题与列表。
        "- PRENERGY 与 *GET/PRENERGY：Ansys 2026 R1 Command Reference, Hlp_C_PRENERGY.html 与 Hlp_C_GET.html。",  # 说明官方总量、组件量和比例的依据。
        "- ETABLE/SENE、SSUM 与 *GET/SSUM：Ansys 2026 R1 Command Reference, Hlp_C_ETABLE.html、Hlp_C_SSUM.html 与 Hlp_C_GET.html。",  # 说明独立求和通道依据。
        "- FILE/RSTP 与线性扰动模态：Ansys 2026 R1 Command Reference 和 Structural Analysis Guide。",  # 说明结果文件读取路径依据。
        "- OUTRES/VENG：Ansys Command Reference 将 VENG 定义为元素能量；ALL,NONE 的后续顺序决定能量记录是否写入。",  # 说明已知风险判断依据。
    ]  # 结束 README 文本行。
    return "\n".join(lines) + "\n"  # 返回带末尾换行的 UTF-8 Markdown 文本。


def write_artifact_ledger(run_dir: Path) -> None:  # 为所有准备产物生成不包含自身的 SHA-256 清单。
    """扫描 run_dir 下普通文件并写 artifact_hashes.sha256；该调用后不得再改写产物。"""  # 函数说明明确输入、输出和调用顺序约束。
    ledger_path = run_dir / "artifact_hashes.sha256"  # 固定账本文件位于准备目录根层级。
    require(not ledger_path.exists(), f"拒绝覆盖既有产物账本：{ledger_path}")  # 在扫描前确保账本尚不存在。
    files = sorted(path for path in run_dir.rglob("*") if path.is_file())  # 按相对路径稳定排序全部现有普通文件。
    lines: list[str] = []  # 初始化账本行集合。
    for path in files:  # 逐文件计算封板摘要。
        relative = path.relative_to(run_dir).as_posix()  # 使用跨工具稳定的正斜杠相对路径。
        lines.append(f"{sha256_file(path)}  {relative}")  # 形成标准 SHA-256 双空格清单行。
    write_new_text(ledger_path, "\n".join(lines) + "\n")  # 最后写入账本并拒绝任何覆盖。


def prepare_run() -> Path:  # 执行全部只读验证并创建唯一、独立、不可覆盖的准备包。
    """返回新准备目录绝对路径；仅写新目录，不启动进程、不改 B00。"""  # 函数说明明确输入为空、输出和副作用边界。
    source_audit, source_stats = validate_baseline()  # 在创建任何新目录前完成全部 B00 来源门禁和哈希。
    created = datetime.now(timezone.utc)  # 获取带时区的当前 UTC 时间用于唯一标识和审计。
    timestamp = created.strftime("%Y%m%dT%H%M%S%fZ")  # 生成包含微秒的文件系统安全 UTC 标识。
    suffix = secrets.token_hex(1)  # 生成两位十六进制随机后缀规避同微秒碰撞。
    run_name = f"{RUN_PREFIX}_{timestamp}_{suffix}"  # 组合不可与 B00 主目录相同的新准备目录名。
    run_dir = ULTRA_RUNS_ROOT / run_name  # 在 ultra_runs 下解析唯一准备目录。
    require(not run_dir.exists(), f"拒绝覆盖既有准备目录：{run_dir}")  # 目录存在时立即失败而不复用。
    input_dir = run_dir / "input"  # 独立输入目录只存 APDL 和源二进制清单。
    output_dir = run_dir / "output"  # 独立输出目录作为未来 MAPDL 工作目录且初始不含主输出。
    qa_dir = run_dir / "qa"  # 独立 QA 目录存静态门禁和资源快照。
    snapshot_dir = run_dir / "orchestrator_snapshot"  # 独立 lineage 目录存当前准备工具源码快照。
    input_dir.mkdir(parents=True, exist_ok=False)  # 原子创建 run 根和 input，禁止复用既有路径。
    output_dir.mkdir(exist_ok=False)  # 创建空的独立 MAPDL 工作目录。
    qa_dir.mkdir(exist_ok=False)  # 创建静态 QA 目录。
    snapshot_dir.mkdir(exist_ok=False)  # 创建工具源码快照目录。
    short_time = created.strftime("%m%dt%H%M%S")  # 生成紧凑月日时分秒字段控制 MAPDL jobname 长度。
    jobname = f"{JOB_PREFIX}_{short_time}_{suffix}"  # 构造包含唯一时间和随机后缀的新 jobname。
    require(len(jobname) <= 32, f"MAPDL jobname 超过 32 字符：{jobname}")  # 遵守 MAPDL jobname 长度约束。
    csv_stem = f"b00_gate_bottom_energy_{timestamp}_{suffix}"  # 构造唯一结构化能量输出无扩展名文件干。
    status_stem = f"b00_gate_bottom_energy_status_{timestamp}_{suffix}"  # 构造唯一运行时状态无扩展名文件干。
    input_name = f"b00_gate_bottom_energy_post_{timestamp}_{suffix}.inp"  # 构造唯一 APDL 输入文件名。
    main_output_name = f"b00_gate_bottom_energy_{timestamp}_{suffix}.out"  # 构造唯一 MAPDL 主输出文件名。
    csv_name = f"{csv_stem}.csv"  # 形成未来唯一 CSV 文件名。
    status_name = f"{status_stem}.txt"  # 形成未来唯一状态文件名。
    input_path = input_dir / input_name  # 解析独立 APDL 输入绝对路径。
    main_output = output_dir / main_output_name  # 解析独立且唯一的未来主 OUT 路径。
    expected_csv = output_dir / csv_name  # 解析独立且唯一的未来 CSV 路径。
    expected_status = output_dir / status_name  # 解析独立且唯一的未来状态路径。
    require(not main_output.exists() and not expected_csv.exists() and not expected_status.exists(), "未来输出目标在准备前已存在")  # 防止任何新目录内的意外覆盖。
    require(BASELINE_RUN.resolve() not in main_output.resolve().parents, "未来主输出错误地位于 B00 基线内")  # 硬性隔离主 OUT 与 B00。
    apdl_text = build_apdl(csv_stem, status_stem)  # 生成双通道逐阶只读 APDL 文本。
    apdl_gate = static_gate_apdl(apdl_text)  # 在写入前静态拒绝任何求解、保存或文件变更命令。
    write_new_text(input_path, apdl_text)  # 将已通过门禁的 APDL 写入独立 input 目录。
    write_new_json(input_dir / "source_binary_manifest.json", source_audit)  # 写入不支持注释的源二进制机器清单。
    write_new_text(snapshot_dir / SCRIPT_PATH.name, SCRIPT_PATH.read_text(encoding="utf-8"))  # 快照本工具源码用于 lineage 复核。
    memory = memory_snapshot()  # 记录准备瞬间内存快照但不据此自动执行。
    disk = disk_snapshot()  # 记录准备瞬间目标卷空间但不据此自动执行。
    argv = [str(MAPDL_EXE.resolve()), "-b", "-smp", "-np", str(PROCESS_COUNT), "-j", jobname, "-dir", str(output_dir.resolve()), "-i", str(input_path.resolve()), "-o", str(main_output.resolve())]  # 构造未来单进程命令参数列表但不调用。
    launch_text = build_launch_command(argv, main_output)  # 生成只供人工审核的未来命令文本。
    write_new_text(run_dir / "launch_command.txt", launch_text)  # 写入证据性命令文件且不执行。
    static_gate = {  # 汇总 APDL 门禁、路径隔离、资源和非执行事实。
        "schema_version": 1,  # 静态门禁 JSON 当前模式版本为 1。
        "generated_utc": created.isoformat(),  # 记录准备 UTC 时间并保留微秒和时区。
        "run_name": run_name,  # 记录唯一准备目录名。
        "apdl_gate": apdl_gate,  # 嵌入禁用命令扫描和关键命令计数。
        "source_gate_passed": True,  # 表示十一项 B00 二进制和文本证据全部通过。
        "unique_output_gate_passed": True,  # 表示主 OUT、CSV、状态文件均为新路径且不在 B00 内。
        "baseline_mutation_attempted": False,  # 明确工具未调用复制、移动、删除、改属性或保存操作。
        "mapdl_execution_attempted": False,  # 明确工具未启动 MAPDL。
        "process_started": False,  # 明确工具未创建任何外部进程。
        "memory_snapshot": memory,  # 记录未来人工运行前仍需重查的内存状态。
        "disk_snapshot": disk,  # 记录未来人工运行前仍需重查的磁盘状态。
        "runtime_sene_availability_unproven": True,  # 明确静态准备不能宣称现有 RSTP 含 SENE。
        "runtime_fail_closed_on_nonpositive_total_sene": True,  # 明确运行时两条总量通道任一非正即拒绝。
    }  # 结束静态门禁对象。
    write_new_json(qa_dir / "static_gate.json", static_gate)  # 写入机器可读静态 QA，不向 JSON 插入注释。
    readme = build_readme(run_name, input_name, csv_name, status_name, main_output_name, source_audit)  # 生成人工可读配置与判据说明。
    write_new_text(run_dir / "README.md", readme)  # 写入配套 Markdown 逐项解释 JSON 和运行规则。
    manifest = {  # 构造准备包根 manifest 记录路径、预期产物和未来命令。
        "schema_version": 1,  # 根 manifest 当前模式版本为 1。
        "run_id": "B00_GATE_BOTTOM_ENERGY_READ_ONLY_POST",  # 标识本包为 B00 门架下横梁能量只读后处理。
        "run_name": run_name,  # 记录唯一准备目录名。
        "created_utc": created.isoformat(),  # 记录准备时间并保留微秒与 UTC 时区。
        "status": "PREPARED_NOT_STARTED",  # 当前只完成准备，绝不表示 MAPDL 或能量导出完成。
        "prepare_only": True,  # 明确工具职责只有准备。
        "mapdl_execution_attempted": False,  # 明确没有启动 MAPDL。
        "process_started": False,  # 明确没有启动外部进程。
        "baseline_run": str(BASELINE_RUN.resolve()),  # 记录固定 B00 基线路径。
        "baseline_job_stem": BASE_JOB_STEM,  # 记录源结果文件前缀。
        "baseline_modal_db": str(BASE_MODAL_DB.resolve()),  # 记录只读恢复数据库绝对路径。
        "baseline_rstp": str(BASE_RSTP.resolve()),  # 记录只读结果主文件绝对路径。
        "baseline_mode": str(BASE_MODE.resolve()),  # 记录只读 MODE 伴随文件绝对路径。
        "baseline_binary_count": len(EXPECTED_BINARY_SPECS),  # 记录封板二进制总数为十一项。
        "baseline_binary_copy_bytes": 0,  # 记录零复制策略没有新增大型文件。
        "jobname": jobname,  # 记录与 B00 不同的未来 MAPDL jobname。
        "parallel_mode": "SMP",  # 记录未来后处理使用共享内存模式。
        "processes": PROCESS_COUNT,  # 记录未来后处理固定单进程。
        "main_input": str(input_path.resolve()),  # 记录唯一 APDL 输入绝对路径。
        "expected_main_output": str(main_output.resolve()),  # 记录唯一 MAPDL OUT 绝对路径。
        "expected_energy_csv": str(expected_csv.resolve()),  # 记录唯一结构化能量 CSV 绝对路径。
        "expected_status_file": str(expected_status.resolve()),  # 记录唯一运行时状态绝对路径。
        "expected_mode_count": EXPECTED_MODE_COUNT,  # 记录运行时必须闭合的 59 阶。
        "expected_gate_element_count": EXPECTED_GATE_ELEMENT_COUNT,  # 记录运行时必须闭合的 2698 个单元。
        "runtime_completion_gate": "STATUS_COMPLETED_AND_59_ROWS_AND_ZERO_MAPDL_ERRORS_AND_DUAL_CHANNEL_TOLERANCES_AND_SOURCE_HASHES_UNCHANGED",  # 以单一字符串概括完成定义。
        "future_launch_argv": argv,  # 记录未经执行的未来 argv 数组。
        "launch_command_file": "launch_command.txt",  # 记录人工命令文件相对路径。
        "static_gate_file": "qa/static_gate.json",  # 记录机器静态门禁相对路径。
        "source_binary_manifest": "input/source_binary_manifest.json",  # 记录源二进制清单相对路径。
        "orchestrator_snapshot": f"orchestrator_snapshot/{SCRIPT_PATH.name}",  # 记录工具源码快照相对路径。
    }  # 结束根 manifest 对象。
    write_new_json(run_dir / "manifest.json", manifest)  # 写入根机器清单且不向 JSON 插入非法注释。
    verify_source_stats_unchanged(source_stats)  # 在封板完成前再次证明所有 B00 二进制大小和修改时间未变。
    write_artifact_ledger(run_dir)  # 最后生成所有准备产物的摘要账本，此后不再写 run 目录。
    return run_dir.resolve()  # 返回已完整封板的新准备目录绝对路径。


def main() -> int:  # 定义无参数 prepare-only 命令行入口并返回标准进程码。
    """成功准备返回 0；任一静态门禁失败返回 2；不会启动 MAPDL。"""  # 函数说明明确输出码和绝对安全边界。
    try:  # 捕获所有门禁、哈希、路径和写入异常以输出单行失败原因。
        run_dir = prepare_run()  # 执行只读校验与新目录封板，不调用任何外部进程。
    except Exception as exc:  # 任一异常均进入统一失败路径且不伪造成功状态。
        print(f"B00 GATE_BOTTOM_E prepare-only FAILED: {exc}")  # 向标准输出报告具体失败原因供人工处理。
        return 2  # 返回非零码表示没有形成可接受的准备包。
    print(f"B00 GATE_BOTTOM_E prepare-only completed without MAPDL execution: {run_dir}")  # 报告新目录和未执行事实。
    return 0  # 返回零仅表示准备封板完成，不表示能量记录存在或工程判定通过。


if __name__ == "__main__":  # 只有直接运行本脚本时才进入 prepare-only 主流程。
    raise SystemExit(main())  # 将标准返回码交给操作系统；导入模块时无任何写入或执行。
