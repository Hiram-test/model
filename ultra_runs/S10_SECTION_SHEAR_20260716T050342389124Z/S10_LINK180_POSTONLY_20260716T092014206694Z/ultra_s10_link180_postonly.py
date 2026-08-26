"""为固定 S10 运行执行只读 LINK180 轴力审计，并生成可由最终化器直接复核的完整证据包。"""  # 模块只启动 POST1-only SMP1 会话，禁止结构求解、数据库保存和源结果修改。

from __future__ import annotations  # 启用延迟类型注解，避免复杂容器注解在导入阶段产生兼容性副作用。

import argparse  # 构造仅接受零业务参数的 CLI，使 --help 和未知参数在任何文件或 MAPDL 操作前退出。
import csv  # 解析 MAPDL 写出的无标题两列轴力 CSV，并核对行数、唯一性和有限数值。
import hashlib  # 流式计算输入、源 DB/RST、输出和审计包全部文件的 SHA-256。
import json  # 生成合法的 preflight、postflight 和 qa_summary JSON 机器证据。
import math  # 拒绝轴力 CSV 中的 NaN、无穷值和其他非有限数值。
import re  # 扫描 APDL 禁止命令、MAPDL 警告错误标记和机器摘要键值。
import shutil  # 仅在失败路径安全清理本次隐藏 staging 目录，绝不删除正式审计目录。
import subprocess  # 以隐藏、低优先级、SMP1 批处理方式启动独立 MAPDL POST1 会话。
from datetime import datetime, timezone  # 生成 UTC 审计目录名和 ISO-8601 证据时间。
from pathlib import Path  # 统一处理固定 run、独立审计目录和相对源路径。
from typing import Any  # 描述 JSON 动态对象和证据汇总字典。


SCRIPT_PATH = Path(__file__).resolve()  # 固定当前审计编排器源码绝对路径，供身份记录和最终账本使用。
TOOLS_DIR = SCRIPT_PATH.parent  # ultra_tools 是当前脚本所在的唯一源码目录。
PROJECT_ROOT = TOOLS_DIR.parent  # V2.0 项目根目录承载固定 ultra_runs。
RUN_NAME = "S10_SECTION_SHEAR_20260716T050342389124Z"  # 本脚本只允许审计这一已完成的 S10 正式运行。
RUN_DIR = PROJECT_ROOT / "ultra_runs" / RUN_NAME  # 指向固定 S10 运行目录。
SOLVER_DIR = RUN_DIR / "solver"  # solver 目录只读承载 S10 平衡 DB 和静力 RST。
JOBNAME = "cw_S10_0716t050342_a4"  # 固定原 S10 MAPDL 作业名，禁止通配选择其他结果。
EQ_DB_PATH = SOLVER_DIR / f"{JOBNAME}_eq.db"  # LS2 平衡数据库是只读 RESUME 源。
STATIC_RST_PATH = SOLVER_DIR / f"{JOBNAME}.rst"  # 合并静力 RST 是只读 POST1 结果源。
MAPDL_EXE = Path(r"D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe")  # 固定本机 ANSYS 2026 R1 MAPDL 可执行文件。
EXPECTED_LINK_COUNT = 73_692  # TYPE4 LINK180 冻结数量必须与 S10 拓扑统计完全一致。
EXPECTED_LOAD_STEP = 2  # 轴力审计必须读取模态扰动所用的 LS2 保持步。
EXPECTED_RESULT_SUBSTEP = 1  # LS2 最后结果集冻结为第 1 子步，QA 必须记录实测值并与此比较。
EXPECTED_RESULT_TIME = 1.001  # LS2 保持步伪时间固定为 1.001。
RESULT_TIME_TOLERANCE = 1.0e-12  # 结果集伪时间比较采用 1e-12 绝对容差，覆盖文本转浮点舍入且不放宽结果集身份。
FORCE_ABSOLUTE_TOLERANCE_N = 1.0e-6  # CSV 与 MAPDL 摘要轴力比较的最小绝对容差为 1e-6 N。
FORCE_RELATIVE_TOLERANCE = 1.0e-12  # 大轴力比较采用 1e-12 相对容差，保持双精度输出的一致性要求。
EXPECTED_DIAGNOSTIC_COUNT = 0  # warning、error、fatal、负主元和零主元的允许计数均为零。
EXPECTED_SUMMARY_COUNT = 0  # MAPDL 退出摘要中 warning 与 error 的允许值均为零。
EXPECTED_NONPOSITIVE_COUNT = 0  # LINK180 非正轴力允许数量为零，任一非正记录均阻断通过。
EXPECTED_ACTIVE_PROCESS_COUNT = 0  # 启动前和退出后允许存在的 MAPDL/MPI/Hydra 活动求解进程数为零。
NONPOSITIVE_FORCE_LIMIT_N = 0.0  # 轴力小于或等于 0 N 归入非正失败集合，严格正值才表示索单元保持受拉。
MAPDL_GATE_PASS_VALUE = 1  # MAPDL 内部门禁仅以整数 1 表示数量闭合且非正轴力为零。
MAPDL_PROCESS_COUNT = 1  # POST1-only 固定使用一个 SMP 进程，避免并行后处理引入额外文件和诊断口径。
EVIDENCE_SCHEMA_VERSION = 2  # preflight、postflight 与 qa_summary 使用第二版字段结构。
SUCCESS_EXIT_CODE = 0  # Python CLI 与 MAPDL 子进程的成功退出码均为零。
FAILURE_EXIT_CODE = 2  # Python CLI 的 fail-closed 业务失败退出码固定为二。
AUDIT_PREFIX = "S10_LINK180_POSTONLY_"  # 独立审计目录使用固定前缀供最终化器安全选择。
POST_JOBNAME = "s10_link180_post"  # POST1-only 作业名采用短 ASCII 名，避免覆盖原 S10 作业文件。
INPUT_NAME = "s10_link180_post_only.inp"  # APDL 只读审计输入使用固定安全文件名。
OUT_NAME = f"{POST_JOBNAME}.out"  # 主 OUT 固定由 -o 参数写入独立审计目录。
ERR_NAME = f"{POST_JOBNAME}.err"  # MAPDL ERR 固定由作业名生成在独立审计目录。
CSV_NAME = "s10_link180_axial_force_n.csv"  # 纯数值轴力表固定为 element_id 与 axial_force_n 两列。
SUMMARY_NAME = "s10_link180_summary.txt"  # MAPDL 机器摘要记录数量、极值、载荷步和时间。
PREFLIGHT_NAME = "preflight.json"  # 启动前输入安全、进程和源文件身份写入固定 JSON。
POSTFLIGHT_NAME = "postflight_source_integrity.json"  # 执行后源文件前后身份比较写入固定 JSON。
QA_NAME = "qa_summary.json"  # 最终机器门禁写入固定 JSON。
QA_REPORT_NAME = "qa_report.md"  # 用户可读审计结论写入固定 Markdown。
FIELD_DICTIONARY_NAME = "field_dictionary.md"  # JSON/CSV 不可注释字段由相邻 Markdown 解释。
LAUNCH_NAME = "launch_command.txt"  # 复现命令以中文说明和单行参数形式保存。
LEDGER_NAME = "artifact_hashes.sha256"  # 审计包自身账本只排除自身以避免自引用。
SCRIPT_SNAPSHOT_NAME = "ultra_s10_link180_postonly.py"  # 审计包保存本次真实执行生成器源码快照，供 SHA-256 谱系复核。
STAGING_SUFFIX = ".staging"  # 隐藏工作目录使用固定后缀，只有完整复核后才原子改名为正式目录。
MAPDL_TIMEOUT_SECONDS = 900  # POST1-only 最大等待 900 秒，超过即失败且不伪造 QA。
HASH_BLOCK_BYTES = 8 * 1024 * 1024  # 大 DB/RST 哈希采用 8 MiB 块限制内存并提高吞吐。
NANOSECONDS_PER_SECOND = 1_000_000_000  # Unix 纳秒时间换算为秒时使用每秒 10^9 纳秒的固定物理定义。
BELOW_NORMAL_PRIORITY_CLASS_FLAG = 0x00004000  # Windows BELOW_NORMAL_PRIORITY_CLASS 标志值，用于降低审计进程前台资源竞争。
CHINESE_CHARACTER_PATTERN = re.compile(r"[\u4e00-\u9fff]")  # 中文注释门禁至少要求出现一个常用汉字。


def expected_active_apdl_lines() -> tuple[str, ...]:  # 无输入并返回唯一允许出现且顺序固定的 APDL 活动行模板。
    """参数：无；返回：有序 APDL 活动行元组；约束：内容、重复次数和顺序共同构成唯一 strict allowlist，函数无副作用。"""  # 完整说明参数、返回和模板约束。
    return (  # 每一项都是允许执行的一条 APDL 活动行，顺序必须与生成输入完全一致。
        "/CLEAR,NOSTART",  # 清空独立会话且禁止读取启动文件。
        f"RESUME,'..\\solver\\{JOBNAME}_eq','db'",  # 只读恢复固定 S10 LS2 平衡数据库。
        "/POST1",  # 进入通用后处理器。
        f"FILE,'..\\solver\\{JOBNAME}','rst'",  # 绑定固定 S10 静力结果文件。
        f"SET,{EXPECTED_LOAD_STEP},LAST",  # 按命名冻结载荷步读取最后结果集。
        "*GET,S10_LS,ACTIVE,0,SET,LSTP",  # 读取实际载荷步编号。
        "*GET,S10_SUBSTEP,ACTIVE,0,SET,SBST",  # 读取实际子步编号，禁止在 QA 中硬编码。
        "*GET,S10_TIME,ACTIVE,0,SET,TIME",  # 读取实际结果集时间。
        "ALLSEL,ALL",  # 恢复全部实体选择。
        "ESEL,S,TYPE,,4",  # 只选择冻结的 TYPE4 LINK180 单元。
        "*GET,S10_LINK_COUNT,ELEM,0,COUNT",  # 读取所选 LINK180 数量。
        "ETABLE,ERAS",  # 清除继承的单元表标签。
        "ETABLE,AXIAL_F,SMISC,1",  # 建立 LINK180 轴力结果列。
        "S10_WRITTEN=0",  # 初始化 CSV 写出计数。
        "S10_NONPOS=0",  # 初始化非正轴力计数。
        "S10_MIN_FORCE=1.0E199",  # 初始化最小轴力哨兵值，单位 N。
        "S10_MIN_EID=0",  # 初始化最小轴力对应单元号。
        "S10_MAX_FORCE=-1.0E199",  # 初始化最大轴力哨兵值，单位 N。
        "S10_MAX_EID=0",  # 初始化最大轴力对应单元号。
        "*GET,S10_EID,ELEM,0,NUM,MIN",  # 读取首个选中单元号。
        "*CFOPEN,s10_link180_axial_force_n,csv",  # 打开无标题两列轴力 CSV。
        "*IF,S10_LINK_COUNT,GT,0,THEN",  # 仅在非空选择时进入遍历。
        "*DO,S10_I,1,S10_LINK_COUNT",  # 按实际选择数遍历全部 LINK180。
        "*GET,S10_FORCE,ELEM,S10_EID,ETAB,AXIAL_F",  # 读取当前单元轴力。
        "*VWRITE,S10_EID,S10_FORCE",  # 写出当前单元号和轴力。
        "(F12.0,',',E24.16)",  # 定义两列纯数值 CSV 格式。
        "S10_WRITTEN=S10_WRITTEN+1",  # 增加写出计数。
        "*IF,S10_FORCE,LT,S10_MIN_FORCE,THEN",  # 判断是否出现更小轴力。
        "S10_MIN_FORCE=S10_FORCE",  # 更新最小轴力。
        "S10_MIN_EID=S10_EID",  # 更新最小轴力对应单元号。
        "*ENDIF",  # 结束最小轴力更新分支。
        "*IF,S10_FORCE,GT,S10_MAX_FORCE,THEN",  # 判断是否出现更大轴力。
        "S10_MAX_FORCE=S10_FORCE",  # 更新最大轴力。
        "S10_MAX_EID=S10_EID",  # 更新最大轴力对应单元号。
        "*ENDIF",  # 结束最大轴力更新分支。
        "*IF,S10_FORCE,LE,0.0,THEN",  # 判断当前轴力是否非正。
        "S10_NONPOS=S10_NONPOS+1",  # 增加非正轴力计数。
        "*ENDIF",  # 结束非正轴力分支。
        "*GET,S10_EID,ELEM,S10_EID,NXTH",  # 推进到下一选中单元。
        "*ENDDO",  # 结束 LINK180 遍历循环。
        "*ENDIF",  # 结束非空选择分支。
        "*CFCLOS",  # 关闭轴力 CSV。
        "S10_GATE_PASS=0",  # 初始化 MAPDL 内部门禁状态。
        f"*IF,S10_LINK_COUNT,EQ,{EXPECTED_LINK_COUNT},THEN",  # 检查 LINK180 数量是否为冻结值。
        "*IF,S10_NONPOS,EQ,0,THEN",  # 检查非正轴力计数是否为零。
        f"S10_GATE_PASS={MAPDL_GATE_PASS_VALUE}",  # 两项条件同时满足时写入命名通过值。
        "*ENDIF",  # 结束非正轴力门禁分支。
        "*ENDIF",  # 结束数量门禁分支。
        "/OUTPUT,s10_link180_summary,txt",  # 把机器摘要写入独立文本文件。
        "*VWRITE,S10_LINK_COUNT,S10_WRITTEN,S10_NONPOS,S10_GATE_PASS",  # 写出数量和门禁摘要。
        "('ACTUAL_COUNT=',F12.0,',WRITTEN_COUNT=',F12.0,',NONPOSITIVE_COUNT=',F12.0,',GATE_PASS=',F4.0)",  # 定义数量摘要格式。
        "*VWRITE,S10_MIN_FORCE,S10_MIN_EID,S10_MAX_FORCE,S10_MAX_EID",  # 写出轴力极值和对应单元号。
        "('MIN_FORCE_N=',E24.16,',MIN_ELEMENT_ID=',F12.0,',MAX_FORCE_N=',E24.16,',MAX_ELEMENT_ID=',F12.0)",  # 定义极值摘要格式。
        "*VWRITE,S10_LS,S10_SUBSTEP,S10_TIME",  # 写出实际载荷步、子步和结果时间。
        "('RESULT_LOAD_STEP=',F8.0,',RESULT_SUBSTEP=',F8.0,',RESULT_TIME=',E24.16)",  # 定义结果集身份摘要格式。
        "/OUTPUT",  # 恢复主 OUT。
        "ALLSEL,ALL",  # 退出前恢复全部实体选择。
        "FINISH",  # 离开 POST1。
        "/EXIT,NOSAVE",  # 无保存退出独立 MAPDL 会话。
    )  # 完成唯一活动行 allowlist。


def require(condition: bool, message: str) -> None:  # 输入布尔门禁和失败说明，成功无返回，失败立即抛异常。
    """参数：condition 为门禁布尔值，message 为失败说明；返回：None；约束：condition 为假时立即抛 RuntimeError。"""  # 完整说明两个参数、返回和 fail-closed 异常语义。
    if not condition:  # 仅当硬门禁为假时进入拒绝路径。
        raise RuntimeError(message)  # 抛出包含上下文的异常并由顶层返回非零退出码。


def sha256_file(path: Path) -> str:  # 输入现存普通文件并流式返回小写 SHA-256。
    """参数：path 为现存普通文件；返回：64 位小写 SHA-256；约束：仅二进制只读，缺失文件或读取异常直接失败。"""  # 完整说明路径参数、摘要返回和只读约束。
    require(path.is_file(), f"待哈希文件不存在：{path}")  # 哈希前确认目标是普通文件。
    digest = hashlib.sha256()  # 为当前文件创建独立 SHA-256 累加器。
    with path.open("rb") as stream:  # 以二进制只读模式打开，禁止任何内容修改。
        while True:  # 循环读取直至明确到达文件末尾。
            block = stream.read(HASH_BLOCK_BYTES)  # 每次读取固定 8 MiB 原始字节。
            if not block:  # 空字节串仅表示正常 EOF。
                break  # 结束读取循环并保留累计摘要。
            digest.update(block)  # 把当前原始字节块加入摘要状态。
    return digest.hexdigest()  # 返回 64 位小写十六进制摘要。


def sha256_bytes(payload: bytes) -> str:  # 输入完整原始字节并返回小写 SHA-256。
    """参数：payload 为已冻结原始 bytes；返回：64 位小写 SHA-256；约束：拒绝非 bytes，且不执行任何编码转换。"""  # 完整说明字节参数、摘要返回和类型约束。
    require(isinstance(payload, bytes), "待计算摘要的 payload 不是 bytes。")  # 拒绝隐式文本编码差异。
    return hashlib.sha256(payload).hexdigest()  # 对调用方已经冻结的原始字节一次计算摘要。


def read_stable_bytes(path: Path) -> bytes:  # 输入普通文件并在前后元数据不变时返回完整原始字节。
    """参数：path 为待冻结普通文件；返回：完整原始 bytes；约束：读取前后大小与 mtime_ns 必须相同且字节数闭合。"""  # 完整说明路径参数、字节返回和竞态约束。
    require(path.is_file(), f"待稳定读取文件不存在：{path}")  # 读取前确认目标是普通文件。
    before = path.stat()  # 记录读取前字节数和纳秒修改时间。
    payload = path.read_bytes()  # 一次读取完整原始字节。
    after = path.stat()  # 记录读取后字节数和纳秒修改时间。
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"读取期间文件发生变化：{path}")  # 元数据漂移即拒绝。
    require(len(payload) == before.st_size, f"稳定读取字节数与 stat 不一致：{path}")  # 防止短读或异常文件语义。
    return payload  # 返回读取窗口内已证明稳定的原始字节。


def json_bytes(value: dict[str, Any]) -> bytes:  # 输入 JSON 顶层对象并返回确定性 UTF-8 字节。
    """参数：value 为 JSON 可序列化顶层字典；返回：确定性 UTF-8 bytes；约束：两空格缩进、中文直写并保留末尾 LF。"""  # 完整说明对象参数、字节返回和序列化格式。
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")  # 渲染并编码合法 JSON。


def write_new_bytes(path: Path, payload: bytes) -> None:  # 输入独立审计目录内的新文件和完整字节并排他创建。
    """参数：path 为新文件目标，payload 为完整 bytes；返回：None；约束：父目录必须存在且目标不得存在，采用排他创建。"""  # 完整说明两个参数、返回和不可覆盖约束。
    require(path.parent.is_dir(), f"写目标父目录不存在：{path.parent}")  # 写入前确认独立审计目录已存在。
    require(not path.exists(), f"拒绝覆盖既有审计文件：{path}")  # 任何同名文件都阻断当前审计。
    with path.open("xb") as stream:  # 排他创建二进制文件避免竞争覆盖。
        stream.write(payload)  # 一次写出调用方已完整构造的字节。
        stream.flush()  # 把 Python 缓冲区刷新到操作系统。


def utc_iso_from_ns(value_ns: int) -> str:  # 输入 Unix 纳秒时间并返回 UTC ISO-8601 字符串。
    """参数：value_ns 为 Unix 纳秒整数；返回：含 UTC 时区的 ISO-8601 字符串；约束：按每秒 10^9 纳秒换算。"""  # 完整说明时间参数、文本返回和单位约束。
    return datetime.fromtimestamp(value_ns / NANOSECONDS_PER_SECOND, timezone.utc).isoformat()  # 按命名物理常量转换纳秒并保留时区。


def file_identity(path: Path) -> dict[str, Any]:  # 输入只读源文件并返回大小、时间和 SHA-256 身份。
    """参数：path 为只读普通文件；返回：大小、UTC 时间和 SHA-256 字典；约束：哈希窗口内大小与 mtime_ns 必须稳定。"""  # 完整说明路径参数、身份返回和竞态约束。
    require(path.is_file(), f"源文件不存在：{path}")  # 身份计算前确认普通文件存在。
    before = path.stat()  # 记录哈希前大小、创建时间和修改时间。
    digest = sha256_file(path)  # 流式计算当前完整内容摘要。
    after = path.stat()  # 记录哈希后元数据用于竞态比较。
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"哈希期间源文件发生变化：{path}")  # 大小或修改时间漂移即拒绝。
    return {  # 返回可序列化且每个字段含义明确的身份对象。
        "length_bytes": before.st_size,  # 文件完整字节数，用于检测截断或替换。
        "creation_time_utc": utc_iso_from_ns(before.st_ctime_ns),  # Windows 创建时间的 UTC 表示。
        "last_write_time_utc": utc_iso_from_ns(before.st_mtime_ns),  # 最后修改时间的 UTC 表示。
        "sha256": digest,  # 完整原始字节的小写 SHA-256。
    }  # 完成单文件身份对象。


def active_heavy_processes() -> list[dict[str, str]]:  # 无输入并返回可能表示活动求解的进程列表。
    """参数：无；返回：活动求解进程名和 PID 字典列表；约束：仅匹配冻结的 MAPDL、MPI 与 Hydra 名称，不修改进程。"""  # 完整说明返回结构和只读进程边界。
    command = [  # 构造只读 Windows 进程枚举命令。
        "tasklist",  # 调用 Windows 原生进程列表程序。
        "/FO",  # 指定后续输出格式参数。
        "CSV",  # 选择可由 csv.reader 稳定解析的 CSV 格式。
        "/NH",  # 省略标题行，避免本地化列名影响解析。
    ]  # 完成进程枚举参数列表。
    completed = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")  # 只读获取当前进程表。
    heavy_names = {  # 固定需要阻断并发审计的活动求解进程名集合。
        "ansys.exe",  # ANSYS 通用 MAPDL 主进程名。
        "ansys261.exe",  # ANSYS 2026 R1 MAPDL 版本化主进程名。
        "mpiexec.exe",  # Intel MPI 启动器进程名。
        "hydra_pmi_proxy.exe",  # Intel MPI Hydra PMI 代理进程名。
        "hydra_bstrap_proxy.exe",  # Intel MPI Hydra 引导代理进程名。
    }  # 完成需要阻断的活动求解进程集合。
    rows: list[dict[str, str]] = []  # 初始化活动求解进程记录列表。
    for raw_row in csv.reader(completed.stdout.splitlines()):  # 逐行解析 tasklist CSV。
        if len(raw_row) < 2:  # 非标准提示行不属于进程记录。
            continue  # 跳过缺少进程名和 PID 的行。
        image_name = raw_row[0].strip().lower()  # 统一进程名大小写便于集合匹配。
        if image_name in heavy_names:  # 仅保留固定求解进程集合。
            rows.append({"image_name": raw_row[0], "pid": raw_row[1]})  # 保存用户可读进程名和 PID。
    return rows  # 返回启动前或结束后的活动求解进程列表。


def build_apdl_input() -> str:  # 无输入并返回逐行中文注释的 POST1-only APDL。
    """参数：无；返回：末尾含 LF 的固定 APDL 文本；约束：只恢复 S10 LS2、读取 TYPE4 SMISC,1 并以 NOSAVE 退出。"""  # 完整说明返回格式和唯一执行范围。
    lines = [  # 按严格执行顺序构造 APDL 源行。
        "! 清空当前会话且不读取启动文件，确保本审计不继承任何未封存内存状态。",  # 解释下一条清空命令。
        "/CLEAR,NOSTART",  # 清空独立 MAPDL 会话。
        "! 只读恢复 S10 的 LS2 平衡数据库；相对路径固定指向父运行目录的 solver 文件。",  # 解释恢复源。
        f"RESUME,'..\\solver\\{JOBNAME}_eq','db'",  # 恢复固定平衡 DB。
        "! 进入通用后处理器，仅访问既有静力结果文件。",  # 解释处理器用途。
        "/POST1",  # 进入只读结果后处理器。
        "! 显式绑定 S10 合并静力结果文件；扩展名 rst 表示非线性静力结果。",  # 解释结果源。
        f"FILE,'..\\solver\\{JOBNAME}','rst'",  # 绑定固定静力 RST。
        "! 读取载荷步 2 的最后结果集；该结果集时间应为 1.001，且是模态扰动基态。",  # 解释结果集选择。
        f"SET,{EXPECTED_LOAD_STEP},LAST",  # 按命名冻结载荷步读取最后结果集。
        "! 读取当前结果集载荷步编号，用于证明审计读取的是 LS2。",  # 解释载荷步参数。
        "*GET,S10_LS,ACTIVE,0,SET,LSTP",  # 获取载荷步编号。
        "! 读取当前结果集子步编号，用于证明 LS2 的最后结果集确为 substep 1。",  # 解释子步参数。
        "*GET,S10_SUBSTEP,ACTIVE,0,SET,SBST",  # 获取实际子步编号。
        "! 读取当前结果集时间，用于证明审计读取的是 1.001 终态。",  # 解释时间参数。
        "*GET,S10_TIME,ACTIVE,0,SET,TIME",  # 获取结果集伪时间。
        "! 恢复全部实体选择，避免数据库保存时的选择状态影响审计范围。",  # 解释选择复位。
        "ALLSEL,ALL",  # 选择全部实体。
        "! 只选择 TYPE 4；S10 冻结模型规定 TYPE 4 为全部 LINK180 索单元。",  # 解释元素类型边界。
        "ESEL,S,TYPE,,4",  # 选择全部 TYPE4 元素。
        "! 读取选中 LINK180 单元总数；硬门禁目标为 73692 个。",  # 解释数量参数。
        "*GET,S10_LINK_COUNT,ELEM,0,COUNT",  # 获取选中单元数。
        "! 清空数据库内可能继承的单元表标签，避免同名结果列污染。",  # 解释 ETABLE 清理。
        "ETABLE,ERAS",  # 清除已有单元表。
        "! 从 LINK180 的 SMISC 第 1 项建立轴力列；单位沿用模型的 N。",  # 解释结果项。
        "ETABLE,AXIAL_F,SMISC,1",  # 建立轴力单元表。
        "! 把已写出记录数初始化为 0，供 CSV 行数闭合。",  # 解释写出计数。
        "S10_WRITTEN=0",  # 初始化写出计数。
        "! 把非正轴力计数初始化为 0；轴力小于或等于 0 N 均计入失败集合。",  # 解释失败计数。
        "S10_NONPOS=0",  # 初始化非正轴力计数。
        "! 用 1.0E199 N 初始化最小值哨兵；该值低于 APDL 输入上限且高于真实轴力。",  # 解释最小值哨兵。
        "S10_MIN_FORCE=1.0E199",  # 初始化最小轴力。
        "! 把最小轴力对应单元号初始化为 0，表示尚未读取任何单元。",  # 解释最小值单元号。
        "S10_MIN_EID=0",  # 初始化最小值单元号。
        "! 用 -1.0E199 N 初始化最大值哨兵；任一真实轴力都会替换该值。",  # 解释最大值哨兵。
        "S10_MAX_FORCE=-1.0E199",  # 初始化最大轴力。
        "! 把最大轴力对应单元号初始化为 0，表示尚未读取任何单元。",  # 解释最大值单元号。
        "S10_MAX_EID=0",  # 初始化最大值单元号。
        "! 读取当前选中集合的最小单元号，作为严格递增遍历起点。",  # 解释遍历起点。
        "*GET,S10_EID,ELEM,0,NUM,MIN",  # 获取最小选中单元号。
        "! 打开无标题纯数值 CSV；两列依次为 element_id 与 axial_force_n。",  # 解释 CSV 结构。
        "*CFOPEN,s10_link180_axial_force_n,csv",  # 打开轴力 CSV。
        "! 只有选中单元数大于 0 时才进入遍历，避免空集合产生伪记录。",  # 解释非空分支。
        "*IF,S10_LINK_COUNT,GT,0,THEN",  # 进入非空选择分支。
        "! 按实际选中单元数循环，确保循环次数与预期 CSV 记录数一致。",  # 解释循环范围。
        "*DO,S10_I,1,S10_LINK_COUNT",  # 遍历全部选中 LINK180。
        "! 读取当前 LINK180 单元的 SMISC,1 轴力，单位为 N。",  # 解释轴力读取。
        "*GET,S10_FORCE,ELEM,S10_EID,ETAB,AXIAL_F",  # 获取当前轴力。
        "! 写出当前单元号和轴力；下一行格式保证只有两个数值字段且用逗号分隔。",  # 解释 VWRITE 和格式行。
        "*VWRITE,S10_EID,S10_FORCE",  # 写出两个数值参数。
        "(F12.0,',',E24.16)",  # 定义无标题两列 CSV 格式。
        "! 已写出记录数增加 1，用于和选择计数及外部 CSV 行数三方闭合。",  # 解释写出计数更新。
        "S10_WRITTEN=S10_WRITTEN+1",  # 增加写出计数。
        "! 当当前轴力小于已知最小值时，更新最小值及其单元号。",  # 解释最小值分支。
        "*IF,S10_FORCE,LT,S10_MIN_FORCE,THEN",  # 进入更小轴力分支。
        "! 保存更小的轴力值，单位为 N。",  # 解释最小值更新。
        "S10_MIN_FORCE=S10_FORCE",  # 更新最小轴力。
        "! 保存更小轴力对应的 LINK180 单元号。",  # 解释最小单元号更新。
        "S10_MIN_EID=S10_EID",  # 更新最小轴力单元号。
        "! 结束最小值更新分支。",  # 解释分支结束。
        "*ENDIF",  # 结束最小值分支。
        "! 当当前轴力大于已知最大值时，更新最大值及其单元号。",  # 解释最大值分支。
        "*IF,S10_FORCE,GT,S10_MAX_FORCE,THEN",  # 进入更大轴力分支。
        "! 保存更大的轴力值，单位为 N。",  # 解释最大值更新。
        "S10_MAX_FORCE=S10_FORCE",  # 更新最大轴力。
        "! 保存更大轴力对应的 LINK180 单元号。",  # 解释最大单元号更新。
        "S10_MAX_EID=S10_EID",  # 更新最大轴力单元号。
        "! 结束最大值更新分支。",  # 解释分支结束。
        "*ENDIF",  # 结束最大值分支。
        "! 轴力小于或等于 0 N 时进入非正计数分支。",  # 解释非正轴力分支。
        "*IF,S10_FORCE,LE,0.0,THEN",  # 检查非正轴力。
        "! 非正轴力计数增加 1；硬门禁要求最终值严格等于 0。",  # 解释失败计数更新。
        "S10_NONPOS=S10_NONPOS+1",  # 增加非正计数。
        "! 结束非正轴力计数分支。",  # 解释分支结束。
        "*ENDIF",  # 结束非正轴力分支。
        "! 读取当前选中集合中的下一单元号，保持严格覆盖全部 TYPE 4 单元。",  # 解释遍历推进。
        "*GET,S10_EID,ELEM,S10_EID,NXTH",  # 获取下一选中单元号。
        "! 结束 LINK180 单元遍历循环。",  # 解释循环结束。
        "*ENDDO",  # 结束单元循环。
        "! 结束非空选择集合分支。",  # 解释分支结束。
        "*ENDIF",  # 结束非空选择分支。
        "! 关闭纯数值 CSV，确保全部缓冲内容落盘。",  # 解释文件关闭。
        "*CFCLOS",  # 关闭轴力 CSV。
        "! 把硬门禁初始状态设为 0，表示尚未同时满足数量与非正计数条件。",  # 解释门禁初值。
        "S10_GATE_PASS=0",  # 初始化门禁状态。
        "! 只有实际选择数严格等于冻结目标 73692 时才检查第二项条件。",  # 解释数量分支。
        f"*IF,S10_LINK_COUNT,EQ,{EXPECTED_LINK_COUNT},THEN",  # 检查 LINK180 数量。
        "! 只有非正轴力计数严格等于 0 时才允许门禁通过。",  # 解释轴力分支。
        "*IF,S10_NONPOS,EQ,0,THEN",  # 检查非正轴力计数。
        "! 两项硬条件均满足时把门禁状态设为 1。",  # 解释通过赋值。
        f"S10_GATE_PASS={MAPDL_GATE_PASS_VALUE}",  # 写入命名的 MAPDL 门禁通过值。
        "! 结束非正轴力为零分支。",  # 解释分支结束。
        "*ENDIF",  # 结束非正轴力分支。
        "! 结束 LINK180 数量闭合分支。",  # 解释分支结束。
        "*ENDIF",  # 结束数量分支。
        "! 把机器可解析摘要重定向到独立文本文件，不污染纯数值 CSV。",  # 解释摘要输出。
        "/OUTPUT,s10_link180_summary,txt",  # 打开摘要文本。
        "! 写出实际选择数、CSV 写出数、非正计数和门禁布尔值。",  # 解释第一行摘要。
        "*VWRITE,S10_LINK_COUNT,S10_WRITTEN,S10_NONPOS,S10_GATE_PASS",  # 写出数量门禁参数。
        "('ACTUAL_COUNT=',F12.0,',WRITTEN_COUNT=',F12.0,',NONPOSITIVE_COUNT=',F12.0,',GATE_PASS=',F4.0)",  # 定义第一行摘要格式。
        "! 写出最小轴力、对应单元号、最大轴力和对应单元号。",  # 解释第二行摘要。
        "*VWRITE,S10_MIN_FORCE,S10_MIN_EID,S10_MAX_FORCE,S10_MAX_EID",  # 写出极值参数。
        "('MIN_FORCE_N=',E24.16,',MIN_ELEMENT_ID=',F12.0,',MAX_FORCE_N=',E24.16,',MAX_ELEMENT_ID=',F12.0)",  # 定义第二行摘要格式。
        "! 写出结果集载荷步、子步和时间，用于证明审计锁定 LS2/substep1/TIME=1.001。",  # 解释第三行摘要。
        "*VWRITE,S10_LS,S10_SUBSTEP,S10_TIME",  # 写出实际结果集身份。
        "('RESULT_LOAD_STEP=',F8.0,',RESULT_SUBSTEP=',F8.0,',RESULT_TIME=',E24.16)",  # 定义第三行摘要格式。
        "! 恢复主输出文件，使退出统计和诊断保留在独立 OUT 中。",  # 解释输出恢复。
        "/OUTPUT",  # 恢复主 OUT。
        "! 恢复全部实体选择，避免结束时留下局部选择状态。",  # 解释选择复位。
        "ALLSEL,ALL",  # 选择全部实体。
        "! 离开通用后处理器，不保存任何数据库变更。",  # 解释处理器退出。
        "FINISH",  # 离开 POST1。
        "! 无保存退出独立会话，明确禁止覆盖源 DB 或创建派生数据库。",  # 解释最终退出。
        "/EXIT,NOSAVE",  # 无保存退出 MAPDL。
    ]  # 完成 APDL 行列表。
    return "\n".join(lines) + "\n"  # 返回 UTF-8 文本并保证末尾 LF。


def scan_input(text: str) -> dict[str, Any]:  # 输入 APDL 全文并返回禁止命令和注释覆盖审计。
    """参数：text 为完整 APDL 文本；返回：活动行、模板差异和注释覆盖字典；约束：仅分析内存文本，不执行 APDL 或写文件。"""  # 完整说明文本参数、审计返回和纯函数约束。
    lines = text.splitlines()  # 保留源行顺序供相邻注释审计。
    active_lines: list[str] = []  # 初始化活动 APDL 行列表。
    uncommented_count = 0  # 初始化未被紧邻注释解释的活动行计数。
    non_chinese_comment_count = 0  # 初始化不含中文字符的 APDL 注释行计数。
    previous_nonblank = ""  # 保存上一条非空源行供相邻注释判断。
    second_previous_nonblank = ""  # 保存上上条非空源行供 *VWRITE 格式续行判断。
    for raw_line in lines:  # 逐行扫描输入。
        stripped = raw_line.strip()  # 移除不影响语义的首尾空白。
        if not stripped:  # 空行不属于活动命令也不改变上一非空行。
            continue  # 跳到下一源行。
        if stripped.startswith("!"):  # 感叹号开头的行是 APDL 注释。
            if CHINESE_CHARACTER_PATTERN.search(stripped) is None:  # 注释没有任何中文字符时违反本项目注释语言要求。
                non_chinese_comment_count += 1  # 记录非中文注释行。
        else:  # 非注释行属于活动 APDL 命令或紧随 *VWRITE 的格式续行。
            active_lines.append(stripped)  # 保存当前活动行供禁止命令扫描。
            if stripped.startswith("("):  # Fortran 格式续行必须紧随 *VWRITE，语法不允许在两者之间插入注释。
                format_comment_valid = previous_nonblank.upper().startswith("*VWRITE") and second_previous_nonblank.startswith("!") and CHINESE_CHARACTER_PATTERN.search(second_previous_nonblank) is not None  # 上上行中文注释必须解释相邻的 *VWRITE 与格式续行。
                if not format_comment_valid:  # 格式续行没有合法相邻说明时进入失败计数。
                    uncommented_count += 1  # 记录缺少中文解释的格式续行。
            elif not previous_nonblank.startswith("!") or CHINESE_CHARACTER_PATTERN.search(previous_nonblank) is None:  # 其他活动行的紧邻上一非空行必须是中文注释。
                uncommented_count += 1  # 记录缺少相邻解释的活动行。
        second_previous_nonblank = previous_nonblank  # 推进上上条非空行状态。
        previous_nonblank = stripped  # 更新上一非空行。
    expected_lines = list(expected_active_apdl_lines())  # 取得允许活动行的唯一有序模板。
    remaining_expected = expected_lines.copy()  # 复制模板供多重集合差异计算，保留重复 *ENDIF。
    unexpected_lines: list[str] = []  # 初始化模板外活动行列表。
    for active_line in active_lines:  # 逐项从期望多重集合中消费实际活动行。
        if active_line in remaining_expected:  # 当前活动行仍有一个未消费的期望实例。
            remaining_expected.remove(active_line)  # 消费一个同值模板实例。
        else:  # 当前活动行不存在于剩余 allowlist。
            unexpected_lines.append(active_line)  # 保存模板外或重复过量活动行。
    missing_lines = remaining_expected  # 未被消费的模板实例就是缺失活动行。
    active_line_order_match = active_lines == expected_lines  # 要求数量、内容和顺序逐项完全一致。
    resume_line = f"RESUME,'..\\solver\\{JOBNAME}_eq','db'"  # 定义必须实际执行的平衡 DB 恢复命令。
    result_file_line = f"FILE,'..\\solver\\{JOBNAME}','rst'"  # 定义必须实际执行的静力 RST 绑定命令。
    has_resume_eq_db = resume_line in active_lines  # 仅在活动行中识别 RESUME，注释文本不能满足。
    has_static_rst_file_binding = result_file_line in active_lines  # 仅在活动行中识别 FILE 绑定。
    has_ls2_last_set = f"SET,{EXPECTED_LOAD_STEP},LAST" in active_lines  # 仅在活动行中识别命名冻结载荷步的最后结果集。
    has_result_substep_get = "*GET,S10_SUBSTEP,ACTIVE,0,SET,SBST" in active_lines  # 仅在活动行中识别子步读取。
    has_type4_selection = "ESEL,S,TYPE,,4" in active_lines  # 仅在活动行中识别 TYPE4 选择。
    has_smisc1_etable = "ETABLE,AXIAL_F,SMISC,1" in active_lines  # 仅在活动行中识别 SMISC,1 轴力表。
    has_exit_nosave = "/EXIT,NOSAVE" in active_lines  # 仅在活动行中识别无保存退出。
    return {  # 返回逐字段解释的完整输入安全对象。
        "line_count": len(lines),  # APDL 输入物理行总数。
        "active_line_count": len(active_lines),  # 非注释且非空的活动行总数。
        "expected_active_line_count": len(expected_lines),  # strict allowlist 期望活动行总数。
        "unexpected_active_line_count": len(unexpected_lines),  # 模板外或重复过量活动行数量。
        "missing_active_line_count": len(missing_lines),  # 缺失的模板活动行数量。
        "active_line_order_match": active_line_order_match,  # 实际活动行是否与模板逐项同序。
        "unexpected_active_lines": unexpected_lines,  # 模板外活动行原文，空列表表示无额外执行。
        "missing_active_lines": missing_lines,  # 缺失活动行原文，空列表表示能力完整。
        "uncommented_executable_line_count": uncommented_count,  # 缺少相邻中文解释的活动行数量。
        "non_chinese_comment_line_count": non_chinese_comment_count,  # 不含中文字符的 APDL 注释行数量。
        "has_resume_eq_db": has_resume_eq_db,  # 活动命令是否恢复固定平衡 DB。
        "has_static_rst_file_binding": has_static_rst_file_binding,  # 活动命令是否绑定固定静力 RST。
        "has_ls2_last_set": has_ls2_last_set,  # 活动命令是否读取 LS2 最后结果集。
        "has_result_substep_get": has_result_substep_get,  # 活动命令是否读取实际子步。
        "has_type4_selection": has_type4_selection,  # 活动命令是否只选 TYPE4。
        "has_smisc1_etable": has_smisc1_etable,  # 活动命令是否读取 LINK180 SMISC,1。
        "has_exit_nosave": has_exit_nosave,  # 活动命令是否明确 NOSAVE 退出。
    }  # 完成严格 allowlist 与注释覆盖结果。


def parse_summary(path: Path) -> dict[str, float]:  # 输入 MAPDL 摘要文本并返回所有键值浮点映射。
    """参数：path 为 MAPDL 摘要文件；返回：大写键到有限浮点值映射；约束：文件必须存在，非有限值立即失败。"""  # 完整说明路径参数、映射返回和数值约束。
    require(path.is_file(), f"缺少 MAPDL 摘要：{path}")  # 解析前确认摘要存在。
    text = path.read_text(encoding="utf-8", errors="replace")  # 以替换模式兼容 MAPDL 本地编码。
    pairs = re.findall(r"([A-Z_]+)=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)", text.upper())  # 提取固定键和值。
    values = {key: float(value) for key, value in pairs}  # 转换为浮点映射。
    require(all(math.isfinite(value) for value in values.values()), "MAPDL 摘要含非有限数值。")  # 拒绝 NaN 和无穷。
    return values  # 返回摘要字段映射。


def summary_integer(values: dict[str, float], key: str) -> int:  # 输入摘要映射和字段名并返回经整数性验证的值。
    """参数：values 为摘要映射，key 为必需字段名；返回：严格整数值；约束：字段必须存在、有限且数学上为整数。"""  # 完整说明两个参数、整数返回和拒绝截断约束。
    require(key in values, f"MAPDL 摘要缺少整数键：{key}")  # 缺少必需字段立即失败。
    raw_value = values[key]  # 读取当前摘要浮点值。
    require(math.isfinite(raw_value) and raw_value.is_integer(), f"MAPDL 摘要字段不是有限整数：{key}={raw_value}")  # 拒绝小数、NaN 和无穷。
    return int(raw_value)  # 在整数性已经证明后安全转换为 Python 整数。


def parse_force_csv(path: Path) -> dict[str, Any]:  # 输入两列纯数值 CSV 并返回覆盖、唯一性和极值统计。
    """参数：path 为无标题两列轴力 CSV；返回：覆盖、唯一性、质量和极值统计；约束：有效行须含整数 ID 与有限轴力。"""  # 完整说明路径参数、统计返回和行级数据约束。
    require(path.is_file(), f"缺少轴力 CSV：{path}")  # 解析前确认文件存在。
    element_ids: list[int] = []  # 初始化元素号列表。
    forces: list[float] = []  # 初始化轴力列表。
    invalid_numeric_line_count = 0  # 初始化非法数值行计数。
    with path.open("r", encoding="utf-8-sig", newline="") as stream:  # 按文本方式读取纯数值 CSV。
        for raw_row in csv.reader(stream):  # 逐行解析两个字段。
            if len(raw_row) != 2:  # 非两列记录属于非法行。
                invalid_numeric_line_count += 1  # 增加非法行计数。
                continue  # 跳过当前非法行。
            try:  # 尝试把两个字段转换为数值。
                element_value = float(raw_row[0].strip())  # 解析元素号浮点表示。
                force_value = float(raw_row[1].strip())  # 解析轴力。
            except ValueError:  # 非数值字段进入明确失败计数。
                invalid_numeric_line_count += 1  # 增加非法行计数。
                continue  # 跳过当前非法行。
            if not element_value.is_integer() or not math.isfinite(force_value):  # 元素号非整数或轴力非有限均非法。
                invalid_numeric_line_count += 1  # 增加非法行计数。
                continue  # 跳过当前非法行。
            element_ids.append(int(element_value))  # 保存整数元素号。
            forces.append(force_value)  # 保存有限轴力。
    duplicate_count = len(element_ids) - len(set(element_ids))  # 计算重复元素号数量。
    nonpositive_count = sum(1 for value in forces if value <= NONPOSITIVE_FORCE_LIMIT_N)  # 使用命名阈值统计非正轴力数量。
    require(bool(forces), "轴力 CSV 没有有效记录。")  # 空有效集合不能形成极值和门禁。
    minimum_index = min(range(len(forces)), key=forces.__getitem__)  # 查找最小轴力索引。
    maximum_index = max(range(len(forces)), key=forces.__getitem__)  # 查找最大轴力索引。
    return {  # 返回逐字段解释的完整轴力统计。
        "csv_row_count": len(element_ids),  # 有效两列数值记录总数。
        "unique_element_count": len(set(element_ids)),  # 唯一 LINK180 单元号总数。
        "duplicate_element_count": duplicate_count,  # 重复单元记录数量。
        "invalid_numeric_line_count": invalid_numeric_line_count,  # 非两列、非整数 ID 或非有限轴力行数量。
        "nonpositive_count": nonpositive_count,  # 轴力小于或等于 0 N 的记录数量。
        "minimum_force_n": forces[minimum_index],  # CSV 中最小轴力，单位 N。
        "minimum_element_id": element_ids[minimum_index],  # 最小轴力对应 LINK180 单元号。
        "maximum_force_n": forces[maximum_index],  # CSV 中最大轴力，单位 N。
        "maximum_element_id": element_ids[maximum_index],  # 最大轴力对应 LINK180 单元号。
        "csv_sha256": sha256_file(path),  # CSV 完整原始字节 SHA-256。
    }  # 完成轴力统计对象。


def build_field_dictionary() -> str:  # 无输入并返回 JSON、CSV 和摘要字段说明 Markdown。
    """参数：无；返回：末尾含 LF 的字段说明 Markdown；约束：文本内容和顺序固定，不读取文件或修改状态。"""  # 完整说明参数、返回和纯函数约束。
    lines = [  # 逐行构造 Markdown，使每个文本字面值都有中文用途说明。
        "# S10 LINK180 POST1-only 字段说明",  # 文档一级标题。
        "",  # 标题与正文之间的 Markdown 空行。
        "本目录只恢复既有 S10 LS2 平衡数据库并读取静力 RST，不执行新的结构计算。运行固定采用 SMP 单进程、`/POST1` 和 `/EXIT,NOSAVE`；源 DB/RST 在运行前后均按长度、UTC 时间和 SHA-256 复核。",  # 总述只读执行范围和源完整性口径。
        "",  # 总述与轴力 CSV 小节之间的空行。
        "## 轴力 CSV",  # 轴力 CSV 字段说明小节标题。
        "",  # 小节标题与条目之间的空行。
        "- `s10_link180_axial_force_n.csv` 无标题且每行两列。",  # 说明 CSV 文件名和列数。
        "- 第一列 `element_id` 是 TYPE4 LINK180 单元号，为无量纲整数。",  # 说明第一列用途、类型和量纲。
        "- 第二列 `axial_force_n` 是 `SMISC,1` 轴力，单位 N；正值表示受拉。",  # 说明第二列结果项、单位和符号约定。
        "- 硬门禁要求 73,692 行、73,692 个唯一单元、零非法行和零非正轴力。",  # 说明 CSV 覆盖和数据质量门禁。
        "",  # CSV 小节与机器摘要小节之间的空行。
        "## 机器摘要",  # MAPDL 机器摘要字段小节标题。
        "",  # 小节标题与条目之间的空行。
        "- `ACTUAL_COUNT` 是 POST1 中选中的 TYPE4 数量。",  # 说明实际选择数量字段。
        "- `WRITTEN_COUNT` 是 APDL 写入 CSV 的记录数。",  # 说明写出记录数量字段。
        "- `NONPOSITIVE_COUNT` 是轴力小于或等于零的记录数。",  # 说明非正轴力计数字段。
        "- `GATE_PASS` 仅在数量为 73,692 且非正计数为零时等于 1。",  # 说明 MAPDL 内部门禁布尔数值的成立条件。
        "- `RESULT_LOAD_STEP`、`RESULT_SUBSTEP` 与 `RESULT_TIME` 必须分别为 2、1 和 1.001。",  # 说明结果集身份字段及冻结值。
        "",  # 机器摘要与源完整性小节之间的空行。
        "## 源完整性",  # 源文件完整性证据小节标题。
        "",  # 小节标题与条目之间的空行。
        "- `preflight.json` 记录执行前 DB/RST 身份、输入安全扫描和活动求解进程数。",  # 说明启动前证据文件角色。
        "- `postflight_source_integrity.json` 记录执行前后两个源文件身份逐字段比较。",  # 说明执行后证据文件角色。
        "- `source_integrity_passed=true` 只在长度、创建时间、修改时间和 SHA-256 全部不变时成立。",  # 说明源完整性真值约束。
        "- `ultra_s10_link180_postonly.py` 是本次真实执行生成器源码快照，其 SHA-256 同时写入 preflight 与最终 QA。",  # 说明生成器源码谱系。
        "",  # 源完整性与最终 QA 小节之间的空行。
        "## 最终 QA",  # 最终机器门禁字段小节标题。
        "",  # 小节标题与条目之间的空行。
        "- `qa_summary.json` 的 `status=PASSED` 与 `gate_passed=true` 表示轴力、执行、结果集和源完整性门禁全部通过。",  # 说明最终 QA 顶层状态语义。
        "- `mapdl_warning_count`、`mapdl_error_count`、`mapdl_fatal_count`、`negative_pivot_count` 与 `zero_pivot_count` 必须均为零。",  # 说明五类诊断硬门禁。
        "- `summary_warning_counts=[0]` 与 `summary_error_counts=[0]` 证明退出摘要各出现一次且为零。",  # 说明退出摘要唯一零值门禁。
        "- `exit_without_saving_confirmed=true` 表示独立 POST1 会话没有保存或覆盖源数据库。",  # 说明无保存退出真值。
        "- `artifact_hashes.sha256` 覆盖本目录除账本自身外全部普通文件。",  # 说明包账本覆盖范围。
        "- 正式 `S10_LINK180_POSTONLY_*` 目录只在隐藏 staging 内全部文件和账本严格复核后，通过同父目录原子改名出现。",  # 说明原子发布协议。
    ]  # 完成字段说明 Markdown 行列表。
    return "\n".join(lines) + "\n"  # 按原有文本逐行拼接并保留末尾 LF。


def build_qa_report(qa: dict[str, Any]) -> str:  # 输入机器 QA 并返回结论优先的用户可读报告。
    """参数：qa 为已通过门禁且含结果集和轴力对象的字典；返回：末尾含 LF 的报告；约束：缺少必需字段时直接抛 KeyError。"""  # 完整说明输入结构、返回格式和失败约束。
    force = qa["link180_axial_force"]  # 提取轴力统计对象。
    lines = [  # 逐行构造报告，使每个动态文本字面值都有中文说明。
        "# S10 LINK180 POST1-only 审计结论",  # 报告一级标题。
        "",  # 标题与结论列表之间的 Markdown 空行。
        f"- 状态：`{qa['status']}`；硬门禁：`LINK180_NONPOSITIVE_AXIAL_FORCE_REVIEW`。",  # 呈现顶层状态和固定硬门禁名称。
        "- 执行：MAPDL POST1-only、SMP1、零 warning、零 error、`/EXIT,NOSAVE`。",  # 呈现执行模式和干净退出结论。
        f"- 结果集：LS{qa['result_set']['load_step']} / substep {qa['result_set']['substep']} / time {qa['result_set']['time']:.16g}。",  # 呈现实测结果集身份。
        f"- 覆盖：TYPE4 实际、写出、CSV 和唯一元素均为 {force['actual_count']}。",  # 呈现 LINK180 覆盖数量闭合。
        f"- 非正轴力：{force['nonpositive_count']}。",  # 呈现非正轴力计数。
        f"- 最小轴力：{force['minimum_force_n']:.16g} N，元素 {force['minimum_element_id']}。",  # 呈现最小轴力和对应单元号。
        f"- 最大轴力：{force['maximum_force_n']:.16g} N，元素 {force['maximum_element_id']}。",  # 呈现最大轴力和对应单元号。
        "- 源完整性：平衡 DB 与静力 RST 的长度、时间和 SHA-256 在运行前后完全一致。",  # 呈现两个只读源未变化结论。
    ]  # 完成用户可读报告行列表。
    return "\n".join(lines) + "\n"  # 按原有文本逐行拼接并保留末尾 LF。


def write_artifact_ledger(audit_dir: Path) -> tuple[str, int]:  # 输入已完成审计目录并写出排除自身的 SHA-256 账本。
    """参数：audit_dir 为待封板审计目录；返回：账本 SHA-256 与条目数；约束：账本不得预存，且覆盖除自身外全部普通文件。"""  # 完整说明目录参数、二元返回和自排除覆盖约束。
    ledger_path = audit_dir / LEDGER_NAME  # 固定账本目标路径。
    require(not ledger_path.exists(), f"审计账本已存在：{ledger_path}")  # 禁止覆盖不明账本。
    files = sorted((path for path in audit_dir.rglob("*") if path.is_file() and path != ledger_path), key=lambda path: path.relative_to(audit_dir).as_posix())  # 稳定枚举全部其他普通文件。
    entries: list[str] = []  # 初始化账本行列表。
    for path in files:  # 逐文件计算摘要并核对哈希期间元数据。
        before = path.stat()  # 记录哈希前大小和修改时间。
        digest = sha256_file(path)  # 计算当前完整文件摘要。
        after = path.stat()  # 记录哈希后元数据。
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"账本哈希期间文件变化：{path}")  # 并发变化立即拒绝。
        entries.append(f"{digest}  {path.relative_to(audit_dir).as_posix()}")  # 保存规范双空格分隔行。
    payload = ("\n".join(entries) + "\n").encode("utf-8")  # 构造末尾含 LF 的账本字节。
    write_new_bytes(ledger_path, payload)  # 最后排他写入账本。
    return sha256_file(ledger_path), len(entries)  # 返回账本自身摘要和条目数。


def validate_artifact_ledger(audit_dir: Path) -> dict[str, Any]:  # 输入候选审计目录并严格复核自排除账本和全部普通文件。
    """参数：audit_dir 为候选包目录；返回：账本路径、条目数、摘要和自排除标志；约束：格式、路径、集合、摘要及元数据全程闭合。"""  # 完整说明目录参数、证据返回和严格验证约束。
    require(audit_dir.is_dir(), f"待验证审计目录不存在：{audit_dir}")  # 验证前确认目录存在。
    audit_root = audit_dir.resolve(strict=True)  # 取得审计目录规范绝对路径。
    ledger_path = audit_dir / LEDGER_NAME  # 绑定固定账本路径。
    require(ledger_path.is_file(), f"审计账本不存在：{ledger_path}")  # 缺少账本时拒绝发布。
    ledger_before = ledger_path.stat()  # 记录账本读取前元数据。
    ledger_bytes = ledger_path.read_bytes()  # 一次冻结账本原始字节。
    ledger_after = ledger_path.stat()  # 记录账本读取后元数据。
    require((ledger_before.st_size, ledger_before.st_mtime_ns) == (ledger_after.st_size, ledger_after.st_mtime_ns), "审计账本读取期间发生变化。")  # 拒绝账本竞态。
    ledger_text = ledger_bytes.decode("utf-8")  # 按无 BOM UTF-8 严格解码账本。
    records: dict[str, str] = {}  # 初始化相对路径到摘要映射。
    for line_number, line in enumerate(ledger_text.splitlines(), start=1):  # 逐行解析规范账本。
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)  # 要求小写摘要、双空格和非空标签。
        require(match is not None, f"审计账本第 {line_number} 行格式非法。")  # 非规范行立即失败。
        digest = match.group(1)  # 提取当前文件预期 SHA-256。
        relative_text = match.group(2)  # 提取 POSIX 相对路径标签。
        relative_path = Path(relative_text)  # 把标签转换为路径对象供安全检查。
        require(not relative_path.is_absolute() and ".." not in relative_path.parts, f"审计账本路径不安全：{relative_text}")  # 拒绝绝对和父级路径。
        require(relative_text not in records, f"审计账本标签重复：{relative_text}")  # 拒绝同一路径多次登记。
        candidate = (audit_dir / relative_path).resolve(strict=False)  # 规范化当前候选文件路径。
        try:  # 尝试证明候选仍位于审计目录内部。
            candidate.relative_to(audit_root)  # 成功时表示候选没有逃逸审计目录。
        except ValueError as exc:  # 路径逃逸进入明确失败。
            raise RuntimeError(f"审计账本路径越界：{relative_text}") from exc  # 阻止读取包外任意文件。
        require(candidate.is_file(), f"审计账本登记文件缺失：{candidate}")  # 每个标签必须指向普通文件。
        records[relative_text] = digest  # 保存已验证格式和路径安全的记录。
    initial_metadata: dict[str, tuple[int, int]] = {}  # 初始化全部实际文件的起点元数据。
    for actual_path in audit_dir.rglob("*"):  # 递归枚举账本自身之外全部普通文件。
        if actual_path.is_file() and actual_path != ledger_path:  # 只纳入正式普通文件并排除自引用账本。
            relative_text = actual_path.relative_to(audit_dir).as_posix()  # 生成稳定 POSIX 标签。
            actual_stat = actual_path.stat()  # 记录当前文件大小和修改时间。
            initial_metadata[relative_text] = (actual_stat.st_size, actual_stat.st_mtime_ns)  # 冻结全局验证起点。
    require(set(records) == set(initial_metadata), "审计账本标签集合与实际文件集合不闭合。")  # 拒绝漏登和幽灵记录。
    for relative_text, expected_digest in records.items():  # 按账本记录逐项重算文件摘要。
        candidate = audit_dir / Path(relative_text)  # 绑定已通过安全检查的包内文件。
        before = candidate.stat()  # 记录当前文件哈希前元数据。
        actual_digest = sha256_file(candidate)  # 流式计算完整原始字节摘要。
        after = candidate.stat()  # 记录当前文件哈希后元数据。
        require(initial_metadata[relative_text] == (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"审计包文件哈希期间发生变化：{relative_text}")  # 当前文件必须全程稳定。
        require(actual_digest == expected_digest, f"审计包文件摘要不匹配：{relative_text}")  # 摘要不一致即拒绝正式发布。
    final_metadata: dict[str, tuple[int, int]] = {}  # 初始化全部文件的结束元数据。
    for actual_path in audit_dir.rglob("*"):  # 第二次递归枚举捕获新增、删除和后续漂移。
        if actual_path.is_file() and actual_path != ledger_path:  # 继续排除账本自身并只记录普通文件。
            relative_text = actual_path.relative_to(audit_dir).as_posix()  # 生成结束快照标签。
            actual_stat = actual_path.stat()  # 取得结束时大小和修改时间。
            final_metadata[relative_text] = (actual_stat.st_size, actual_stat.st_mtime_ns)  # 保存结束版本。
    require(final_metadata == initial_metadata, "审计包账本复核全窗口内文件集合或元数据发生变化。")  # 全局起止版本必须一致。
    return {  # 返回正式发布前的严格账本证据。
        "path": LEDGER_NAME,  # 账本在审计包内的固定相对路径。
        "entry_count": len(records),  # 除账本自身外的普通文件数量。
        "sha256": sha256_bytes(ledger_bytes),  # 账本自身完整字节 SHA-256。
        "self_excluded": True,  # 明确账本按设计排除自身避免递归摘要。
    }  # 完成严格账本验证结果。


def validate_staging_cleanup_target(staging_dir: Path, expected_name: str) -> Path:  # 输入候选 staging 路径和本次精确名称并返回安全规范路径。
    """参数：staging_dir 为候选目录，expected_name 为本次精确名称；返回：规范绝对路径；约束：目标须为 RUN_DIR 直属非链接隐藏 staging。"""  # 完整说明两个参数、路径返回和删除前安全约束。
    require(RUN_DIR.is_dir(), f"固定 RUN_DIR 不存在，拒绝清理：{RUN_DIR}")  # 清理前确认边界目录存在。
    run_root = RUN_DIR.resolve(strict=True)  # 取得固定运行目录规范绝对路径。
    required_prefix = f".{AUDIT_PREFIX}"  # 隐藏 staging 名称必须使用点号加正式前缀。
    require(expected_name.startswith(required_prefix) and expected_name.endswith(STAGING_SUFFIX), f"本次 staging 名称不符合固定格式：{expected_name}")  # 拒绝任意名称授权。
    require(staging_dir.name == expected_name, f"候选 staging 名称与本次名称不一致：{staging_dir.name}")  # 名称必须逐字相同。
    require(staging_dir.exists() and staging_dir.is_dir(), f"候选 staging 目录不存在：{staging_dir}")  # 只允许清理现存目录。
    require(not staging_dir.is_symlink(), f"候选 staging 是符号链接，拒绝递归清理：{staging_dir}")  # 防止链接目标越界。
    candidate_root = staging_dir.resolve(strict=True)  # 解析候选目录的真实绝对路径。
    require(candidate_root.parent == run_root, f"候选 staging 不在 RUN_DIR 直属范围：{candidate_root}")  # 只允许固定 run 的直属子目录。
    return candidate_root  # 返回已经证明安全的递归清理目标。


def cleanup_staging_directory(staging_dir: Path, expected_name: str) -> None:  # 输入本次 staging 路径和精确名称并安全递归删除。
    """参数：staging_dir 与 expected_name 标识本次隐藏目录；返回：None；约束：先通过安全验证，且永不接受正式审计目录。"""  # 完整说明两个参数、返回和递归删除边界。
    safe_target = validate_staging_cleanup_target(staging_dir, expected_name)  # 在删除前完成绝对路径、名称和链接检查。
    shutil.rmtree(safe_target)  # 使用单一 PowerShell 外的 Python 文件系统语义递归删除已验证 staging。
    require(not safe_target.exists(), f"staging 清理后仍存在：{safe_target}")  # 删除完成后确认目标消失。


def build_argument_parser() -> argparse.ArgumentParser:  # 无输入并返回不接受业务参数的安全 CLI 解析器。
    """参数：无；返回：零业务参数 argparse 解析器；约束：禁止选项缩写，--help 与未知参数须在任何副作用前退出。"""  # 完整说明解析器返回和 CLI 安全约束。
    parser = argparse.ArgumentParser(  # 创建严格参数解析器。
        prog=SCRIPT_PATH.name,  # 帮助标题使用当前脚本文件名。
        description="对固定 S10 运行执行一次只读 LINK180 POST1-only 审计；不接受 run、路径或覆盖参数。",  # 说明脚本固定范围和无可变目标。
        allow_abbrev=False,  # 禁止长选项缩写，未知输入必须明确失败。
    )  # 完成零业务参数解析器。
    return parser  # 返回仅含 argparse 自动帮助选项的解析器。


def main(argv: list[str] | None = None) -> int:  # 输入可选 CLI 参数并返回零表示完整通过、二表示 fail-closed 失败。
    """参数：argv 为可选 CLI 字符串列表，None 表示系统参数；返回：成功 0、失败 2；约束：帮助或未知参数由 argparse 直接退出且正式目录最后发布。"""  # 完整说明参数、退出码和副作用时序。
    parser = build_argument_parser()  # 在任何文件读取、目录创建或 MAPDL 调用前构造解析器。
    parsed_arguments = parser.parse_args(argv)  # --help 和未知参数在此直接 SystemExit，绝不进入执行流程。
    require(vars(parsed_arguments) == {}, "零参数 CLI 意外产生业务字段。")  # 防止后续新增未审计参数静默扩展权限。
    staging_dir: Path | None = None  # 初始化异常清理所需 staging 路径，创建前保持为空。
    staging_name = ""  # 初始化本次精确 staging 名称，创建后才授权清理。
    staging_created = False  # 只有当前进程成功创建目录后才允许异常清理，避免删除碰巧同名的既有目录。
    try:  # 捕获全部路径、输入、MAPDL、数值、谱系和提交异常。
        require(RUN_DIR.is_dir() and SOLVER_DIR.is_dir(), f"固定 S10 run 结构不存在：{RUN_DIR}")  # 确认固定运行结构。
        require(MAPDL_EXE.is_file(), f"MAPDL 可执行文件不存在：{MAPDL_EXE}")  # 确认固定执行程序。
        require(EQ_DB_PATH.is_file() and STATIC_RST_PATH.is_file(), "S10 平衡 DB 或静力 RST 缺失。")  # 确认两个只读源。
        active_before = active_heavy_processes()  # 获取启动前活动求解进程。
        require(not active_before, f"仍有活动求解进程，拒绝 POSTONLY：{active_before}")  # 禁止与其他 MAPDL 求解并发。
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")  # 生成微秒级 UTC 唯一目录标识。
        audit_id = f"{AUDIT_PREFIX}{timestamp}"  # 构造正式审计 ID。
        final_dir = RUN_DIR / audit_id  # 正式目录只在完整复核后出现。
        staging_name = f".{audit_id}{STAGING_SUFFIX}"  # 构造本次唯一隐藏 staging 名称。
        staging_dir = RUN_DIR / staging_name  # staging 与正式目录同父目录以支持原子改名。
        require(not final_dir.exists() and not staging_dir.exists(), "正式目录或本次 staging 已存在。")  # 拒绝覆盖任何既有目录。
        staging_dir.mkdir(parents=False, exist_ok=False)  # 排他创建隐藏 staging。
        staging_created = True  # 标记当前进程拥有该 staging 的清理权限。
        script_bytes = read_stable_bytes(SCRIPT_PATH)  # 冻结本次真实执行生成器源码。
        script_sha256 = sha256_bytes(script_bytes)  # 计算生成器源码快照摘要。
        script_snapshot_path = staging_dir / SCRIPT_SNAPSHOT_NAME  # 绑定包内生成器快照路径。
        write_new_bytes(script_snapshot_path, script_bytes)  # 写入与当前脚本逐字节一致的源码快照。
        input_text = build_apdl_input()  # 在内存构造完整 APDL 输入。
        input_scan = scan_input(input_text)  # 执行 strict allowlist、顺序和中文注释覆盖扫描。
        strict_violation_count = input_scan["unexpected_active_line_count"] + input_scan["missing_active_line_count"] + (0 if input_scan["active_line_order_match"] else 1)  # 汇总模板外、缺失和重排违规。
        require(strict_violation_count == 0, "POSTONLY 输入与 strict allowlist 模板不一致。")  # 任一活动行漂移即拒绝。
        require(input_scan["uncommented_executable_line_count"] == 0 and input_scan["non_chinese_comment_line_count"] == 0, "POSTONLY 输入中文注释覆盖不完整。")  # 强制逐行中文说明。
        required_keys = (  # 定义七项必须由活动命令证明的只读能力字段。
            "has_resume_eq_db",  # 必须恢复固定 LS2 平衡 DB。
            "has_static_rst_file_binding",  # 必须绑定固定静力 RST。
            "has_ls2_last_set",  # 必须读取冻结载荷步最后结果集。
            "has_result_substep_get",  # 必须实测当前结果集子步。
            "has_type4_selection",  # 必须只选择 TYPE4 LINK180。
            "has_smisc1_etable",  # 必须读取 LINK180 SMISC,1 轴力。
            "has_exit_nosave",  # 必须无保存退出独立会话。
        )  # 完成必需能力字段元组。
        require(all(input_scan[key] is True for key in required_keys), "POSTONLY 输入缺少固定只读活动命令。")  # 七项能力必须由活动行证明。
        input_path = staging_dir / INPUT_NAME  # 绑定 staging 内 APDL 输入路径。
        write_new_bytes(input_path, input_text.encode("utf-8"))  # 以 UTF-8 无 BOM 写入输入。
        source_before = {  # 记录执行前两个只读源身份。
            "equilibrium_database": file_identity(EQ_DB_PATH),  # 平衡 DB 执行前身份。
            "static_result": file_identity(STATIC_RST_PATH),  # 静力 RST 执行前身份。
        }  # 完成执行前源身份对象。
        process_preflight_record = {  # 构造启动前进程门禁记录。
            "active_mapdl_or_solution_process_count": EXPECTED_ACTIVE_PROCESS_COUNT,  # 启动前活动求解进程数采用命名零值。
            "processes": active_before,  # 保存空进程列表供机器复核。
        }  # 完成进程门禁记录。
        input_identity_record = {  # 构造 APDL 输入文件身份。
            "path": INPUT_NAME,  # 输入在审计包内的固定相对路径。
            "length_bytes": input_path.stat().st_size,  # 输入完整字节数。
            "sha256": sha256_file(input_path),  # 输入完整原始字节摘要。
        }  # 完成输入身份记录。
        input_preflight_record = input_identity_record | input_scan  # 合并文件身份和 strict allowlist 扫描结果。
        equilibrium_source_record = {  # 构造平衡 DB 执行前记录。
            "role": "equilibrium_database",  # 固定角色表示 LS2 平衡数据库。
            "path": f"../solver/{EQ_DB_PATH.name}",  # 相对审计目录的只读源路径。
        } | source_before["equilibrium_database"]  # 合并平衡 DB 完整身份。
        static_source_record = {  # 构造静力 RST 执行前记录。
            "role": "static_result",  # 固定角色表示合并静力结果。
            "path": f"../solver/{STATIC_RST_PATH.name}",  # 相对审计目录的只读源路径。
        } | source_before["static_result"]  # 合并静力 RST 完整身份。
        orchestrator_preflight_record = {  # 构造生成器谱系记录。
            "snapshot_path": SCRIPT_SNAPSHOT_NAME,  # 包内源码快照固定路径。
            "sha256": script_sha256,  # 当前脚本和快照共同摘要。
            "source_path": str(SCRIPT_PATH),  # 执行时外部脚本绝对路径。
        }  # 完成生成器谱系记录。
        source_protection_record = {  # 构造只读源保护策略记录。
            "audit_directory_isolated": True,  # 输出只写入独立 staging。
            "source_paths_outside_audit_directory": True,  # DB/RST 位于相邻 solver 目录。
            "database_save_prohibited": True,  # strict 模板仅允许 /EXIT,NOSAVE。
            "post_run_identity_recheck_required": True,  # 执行后必须再次计算源完整身份。
        }  # 完成源保护记录。
        mapdl_record = {  # 构造固定 MAPDL 程序身份和资源参数。
            "executable_path": str(MAPDL_EXE),  # 固定 ANSYS 2026 R1 可执行文件绝对路径。
            "executable_length_bytes": MAPDL_EXE.stat().st_size,  # 可执行文件完整字节数。
            "executable_sha256": sha256_file(MAPDL_EXE),  # 可执行文件完整摘要。
            "processes": MAPDL_PROCESS_COUNT,  # 使用命名的固定单进程数量。
            "parallel_mode": "SMP",  # 固定共享内存模式。
        }  # 完成 MAPDL 记录。
        preflight = {  # 构造启动前机器证据。
            "schema_version": EVIDENCE_SCHEMA_VERSION,  # 使用命名证据结构版本。
            "audit_id": audit_id,  # 固定正式审计 ID。
            "generated_utc": datetime.now(timezone.utc).isoformat(),  # 启动前证据 UTC 时间。
            "status": "PASSED",  # 仅表示启动前门禁已通过。
            "execution_mode": "POST1_ONLY_SMP1",  # 固定只读后处理和单进程模式。
            "publication_mode": "HIDDEN_STAGING_ATOMIC_RENAME",  # 声明正式目录采用同父原子发布。
            "launch_allowed": True,  # 所有启动前门禁通过后才写真值。
            "process_preflight": process_preflight_record,  # 记录启动前无活动求解进程。
            "input_preflight": input_preflight_record,  # 记录输入身份和严格扫描结果。
            "source_files": [equilibrium_source_record, static_source_record],  # 记录两个固定源执行前身份。
            "orchestrator": orchestrator_preflight_record,  # 绑定真实生成器源码快照和摘要。
            "source_protection": source_protection_record,  # 记录只读隔离策略。
            "mapdl": mapdl_record,  # 记录固定 MAPDL 程序和并行参数。
        }  # 完成 preflight 对象。
        write_new_bytes(staging_dir / PREFLIGHT_NAME, json_bytes(preflight))  # 写入 preflight JSON。
        launch_args = [  # 构造实际 staging SMP1 批处理参数。
            str(MAPDL_EXE),  # 固定 MAPDL 可执行文件。
            "-b",  # 启用批处理模式。
            "-smp",  # 启用共享内存并行模式。
            "-np",  # 指定后续进程数参数。
            str(MAPDL_PROCESS_COUNT),  # 把命名进程数转换为 MAPDL CLI 字符串。
            "-j",  # 指定后续作业名参数。
            POST_JOBNAME,  # 使用独立 POST1-only 作业名。
            "-dir",  # 指定后续工作目录参数。
            str(staging_dir),  # 实际工作目录为隐藏 staging。
            "-i",  # 指定后续输入文件参数。
            str(input_path),  # 输入文件位于隐藏 staging。
            "-o",  # 指定后续主输出文件参数。
            str(staging_dir / OUT_NAME),  # OUT 写入隐藏 staging。
        ]  # 完成实际启动参数。
        replay_args = launch_args.copy()  # 从已审计实际参数复制正式复现参数骨架。
        replay_args[8] = str(final_dir)  # 把复现工作目录替换为原子发布后的正式目录。
        replay_args[10] = str(final_dir / INPUT_NAME)  # 把复现输入路径替换为正式目录路径。
        replay_args[12] = str(final_dir / OUT_NAME)  # 把复现 OUT 路径替换为正式目录路径。
        actual_header = "# 实际命令在隐藏 staging 中执行；完整复核后目录原子改名。\n"  # 解释历史真实命令角色。
        actual_command = "ACTUAL_STAGING_COMMAND=" + subprocess.list2cmdline(launch_args) + "\n"  # 渲染实际 staging 命令。
        replay_header = "# 下列命令使用发布后的正式目录复现同一 POST1-only 输入。\n"  # 解释正式复现命令角色。
        replay_command = "FORMAL_REPLAY_COMMAND=" + subprocess.list2cmdline(replay_args) + "\n"  # 渲染正式目录复现命令。
        launch_text = actual_header + actual_command + replay_header + replay_command  # 合并历史真实命令和正式复现命令。
        write_new_bytes(staging_dir / LAUNCH_NAME, launch_text.encode("utf-8"))  # 保存执行与复现命令。
        create_no_window_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # 获取 Windows 隐藏窗口标志，非 Windows 回退为零。
        below_normal_priority_flag = BELOW_NORMAL_PRIORITY_CLASS_FLAG  # 使用已解释的 Windows 低优先级标志常量。
        creation_flags = create_no_window_flag | below_normal_priority_flag  # 合并隐藏窗口和低优先级标志。
        completed = subprocess.run(launch_args, cwd=staging_dir, timeout=MAPDL_TIMEOUT_SECONDS, check=False, capture_output=True, creationflags=creation_flags)  # 同步执行只读 MAPDL。
        require(completed.returncode == SUCCESS_EXIT_CODE, f"MAPDL POSTONLY 返回非零退出码：{completed.returncode}")  # 使用命名成功退出码拒绝异常执行。
        out_path = staging_dir / OUT_NAME  # 绑定主 OUT 路径。
        err_path = staging_dir / ERR_NAME  # 绑定 ERR 路径。
        require(out_path.is_file() and err_path.is_file(), "MAPDL POSTONLY 未生成 OUT/ERR。")  # 两份原生诊断必须存在。
        out_text = out_path.read_text(encoding="utf-8", errors="replace")  # 读取主 OUT ASCII 诊断。
        err_text = err_path.read_text(encoding="utf-8", errors="replace")  # 读取 ERR ASCII 诊断。
        diagnostic_text = out_text + "\n" + err_text  # 合并 OUT 与 ERR 形成统一诊断口径。
        warning_count = len(re.findall(r"(?im)^\s*\*{3}\s+WARNING\s+\*{3}(?:\s|$)", diagnostic_text))  # 统计合并 warning 标题。
        error_count = len(re.findall(r"(?im)^\s*\*{3}\s+ERROR\s+\*{3}(?:\s|$)", diagnostic_text))  # 统计合并 error 标题。
        fatal_count = len(re.findall(r"(?im)^\s*\*{3}\s+FATAL(?:\s+\*{3})?(?:\s|$)", diagnostic_text))  # 统计合并 fatal 标题。
        negative_pivot_count = len(re.findall(r"(?i)\bnegative\s+pivots?\b", diagnostic_text))  # 统计负主元诊断短语。
        zero_pivot_count = len(re.findall(r"(?i)\bzero\s+pivots?\b", diagnostic_text))  # 统计零主元诊断短语。
        summary_warnings = [int(value) for value in re.findall(r"(?im)^\s*NUMBER OF WARNING MESSAGES ENCOUNTERED=\s*(\d+)\s*$", out_text)]  # 提取 OUT 退出摘要 warning 数。
        summary_errors = [int(value) for value in re.findall(r"(?im)^\s*NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*(\d+)\s*$", out_text)]  # 提取 OUT 退出摘要 error 数。
        diagnostic_counts = (  # 汇总五类必须为零的诊断计数。
            warning_count,  # OUT+ERR warning 标题数量。
            error_count,  # OUT+ERR error 标题数量。
            fatal_count,  # OUT+ERR fatal 标题数量。
            negative_pivot_count,  # OUT+ERR 负主元短语数量。
            zero_pivot_count,  # OUT+ERR 零主元短语数量。
        )  # 完成诊断计数元组。
        expected_diagnostic_counts = (EXPECTED_DIAGNOSTIC_COUNT,) * len(diagnostic_counts)  # 按实际诊断类别数构造全零期望元组。
        require(diagnostic_counts == expected_diagnostic_counts, "POSTONLY OUT/ERR 存在 warning、error、fatal 或负/零主元。")  # 合并诊断必须全零。
        require(summary_warnings == [EXPECTED_SUMMARY_COUNT] and summary_errors == [EXPECTED_SUMMARY_COUNT], "POSTONLY 退出摘要 warning/error 不是唯一零值。")  # 摘要必须各出现一次且为零。
        require("EXIT MAPDL WITHOUT SAVING DATABASE" in out_text and "RUN COMPLETED" in out_text, "POSTONLY 未确认 NOSAVE 正常完成。")  # 确认无保存退出和正常完成。
        summary = parse_summary(staging_dir / SUMMARY_NAME)  # 解析 MAPDL 机器摘要。
        force_stats = parse_force_csv(staging_dir / CSV_NAME)  # 直接解析轴力表。
        actual_count = summary_integer(summary, "ACTUAL_COUNT")  # 读取整数实际选择数。
        written_count = summary_integer(summary, "WRITTEN_COUNT")  # 读取整数写出数。
        summary_nonpositive_count = summary_integer(summary, "NONPOSITIVE_COUNT")  # 读取整数非正计数。
        summary_gate_value = summary_integer(summary, "GATE_PASS")  # 读取整数 MAPDL 门禁值。
        result_load_step = summary_integer(summary, "RESULT_LOAD_STEP")  # 读取实际载荷步。
        result_substep = summary_integer(summary, "RESULT_SUBSTEP")  # 读取实际子步。
        result_time = summary.get("RESULT_TIME", math.nan)  # 读取实际结果集时间。
        minimum_element_id = summary_integer(summary, "MIN_ELEMENT_ID")  # 读取摘要最小轴力单元号。
        maximum_element_id = summary_integer(summary, "MAX_ELEMENT_ID")  # 读取摘要最大轴力单元号。
        require(actual_count == EXPECTED_LINK_COUNT and written_count == EXPECTED_LINK_COUNT, "MAPDL TYPE4 实际数或写出数不是 73692。")  # 检查数量闭合。
        require(summary_nonpositive_count == EXPECTED_NONPOSITIVE_COUNT and summary_gate_value == MAPDL_GATE_PASS_VALUE, "MAPDL 摘要未通过正轴力门禁。")  # 使用命名期望值检查摘要门禁。
        require(result_load_step == EXPECTED_LOAD_STEP and result_substep == EXPECTED_RESULT_SUBSTEP and abs(result_time - EXPECTED_RESULT_TIME) <= RESULT_TIME_TOLERANCE, "POSTONLY 结果集不是 LS2/substep1/time=1.001。")  # 使用命名期望值和时间容差检查实测结果集身份。
        require(force_stats["csv_row_count"] == EXPECTED_LINK_COUNT and force_stats["unique_element_count"] == EXPECTED_LINK_COUNT, "轴力 CSV 覆盖不闭合。")  # 检查 CSV 行数和唯一数。
        require(force_stats["duplicate_element_count"] == 0 and force_stats["invalid_numeric_line_count"] == 0 and force_stats["nonpositive_count"] == 0, "轴力 CSV 含重复、非法或非正记录。")  # 检查原始数据质量。
        require(force_stats["minimum_force_n"] > NONPOSITIVE_FORCE_LIMIT_N, "最小 LINK180 轴力不是严格正值。")  # 使用命名非正阈值强制全部索单元受拉。
        require(abs(force_stats["minimum_force_n"] - summary["MIN_FORCE_N"]) <= max(FORCE_ABSOLUTE_TOLERANCE_N, abs(summary["MIN_FORCE_N"]) * FORCE_RELATIVE_TOLERANCE), "CSV 最小轴力与摘要不一致。")  # 使用命名绝对和相对容差复核最小轴力。
        require(abs(force_stats["maximum_force_n"] - summary["MAX_FORCE_N"]) <= max(FORCE_ABSOLUTE_TOLERANCE_N, abs(summary["MAX_FORCE_N"]) * FORCE_RELATIVE_TOLERANCE), "CSV 最大轴力与摘要不一致。")  # 使用命名绝对和相对容差复核最大轴力。
        require(force_stats["minimum_element_id"] == minimum_element_id and force_stats["maximum_element_id"] == maximum_element_id, "CSV 极值单元号与摘要不一致。")  # 复核两个极值对应单元号。
        source_after = {  # 记录执行后两个只读源身份。
            "equilibrium_database": file_identity(EQ_DB_PATH),  # 平衡 DB 执行后身份。
            "static_result": file_identity(STATIC_RST_PATH),  # 静力 RST 执行后身份。
        }  # 完成执行后源身份对象。
        source_records: list[dict[str, Any]] = []  # 初始化源前后比较记录。
        for role, path in (("equilibrium_database", EQ_DB_PATH), ("static_result", STATIC_RST_PATH)):  # 按固定角色比较两个源文件。
            before = source_before[role]  # 读取执行前身份。
            after = source_after[role]  # 读取执行后身份。
            source_record = {  # 构造当前源逐字段比较记录。
                "role": role,  # 固定源角色。
                "path": f"../solver/{path.name}",  # 相对正式审计目录的源路径。
                "before": before,  # 执行前完整身份。
                "after": after,  # 执行后完整身份。
                "length_unchanged": before["length_bytes"] == after["length_bytes"],  # 字节数是否不变。
                "creation_time_unchanged": before["creation_time_utc"] == after["creation_time_utc"],  # 创建时间是否不变。
                "last_write_time_unchanged": before["last_write_time_utc"] == after["last_write_time_utc"],  # 修改时间是否不变。
                "sha256_unchanged": before["sha256"] == after["sha256"],  # 完整内容摘要是否不变。
            }  # 完成当前源比较记录。
            source_records.append(source_record)  # 保存当前源比较记录。
        integrity_keys = (  # 定义全部源完整性布尔字段。
            "length_unchanged",  # 文件字节数必须不变。
            "creation_time_unchanged",  # Windows 创建时间必须不变。
            "last_write_time_unchanged",  # 最后修改时间必须不变。
            "sha256_unchanged",  # 完整原始字节摘要必须不变。
        )  # 完成源完整性字段元组。
        source_integrity_passed = all(all(record[key] is True for key in integrity_keys) for record in source_records)  # 汇总两个源文件完整性。
        require(source_integrity_passed, "POSTONLY 前后源 DB/RST 身份发生变化。")  # 源完整性是硬门禁。
        active_after = active_heavy_processes()  # 获取执行后活动求解进程。
        require(not active_after, f"POSTONLY 结束后仍有活动求解进程：{active_after}")  # 禁止残留 MAPDL/MPI。
        require(sha256_file(SCRIPT_PATH) == script_sha256 and sha256_file(script_snapshot_path) == script_sha256, "执行生成器源码或包内快照发生漂移。")  # 发布前再次绑定真实脚本版本。
        postflight = {  # 构造执行后源完整性对象。
            "schema_version": EVIDENCE_SCHEMA_VERSION,  # 使用命名证据结构版本。
            "audit_id": audit_id,  # 固定正式审计 ID。
            "checked_utc": datetime.now(timezone.utc).isoformat(),  # 执行后检查 UTC 时间。
            "source_integrity_passed": True,  # 两个源全部字段相同后的真值。
            "exit_without_saving_confirmed": True,  # OUT 已确认 NOSAVE 的真值。
            "active_mapdl_process_count_after": EXPECTED_ACTIVE_PROCESS_COUNT,  # 执行后活动求解进程数采用命名零值。
            "files": source_records,  # 两个源文件逐字段比较记录。
        }  # 完成 postflight 对象。
        write_new_bytes(staging_dir / POSTFLIGHT_NAME, json_bytes(postflight))  # 写入 postflight JSON。
        execution_record = {  # 构造最终 QA 执行证据。
            "mode": "POST1_ONLY_SMP1",  # 固定执行模式。
            "mapdl_exit_code": completed.returncode,  # MAPDL 进程退出码。
            "processes": MAPDL_PROCESS_COUNT,  # 使用命名的固定单进程数量。
            "input_path": INPUT_NAME,  # 包内 APDL 输入路径。
            "input_sha256": sha256_file(input_path),  # APDL 输入完整摘要。
            "input_forbidden_command_count": strict_violation_count,  # strict allowlist 违规总数，兼容 finalizer 旧字段名。
            "input_allowlist_exact_match": True,  # 活动行与模板逐项同序。
            "uncommented_executable_line_count": input_scan["uncommented_executable_line_count"],  # 未解释活动行数量。
            "non_chinese_comment_line_count": input_scan["non_chinese_comment_line_count"],  # 非中文 APDL 注释行数量。
            "mapdl_warning_count": warning_count,  # OUT+ERR 合并 warning 数。
            "mapdl_error_count": error_count,  # OUT+ERR 合并 error 数。
            "mapdl_fatal_count": fatal_count,  # OUT+ERR 合并 fatal 数。
            "negative_pivot_count": negative_pivot_count,  # OUT+ERR 负主元短语数。
            "zero_pivot_count": zero_pivot_count,  # OUT+ERR 零主元短语数。
            "summary_warning_counts": summary_warnings,  # OUT 退出摘要 warning 列表。
            "summary_error_counts": summary_errors,  # OUT 退出摘要 error 列表。
            "err_length_bytes": err_path.stat().st_size,  # ERR 完整字节数。
            "exit_without_saving_confirmed": True,  # NOSAVE 完成标志。
            "out_sha256": sha256_file(out_path),  # OUT 完整摘要。
            "err_sha256": sha256_file(err_path),  # ERR 完整摘要。
        }  # 完成执行证据。
        result_set_record = {  # 构造实测结果集身份。
            "load_step": result_load_step,  # 实测载荷步 2。
            "substep": result_substep,  # 实测子步 1。
            "time": result_time,  # 实测伪时间 1.001。
            "basis": "S10 final no-stabilization LS2 hold state used by perturbation modal analysis",  # 说明结果集工程角色。
        }  # 完成结果集对象。
        force_record = {  # 构造轴力 QA 基础字段。
            "result_item": "SMISC,1",  # LINK180 轴力结果项。
            "unit": "N",  # 轴力单位为牛顿。
            "expected_count": EXPECTED_LINK_COUNT,  # 冻结期望 LINK180 数量。
            "actual_count": actual_count,  # MAPDL 实际选择数量。
            "written_count": written_count,  # MAPDL 实际写出数量。
        } | force_stats | {  # 合并 CSV 深度统计。
            "summary_gate_value": summary_gate_value,  # MAPDL 内部门禁值。
            "csv_path": CSV_NAME,  # 包内轴力 CSV 路径。
        }  # 完成轴力 QA 对象。
        source_integrity_record = {  # 构造最终 QA 的源完整性摘要。
            "source_integrity_passed": True,  # DB/RST 全部前后字段相同后的真值。
            "postflight_path": POSTFLIGHT_NAME,  # 包内详细 postflight JSON 路径。
            "equilibrium_database_sha256_before_after": source_after["equilibrium_database"]["sha256"],  # 平衡 DB 前后共同摘要。
            "static_result_sha256_before_after": source_after["static_result"]["sha256"],  # 静力 RST 前后共同摘要。
        }  # 完成源完整性摘要。
        orchestrator_qa_record = {  # 构造最终 QA 的生成器谱系摘要。
            "snapshot_path": SCRIPT_SNAPSHOT_NAME,  # 包内真实脚本快照路径。
            "sha256": script_sha256,  # 外部脚本与包内快照共同摘要。
        }  # 完成生成器谱系摘要。
        qa = {  # 构造最终机器 QA。
            "schema_version": EVIDENCE_SCHEMA_VERSION,  # 使用命名证据结构版本。
            "audit_id": audit_id,  # 固定正式审计 ID。
            "generated_utc": datetime.now(timezone.utc).isoformat(),  # QA 生成 UTC 时间。
            "status": "PASSED",  # 全部硬门禁通过后的状态。
            "gate_passed": True,  # 机器门禁通过真值。
            "hard_blocker_closed": "LINK180_NONPOSITIVE_AXIAL_FORCE_REVIEW",  # 本审计关闭的固定硬阻断。
            "publication_mode": "HIDDEN_STAGING_ATOMIC_RENAME",  # 正式目录发布协议。
            "execution": execution_record,  # 完整执行诊断证据。
            "result_set": result_set_record,  # 实测结果集身份。
            "link180_axial_force": force_record,  # 轴力覆盖和极值证据。
            "source_integrity": source_integrity_record,  # 绑定 postflight 和两个源摘要。
            "orchestrator": orchestrator_qa_record,  # 绑定包内生成器源码快照。
            "artifact_hash_manifest": LEDGER_NAME,  # 固定包账本路径。
            "artifact_hash_manifest_excludes": [LEDGER_NAME],  # 账本仅排除自身避免递归。
        }  # 完成最终 QA。
        write_new_bytes(staging_dir / QA_NAME, json_bytes(qa))  # 写入机器 QA。
        write_new_bytes(staging_dir / FIELD_DICTIONARY_NAME, build_field_dictionary().encode("utf-8"))  # 写入字段说明。
        write_new_bytes(staging_dir / QA_REPORT_NAME, build_qa_report(qa).encode("utf-8"))  # 写入用户可读报告。
        ledger_sha256, ledger_entries = write_artifact_ledger(staging_dir)  # 生成自排除包账本。
        ledger_validation = validate_artifact_ledger(staging_dir)  # 在正式发布前严格复核全部账本条目。
        require(ledger_validation["sha256"] == ledger_sha256 and ledger_validation["entry_count"] == ledger_entries, "账本写入摘要或条目数与严格复核不一致。")  # 写入结果与独立复核必须一致。
        result = {  # 构造原子发布后的成功摘要。
            "status": "PASSED",  # 全部门禁和账本复核通过。
            "audit_id": audit_id,  # 正式审计 ID。
            "audit_dir": str(final_dir),  # 原子发布后的正式目录。
            "link180_count": actual_count,  # 实测 LINK180 数量。
            "nonpositive_count": force_stats["nonpositive_count"],  # 非正轴力数量。
            "minimum_force_n": force_stats["minimum_force_n"],  # 最小轴力，单位 N。
            "maximum_force_n": force_stats["maximum_force_n"],  # 最大轴力，单位 N。
            "source_integrity_passed": True,  # 源 DB/RST 前后身份一致。
            "artifact_ledger_entries": ledger_entries,  # 包账本条目数。
            "artifact_ledger_sha256": ledger_sha256,  # 包账本自身摘要。
            "orchestrator_sha256": script_sha256,  # 本次生成器源码摘要。
        }  # 完成成功摘要。
        staging_dir.rename(final_dir)  # 同父目录原子改名是正式包唯一 commit 动作，之后不再执行可失败文件操作。
    except Exception as exc:  # 任一路径、执行、门禁、账本或原子发布失败进入统一非零返回。
        cleanup_error = ""  # 初始化异常清理错误说明。
        if staging_created and staging_dir is not None and staging_dir.exists():  # 仅清理当前进程确已创建且仍存在的 staging。
            try:  # 尝试按严格边界安全清理本次 staging。
                cleanup_staging_directory(staging_dir, staging_name)  # 递归删除已验证位于 RUN_DIR 内的隐藏 staging。
            except Exception as cleanup_exc:  # 清理失败必须与原始错误同时披露。
                cleanup_error = f"；staging 清理失败：{cleanup_exc}"  # 聚合清理失败上下文。
        print(f"S10 LINK180 POSTONLY FAILED: {exc}{cleanup_error}", flush=True)  # 输出具体失败原因且不伪造通过。
        return FAILURE_EXIT_CODE  # 返回命名的 fail-closed 失败退出码。
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)  # 成功时输出与正式目录一致的机器摘要。
    return SUCCESS_EXIT_CODE  # 返回命名的成功退出码表示只读轴力审计已完整原子发布。


if __name__ == "__main__":  # 仅直接执行脚本时进入审计流程，导入模块不会启动 MAPDL。
    raise SystemExit(main())  # 把明确退出码交给操作系统和调用方。
