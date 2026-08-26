"""准备、执行并审计 U01 小算例套件；本脚本拒绝装载或启动任何全桥输入。"""  # 模块说明限定脚本只能处理任务书第 5 节的隔离小模型。

from __future__ import annotations  # 启用延迟类型注解，避免运行时解析复合类型带来兼容差异。

import argparse  # 解析显式的 ``--execute`` 开关，默认只准备而不启动 MAPDL。
import csv  # 写出不支持注释的门禁明细 CSV；字段含义同步写入 Markdown。
import ctypes  # 调用 Windows 内存状态 API，以重新核验 8 GiB 全桥启动门槛。
import hashlib  # 计算可执行文件、源模板、输入快照和结果产物的 SHA-256。
import json  # 生成任务书要求的 manifest.json 与 U01_status.json。
import math  # 计算相对误差、向量范数和有限转动解析量。
import os  # 使用 ``os.replace`` 原子更新状态 JSON，避免半写文件被误读。
import re  # 从 MAPDL 主输出中提取原生错误数、警告数和完成标志。
import secrets  # 生成两位随机十六进制后缀，防止同秒准备产生重复作业名。
import shutil  # 将输入快照真实复制到各自 solver 子目录，并复制机器结果到 post。
import subprocess  # 仅在用户显式传入 ``--execute`` 时前台运行白名单 U01 小作业。
import sys  # 返回可由外部调度识别的成功或失败退出码。
import time  # 记录每个 MAPDL 小作业的前台运行耗时，单位秒。
from datetime import datetime, timezone  # 生成不依赖本地时区歧义的 UTC 作业身份。
from pathlib import Path  # 以可解析路径对象实施工作区边界、复制和哈希检查。
from typing import Any  # 标注 JSON 兼容的异构字典值，避免省略接口约束。


SCRIPT_PATH = Path(__file__).resolve()  # 解析当前 U01 编排脚本绝对路径，供工程定位、快照复制和 SHA-256 身份封存共用。
V2_ROOT = SCRIPT_PATH.parents[1]  # 将脚本父级解析为附件 2-3 V2.0 权威工程根目录。
WORKSPACE_ROOT = V2_ROOT.parents[1]  # 将二级父目录解析为 D:\张靖皋大桥 工作区根目录，避免误跳到 D:\ 盘符根目录。
ULTRA_RUNS_ROOT = V2_ROOT / "ultra_runs"  # 把新执行链限制在与历史 runs 隔离的 ultra_runs 根目录。
TEMPLATE_ROOT = SCRIPT_PATH.parent / "u01_templates"  # 定位本脚本旁的正式 U01 APDL 模板目录。
U00_RUN = ULTRA_RUNS_ROOT / "U00_SOURCE_GATE_20260715T024455Z"  # 显式绑定已审核 U00，不按“最新目录”通配选择。
U00_STATUS_PATH = U00_RUN / "U00_status.json"  # 指向 U00 三态门禁文件，只有 PASS_A 才允许准备 U01。
U00_ENV_PATH = U00_RUN / "mapdl_environment.json"  # 指向已封存 MAPDL 路径、版本和可执行哈希记录。
MAPDL_EXE = Path(r"D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe")  # 固定使用 U00 审核过的 2026 R1 可执行文件。
LINK_SOURCE = WORKSPACE_ROOT / "benchmark" / "catwalk_dynamics_known_answer_20260713" / "vm53_prestressed_string_modal.inp"  # 复用官方 VM53 已知答案输入作为完整索链来源。
MPC_SOURCE = V2_ROOT / "runs" / "modal_20260714_0627_penalty5e10_continue_stab1e4" / "verification_snapshot" / "mpc184_penalty_5e10.inp"  # 复用已审计 5E10 偏置刚臂输入作为 MPC 来源。
MIN_FULL_SOLVE_BYTES = 8 * 1024**3  # 将任务书全桥启动最低可用物理内存固定为 8 GiB 字节数。
MAX_JOBNAME_LENGTH = 28  # 限制作业名不超过 28 个 ASCII 字符，为 DMP 分区后缀保留空间。
ALLOWED_JOB_PREFIX = "cw_u01_"  # 只允许 U01 白名单前缀，阻止脚本被改参数后启动 B00 或旧作业。
FORBIDDEN_JOB_PREFIXES = ("attachment23_v2", "a23v2_")  # 显式拒绝任务书列出的历史污染作业名前缀。


class MemoryStatusEx(ctypes.Structure):  # 定义 Windows GlobalMemoryStatusEx 所需的固定二进制结构。
    """保存 Windows 返回的物理与虚拟内存计数；各字段单位均为字节或百分比。"""  # 类说明给出结构用途、输出单位和平台约束。

    _fields_ = [  # 按 Windows MEMORYSTATUSEX ABI 顺序声明全部字段，禁止重排。
        ("length", ctypes.c_ulong),  # 结构长度字段，调用前必须写入 sizeof(MemoryStatusEx)。
        ("memory_load", ctypes.c_ulong),  # 当前物理内存负载百分比，范围 0 至 100。
        ("total_physical", ctypes.c_ulonglong),  # 主机总物理内存字节数。
        ("available_physical", ctypes.c_ulonglong),  # 当前可用物理内存字节数，决定全桥门禁。
        ("total_page_file", ctypes.c_ulonglong),  # 总提交限制字节数，用于辅助诊断而不替代物理内存门禁。
        ("available_page_file", ctypes.c_ulonglong),  # 当前可用提交字节数，用于报告内存压力。
        ("total_virtual", ctypes.c_ulonglong),  # 当前进程地址空间总字节数。
        ("available_virtual", ctypes.c_ulonglong),  # 当前进程可用地址空间字节数。
        ("available_extended_virtual", ctypes.c_ulonglong),  # 保留扩展地址空间字段，现代 64 位 Windows 通常为零。
    ]  # 结束 ABI 字段声明，字段数量与 Windows 文档保持一致。


def utc_now() -> datetime:  # 定义统一 UTC 时钟函数，避免目录名、manifest 和日志使用不同时间源。
    """返回带 UTC 时区的当前时间；无参数，输出为 timezone-aware ``datetime``。"""  # 函数说明明确输入为空和输出时区约束。

    return datetime.now(timezone.utc)  # 读取系统 UTC 时间并保留显式时区信息。


def sha256_file(path: Path) -> str:  # 定义流式文件哈希函数，参数为现存文件路径，返回小写十六进制摘要。
    """计算 ``path`` 的 SHA-256；输入必须是文件，输出为 64 字符小写十六进制字符串。"""  # 函数说明记录输入、输出及文件存在约束。

    digest = hashlib.sha256()  # 创建新的 SHA-256 状态，避免不同文件共享摘要状态。
    with path.open("rb") as handle:  # 以二进制只读方式打开文件，确保换行和编码不会改变哈希。
        for block in iter(lambda: handle.read(1024 * 1024), b""):  # 以 1 MiB 块读取，兼顾小文件和大输出内存占用。
            digest.update(block)  # 将当前原始字节块加入摘要计算。
    return digest.hexdigest()  # 返回稳定的 64 字符小写十六进制摘要。


def read_json(path: Path) -> dict[str, Any]:  # 定义 JSON 读取函数，参数为 UTF-8 文件路径，输出为字典。
    """读取 UTF-8 JSON 对象；输入必须存在且顶层为对象，输出为可变字典。"""  # 函数说明给出输入文件和顶层类型约束。

    value = json.loads(path.read_text(encoding="utf-8"))  # 按 UTF-8 读取并解析 JSON，拒绝带注释或无效语法。
    if not isinstance(value, dict):  # 检查顶层类型，防止数组被误当成 manifest 对象。
        raise TypeError(f"JSON 顶层不是对象：{path}")  # 以可复核路径说明类型错误并立即停止。
    return value  # 返回已验证的 JSON 字典。


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:  # 定义原子 JSON 写入函数，参数为目标路径和字典，无返回值。
    """原子写入 UTF-8 JSON；输入对象必须可序列化，输出文件采用两空格缩进并以换行结尾。"""  # 函数说明明确输入、输出和序列化约束。

    temporary = path.with_suffix(path.suffix + ".tmp")  # 在同目录构造临时文件，确保 os.replace 不跨卷。
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"  # 保留中文、使用两空格缩进并添加 POSIX 末换行。
    temporary.write_text(payload, encoding="utf-8")  # 先完整写入临时文件，避免读者看到半个 JSON。
    os.replace(temporary, path)  # 原子替换目标文件；同一路径旧版本不会出现部分更新。


def write_new_text(path: Path, text: str) -> None:  # 定义禁止覆盖的文本写入函数，参数为路径和完整文本。
    """创建新的 UTF-8 文本；若目标已存在则失败，输出总是以调用者提供的内容为准。"""  # 函数说明强调不可覆盖约束。

    with path.open("x", encoding="utf-8", newline="\n") as handle:  # 使用排他创建模式并统一 LF 换行，已有文件会抛出异常。
        handle.write(text)  # 一次写入完整文本，使输入快照内容可直接哈希。


def memory_snapshot() -> dict[str, int | bool]:  # 定义当前内存读取函数，无参数，返回字节计数和全桥门禁布尔值。
    """读取 Windows 当前内存；输出含总量、可用量、负载及是否达到 8 GiB 全桥门槛。"""  # 函数说明列出输出语义与单位。

    status = MemoryStatusEx()  # 创建零初始化的 Windows 内存状态结构。
    status.length = ctypes.sizeof(MemoryStatusEx)  # 写入结构字节长度，这是 Windows API 的强制输入。
    succeeded = bool(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)))  # 调用内核 API 并把非零返回值解释为成功。
    if not succeeded:  # 检查 API 调用结果，避免用全零内存值做危险放行。
        raise OSError("GlobalMemoryStatusEx 调用失败，不能核验全桥内存门禁。")  # 无法读取内存时采取失败关闭策略。
    return {  # 返回只含 JSON 基本类型的内存快照对象。
        "total_physical_bytes": int(status.total_physical),  # 写入总物理内存字节数。
        "available_physical_bytes": int(status.available_physical),  # 写入当前可用物理内存字节数。
        "available_page_file_bytes": int(status.available_page_file),  # 写入当前可用提交字节数。
        "memory_load_percent": int(status.memory_load),  # 写入当前物理内存负载百分比。
        "full_solve_memory_ready": bool(status.available_physical >= MIN_FULL_SOLVE_BYTES),  # 仅当可用物理内存不少于 8 GiB 时标记全桥就绪。
    }  # 结束内存快照对象。


def validate_u00() -> dict[str, Any]:  # 定义 U00 前置验证函数，无参数，返回环境清单。
    """要求固定 U00 为 PASS_A 且可执行哈希未漂移；失败时抛异常，成功时返回环境对象。"""  # 函数说明给出输入来源、输出和失败策略。

    status = read_json(U00_STATUS_PATH)  # 读取显式绑定的 U00 三态门禁文件。
    if status.get("status") != "PASS_A":  # 只接受完整源链 PASS_A，PASS_B 或 FAIL 均不得继续 U01 正式链。
        raise RuntimeError(f"U00 不是 PASS_A：{status.get('status')}")  # 报告实际状态并停止准备。
    environment = read_json(U00_ENV_PATH)  # 读取 U00 封存的 MAPDL 环境与可执行哈希。
    if not MAPDL_EXE.is_file():  # 检查固定 MAPDL 可执行文件仍然存在。
        raise FileNotFoundError(MAPDL_EXE)  # 以实际路径报告缺失文件。
    actual_hash = sha256_file(MAPDL_EXE)  # 重新计算当前可执行文件哈希，防止升级或替换后沿用旧结论。
    expected_hash = str(environment.get("executable_sha256", "")).lower()  # 读取 U00 封存哈希并统一为小写。
    if actual_hash.lower() != expected_hash:  # 比较当前和封存哈希，任何字节漂移都拒绝执行。
        raise RuntimeError(f"MAPDL 可执行哈希漂移：{actual_hash} != {expected_hash}")  # 报告两份摘要供人工复核。
    return environment  # 返回已验证环境对象，供 manifest 写入版本和并行设置。


def make_jobname(case_index: int, stamp: str, suffix: str) -> str:  # 定义唯一作业名函数，输入案例序号、时间戳和随机后缀。
    """生成 ``cw_u01`` 作业名；序号范围 1..99，时间戳为 MMDDtHHMMSS，输出仅含小写 ASCII、数字和下划线。"""  # 函数说明解释三个参数和输出限制。

    if not 1 <= case_index <= 99:  # 要求案例序号落在两位十进制可表达的 1 至 99 闭区间，防止零号或三位编号破坏固定身份格式。
        raise ValueError(f"U01 案例序号超出 1..99：{case_index}")  # 报告实际序号并在构造作业名前失败关闭。
    if not re.fullmatch(r"\d{4}t\d{6}", stamp):  # 要求时间戳严格采用四位月日、字面量 t 和六位时分秒组成的 MMDDtHHMMSS 格式。
        raise ValueError(f"U01 时间戳格式非法：{stamp}")  # 拒绝长度漂移、路径字符或大写 T，保证作业名可预测且仅含白名单字符。
    if not re.fullmatch(r"[0-9a-f]{2}", suffix):  # 要求随机后缀恰好为两位小写十六进制字符，对应 secrets.token_hex(1) 的 8 位随机量。
        raise ValueError(f"U01 随机后缀格式非法：{suffix}")  # 拒绝空后缀、非十六进制值或额外字符，维持同秒碰撞防护约束。
    jobname = f"cw_u01_{case_index:02d}_{stamp}_{suffix}"  # 组合固定前缀、两位序号、秒级 UTC 和两位随机后缀。
    if len(jobname) > MAX_JOBNAME_LENGTH:  # 检查 DMP 安全长度，防止分区后缀截断作业身份。
        raise ValueError(f"作业名过长：{jobname}")  # 报告实际作业名并停止准备。
    if not re.fullmatch(r"[a-z0-9_]+", jobname):  # 限制字符集为小写 ASCII、数字和下划线。
        raise ValueError(f"作业名含非法字符：{jobname}")  # 拒绝空格、中文、路径符号或 shell 元字符。
    if not jobname.startswith(ALLOWED_JOB_PREFIX):  # 检查作业名仍属于 U01 白名单。
        raise ValueError(f"作业名不在 U01 白名单：{jobname}")  # 防止该脚本被复用于全桥阶段。
    if any(jobname.startswith(prefix) for prefix in FORBIDDEN_JOB_PREFIXES):  # 二次拒绝任务书列出的历史前缀。
        raise ValueError(f"作业名命中禁用前缀：{jobname}")  # 以失败关闭方式阻断历史身份复用。
    return jobname  # 返回通过全部字符、长度和前缀检查的作业名。


def replace_filename(text: str, jobname: str) -> str:  # 定义 APDL /FILNAME 替换函数，输入源文本和唯一作业名。
    """把且仅把首个 ``/FILNAME`` 命令替换为 ``jobname``；缺失或多重定义均失败。"""  # 函数说明强调单一身份约束。

    pattern = re.compile(r"(?im)^\s*/FILNAME\s*,[^\r\n!]*(?:!.*)?$")  # 匹配整行 /FILNAME 及可选行尾说明，不跨行。
    matches = list(pattern.finditer(text))  # 收集全部匹配，防止输入中隐藏第二个作业名前缀。
    if len(matches) != 1:  # 要求每个正式小输入恰好有一个 /FILNAME。
        raise RuntimeError(f"/FILNAME 数量不是 1：count={len(matches)}")  # 报告实际数量并拒绝生成。
    replacement = f"/FILNAME,{jobname} ! 使用本次 U01 manifest 绑定的唯一作业名，禁止复用历史前缀。"  # 构造带中文行尾注释的新命令。
    return pattern.sub(replacement, text, count=1)  # 只替换唯一匹配并返回新文本。


def build_link_input(jobname: str) -> tuple[str, list[Path]]:  # 定义 LINK180 输入构造函数，参数为唯一作业名，返回文本和源路径列表。
    """由官方 VM53 输入派生 tension-only+INISTATE+NLGEOM+PERTURB 算例；输出文本及唯一源文件。"""  # 函数说明给出组合覆盖范围和返回结构。

    source = LINK_SOURCE.read_text(encoding="utf-8")  # 读取已有官方已知答案输入，不修改基准源文件。
    source = replace_filename(source, jobname)  # 将固定 VM53 作业名替换为本次唯一 U01 作业名。
    legacy_tension_marker = "KEYOPT,1,3,1                           ! 启用 LINK180 仅受拉选项，检验项目索单元所依赖的 tension-only 行为。"  # 绑定验证手册沿用但 MAPDL 2026 R1 已报告未文档化的旧张拉开关。
    if source.count(legacy_tension_marker) != 1:  # 要求旧 tension-only 标记唯一，防止派生输入同时保留两种互相冲突的设置。
        raise RuntimeError("VM53 旧 tension-only 标记数量漂移，不能安全迁移到 SECCONTROL。")  # 源结构变化时失败关闭。
    legacy_tension_note = "! MAPDL 2026 R1 已将 KEYOPT(3)=1 报告为未文档化；本派生算例改用官方 LINK 截面的 SECCONTROL TENSKEY。"  # 用 APDL 注释保留验证手册旧设置的迁移原因。
    source = source.replace(legacy_tension_marker, legacy_tension_note, 1)  # 移除会产生原生警告的旧 KEYOPT 命令并保留审计说明。
    section_data_marker = "SECDATA,306796E-8                      ! 将面积设为 306,796×10^-8 in^2，数值来自官方 VM53 一致单位定义。"  # 绑定唯一 LINK 截面面积行，以便紧邻定义张拉行为。
    if source.count(section_data_marker) != 1:  # 要求截面面积标记唯一，避免把 SECCONTROL 绑定到错误截面。
        raise RuntimeError("VM53 LINK 截面面积标记数量漂移，不能安全设置 tension-only。")  # 源结构变化时拒绝猜测截面上下文。
    section_with_tension = section_data_marker + "\nSECCONTROL,,1                         ! 将 LINK 截面的 TENSKEY 设为 1，按 MAPDL 2026 R1 官方接口启用仅受拉行为。"  # 构造面积与 tension-only 控制的连续截面定义。
    source = source.replace(section_data_marker, section_with_tension, 1)  # 仅在 1 号 LINK 截面面积后插入正式 tension-only 控制。
    initial_strain_type_marker = "INISTATE,SET,DTYP,EPEL                 ! 将初始状态数据类型设为弹性应变，与官方 VM53 的预拉方式一致。"  # 绑定官方 VM53 的初始弹性应变类型行，避免模糊替换其他初始状态设置。
    if source.count(initial_strain_type_marker) != 1:  # 要求 EPEL 类型标记恰好出现一次，保证等效应力迁移只作用于目标受拉弦。
        raise RuntimeError("VM53 初始弹性应变类型标记数量漂移，不能安全迁移到等效初始应力。")  # 源结构变化时停止派生，避免生成混合 EPEL/STRE 状态。
    initial_stress_type_line = "INISTATE,SET,DTYP,STRE                 ! 将初始状态改为轴向应力，使 NLGEOM 线性扰动重形成能够继承预拉几何刚度。"  # 定义经独立对照探针验证的 STRE 初始状态类型。
    source = source.replace(initial_strain_type_marker, initial_stress_type_line, 1)  # 把唯一 EPEL 类型行替换为等效 STRE 类型行。
    initial_strain_value_marker = "INISTATE,DEFINE,,,,,543248E-8          ! 对全部单元施加 543,248×10^-8 初始弹性应变，以形成约 500 lb 拉力。"  # 绑定官方 VM53 的初始弹性应变数值行。
    if source.count(initial_strain_value_marker) != 1:  # 要求应变数值标记唯一，避免只替换数据类型而遗留量纲错误的数值。
        raise RuntimeError("VM53 初始弹性应变数值标记数量漂移，不能安全换算等效初始应力。")  # 源结构变化时失败关闭而不猜测单位或材料参数。
    initial_stress_value_line = "INISTATE,DEFINE,,,,,162974.4           ! 施加 162974.4 psi 初始拉应力；该值等于 30E6 psi×543248E-8，对应约 500 lb 拉力。"  # 定义由官方材料模量与应变精确换算的等效应力字面值。
    source = source.replace(initial_strain_value_marker, initial_stress_value_line, 1)  # 将无量纲应变数值替换为 psi 应力数值，保持同一预拉水平。
    derived_comment_replacements = (  # 定义因 EPEL→STRE、完全约束→活动轴向自由度迁移而必须同步更新的七条 APDL 中文注释。
        ("/PREP7                                 ! 进入前处理器，以定义受拉弦的单元、截面、材料、网格与初始应变。", "/PREP7                                 ! 进入前处理器，以定义受拉弦的单元、截面、材料、网格与等效初始拉应力。"),  # 把前处理器说明从已移除的初始应变改为实际 STRE 初始应力。
        ("ANTYPE,STATIC                          ! 首先选择静力分析，用初始应变建立后续线性扰动模态所需的预应力基态。", "ANTYPE,STATIC                          ! 首先选择静力分析，用等效初始拉应力建立后续线性扰动模态所需的非线性平衡基态。"),  # 说明静力母分析的实际 STRE 输入和 NLGEOM 平衡用途。
        ("INISTATE,SET,CSYS,-2                   ! 将初始状态坐标系设为单元坐标系，令初始应变沿弦的轴向施加。", "INISTATE,SET,CSYS,-2                   ! 将初始状态坐标系设为单元坐标系，令等效初始拉应力沿弦轴向施加。"),  # 把坐标系说明的物理量改为当前轴向应力。
        ("SOLVE                                  ! 求解完全约束下的初始应变问题，生成应力、反力和 restart 数据。", "SOLVE                                  ! 在全体 UY/UZ 与两端 UX 约束下求解初始拉应力平衡态，生成应力、反力和 restart 数据。"),  # 准确列出当前基态边界并移除“完全约束”旧表述。
        ("*GET,FREQ1,MODE,1,FREQ                 ! 读取第一阶频率，官方已知答案为 74.708 Hz。", "*GET,FREQ1,MODE,1,FREQ                 ! 读取第一阶离散频率；13 单元参考约 74.89 Hz，74.708 Hz 为连续弦解析参考。"),  # 区分第一阶有限元离散门禁目标和连续弦解析值。
        ("*GET,FREQ2,MODE,2,FREQ                 ! 读取第二阶频率，官方已知答案为 149.42 Hz。", "*GET,FREQ2,MODE,2,FREQ                 ! 读取第二阶离散频率；13 单元参考约 150.875 Hz，149.42 Hz 为连续弦解析参考。"),  # 区分第二阶有限元离散门禁目标和连续弦解析值。
        ("*GET,FREQ3,MODE,3,FREQ                 ! 读取第三阶频率，官方已知答案为 224.12 Hz。", "*GET,FREQ3,MODE,3,FREQ                 ! 读取第三阶离散频率；13 单元参考约 229.06 Hz，224.12 Hz 为连续弦解析参考。"),  # 区分第三阶有限元离散门禁目标和连续弦解析值。
    )  # 结束七条派生注释替换规则，规则数量由本元组固定而不依赖外部输入。
    for old_comment_line, new_comment_line in derived_comment_replacements:  # 逐条同步派生注释，避免命令已迁移而说明仍陈述旧物理模型。
        if source.count(old_comment_line) != 1:  # 要求每条旧注释在基准源中恰好出现一次，源结构漂移时不得静默生成错误说明。
            raise RuntimeError(f"VM53 派生注释标记数量漂移，不能安全更新：{old_comment_line}")  # 报告无法唯一绑定的整行标记并停止派生。
        source = source.replace(old_comment_line, new_comment_line, 1)  # 仅替换当前唯一标记，保持其余官方基准命令和注释逐字节不变。
    constraint_marker = "D,ALL,ALL                              ! 在静力基态阶段约束所有节点全部自由度，使初始应变转化为均匀拉力而不发生位移。"  # 绑定原 VM53 完全约束行，避免对未知源结构做模糊替换。
    if source.count(constraint_marker) != 1:  # 要求原完全约束标记唯一，防止错误修改线性摄动边界。
        raise RuntimeError("VM53 完全约束标记数量漂移，不能安全建立 NLGEOM 活动自由度。")  # 源结构变化时失败关闭而不猜测约束位置。
    active_base_constraints = "\n".join([  # 构造具有活动轴向自由度的非线性静力边界，避免零活动自由度时跳过有效应力刚化矩阵。
        "D,ALL,UY                              ! 在 NLGEOM 静力基态约束全部横向 UY，防止无初始横向刚度的受拉弦形成机构。",  # 解释第一组横向约束的稳定目的。
        "D,ALL,UZ                              ! 在 NLGEOM 静力基态约束全部横向 UZ，使三维 LINK180 只沿轴向寻找平衡。",  # 解释第二组横向约束的稳定目的。
        "D,1,UX                                ! 约束左端节点 1 的轴向 UX，定义受拉弦总长的左边界。",  # 解释左端轴向约束的物理含义。
        "D,14,UX                               ! 约束右端节点 14 的轴向 UX，固定总长并让节点 2 至 13 保持活动轴向自由度。",  # 解释右端轴向约束与活动自由度来源。
    ])  # 结束四条非线性静力边界构造。
    source = source.replace(constraint_marker, active_base_constraints, 1)  # 仅替换原完全约束行，使静力基态存在十二个活动轴向自由度。
    marker = "/SOLU                                  ! 进入求解器以计算受拉弦的预应力静力基态。"  # 绑定首个静力求解器入口的完整注释行。
    if source.count(marker) != 1:  # 要求源输入中的静力入口标记唯一，防止错误插入到扰动阶段。
        raise RuntimeError("VM53 静力 /SOLU 标记数量漂移，不能安全插入 NLGEOM。")  # 源结构变化时停止派生而非猜测。
    addition = marker + "\nNLGEOM,ON                              ! 显式打开几何非线性，使本算例完整覆盖 U01 要求的 NLGEOM 静力链。\nNSUBST,1,1,1                           ! 固定一个静力子步；三个 1 分别表示目标、最小和最大子步数，消除自动初始步长歧义。"  # 构造带逐行中文注释的几何非线性与固定单子步插入段。
    source = source.replace(marker, addition, 1)  # 仅在首个静力入口后插入 NLGEOM 与固定单子步设置，避免影响后续扰动求解器入口。
    axial_release_marker = "DDELE,2,UX,13                          ! 释放节点 2 至 13 的轴向 UX，自由度范围与官方 VM53 完全一致。"  # 绑定原摄动阶段轴向释放行，防止保留对已活动自由度的冗余操作。
    if source.count(axial_release_marker) != 1:  # 要求原轴向释放行唯一，保证边界派生仍对应同一 VM53 身份。
        raise RuntimeError("VM53 轴向释放标记数量漂移，不能安全派生 NLGEOM 摄动边界。")  # 源结构变化时拒绝继续。
    axial_release_note = "! 节点 2 至 13 的 UX 已在 NLGEOM 静力基态保持活动，摄动阶段无需再次删除轴向约束。"  # 用 APDL 注释保留边界变更审计轨迹。
    source = source.replace(axial_release_marker, axial_release_note, 1)  # 删除冗余 DDELE 命令但保留中文原因说明。
    return source, [LINK_SOURCE]  # 返回派生输入和单一权威源文件列表。


def build_template_input(template_name: str, jobname: str) -> tuple[str, list[Path]]:  # 定义静态模板构造函数，输入模板名和作业名。
    """读取正式 U01 模板并替换 ``__JOBNAME__``；输出派生文本和模板源路径。"""  # 函数说明记录 token 必须唯一。

    template_path = TEMPLATE_ROOT / template_name  # 将调用者给出的文件名限制在正式模板目录下。
    source = template_path.read_text(encoding="utf-8")  # 以 UTF-8 读取含逐行中文注释的 APDL 模板。
    if source.count("__JOBNAME__") != 1:  # 要求模板中作业名 token 恰好出现一次。
        raise RuntimeError(f"模板作业名 token 数量不是 1：{template_path}")  # 防止遗漏或多处身份定义。
    source = source.replace("__JOBNAME__", jobname, 1)  # 将唯一 token 替换为经过白名单验证的作业名。
    return source, [template_path]  # 返回派生输入和模板源路径列表。


def build_mpc_input(jobname: str, penalty_label: str) -> tuple[str, list[Path]]:  # 定义 MPC 输入构造函数，输入作业名和 5e10/1e11 档位标签。
    """派生 5E10 或 1E11 MPC184 算例；标签仅允许 ``5e10`` 与 ``1e11``，输出文本和源路径。"""  # 函数说明给出允许值和返回结构。

    if penalty_label not in {"5e10", "1e11"}:  # 将罚因子档位限制为预注册相邻两档。
        raise ValueError(f"未注册 MPC 罚因子档位：{penalty_label}")  # 拒绝任意调参或追结果值。
    source = MPC_SOURCE.read_text(encoding="utf-8")  # 读取已实跑的 5E10 中文逐行注释输入作为唯一来源。
    if penalty_label == "1e11":  # 仅对相邻更高档算例执行确定性数值和说明替换。
        penalty_replacements = (  # 固定三类大小写敏感 token、目标值及其在已审计 5E10 源中的预期出现次数。
            ("5.0E10", "1.0E11", 3),  # 三处带小数点的大写字面值分别位于罚刚度命令及其中文单位说明，均改为 1.0E11 N/mm。
            ("5E10", "1E11", 1),  # 一处紧凑大写标签位于标题或说明身份中，改为相邻 1E11 档位标签。
            ("5e10", "1e11", 2),  # 两处小写标签分别位于原始作业名与结果文件名中，均改为与案例 manifest 一致的 1e11 档位身份。
        )  # 结束三类 token 规则；预期次数锁定当前权威来源结构并防止过度替换。
        for old_token, new_token, expected_count in penalty_replacements:  # 按长数字、大写标签和小写标签顺序执行可审计派生。
            actual_count = source.count(old_token)  # 统计当前 token 的精确大小写匹配数，作为源漂移检测依据。
            if actual_count != expected_count:  # 要求实际次数与预注册次数完全相等，少一处或多一处都拒绝继续。
                raise RuntimeError(f"MPC 罚因子 token 数量漂移：{old_token}={actual_count}，期望 {expected_count}")  # 报告 token、实际数和期望数供源链复核。
            source = source.replace(old_token, new_token)  # 在次数已核验后替换该类全部标记，确保命令、说明和文件身份同步迁移。
            if old_token in source:  # 替换后再次确认旧 token 已完全清除，防止 Python 替换行为或源编码异常留下混合档位。
                raise RuntimeError(f"MPC 罚因子 token 替换后仍有残留：{old_token}")  # 任何残留都失败关闭而不生成含双重档位的输入。
    source = replace_filename(source, jobname)  # 在原始罚因子 token 完成计数和派生后替换唯一 /FILNAME，避免作业名迁移提前移除计数标记。
    return source, [MPC_SOURCE]  # 返回派生输入和单一来源路径。


def ensure_apdl_identity(text: str, jobname: str) -> None:  # 定义 APDL 身份检查函数，输入完整文本和预期作业名，无返回值。
    """验证输入只有一个匹配的 ``/FILNAME``，且不含历史作业名前缀；失败时抛异常。"""  # 函数说明明确身份和禁词约束。

    expected = re.findall(r"(?im)^\s*/FILNAME\s*,\s*([a-zA-Z0-9_]+)", text)  # 提取全部 /FILNAME 参数。
    if expected != [jobname]:  # 要求提取结果与 manifest 作业名一项完全一致。
        raise RuntimeError(f"APDL /FILNAME 与 manifest 不一致：{expected} != {[jobname]}")  # 报告实际与预期身份。
    lowered = text.lower()  # 转为小写后检查历史作业名，不影响原始输入内容。
    for forbidden in FORBIDDEN_JOB_PREFIXES:  # 遍历两类任务书明令禁止的历史前缀。
        if forbidden.lower() in lowered:  # 检查任一历史前缀是否残留在命令或路径中。
            raise RuntimeError(f"APDL 残留禁用作业名前缀：{forbidden}")  # 发现污染时立即停止。


def powershell_quote(value: str) -> str:  # 定义 PowerShell 审计文本引用函数，输入任意参数字符串。
    """返回单引号 PowerShell 字面量；输入中的单引号按两个单引号转义，输出只用于 launch_command.txt。"""  # 函数说明限定不反向执行审计文本。

    return "'" + value.replace("'", "''") + "'"  # 按 PowerShell 单引号规则构造可读参数。


def launch_argv(case: dict[str, Any], input_path: Path, output_path: Path, solver_dir: Path) -> list[str]:  # 定义 MAPDL argv 构造函数。
    """由案例 manifest 构造前台启动参数；输入含并行模式和作业名，输出为不经 shell 的 argv 列表。"""  # 函数说明强调参数不通过 shell 解析。

    argv = [str(MAPDL_EXE), "-b"]  # 以固定可执行路径和批处理模式开始参数列表。
    if case["parallel_mode"] == "DMP":  # 只允许标记为 DMP 的质量闭合案例启用分布式并行。
        argv.extend(["-dis", "-mpi", "intelmpi", "-np", "4"])  # 使用任务书要求的 Intel MPI 四进程配置。
    else:  # 其余小算例使用单进程，减少许可证和内存占用并提供串行对照。
        argv.extend(["-np", "1"])  # 显式请求一个进程，避免继承环境变量中的并行数。
    argv.extend(["-j", str(case["jobname"]), "-dir", str(solver_dir), "-i", str(input_path), "-o", str(output_path)])  # 绑定唯一作业名、隔离目录、唯一输入和主输出。
    return argv  # 返回可直接交给 subprocess.run 且不经过 shell 的参数数组。


def parse_numeric_csv(path: Path) -> list[list[float]]:  # 定义纯数值 CSV 读取函数，输入文件路径，输出二维浮点数组。
    """读取 APDL 生成的无表头数值 CSV；空行忽略，任一空值、非数值或 NaN/Inf 字段都会失败。"""  # 函数说明给出输入格式、有限值约束和严格失败策略。

    rows: list[list[float]] = []  # 创建结果行列表，每行保持原始列序。
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:  # 以 UTF-8 容错方式读取 ASCII 数值 CSV。
        for row_index, raw_row in enumerate(csv.reader(handle), start=1):  # 使用标准 CSV 解析逗号并记录从 1 开始的物理行号，便于精确报告坏值。
            if not raw_row or all(not cell.strip() for cell in raw_row):  # 跳过 MAPDL 可能写出的空行。
                continue  # 空行不计入频率、SET 或向量闭合数量。
            parsed_row: list[float] = []  # 创建当前行的有限浮点值列表，只有整行验证完成后才加入结果。
            for column_index, cell in enumerate(raw_row, start=1):  # 按从 1 开始的列号逐字段验证，覆盖行内空值、文本和非有限特殊值。
                stripped_cell = cell.strip()  # 去除 MAPDL 定宽输出附带的首尾空格，同时保留数值符号和科学计数法。
                if not stripped_cell:  # 拒绝非空行内部的空字段，防止缺失列被当成可忽略空白。
                    raise ValueError(f"数值 CSV 含空字段：{path}，行 {row_index}，列 {column_index}")  # 报告文件、行和列并阻断门禁计算。
                value = float(stripped_cell)  # 将已确认非空的字段转换为 Python 浮点数，非法文本会原生抛出 ValueError。
                if not math.isfinite(value):  # 明确拒绝 NaN、正无穷和负无穷，避免比较与 max/min 的顺序语义产生假通过。
                    raise ValueError(f"数值 CSV 含非有限值：{path}，行 {row_index}，列 {column_index}，值 {stripped_cell!r}")  # 保留坏值文本和精确位置供审计。
                parsed_row.append(value)  # 当前字段通过非空、数值和有限性检查后按原列序加入行结果。
            rows.append(parsed_row)  # 整行全部字段验证成功后才提交，防止部分有效行泄漏到后续判门逻辑。
    return rows  # 返回保持文件行序和列序的二维数值数组。


def relative_error(actual: float, expected: float) -> float:  # 定义相对误差函数，输入实际值和非零期望值。
    """返回 ``abs(actual-expected)/abs(expected)``；expected 必须非零，输出为无量纲非负数。"""  # 函数说明给出公式与约束。

    if expected == 0.0:  # 拒绝用相对误差比较零目标，避免除零或虚假无限值。
        raise ValueError("relative_error 的 expected 不能为零。")  # 提示调用者改用绝对误差门槛。
    return abs(actual - expected) / abs(expected)  # 按绝对差除以期望绝对值返回无量纲误差。


def validate_mapdl_output(output_path: Path, return_code: int) -> dict[str, int | bool]:  # 定义原生日志检查函数。
    """检查返回码、ERROR 汇总和 RUN COMPLETED；成功返回错误/警告计数，失败抛异常。"""  # 函数说明列出输入与硬门禁。

    if return_code != 0:  # 非零进程返回码表示许可证、MPI、输入或求解器级失败。
        raise RuntimeError(f"MAPDL 返回码非零：{return_code}，输出={output_path}")  # 报告返回码和日志路径。
    text = output_path.read_text(encoding="utf-8", errors="replace")  # 读取主输出，替换罕见本地编码字符但保留 ASCII 状态词。
    errors = [int(value) for value in re.findall(r"NUMBER OF ERROR\s+MESSAGES ENCOUNTERED\s*=\s*([0-9]+)", text)]  # 提取全部阶段错误汇总。
    warnings = [int(value) for value in re.findall(r"NUMBER OF WARNING\s+MESSAGES ENCOUNTERED\s*=\s*([0-9]+)", text)]  # 提取全部阶段警告汇总。
    maximum_errors = max(errors, default=0)  # 用所有汇总中的最大错误数作为硬门禁。
    maximum_warnings = max(warnings, default=0)  # 保存最大警告数供 Result Packet 解释而不自动拒绝。
    explicit_error = "*** ERROR ***" in text or "PROBLEM TERMINATED BY INDICATED ERROR" in text  # 捕获没有最终汇总的原生错误块。
    completed = "RUN COMPLETED" in text  # 检查 MAPDL 正常批处理完成横幅。
    if maximum_errors != 0 or explicit_error or not completed:  # 任一错误、错误块或缺完成标志都使案例失败。
        raise RuntimeError(f"MAPDL 日志门禁失败：errors={maximum_errors}, explicit_error={explicit_error}, completed={completed}, output={output_path}")  # 汇总失败证据。
    return {"errors": maximum_errors, "warnings": maximum_warnings, "run_completed": completed}  # 返回可写入 case manifest 的原生状态。


def run_case(case: dict[str, Any], run_dir: Path) -> dict[str, Any]:  # 定义单案例前台执行函数，输入案例字典和套件根目录。
    """执行一个白名单 U01 小输入；输出含返回码、耗时、日志计数和结果文件路径，任何越界或求解错误都会失败。"""  # 函数说明给出输入、输出和安全边界。

    case_id = str(case["case_id"])  # 读取稳定案例标识，用于目录名和结果前缀。
    solver_dir = (run_dir / "solver" / case_id).resolve()  # 解析当前案例独立 solver 子目录。
    if run_dir.resolve() not in solver_dir.parents:  # 检查 solver 目录确实位于本次套件根目录内。
        raise RuntimeError(f"solver 路径越界：{solver_dir}")  # 拒绝任何路径穿越或错误根目录。
    input_snapshot = (run_dir / "input_snapshot" / f"{case_id}.inp").resolve()  # 定位已封板输入快照。
    solver_input = solver_dir / f"{case_id}.inp"  # 在独立 solver 子目录中定义执行副本路径。
    shutil.copy2(input_snapshot, solver_input)  # 创建真实副本而非硬链接，保留时间信息供审计。
    if sha256_file(input_snapshot) != sha256_file(solver_input):  # 比较快照和 solver 副本的逐字节哈希。
        raise RuntimeError(f"solver 输入与快照哈希不一致：{case_id}")  # 发现复制或磁盘漂移时停止执行。
    output_path = solver_dir / f"{case['jobname']}.out"  # 构造与唯一作业名一致的主输出路径。
    if output_path.exists():  # 禁止覆盖任何已有主输出，即使案例 manifest 仍标记为准备态。
        raise FileExistsError(output_path)  # 以实际路径报告不可覆盖冲突。
    argv = launch_argv(case, solver_input, output_path, solver_dir)  # 从 manifest 字段构造不经 shell 的正式 argv。
    started = time.monotonic()  # 记录单调时钟起点，避免系统时间调整影响耗时。
    completed = subprocess.run(argv, cwd=solver_dir, check=False)  # 前台运行 MAPDL 并等待退出，不隐藏早期许可证或 MPI 错误。
    elapsed = time.monotonic() - started  # 计算前台运行耗时秒数。
    native = validate_mapdl_output(output_path, completed.returncode)  # 应用返回码、ERROR 和完成横幅硬门禁。
    result_paths: list[str] = []  # 创建机器结果路径列表，用于逐文件存在、复制和哈希审计。
    for filename in case["result_files"]:  # 遍历当前案例预注册的机器结果文件名，禁止通配搜索后择优。
        result_path = solver_dir / str(filename)  # 构造固定文件名的预期结果路径。
        if not result_path.is_file() or result_path.stat().st_size == 0:  # 要求每个结果文件存在且非空。
            raise RuntimeError(f"缺少或为空的预注册结果：{result_path}")  # 发现缺件时拒绝案例通过。
        post_path = run_dir / "post" / f"{case_id}__{filename}"  # 在套件 post 目录构造带案例前缀的唯一副本名。
        shutil.copy2(result_path, post_path)  # 复制机器结果供集中解析，同时保留 solver 原始文件。
        result_paths.append(str(post_path))  # 记录集中结果路径，供 manifest 和 Result Packet 引用。
    return {"return_code": completed.returncode, "elapsed_seconds": elapsed, "output_path": str(output_path), "result_paths": result_paths, **native}  # 返回完整执行证据对象。


def evaluate_link(run_dir: Path) -> dict[str, Any]:  # 定义 LINK180 组合链判门函数，输入套件目录，输出测试状态和指标。
    """比较 VM53 五项结果与官方 13 单元值；最大相对误差必须小于 0.1%。"""  # 函数说明给出理论来源和阈值。

    rows = parse_numeric_csv(run_dir / "post" / "link_prestress__vm53_result.csv")  # 读取唯一五列 LINK180 结果。
    if len(rows) != 1 or len(rows[0]) != 5:  # 要求结果恰好一行五列，禁止部分结果通过。
        raise RuntimeError(f"LINK180 结果形状错误：{rows}")  # 报告实际二维数据。
    actual = [abs(rows[0][0]), rows[0][1], rows[0][2], rows[0][3], rows[0][4]]  # 按拉力绝对值、应力和三阶频率固定列序取值。
    expected = [499.99, 162974.0, 74.89, 150.875, 229.06]  # 使用 ANSYS 官方 13 单元 LINK180 参考值，而非调参目标。
    errors = [relative_error(value, target) for value, target in zip(actual, expected, strict=True)]  # 逐项计算相对官方值误差。
    passed = max(errors) < 0.001  # 将 0.1% 写为无量纲 0.001 严格小于门槛。
    return {"test_id": "U01_01_LINK180_FULL_CHAIN", "passed": passed, "maximum_relative_error": max(errors), "threshold": 0.001, "actual": actual, "expected": expected}  # 返回机器可读判定。


def evaluate_axis(run_dir: Path) -> dict[str, Any]:  # 定义 BEAM188 方向判门函数，输入套件目录，输出轴与位移指标。
    """验证 ex=-Y、ey=+Z、ez=-X 的正交右手系，并要求双向简支梁误差均小于 0.2%。"""  # 函数说明给出方向和阈值。

    rows = parse_numeric_csv(run_dir / "post" / "beam_axis__u01_beam_axis_result.csv")  # 读取四列双向位移结果。
    if len(rows) != 1 or len(rows[0]) != 4:  # 要求结果恰好一行四列。
        raise RuntimeError(f"BEAM188 方向结果形状错误：{rows}")  # 报告实际结果供修复。
    mapdl_y, theory_y, mapdl_z, theory_z = rows[0]  # 按 local-y 数值/理论、local-z 数值/理论固定列序解包。
    errors = [relative_error(mapdl_y, theory_y), relative_error(mapdl_z, theory_z)]  # 计算双向 Euler-Bernoulli 相对误差。
    ex = (0.0, -1.0, 0.0)  # 定义代表梁 I→J 的单位轴向向量 -global Y。
    ey = (0.0, 0.0, 1.0)  # 定义任务书要求的目标 local-y 向量 +global Z。
    ez = (-1.0, 0.0, 0.0)  # 定义由 cross(ex,ey) 得到的方向节点向量 -global X。
    dot_xy = sum(a * b for a, b in zip(ex, ey, strict=True))  # 计算 ex·ey 正交性指标。
    dot_xz = sum(a * b for a, b in zip(ex, ez, strict=True))  # 计算 ex·ez 正交性指标。
    dot_yz = sum(a * b for a, b in zip(ey, ez, strict=True))  # 计算 ey·ez 正交性指标。
    cross_xy = (ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2], ex[0] * ey[1] - ex[1] * ey[0])  # 显式计算 cross(ex,ey)。
    handedness = sum(a * b for a, b in zip(cross_xy, ez, strict=True))  # 计算右手性 dot(cross(ex,ey),ez)。
    axis_pass = max(abs(dot_xy), abs(dot_xz), abs(dot_yz)) < 1.0e-10 and handedness > 0.9999999999  # 应用任务书精确轴门槛。
    passed = max(errors) < 0.002 and axis_pass  # 同时要求双向梁误差小于 0.2% 且轴算法通过。
    return {"test_id": "U01_02_BEAM188_AXIS", "passed": passed, "maximum_relative_error": max(errors), "threshold": 0.002, "orthogonality_max_abs_dot": max(abs(dot_xy), abs(dot_xz), abs(dot_yz)), "handedness": handedness, "mapdl": [mapdl_y, mapdl_z], "theory": [theory_y, theory_z]}  # 返回完整轴与位移判据。


def evaluate_sections(run_dir: Path) -> dict[str, Any]:  # 定义六截面判门函数，输入套件目录，输出属性、剪切映射与柔度指标。
    """要求六类 ASEC 属性闭合、剪切因子映射闭合，且原生/ASEC 成对短梁两方向柔度差均小于 0.5%。"""  # 函数说明给出任务书三组门槛。

    properties = parse_numeric_csv(run_dir / "post" / "sections__u01_section_properties.csv")  # 读取六行十三列原生/ASEC 属性。
    analytic_deflections = parse_numeric_csv(run_dir / "post" / "sections__u01_section_deflections.csv")  # 读取六行七列 ASEC 与 Timoshenko 解析式核对结果。
    native_deflections = parse_numeric_csv(run_dir / "post" / "sections__u01_section_native_deflections.csv")  # 读取六行十四列原生/ASEC 总位移与扣弯曲剪切位移直接比较结果。
    torsion_audit = parse_numeric_csv(run_dir / "post" / "sections__u01_section_torsion_audit.csv")  # 读取六行九列自由端 ROTX 与根部 MX 无寄生扭转证据。
    section_case_manifest = read_json(run_dir / "solver" / "sections" / "manifest.json")  # 读取截面案例求解 manifest，使被 MAPDL 忽略的非法后处理命令不能仅凭默认参数值通过。
    section_warning_count = int(section_case_manifest.get("warnings", -1))  # 取得 MAPDL 原生警告数；字段缺失时用 -1 失败关闭，不把未知状态冒充零警告。
    if len(properties) != 6 or any(len(row) != 13 for row in properties):  # 要求六类截面属性全部闭合。
        raise RuntimeError(f"截面属性结果形状错误：rows={len(properties)}")  # 报告行数并停止判门。
    if len(analytic_deflections) != 6 or any(len(row) != 7 for row in analytic_deflections):  # 要求六类双向 ASEC/解析式结果全部闭合。
        raise RuntimeError(f"截面解析柔度结果形状错误：rows={len(analytic_deflections)}")  # 报告行数并停止判门。
    if len(native_deflections) != 6 or any(len(row) != 14 for row in native_deflections):  # 要求六类双向原生/ASEC 总位移与剪切位移结果全部闭合。
        raise RuntimeError(f"截面原生对照柔度结果形状错误：rows={len(native_deflections)}")  # 报告行数并停止判门。
    if len(torsion_audit) != 6 or any(len(row) != 9 for row in torsion_audit):  # 要求六类四根梁的 ROTX/MX 审计结果全部闭合。
        raise RuntimeError(f"截面无寄生扭转结果形状错误：rows={len(torsion_audit)}")  # 报告行数并停止判门。
    targets = [  # 按任务书六类固定顺序定义 A、Iyy、Izz、J 目标，不含任何调参值。
        (4997.5, 9830899.739583334, 28164706.458333332, 176798.95833333334),  # H175 目标属性，保持 Iyy/Izz 原始次序。
        (2496.0, 10130432.0, 10130432.0, 15185664.0),  # RHS160×160×4 目标属性。
        (2752.035164544659, 7345181.854169695, 7345181.854169695, 14690363.70833939),  # Φ152×6 目标属性。
        (1231.5043202071988, 1480883.9450491567, 1480883.9450491567, 2961767.8900983133),  # Φ102×4 目标属性。
        (590.6194188748811, 164266.0258745763, 164266.0258745763, 328532.0517491526),  # Φ51×4 目标属性。
        (576.0, 75232.0, 176672.0, 158935.11111111112),  # RHS50×30×4 目标属性。
    ]  # 结束六类目标属性表。
    property_errors: list[float] = []  # 收集 24 项 ASEC 属性相对误差。
    shear_errors: list[float] = []  # 收集 12 项原生到 ASEC 剪切因子映射误差。
    native_torsion_differences: list[float] = []  # 记录原生几何 J 与冻结目标 J 差异，只作 S20 来源诊断而不替代 ASEC 门禁。
    for index, row in enumerate(properties):  # 按固定顺序遍历六类截面属性行。
        if row[0] != float(index + 1):  # 要求 APDL 输出截面序号精确等于 1 至 6，禁止 1.49 等非整数值经四舍五入冒充合法编号。
            raise RuntimeError(f"截面属性序号不连续：row={row}")  # 禁止按行位置静默重排。
        native = row[1:7]  # 提取原生 A、Iyy、Izz、J、SCyy、SCzz 六项。
        asec = row[7:13]  # 提取 ASEC A、Iyy、Izz、J、SCyy、SCzz 六项。
        property_errors.extend(relative_error(asec[item], targets[index][item]) for item in range(4))  # 对 A/Iyy/Izz/J 四项应用 0.1% 门槛。
        native_torsion_differences.append(relative_error(native[3], targets[index][3]))  # 记录原生 J 与冻结目标的差异，明确原生截面不能直接无条件并入生产。
        if index == 0:  # H175 物理截面相对原生 I 截面旋转 90°，因此 y/z 剪切因子必须交叉映射。
            shear_errors.extend([relative_error(asec[4], native[5]), relative_error(asec[5], native[4])])  # 比较 ASEC SCyy↔原生 SCzz 和 ASEC SCzz↔原生 SCyy。
        else:  # 方管、圆管和 RHS50×30 保持原生局部轴定义，不交换剪切方向。
            shear_errors.extend([relative_error(asec[4], native[4]), relative_error(asec[5], native[5])])  # 逐方向比较原生与 ASEC 剪切因子。
    analytic_deflection_errors: list[float] = []  # 创建由 ASEC 数值位移与解析位移独立重算的十二项相对误差列表，作为单元公式辅助门禁。
    reported_analytic_error_differences: list[float] = []  # 创建解析式 APDL 自报误差与 Python 重算误差的差值列表，用于发现模板列错位。
    for index, row in enumerate(analytic_deflections, start=1):  # 按预注册六类截面顺序逐行重算 ASEC 与解析式的双向误差。
        if row[0] != float(index):  # 要求柔度 CSV 第一列精确等于 1 至 6，禁止重复、乱序或非整数编号被按行位置接受。
            raise RuntimeError(f"截面解析柔度序号不连续：row={row}")  # 报告整行数据并停止判门，避免不同截面的数值与目标错配。
        recomputed_y_error = relative_error(row[1], row[2])  # 用 local-y MAPDL 位移与解析位移两列独立重算无量纲相对误差。
        recomputed_z_error = relative_error(row[4], row[5])  # 用 local-z MAPDL 位移与解析位移两列独立重算无量纲相对误差。
        analytic_deflection_errors.extend([recomputed_y_error, recomputed_z_error])  # 按截面和方向顺序保存两项解析式误差，供辅助 0.5% 门禁取最大值。
        reported_analytic_error_differences.extend([abs(row[3] - recomputed_y_error), abs(row[6] - recomputed_z_error)])  # 比较 APDL 自报两列与 Python 重算值，防止错误列仍给出虚假小误差。
    native_total_deflection_errors: list[float] = []  # 创建十二项原生/ASEC 总位移相对误差列表，辅助确认 A/I 微差没有污染比较。
    native_shear_deflection_errors: list[float] = []  # 创建任务书要求的十二项扣除各自弯曲项后剪切位移相对误差列表。
    reported_native_error_differences: list[float] = []  # 创建原生对照四类 APDL 自报误差与 Python 重算误差的差值列表。
    for index, row in enumerate(native_deflections, start=1):  # 按预注册六类截面顺序逐行重算原生/ASEC 双向总位移与剪切位移差。
        if row[0] != float(index):  # 要求原生对照 CSV 第一列精确等于 1 至 6。
            raise RuntimeError(f"截面原生对照序号不连续：row={row}")  # 报告整行数据并停止判门，禁止按行位置静默重排。
        expected_mapping_code = 1.0 if index == 1 else 0.0  # H175 使用原生方向节点物理旋转 90 度代码 1，其余五类使用同向代码 0。
        if row[13] != expected_mapping_code:  # 要求 APDL 第十四列明示的方向映射代码与预注册物理规则完全一致。
            raise RuntimeError(f"截面原生对照映射代码错误：row={row}")  # 拒绝 H175 未交换或其他截面误交换方向。
        recomputed_total_y_error = relative_error(row[1], row[2])  # 用 ASEC 与原生全局 Y 总位移独立重算误差。
        recomputed_shear_y_error = relative_error(row[4], row[5])  # 用两者扣除各自弯曲项后的全局 Y 剪切位移独立重算误差。
        recomputed_total_z_error = relative_error(row[7], row[8])  # 用 ASEC 与原生全局 Z 总位移独立重算误差。
        recomputed_shear_z_error = relative_error(row[10], row[11])  # 用两者扣除各自弯曲项后的全局 Z 剪切位移独立重算误差。
        native_total_deflection_errors.extend([recomputed_total_y_error, recomputed_total_z_error])  # 保存两方向总位移直接对照误差，供辅助门禁取最大值。
        native_shear_deflection_errors.extend([recomputed_shear_y_error, recomputed_shear_z_error])  # 保存两方向剪切位移直接对照误差，供 0.5% 主门禁取最大值。
        reported_native_error_differences.extend([abs(row[3] - recomputed_total_y_error), abs(row[6] - recomputed_shear_y_error), abs(row[9] - recomputed_total_z_error), abs(row[12] - recomputed_shear_z_error)])  # 核对 APDL 自报四列没有列错位或硬编码。
    torsion_rotation_values: list[float] = []  # 收集二十四项 ASEC/原生自由端 ROTX 绝对值，单位 rad。
    torsion_moment_values: list[float] = []  # 收集二十四项 ASEC/原生根部 MX 绝对值，单位 N·mm。
    for index, row in enumerate(torsion_audit, start=1):  # 按预注册六类截面顺序读取四根梁的无寄生扭转证据。
        if row[0] != float(index):  # 要求扭转审计 CSV 第一列精确等于 1 至 6。
            raise RuntimeError(f"截面扭转审计序号不连续：row={row}")  # 报告整行并停止判门，禁止错行掩盖寄生扭转。
        torsion_rotation_values.extend(abs(row[item]) for item in (1, 3, 5, 7))  # 提取四个自由端 ROTX 并取绝对值。
        torsion_moment_values.extend(abs(row[item]) for item in (2, 4, 6, 8))  # 提取四个根部 MX 并取绝对值。
    section_names = ["H175", "RHS160X160X4", "CTUBE152X6", "CTUBE102X4", "CTUBE51X4", "RHS50X30X4"]  # 按生产 ASEC 61 至 66 的固定顺序定义六个截面机器标签，字符串仅用于状态追溯而不参与数值判定。
    pair_results: list[dict[str, Any]] = []  # 创建十二组原生/ASEC 方向对照明细，使状态 JSON 而非只有最大值能完整还原每一对响应。
    for index, (deflection_row, torsion_row) in enumerate(zip(native_deflections, torsion_audit, strict=True), start=1):  # 按截面序号严格配对柔度与扭转审计行，两份 CSV 行数不同时立即失败。
        mapping_label = "NATIVE_ROTATED_90_DEG_ABOUT_BEAM_X" if index == 1 else "NATIVE_AND_ASEC_K_PLUS_Z"  # H175 记录原生截面绕梁轴旋转 90 度，其余五类记录共同 K 指向全局 +Z。
        pair_results.append({"section_index": index, "section_name": section_names[index - 1], "asec_section_id": 60 + index, "native_section_id": index, "direction": "GLOBAL_Y", "axis_mapping": mapping_label, "beam_length_mm": 500.0, "tip_load_n": 1000.0, "asec_total_deflection_mm": deflection_row[1], "native_total_deflection_mm": deflection_row[2], "total_deflection_relative_difference": relative_error(deflection_row[1], deflection_row[2]), "asec_bending_deflection_mm": deflection_row[1] - deflection_row[4], "native_bending_deflection_mm": deflection_row[2] - deflection_row[5], "asec_shear_deflection_mm": deflection_row[4], "native_shear_deflection_mm": deflection_row[5], "shear_deflection_relative_difference": relative_error(deflection_row[4], deflection_row[5]), "asec_tip_rotx_rad": torsion_row[1], "native_tip_rotx_rad": torsion_row[5], "asec_root_mx_n_mm": torsion_row[2], "native_root_mx_n_mm": torsion_row[6]})  # 写入当前截面全局 Y 方向对：总挠度、分别扣弯后的剪切挠度、两类相对差、自由端 ROTX 和根部 MX 均保留原始单位。
        pair_results.append({"section_index": index, "section_name": section_names[index - 1], "asec_section_id": 60 + index, "native_section_id": index, "direction": "GLOBAL_Z", "axis_mapping": mapping_label, "beam_length_mm": 500.0, "tip_load_n": 1000.0, "asec_total_deflection_mm": deflection_row[7], "native_total_deflection_mm": deflection_row[8], "total_deflection_relative_difference": relative_error(deflection_row[7], deflection_row[8]), "asec_bending_deflection_mm": deflection_row[7] - deflection_row[10], "native_bending_deflection_mm": deflection_row[8] - deflection_row[11], "asec_shear_deflection_mm": deflection_row[10], "native_shear_deflection_mm": deflection_row[11], "shear_deflection_relative_difference": relative_error(deflection_row[10], deflection_row[11]), "asec_tip_rotx_rad": torsion_row[3], "native_tip_rotx_rad": torsion_row[7], "asec_root_mx_n_mm": torsion_row[4], "native_root_mx_n_mm": torsion_row[8]})  # 写入当前截面全局 Z 方向对，字段与 Y 方向完全同构，便于十二对逐项机器审核。
    property_pass = max(property_errors) < 0.001  # 要求 24 项 ASEC 属性最大误差严格小于 0.1%。
    shear_mapping_pass = max(shear_errors) < 0.005  # 要求原生到 ASEC 的双向剪切映射误差严格小于 0.5%。
    analytic_flexibility_pass = max(analytic_deflection_errors) < 0.005  # 要求十二项 ASEC/解析式误差严格小于 0.5%，用于验证 BEAM188 数值实现。
    native_total_flexibility_pass = max(native_total_deflection_errors) < 0.005  # 要求十二项原生/ASEC 总位移差严格小于 0.5%，防止 A/I 差异淹没剪切对照。
    native_shear_flexibility_pass = max(native_shear_deflection_errors) < 0.005  # 要求十二项原生/ASEC 剪切位移差严格小于 0.5%，落实任务书主门禁。
    torsion_rotation_threshold_rad = 1.0e-10  # 允许自由端绕 X 的数值噪声上限为 1E-10 rad，证明未激发 J 控制的扭转响应。
    torsion_moment_threshold_n_mm = 1.0e-5  # 允许根部关于 X 的稀疏求解与浮点舍入噪声上限为 1E-5 N·mm；该值仅为 500000 N·mm 主弯曲力矩的 2E-11，仍能严格证明未激发物理扭转。
    root_bending_moment_scale_n_mm = 1000.0 * 500.0  # 用每根梁 1000 N 端力与 500 mm 长度构造 500000 N·mm 主弯曲力矩尺度，用于报告寄生 MX 的无量纲占比。
    torsion_isolation_pass = max(torsion_rotation_values) <= torsion_rotation_threshold_rad and max(torsion_moment_values) <= torsion_moment_threshold_n_mm  # 两项无寄生扭转证据必须同时通过。
    reported_error_consistency_threshold = 1.0e-10  # 允许 APDL 与 Python 双精度格式化带来至多 1E-10 的无量纲误差差值，远小于 0.5% 主门槛。
    analytic_error_consistency_pass = max(reported_analytic_error_differences) <= reported_error_consistency_threshold  # 要求十二项解析式 APDL 自报误差与独立重算值全部一致。
    native_error_consistency_pass = max(reported_native_error_differences) <= reported_error_consistency_threshold  # 要求二十四项原生对照 APDL 自报误差与独立重算值全部一致。
    section_output_warning_pass = section_warning_count == 0  # 要求截面案例原生警告数严格为零，防止 *GET 分量非法等命令被忽略后仍产生形似完整的 CSV。
    passed = property_pass and shear_mapping_pass and analytic_flexibility_pass and native_total_flexibility_pass and native_shear_flexibility_pass and torsion_isolation_pass and analytic_error_consistency_pass and native_error_consistency_pass and section_output_warning_pass  # 属性、映射、解析/原生柔度、无扭转、误差一致性和零警告九组门禁必须同时通过。
    return {"test_id": "U01_03_SECTIONS", "passed": passed, "section_mapdl_warning_count": section_warning_count, "section_mapdl_warning_threshold": 0, "maximum_property_relative_error": max(property_errors), "property_threshold": 0.001, "maximum_shear_mapping_relative_error": max(shear_errors), "shear_threshold": 0.005, "maximum_deflection_relative_error": max(native_shear_deflection_errors), "maximum_native_comparison_relative_error": max(native_shear_deflection_errors), "maximum_native_total_deflection_relative_error": max(native_total_deflection_errors), "maximum_analytic_deflection_relative_error": max(analytic_deflection_errors), "deflection_threshold": 0.005, "deflection_comparison_basis": "NATIVE_BEAM_DIRECT_SHEAR_PAIR_WITH_H175_PHYSICAL_90_DEGREE_ORIENTATION", "pair_count": len(pair_results), "pair_results": pair_results, "maximum_parasitic_rotx_rad": max(torsion_rotation_values), "parasitic_rotx_threshold_rad": torsion_rotation_threshold_rad, "maximum_parasitic_root_mx_n_mm": max(torsion_moment_values), "parasitic_root_mx_threshold_n_mm": torsion_moment_threshold_n_mm, "maximum_parasitic_root_mx_to_bending_moment_ratio": max(torsion_moment_values) / root_bending_moment_scale_n_mm, "root_bending_moment_scale_n_mm": root_bending_moment_scale_n_mm, "maximum_reported_native_error_difference": max(reported_native_error_differences), "maximum_reported_analytic_error_difference": max(reported_analytic_error_differences), "reported_error_consistency_threshold": reported_error_consistency_threshold, "maximum_native_torsion_difference_from_frozen_target": max(native_torsion_differences), "native_sections_role": "SHEAR_FLEXIBILITY_REFERENCE_ONLY_J_DIFFERENCE_ISOLATED_BY_ZERO_ROTX_AND_MX"}  # 返回零警告、属性、映射、十二对原生剪切柔度明细、解析辅助柔度、无扭转隔离及原生 J 风险。


def evaluate_mpc(run_dir: Path) -> dict[str, Any]:  # 定义 MPC184 判门函数，输入套件目录，输出滑移和相邻档柔度指标。
    """要求 5E10 刚臂解析误差和 joint 滑移均不超过 1E-5 mm，且 5E10/1E11 位移变化小于 0.1%。"""  # 函数说明给出三项硬门槛。

    low_rows = parse_numeric_csv(run_dir / "post" / "mpc_5e10__mpc184_penalty_5e10_result.csv")  # 读取候选 5E10 十列结果。
    high_rows = parse_numeric_csv(run_dir / "post" / "mpc_1e11__mpc184_penalty_1e11_result.csv")  # 读取相邻 1E11 十列结果。
    if len(low_rows) != 1 or len(low_rows[0]) != 10 or len(high_rows) != 1 or len(high_rows[0]) != 10:  # 要求两档各一行十列。
        raise RuntimeError("MPC184 两档结果形状不是 1×10。")  # 拒绝部分或错列结果。
    low = low_rows[0]  # 取 5E10 固定列序结果。
    high = high_rows[0]  # 取 1E11 固定列序结果。
    rigid_errors = [abs(low[0] - low[6]), abs(low[1] - low[7]), abs(low[2])]  # 比较刚臂节点与有限转动解析 UX/UY 及理论零 UZ。
    slip_components = [abs(low[8]), abs(low[9]), abs(low[5] - low[2])]  # 计算 general joint 三向相对平移绝对值。
    low_vector = (low[3], low[4], low[5])  # 提取 5E10 索侧节点三向位移作为接口柔度代理。
    high_vector = (high[3], high[4], high[5])  # 提取 1E11 索侧节点三向位移作为相邻档代理。
    change_norm = math.sqrt(sum((a - b) ** 2 for a, b in zip(low_vector, high_vector, strict=True)))  # 计算相邻档位移向量差范数。
    reference_norm = math.sqrt(sum(value**2 for value in high_vector))  # 计算较高罚因子位移范数作为非零归一化基准。
    flexibility_change = change_norm / reference_norm  # 计算相邻档接口运动变化比例。
    passed = max(rigid_errors) <= 1.0e-5 and max(slip_components) <= 1.0e-5 and flexibility_change < 0.001  # 同时应用解析、滑移和 0.1% 收敛门槛。
    return {"test_id": "U01_04_MPC184", "passed": passed, "maximum_rigid_arm_absolute_error_mm": max(rigid_errors), "maximum_joint_slip_mm": max(slip_components), "slip_threshold_mm": 1.0e-5, "adjacent_penalty_flexibility_change": flexibility_change, "flexibility_threshold": 0.001, "penalty_values_n_per_mm": [5.0e10, 1.0e11]}  # 返回预注册两档及三项门禁结果。


def evaluate_hinge(run_dir: Path) -> dict[str, Any]:  # 定义 revolute 六自由度判门函数，输入套件目录，输出受限滑移和自由轴刚度比。
    """要求五个受限自由度近零，官方 JRU4 与节点转角一致，自由 ROTX 满足解析值且无寄生力矩。"""  # 函数说明给出节点运动与 MPC184 本体输出的双重门禁。

    rows = parse_numeric_csv(run_dir / "post" / "revolute_6dof__u01_revolute_6dof_result.csv")  # 读取六行五列关节运动、刚度和自由轴约束力矩结果。
    if len(rows) != 6 or any(len(row) != 5 for row in rows):  # 要求六个单位力/力矩工况和五个预注册字段全部存在。
        raise RuntimeError(f"revolute 六自由度结果形状错误：rows={len(rows)}")  # 报告缺失或错列情况。
    for index, row in enumerate(rows, start=1):  # 检查第一列工况序号严格连续。
        if row[0] != float(index):  # 要求输出工况号精确等于预注册 1 至 6，禁止非整数值经四舍五入冒充合法编号。
            raise RuntimeError(f"revolute 工况序号不连续：{row}")  # 禁止重排后择优拼接。
    joint_rows = parse_numeric_csv(run_dir / "post" / "revolute_6dof__u01_revolute_joint_result.csv")  # 读取六行九列 MPC184 约束分量、JRP4 和 JRU4 本体输出。
    if len(joint_rows) != 6 or any(len(row) != 9 for row in joint_rows):  # 要求六个工况与九个预注册本体字段全部存在。
        raise RuntimeError(f"revolute 本体结果形状错误：rows={len(joint_rows)}")  # 报告本体 CSV 的实际行数，拒绝缺列或隐式续写。
    for index, row in enumerate(joint_rows, start=1):  # 检查本体 CSV 第一列工况序号同样严格连续。
        if row[0] != float(index):  # 要求本体工况号精确等于 1 至 6，防止重复、乱序或小数编号错配关节反力。
            raise RuntimeError(f"revolute 本体工况序号不连续：{row}")  # 禁止把不同工况的关节反力或转动错配。
    locked_indices = [0, 1, 2, 4, 5]  # 指定 UX、UY、UZ、ROTY、ROTZ 五个受限相对自由度行索引。
    maximum_locked_relative_motion = max(abs(rows[index][1]) for index in locked_indices)  # 计算五个受限方向的最大相对运动。
    nodal_free_relative_rotation = abs(rows[3][1])  # 读取节点 J 减节点 I 的自由 ROTX 相对转角，单位 rad。
    official_free_relative_rotation = abs(joint_rows[3][8])  # 读取 MPC184 官方 JRU4 自由轴相对转动，第四工况和第九列分别对应单位 MX 与 JRU4。
    expected_free_rotation = 1.0e-3  # 预注册 1 N·mm 除以 1000 N·mm/rad 的小转角解析值，单位 rad。
    free_rotation_absolute_error = abs(official_free_relative_rotation - expected_free_rotation)  # 以官方 JRU4 计算自由轴转角与解析值的绝对误差，单位 rad。
    nodal_official_rotation_difference = abs(nodal_free_relative_rotation - official_free_relative_rotation)  # 计算节点转角差与 JRU4 的独立提取一致性误差，单位 rad。
    free_axis_stiffness = abs(rows[3][3])  # 读取自由轴单位力矩等效刚度，理论为 1000 N·mm/rad。
    expected_free_axis_stiffness = 1000.0  # 预注册 COMBIN14 正则化刚度，单位 N·mm/rad。
    free_stiffness_relative_error = relative_error(free_axis_stiffness, expected_free_axis_stiffness)  # 计算自由轴等效刚度相对解析误差。
    free_axis_parasitic_moment = abs(joint_rows[3][4])  # 从筛选后的 MPC184 本体 CSV 读取 NMISC,22 即自由 X 轴约束力矩绝对值，单位 N·mm。
    free_joint_relative_position = joint_rows[3][7]  # 记录线性分析下官方 JRP4 自由轴相对位置，单位 rad；该量不与 JRU4 强制相等。
    target_constraint_responses = [abs(joint_rows[0][1]), abs(joint_rows[1][2]), abs(joint_rows[2][3]), abs(joint_rows[4][5]), abs(joint_rows[5][6])]  # 按 UX、UY、UZ、ROTY、ROTZ 工况提取对应 JFX、JFY、JFZ、JMY、JMZ 反力绝对值。
    maximum_unit_constraint_response_error = max(abs(value - 1.0) for value in target_constraint_responses)  # 记录五个单位力或单位力矩与 1.0 目标的最大绝对差；本轮作为诊断指标而非新增硬门禁。
    constrained_rotational_stiffness = min(abs(rows[4][3]), abs(rows[5][3]))  # 取 ROTY/ROTZ 两个受限方向较小刚度作为保守值。
    stiffness_ratio = constrained_rotational_stiffness / free_axis_stiffness  # 计算受限转动刚度与自由轴正则化刚度之比。
    passed = maximum_locked_relative_motion <= 1.0e-8 and free_rotation_absolute_error <= 1.0e-8 and nodal_official_rotation_difference <= 1.0e-8 and free_stiffness_relative_error <= 1.0e-5 and free_axis_parasitic_moment <= 1.0e-8 and stiffness_ratio >= 1.0e6  # 同时应用受限运动、JRU4 解析、双提取一致性、刚度解析、零寄生力矩和六数量级刚度比门禁。
    return {"test_id": "U01_05_REVOLUTE_6DOF", "passed": passed, "maximum_locked_relative_motion": maximum_locked_relative_motion, "locked_motion_threshold": 1.0e-8, "nodal_free_relative_rotation_rad": nodal_free_relative_rotation, "official_jru4_free_relative_rotation_rad": official_free_relative_rotation, "expected_free_rotation_rad": expected_free_rotation, "free_rotation_absolute_error": free_rotation_absolute_error, "free_rotation_error_threshold_rad": 1.0e-8, "nodal_official_rotation_difference_rad": nodal_official_rotation_difference, "rotation_consistency_threshold_rad": 1.0e-8, "free_axis_stiffness_n_mm_per_rad": free_axis_stiffness, "expected_free_axis_stiffness_n_mm_per_rad": expected_free_axis_stiffness, "free_stiffness_relative_error": free_stiffness_relative_error, "free_stiffness_relative_error_threshold": 1.0e-5, "free_axis_parasitic_moment_n_mm": free_axis_parasitic_moment, "parasitic_moment_threshold_n_mm": 1.0e-8, "official_jrp4_free_relative_position_rad": free_joint_relative_position, "target_constraint_responses": target_constraint_responses, "maximum_unit_constraint_response_error": maximum_unit_constraint_response_error, "constrained_to_free_rotational_stiffness_ratio": stiffness_ratio, "minimum_stiffness_ratio": 1.0e6}  # 返回节点运动、官方关节本体输出、高低刚度和寄生力矩的完整证据。


def read_mass_case(run_dir: Path, case_id: str) -> tuple[list[float], list[list[float]], list[int], list[int]]:  # 定义 MASS21 单案例读取函数，返回频率、向量、观测闭合和 APDL 报告闭合。
    """读取串行或 DMP 的频率、向量及闭合计数；严格验证 1..6 模态号，并分别返回文件观测计数与 APDL 累计计数。"""  # 函数说明列出四个返回值和编号约束。

    frequencies_rows = parse_numeric_csv(run_dir / "post" / f"{case_id}__u01_mass_modal_frequencies.csv")  # 读取六行两列频率。
    vector_rows = parse_numeric_csv(run_dir / "post" / f"{case_id}__u01_mass_modal_vectors.csv")  # 读取六行七列节点向量。
    closure_rows = parse_numeric_csv(run_dir / "post" / f"{case_id}__u01_mass_modal_closure.csv")  # 读取一行四列闭合计数。
    if len(frequencies_rows) != 6 or any(len(row) != 2 for row in frequencies_rows):  # 要求六阶频率完整且列数正确。
        raise RuntimeError(f"{case_id} 频率结果未闭合。")  # 报告具体案例标识。
    if len(vector_rows) != 6 or any(len(row) != 7 for row in vector_rows):  # 要求六阶六自由度向量完整。
        raise RuntimeError(f"{case_id} 节点向量结果未闭合。")  # 报告具体案例标识。
    if len(closure_rows) != 1 or len(closure_rows[0]) != 4:  # 要求闭合清单恰好一行四列。
        raise RuntimeError(f"{case_id} 闭合计数形状错误。")  # 禁止从日志猜测缺失计数。
    expected_mode_ids = [float(index) for index in range(1, 7)]  # 构造精确浮点模态号 1 至 6，数值来源为本已知答案请求的六阶闭合定义。
    frequency_mode_ids = [row[0] for row in frequencies_rows]  # 提取频率 CSV 首列原始模态号，保留顺序用于严格比较。
    vector_mode_ids = [row[0] for row in vector_rows]  # 提取向量 CSV 首列原始模态号，独立检查 SET 导出顺序。
    if frequency_mode_ids != expected_mode_ids:  # 要求频率模态号逐项精确等于 1 至 6，禁止重复、乱序或 1.49 等非整数值。
        raise RuntimeError(f"{case_id} 频率模态号不是严格 1..6：{frequency_mode_ids}")  # 报告实际首列并停止 MASS21 判门。
    if vector_mode_ids != expected_mode_ids:  # 要求向量模态号同样逐项精确等于 1 至 6，防止频率与向量错阶匹配。
        raise RuntimeError(f"{case_id} 向量模态号不是严格 1..6：{vector_mode_ids}")  # 报告实际首列并拒绝按文件行位置静默配对。
    frequencies = [row[1] for row in frequencies_rows]  # 按连续模态序号提取六项频率。
    vectors = [row[1:7] for row in vector_rows]  # 去除模态序号列并保留六自由度分量。
    reported_closure_raw = closure_rows[0]  # 保留 APDL 写出的请求、频率、成功 SET 和向量四项原始浮点计数。
    if any(value != float(int(value)) for value in reported_closure_raw):  # 要求四项计数本身都是精确整数，禁止 5.6 经 round 后冒充 6。
        raise RuntimeError(f"{case_id} APDL 闭合计数含非整数：{reported_closure_raw}")  # 报告四项原始计数并停止判门。
    reported_closure = [int(value) for value in reported_closure_raw]  # 仅在逐项确认无小数部分后转换为整数，保持机器语义明确。
    observed_closure = [6, len(frequencies_rows), len(vector_rows), len(vector_rows)]  # 由预注册请求数、实际频率行数及通过无原生错误 SET/GET 后写出的向量行数独立构造闭合计数。
    if reported_closure != observed_closure:  # 要求 APDL 运行期累计计数与 Python 从实际文件观测的计数逐项相等。
        raise RuntimeError(f"{case_id} APDL/文件闭合计数不一致：reported={reported_closure}, observed={observed_closure}")  # 报告两套计数阻止硬编码或漏写被接受。
    return frequencies, vectors, observed_closure, reported_closure  # 返回频率、向量、独立观测闭合和 APDL 累计闭合四元组。


def evaluate_mass_and_closure(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:  # 定义 MASS21、频带闭合和 DMP 三项联合判门函数。
    """比较 1..6 Hz 解析频率、6/6/6/6 闭合及串行/DMP 频率与绝对归一化向量；返回三个 U01 测试对象。"""  # 函数说明解释三项输出。

    serial_freq, serial_vectors, serial_observed_closure, serial_reported_closure = read_mass_case(run_dir, "mass_serial")  # 读取单进程频率、向量及两套闭合计数。
    dmp_freq, dmp_vectors, dmp_observed_closure, dmp_reported_closure = read_mass_case(run_dir, "mass_dmp4")  # 读取 Intel MPI 四进程频率、向量及两套闭合计数。
    expected = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]  # 定义由 k=m(2πf)^2 和 kθ=I(2πf)^2 构造的六个解析频率。
    frequency_errors = [relative_error(value, target) for value, target in zip(serial_freq, expected, strict=True)]  # 计算串行 MASS21 六项解析误差。
    mass_pass = max(frequency_errors) < 1.0e-6  # 要求六项频率最大相对误差小于 1 ppm，远严于一般工程门槛。
    expected_closure = [6, 6, 6, 6]  # 定义请求阶数、频率行数、无错误 SET 后向量行数和向量行数四项预期闭合值。
    closure_pass = serial_observed_closure == expected_closure and serial_reported_closure == expected_closure and dmp_observed_closure == expected_closure and dmp_reported_closure == expected_closure  # 要求串行/DMP 的文件观测与 APDL 累计四套计数全部闭合。
    serial_normalized: list[list[float]] = []  # 创建串行绝对归一化向量表，消除特征向量任意符号和尺度。
    dmp_normalized: list[list[float]] = []  # 创建 DMP 绝对归一化向量表，使用相同规则比较。
    for serial_vector, dmp_vector in zip(serial_vectors, dmp_vectors, strict=True):  # 按模态序号逐对处理六自由度向量。
        serial_scale = max(abs(value) for value in serial_vector)  # 取串行向量最大绝对分量作为非零归一化尺度。
        dmp_scale = max(abs(value) for value in dmp_vector)  # 取 DMP 向量最大绝对分量作为非零归一化尺度。
        if serial_scale == 0.0 or dmp_scale == 0.0:  # 任一全零向量都表示导出失败。
            raise RuntimeError("MASS21 模态向量出现全零行。")  # 拒绝用频率存在掩盖向量缺失。
        serial_normalized.append([abs(value) / serial_scale for value in serial_vector])  # 归一化串行绝对分量。
        dmp_normalized.append([abs(value) / dmp_scale for value in dmp_vector])  # 归一化 DMP 绝对分量。
    maximum_frequency_difference = max(abs(a - b) for a, b in zip(serial_freq, dmp_freq, strict=True))  # 计算串行/DMP 最大绝对频差 Hz。
    maximum_vector_difference = max(abs(a - b) for row_a, row_b in zip(serial_normalized, dmp_normalized, strict=True) for a, b in zip(row_a, row_b, strict=True))  # 计算归一化绝对向量最大分量差。
    modal_purity = min(max(row) - sum(sorted(row)[:-1]) for row in serial_normalized)  # 计算每阶主分量减其余分量和的最小值，理想解为 1。
    dmp_pass = maximum_frequency_difference <= 1.0e-8 and maximum_vector_difference <= 1.0e-8 and dmp_observed_closure == expected_closure and dmp_reported_closure == expected_closure  # 应用频率、向量和双重闭合四项 DMP 门禁。
    mass_test = {"test_id": "U01_06_MASS21_INERTIA", "passed": mass_pass, "maximum_frequency_relative_error": max(frequency_errors), "threshold": 1.0e-6, "actual_hz": serial_freq, "expected_hz": expected, "minimum_modal_purity": modal_purity}  # 构造 MASS21 解析频率测试对象。
    closure_test = {"test_id": "U01_07_BLOCK_LANCZOS_CLOSURE", "passed": closure_pass, "serial_observed_counts": serial_observed_closure, "serial_apdl_reported_counts": serial_reported_closure, "dmp_observed_counts": dmp_observed_closure, "dmp_apdl_reported_counts": dmp_reported_closure, "count_order": ["requested_modes", "frequency_rows", "error_free_set_vector_rows", "vector_rows"], "frequency_band_hz": [0.0, 7.0], "known_physical_dof_count": 6}  # 构造含文件观测与 APDL 累计双证据的全频带闭合测试对象。
    dmp_test = {"test_id": "U01_08_DMP4_EXPORT", "passed": dmp_pass, "maximum_frequency_difference_hz": maximum_frequency_difference, "frequency_threshold_hz": 1.0e-8, "maximum_normalized_vector_difference": maximum_vector_difference, "vector_threshold": 1.0e-8, "processes": 4, "mpi": "intelmpi"}  # 构造 DMP4 合并与导出测试对象。
    return mass_test, closure_test, dmp_test  # 返回三项独立 U01 判定。


def write_gate_csv(path: Path, tests: list[dict[str, Any]]) -> None:  # 定义门禁 CSV 写入函数，输入目标路径和八项测试对象。
    """写出 ``test_id,passed,summary_json`` 三列；第三列无损保存单项指标并与 U01_status.json 对照。"""  # 函数说明准确解释三列 CSV 与状态 JSON 的分工。

    with path.open("x", encoding="utf-8", newline="") as handle:  # 排他创建 UTF-8 CSV，禁止覆盖已有审计结论。
        writer = csv.writer(handle, lineterminator="\n")  # 使用标准逗号分隔和 LF 行结尾。
        writer.writerow(["test_id", "passed", "summary_json"])  # 写出三列表头，第三列保存单项完整 JSON 摘要。
        for test in tests:  # 按 U01 01 至 08 固定顺序遍历测试对象。
            writer.writerow([test["test_id"], str(bool(test["passed"])).lower(), json.dumps(test, ensure_ascii=False, sort_keys=True)])  # 写出稳定标识、布尔值和排序后的无损摘要。


def collect_artifact_hashes(run_dir: Path) -> list[tuple[str, str]]:  # 定义产物哈希收集函数，输入套件目录，输出相对路径/摘要列表。
    """递归哈希本次 run 内除哈希清单自身外的全部文件；输出按相对路径排序。"""  # 函数说明给出排除规则和稳定顺序。

    excluded = {"artifact_hashes.sha256"}  # 排除自引用哈希清单，避免不可能的固定点摘要。
    records: list[tuple[str, str]] = []  # 创建相对路径与 SHA-256 二元组列表。
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):  # 递归枚举并按路径排序全部普通文件。
        relative = path.relative_to(run_dir).as_posix()  # 转为稳定的正斜杠相对路径，避免绝对盘符依赖。
        if relative in excluded:  # 跳过自引用清单本身。
            continue  # 不把当前哈希文件加入其自身输入集合。
        records.append((relative, sha256_file(path)))  # 计算并保存当前文件摘要。
    return records  # 返回稳定排序的完整产物哈希列表。


def prepare_cases(run_dir: Path, stamp: str, suffix: str) -> list[dict[str, Any]]:  # 定义八个执行案例准备函数。
    """生成八个独立 APDL 输入快照和案例 manifest；输入为新 run、时间戳和随机后缀，输出案例列表。"""  # 函数说明给出输入和输出结构。

    specifications = [  # 按执行顺序定义案例标识、构造器、并行模式和预注册结果文件。
        {"case_id": "link_prestress", "builder": lambda name: build_link_input(name), "parallel_mode": "SERIAL", "result_files": ["vm53_result.csv"], "purpose": "LINK180 tension-only + INISTATE + NLGEOM + linear perturbation"},  # 完整索链已知答案案例。
        {"case_id": "beam_axis", "builder": lambda name: build_template_input("u01_beam_axis.inp", name), "parallel_mode": "SERIAL", "result_files": ["u01_beam_axis_result.csv"], "purpose": "BEAM188 actual -Y axis and bidirectional bending"},  # 实际方向节点双向弯曲案例。
        {"case_id": "sections", "builder": lambda name: build_template_input("u01_sections.inp", name), "parallel_mode": "SERIAL", "result_files": ["u01_section_properties.csv", "u01_section_deflections.csv", "u01_section_native_deflections.csv", "u01_section_torsion_audit.csv"], "purpose": "six ASEC/native properties plus paired native/ASEC bidirectional short-beam shear with zero-torsion audit"},  # 六截面属性、解析辅助柔度、原生/ASEC 成对短梁和无寄生扭转案例。
        {"case_id": "mpc_5e10", "builder": lambda name: build_mpc_input(name, "5e10"), "parallel_mode": "SERIAL", "result_files": ["mpc184_penalty_5e10_result.csv"], "purpose": "MPC184 rigid arm and translation joint at 5E10 N/mm"},  # 候选罚因子案例。
        {"case_id": "mpc_1e11", "builder": lambda name: build_mpc_input(name, "1e11"), "parallel_mode": "SERIAL", "result_files": ["mpc184_penalty_1e11_result.csv"], "purpose": "adjacent MPC184 penalty convergence at 1E11 N/mm"},  # 相邻更高罚因子案例。
        {"case_id": "revolute_6dof", "builder": lambda name: build_template_input("u01_revolute_6dof.inp", name), "parallel_mode": "SERIAL", "result_files": ["u01_revolute_6dof_result.csv", "u01_revolute_joint_result.csv"], "purpose": "MPC184 revolute six unit load/moment cases"},  # 六自由度铰链案例同时预注册节点运动与关节本体两份结果。
        {"case_id": "mass_serial", "builder": lambda name: build_template_input("u01_mass_modal.inp", name), "parallel_mode": "SERIAL", "result_files": ["u01_mass_modal_frequencies.csv", "u01_mass_modal_vectors.csv", "u01_mass_modal_closure.csv"], "purpose": "MASS21 six-DOF analytic modal serial reference"},  # 串行质量和闭合案例。
        {"case_id": "mass_dmp4", "builder": lambda name: build_template_input("u01_mass_modal.inp", name), "parallel_mode": "DMP", "result_files": ["u01_mass_modal_frequencies.csv", "u01_mass_modal_vectors.csv", "u01_mass_modal_closure.csv"], "purpose": "MASS21 DMP4 merge and vector export"},  # 四进程 DMP 对照案例。
    ]  # 结束八个独立执行案例定义。
    cases: list[dict[str, Any]] = []  # 创建已准备案例列表，后续写入根 manifest 并按序执行。
    for index, specification in enumerate(specifications, start=1):  # 按预注册顺序生成唯一作业名和输入。
        jobname = make_jobname(index, stamp, suffix)  # 为当前案例生成唯一、短且白名单化的作业名。
        text, source_paths = specification["builder"](jobname)  # 调用固定构造器得到 APDL 文本及源路径。
        ensure_apdl_identity(text, jobname)  # 复核 /FILNAME、历史禁词和 manifest 作业名一致。
        case_id = str(specification["case_id"])  # 读取稳定案例标识，作为输入文件和 solver 子目录名。
        snapshot_path = run_dir / "input_snapshot" / f"{case_id}.inp"  # 构造当前案例输入快照路径。
        write_new_text(snapshot_path, text)  # 排他创建完整输入快照，禁止复跑覆盖。
        solver_dir = run_dir / "solver" / case_id  # 构造当前案例独立 solver 目录。
        solver_dir.mkdir(exist_ok=False)  # 原子创建案例目录，已有目录立即失败。
        case = {  # 创建任务书第 18 节在 U01 子作业层面的 manifest 对象。
            "case_id": case_id,  # 写入稳定案例标识。
            "jobname": jobname,  # 写入与 /FILNAME 和命令行 -j 一致的唯一作业名。
            "purpose": specification["purpose"],  # 写入单一测试目的，避免多模型含义混淆。
            "parallel_mode": specification["parallel_mode"],  # 写入 SERIAL 或 DMP 并行模式。
            "processes": 4 if specification["parallel_mode"] == "DMP" else 1,  # 写入实际进程数。
            "mpi": "intelmpi" if specification["parallel_mode"] == "DMP" else "none",  # 写入 DMP 的 Intel MPI 实现或串行无 MPI。
            "input_snapshot": str(snapshot_path),  # 写入输入快照绝对路径供本机复核。
            "input_sha256": sha256_file(snapshot_path),  # 写入派生输入逐字节摘要。
            "source_files": [{"path": str(path), "sha256": sha256_file(path)} for path in source_paths],  # 写入全部模板或已知答案源及其摘要。
            "result_files": list(specification["result_files"]),  # 写入禁止通配替换的预注册结果文件名。
            "status": "PREPARED_NOT_STARTED",  # 初始状态明确表示尚未执行 MAPDL。
        }  # 结束案例 manifest 对象。
        write_json_atomic(solver_dir / "manifest.json", case)  # 在案例 solver 目录原子写入独立 manifest。
        cases.append(case)  # 将当前案例加入根套件顺序列表。
    return cases  # 返回八个已封板案例对象。


def build_launch_text(cases: list[dict[str, Any]], run_dir: Path) -> str:  # 定义 launch_command.txt 构造函数。
    """生成八条只供审计的 PowerShell 命令；执行器始终从结构化字段重建 argv，不反向执行本文件。"""  # 函数说明限制审计文本用途。

    lines = ["# U01 独立小作业正式启动命令", "", "以下命令仅用于审计；本脚本从 manifest 字段重建 argv，不解析或执行本文件。", ""]  # 写入用途和不可反向执行说明。
    for case in cases:  # 按预注册顺序遍历八个案例。
        case_id = str(case["case_id"])  # 读取案例标识以定位 solver 副本和主输出。
        solver_dir = run_dir / "solver" / case_id  # 构造案例独立 solver 目录。
        input_path = solver_dir / f"{case_id}.inp"  # 构造运行时真实输入路径。
        output_path = solver_dir / f"{case['jobname']}.out"  # 构造唯一主输出路径。
        argv = launch_argv(case, input_path, output_path, solver_dir)  # 生成结构化正式参数数组。
        command = "& " + " ".join(powershell_quote(item) for item in argv)  # 把每个参数独立引用为可读 PowerShell 命令。
        lines.extend([f"## {case_id}", "", command, ""])  # 写入案例小标题、命令和空行分隔。
    return "\n".join(lines).rstrip() + "\n"  # 返回以单一末换行结束的审计文本。


def prepare_run(execute: bool) -> tuple[Path, dict[str, Any]]:  # 定义套件准备函数，输入是否执行，返回新 run 目录和根 manifest。
    """验证 U00、创建不可覆盖的 U01 目录并封板八个输入；``execute`` 只记录用户意图，不在本函数启动 MAPDL。"""  # 函数说明区分准备和执行职责。

    environment = validate_u00()  # 首先验证固定 U00 PASS_A 和 MAPDL 可执行哈希。
    created = utc_now()  # 读取唯一 UTC 创建时间，供目录名、manifest 和作业名共享。
    directory_stamp = created.strftime("%Y%m%dT%H%M%S%fZ")  # 生成含微秒的 UTC 目录时间戳，防止并发同名。
    job_stamp = created.strftime("%m%dt%H%M%S").lower()  # 生成短 MMDDtHHMMSS 作业名时间段。
    suffix = secrets.token_hex(1)  # 生成两位十六进制随机后缀，补强同秒唯一性。
    run_dir = ULTRA_RUNS_ROOT / f"U01_UNIT_TESTS_{directory_stamp}"  # 构造任务书 U01 run_id 与 UTC 时间戳目录。
    run_dir.mkdir(parents=False, exist_ok=False)  # 原子创建根目录，任何同名现存目录都立即失败。
    for name in ("input_snapshot", "solver", "post", "qa", "orchestrator_snapshot"):  # 创建四个任务书证据目录和一个编排脚本身份快照目录。
        (run_dir / name).mkdir(exist_ok=False)  # 逐个原子创建，禁止合并进已有目录。
    orchestrator_source_sha256 = sha256_file(SCRIPT_PATH)  # 在准备任何案例前计算当前编排脚本摘要，绑定实际执行逻辑版本。
    orchestrator_snapshot = run_dir / "orchestrator_snapshot" / SCRIPT_PATH.name  # 构造本 run 内不可与模板混淆的编排脚本快照路径。
    shutil.copy2(SCRIPT_PATH, orchestrator_snapshot)  # 真实复制当前脚本并保留时间信息，避免后续源码变化改写历史 run 身份。
    orchestrator_snapshot_sha256 = sha256_file(orchestrator_snapshot)  # 计算复制后快照摘要，用于检测复制期间的内容漂移。
    if orchestrator_snapshot_sha256 != orchestrator_source_sha256:  # 要求执行源与 run 内快照逐字节一致。
        raise RuntimeError("U01 编排脚本快照与执行源哈希不一致。")  # 发现并发编辑或复制损坏时在任何 MAPDL 启动前失败关闭。
    cases = prepare_cases(run_dir, job_stamp, suffix)  # 生成八个输入快照、solver 子目录和案例 manifest。
    memory = memory_snapshot()  # 在准备时读取当前内存，以区分小算例允许与全桥禁止状态。
    manifest = {  # 创建 U01 套件根 manifest，字段同时满足任务书和多小作业扩展需求。
        "schema_version": 1,  # 使用整数 1 标识当前 manifest 结构版本。
        "run_id": "U01_UNIT_TESTS",  # 写入任务书固定阶段标识。
        "suite_id": run_dir.name,  # 写入包含 UTC 微秒的唯一套件目录身份。
        "jobname": f"u01_suite_{job_stamp}_{suffix}",  # 写入套件级审计身份；实际 MAPDL 作业名位于 cases。
        "model_line": "UNIT_TEST",  # 标明本套件不属于 LEGACY、DIAGNOSTIC 或 PRODUCTION 全桥模型线。
        "parent_run": U00_RUN.name,  # 显式绑定唯一 U00 父 run。
        "single_change": "eight isolated solver and element-chain known-answer tests",  # 说明本阶段只建立小算例证据。
        "created_utc": created.isoformat(),  # 写入带时区 ISO 8601 创建时间。
        "mapdl_version": environment.get("ansys_release", "2026 R1 / v261"),  # 写入 U00 核验版本字符串。
        "executable": str(MAPDL_EXE),  # 写入实际 MAPDL 可执行路径。
        "executable_sha256": sha256_file(MAPDL_EXE),  # 写入执行前重新计算的可执行摘要。
        "orchestrator_source": str(SCRIPT_PATH),  # 写入本次实际加载的 U01 编排脚本绝对路径。
        "orchestrator_sha256": orchestrator_source_sha256,  # 写入脚本 SHA-256，使 Python 生成与 QA 逻辑可重构。
        "orchestrator_snapshot": str(orchestrator_snapshot),  # 写入 run 内只读身份快照路径，避免依赖后来可能变化的外部源码。
        "units": "N-mm-tonne-s",  # 写入质量和全桥一致的单位制；官方 VM53 子案例自身沿用一致单位数值。
        "coordinate_system": "X longitudinal, Y transverse, Z vertical",  # 写入项目全局坐标语义，局部小模型在各输入中另有说明。
        "execute_requested": bool(execute),  # 记录用户是否显式传入执行开关。
        "full_solve_memory_gate": memory,  # 写入当前内存快照，但该门禁只控制 B00，不阻止微型 U01。
        "cases": cases,  # 写入八个案例的身份、输入哈希、来源和初始状态。
        "status": "PREPARED_NOT_STARTED",  # 初始状态在任何 MAPDL 启动前明确封板。
    }  # 结束根 manifest 对象。
    write_json_atomic(run_dir / "manifest.json", manifest)  # 原子写入根 manifest。
    write_new_text(run_dir / "launch_command.txt", build_launch_text(cases, run_dir))  # 写入八条审计命令，不把它当作执行来源。
    source_lines: list[str] = [f"{orchestrator_snapshot_sha256}  orchestrator_snapshot/{SCRIPT_PATH.name}", f"{orchestrator_source_sha256}  SOURCE::{SCRIPT_PATH}"]  # 先写入 run 内脚本快照及其外部执行源的同一 SHA-256 身份。
    for case in cases:  # 遍历八个案例并写入派生输入及源文件摘要。
        source_lines.append(f"{case['input_sha256']}  input_snapshot/{case['case_id']}.inp")  # 写入输入快照相对路径和摘要。
        for source_record in case["source_files"]:  # 遍历当前案例的一个模板或已知答案源。
            source_lines.append(f"{source_record['sha256']}  SOURCE::{source_record['path']}")  # 用 SOURCE:: 前缀区分 run 外只读来源。
    write_new_text(run_dir / "source_hashes.sha256", "\n".join(source_lines) + "\n")  # 排他创建初始源哈希台账。
    field_dictionary = """# U01 机器文件字段说明\n\n- `manifest.json`：套件身份、U00 父级、MAPDL 哈希、编排脚本哈希、内存快照和八个案例清单。\n- `orchestrator_snapshot/ultra_u01_suite.py`：本 run 实际生成与判门逻辑的逐字节快照；其 SHA-256 同时写入根 manifest 与 `source_hashes.sha256`。\n- `solver/<case>/manifest.json`：单案例 `/FILNAME`、并行模式、输入哈希、预注册结果和运行状态。\n- `U01_status.json`：八项任务书测试的最终布尔门禁与全部关键指标；U01_03 的 `pair_results` 含六类乘两方向共十二对原生/ASEC 完整响应。\n- `qa/U01_gate_results.csv`：`test_id` 为稳定测试编号，`passed` 为最终布尔值，`summary_json` 为该项完整指标。\n- `sections__u01_section_properties.csv`：六行十三列依次为截面序号，原生 A、Iyy、Izz、J、SCyy、SCzz，以及 ASEC 的同六项属性；面积单位 mm^2，惯性矩与扭转常数单位 mm^4，剪切因子无量纲。\n- `sections__u01_section_deflections.csv`：六行七列依次为截面序号，ASEC 全局 Y 数值/解析总挠度/相对差，ASEC 全局 Z 数值/解析总挠度/相对差；挠度单位 mm，相对差无量纲。\n- `sections__u01_section_native_deflections.csv`：六行十四列依次为截面序号，ASEC/原生 Y 总挠度/相对差、分别扣弯后 Y 剪切挠度/相对差，ASEC/原生 Z 总挠度/相对差、分别扣弯后 Z 剪切挠度/相对差，以及方向映射码；映射码 1 仅表示 H175 原生截面绕梁轴旋转 90 度，0 表示两者 K 均指向 +Z。\n- `sections__u01_section_torsion_audit.csv`：六行九列依次为截面序号，ASEC Y 工况 ROTX/MX，ASEC Z 工况 ROTX/MX，原生 Y 工况 ROTX/MX，原生 Z 工况 ROTX/MX；转角单位 rad，根部力矩单位 N·mm。\n- `revolute_6dof__u01_revolute_6dof_result.csv`：六行五列依次为工况号、节点关节相对运动、载荷端响应、等效刚度、MPC184 自由 X 轴寄生约束力矩；平动单位为 mm 或 N/mm，转动单位为 rad 或 N·mm/rad，力矩单位为 N·mm。\n- `revolute_6dof__u01_revolute_joint_result.csv`：六行九列依次为工况号、JFX、JFY、JFZ、JMX、JMY、JMZ、JRP4、JRU4；约束力单位为 N，约束力矩单位为 N·mm，相对位置与相对转动单位为 rad。\n- `source_hashes.sha256`：编排脚本快照、输入快照及 run 外只读来源的 SHA-256；`SOURCE::` 后为来源绝对路径。\n- `artifact_hashes.sha256`：本次 run 内全部交付文件的最终 SHA-256，不包含该清单自身。\n- 各 APDL CSV 均无表头，因为字段说明由本文件和 `result_packet.md` 承担，未向不支持注释的格式插入非法注释。\n"""  # 定义 JSON、脚本快照、四份截面 CSV、哈希清单及 revolute 两份无表头结果的相邻 Markdown 字段字典。
    write_new_text(run_dir / "qa" / "field_dictionary.md", field_dictionary)  # 写入机器文件逐项说明，满足不可注释格式的配套文档要求。
    return run_dir, manifest  # 返回新目录和已写入的根 manifest。


def execute_run(run_dir: Path, manifest: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:  # 定义套件串行执行函数。
    """按 manifest 顺序前台执行八个白名单小作业并判定八项 U01 门禁；返回更新 manifest 和测试列表。"""  # 函数说明给出输入、输出和执行顺序。

    manifest["status"] = "RUNNING"  # 在首个 MAPDL 启动前把根状态原子更新为 RUNNING。
    manifest["started_utc"] = utc_now().isoformat()  # 记录带 UTC 时区的套件启动时间。
    write_json_atomic(run_dir / "manifest.json", manifest)  # 原子写入运行态，避免崩溃后仍显示未启动。
    case_failures: list[str] = []  # 创建案例执行失败消息列表，允许其余独立小案例继续收集证据。
    for case in manifest["cases"]:  # 按固定 manifest 顺序逐一执行，禁止并发争用许可证或目录。
        case_manifest_path = run_dir / "solver" / str(case["case_id"]) / "manifest.json"  # 定位当前案例独立 manifest。
        case["status"] = "RUNNING"  # 在启动当前案例前更新内存中的状态。
        case["started_utc"] = utc_now().isoformat()  # 记录当前案例 UTC 启动时间。
        write_json_atomic(case_manifest_path, case)  # 原子写入案例运行态。
        try:  # 捕获单个独立案例异常，使其他案例仍可运行并形成完整缺口清单。
            execution = run_case(case, run_dir)  # 前台执行当前白名单案例并验证原生日志和结果文件。
            case.update(execution)  # 合并返回码、耗时、日志计数和结果路径。
            case["status"] = "SOLVE_COMPLETED_QA_PENDING"  # 求解成功只进入待 QA 状态，不能直接标记 PASSED。
        except Exception as error:  # 捕获路径、进程、日志或结果缺件异常。
            case["status"] = "REJECTED"  # 将当前案例明确标记为拒绝。
            case["error"] = f"{type(error).__name__}: {error}"  # 保存异常类型和消息供可复核诊断。
            case_failures.append(f"{case['case_id']}: {case['error']}")  # 将案例标识和错误加入套件缺口列表。
        case["finished_utc"] = utc_now().isoformat()  # 无论成功失败都记录当前案例结束时间。
        write_json_atomic(case_manifest_path, case)  # 原子封存当前案例执行状态。
        write_json_atomic(run_dir / "manifest.json", manifest)  # 同步根 manifest 的案例状态，降低中途崩溃信息损失。
    tests: list[dict[str, Any]] = []  # 创建八项任务书门禁结果列表。
    if not case_failures:  # 只有八个底层 MAPDL 案例全部完成时才进行数值判门。
        tests.append(evaluate_link(run_dir))  # 判定 LINK180 完整组合链。
        tests.append(evaluate_axis(run_dir))  # 判定 BEAM188 实际方向和双向弯曲。
        tests.append(evaluate_sections(run_dir))  # 判定六类截面属性与剪切柔度。
        tests.append(evaluate_mpc(run_dir))  # 判定 MPC184 刚臂、滑移和相邻罚因子收敛。
        tests.append(evaluate_hinge(run_dir))  # 判定 revolute joint 六自由度高低刚度极限。
        mass_test, closure_test, dmp_test = evaluate_mass_and_closure(run_dir)  # 联合判定 MASS21、全频带闭合和 DMP4 导出。
        tests.extend([mass_test, closure_test, dmp_test])  # 按 U01 06 至 08 顺序加入三项结果。
    else:  # 任一底层案例失败时构造八项显式失败对象，禁止缺项被解释为未检查但可放行。
        tests = [{"test_id": f"U01_{index:02d}_NOT_EVALUATED", "passed": False, "reason": "MAPDL_CASE_FAILURE", "case_failures": case_failures} for index in range(1, 9)]  # 生成八个带共同失败清单的拒绝项。
    if len(tests) != 8:  # 检查任务书八项结果数量严格闭合。
        raise RuntimeError(f"U01 测试数量不是 8：{len(tests)}")  # 任何编排缺项都使套件失败。
    overall_passed = all(bool(test["passed"]) for test in tests)  # 只有八项全部通过才允许 U01=PASSED。
    for case in manifest["cases"]:  # 根据数值 QA 总结更新底层成功案例的最终状态。
        if case["status"] == "SOLVE_COMPLETED_QA_PENDING":  # 只更新原生求解已成功的案例。
            case["status"] = "PASSED" if overall_passed else "QA_COMPLETED_SUITE_REJECTED"  # 套件有任一门禁失败时不让单案例冒充 U01 整体通过。
            write_json_atomic(run_dir / "solver" / str(case["case_id"]) / "manifest.json", case)  # 原子写入案例最终状态。
    final_memory = memory_snapshot()  # 在全部小作业结束后重新读取内存，决定全桥下一动作而不影响 U01 本身。
    manifest["finished_utc"] = utc_now().isoformat()  # 记录套件完成或拒绝时间。
    manifest["final_memory_gate"] = final_memory  # 写入结束时的当前内存快照。
    manifest["status"] = "PASSED" if overall_passed else "REJECTED"  # 根据八项 all() 写入唯一根状态。
    manifest["tests"] = tests  # 把八项完整指标嵌入根 manifest，避免 CSV 单独漂移。
    manifest["next_action"] = "PREPARE_B00_ISOLATED_INPUT_ONLY" if overall_passed and not final_memory["full_solve_memory_ready"] else ("B00_PREFLIGHT_REQUIRED" if overall_passed else "FIX_U01_AND_RERUN")  # 在通过但低内存时只允许准备 B00，禁止启动。
    write_json_atomic(run_dir / "manifest.json", manifest)  # 原子写入根最终状态和八项指标。
    return manifest, tests  # 返回更新后的 manifest 和八项测试列表。


def write_result_packet(run_dir: Path, manifest: dict[str, Any], tests: list[dict[str, Any]]) -> None:  # 定义最终 Result Packet 写入函数。
    """写出用户可读 U01 结论、八项状态、内存门禁和关键边界；输入为最终 manifest 与测试列表。"""  # 函数说明给出输入和输出文件。

    passed_count = sum(1 for test in tests if bool(test["passed"]))  # 统计八项中通过数量。
    lines = [  # 创建 Result Packet Markdown 行列表。
        "# U01 Unit Tests Result Packet",  # 写入固定交付标题。
        "",  # 用空行分隔标题和摘要。
        f"- Suite: `{manifest['suite_id']}`",  # 写入唯一套件目录身份。
        f"- Status: `{manifest['status']}`",  # 写入 PASSED 或 REJECTED 根状态。
        f"- Passed tests: `{passed_count}/8`",  # 写入八项闭合计数。
        f"- MAPDL: `{manifest['mapdl_version']}`",  # 写入实际求解器版本。
        f"- Executable SHA-256: `{manifest['executable_sha256']}`",  # 写入可执行文件摘要。
        f"- B00 full-solve memory ready: `{str(bool(manifest['final_memory_gate']['full_solve_memory_ready'])).lower()}`",  # 写入结束时 8 GiB 内存门禁。
        f"- Next action: `{manifest['next_action']}`",  # 写入合法下一动作。
        "",  # 用空行分隔摘要和八项测试表。
        "## Eight mandatory gates",  # 写入八项门禁小标题。
        "",  # 用空行分隔标题和表格。
        "| Test | Status |",  # 写入两列表头。
        "|---|---|",  # 写入 Markdown 表格分隔行。
    ]  # 结束初始 Result Packet 行列表。
    for test in tests:  # 按固定顺序遍历八项测试对象。
        lines.append(f"| `{test['test_id']}` | `{'PASS' if test['passed'] else 'FAIL'}` |")  # 写入稳定测试编号和通过/失败状态。
    lines.extend([  # 追加证据边界和机器文件说明。
        "",  # 用空行分隔表格和边界说明。
        "## Evidence boundary",  # 写入证据边界标题。
        "",  # 用空行分隔标题和正文。
        "本套件只证明本机 MAPDL 的小模型单元、截面、连接、质量、Block Lanczos 与 DMP 导出链；不证明全桥几何、静力平衡或报告目标频率已经正确。",  # 明确 U01 不能外推到全桥物理正确性。
        "",  # 用空行分隔两段边界说明。
        "原生截面仅作为剪切因子和积分属性参考；H175、RHS160 和 RHS50×30 的原生扭转常数与冻结目标可能不满足 0.1%，因此不得把原生截面未经等价处理直接并入生产模型。",  # 明确 S20 后续风险。
        "",  # 用空行分隔正文和机器证据列表。
        "U01_03 的十二对原生/ASEC 总挠度、剪切挠度、ROTX 和根部 MX 明细见 `U01_status.json` 的 `pair_results`，原始求解列见 `post/sections__u01_section_native_deflections.csv` 与 `post/sections__u01_section_torsion_audit.csv`。",  # 指向十二对整合状态和两份相互独立的 MAPDL 原始 CSV 证据。
        "",  # 用空行分隔截面成对证据与通用机器文件说明。
        "完整数值指标见 `U01_status.json` 与 `qa/U01_gate_results.csv`；CSV/JSON 字段见 `qa/field_dictionary.md`。",  # 指向无损机器指标和相邻字段字典。
    ])  # 结束 Result Packet 追加内容。
    write_new_text(run_dir / "result_packet.md", "\n".join(lines) + "\n")  # 排他创建最终用户可读 Result Packet。


def parse_arguments() -> argparse.Namespace:  # 定义命令行解析函数，无参数，返回 argparse 命名空间。
    """解析唯一可变开关 ``--execute``；省略时只准备，指定时顺序运行八个 U01 小作业。"""  # 函数说明给出默认安全行为。

    parser = argparse.ArgumentParser(description=__doc__)  # 创建解析器并复用模块说明作为帮助文本。
    parser.add_argument("--execute", action="store_true", help="显式前台执行八个 U01 小作业；省略时只准备，不启动 MAPDL。")  # 添加唯一执行授权开关。
    return parser.parse_args()  # 解析当前进程参数并返回命名空间。


def main() -> int:  # 定义主入口函数，无参数，返回进程退出码。
    """准备并可选执行 U01；成功准备或全部通过返回 0，执行后任一门禁失败返回 1。"""  # 函数说明给出输入来源、输出和退出码语义。

    arguments = parse_arguments()  # 读取显式执行授权；默认值为 False。
    run_dir, manifest = prepare_run(bool(arguments.execute))  # 创建全新不可覆盖 run 并封板八个输入。
    tests: list[dict[str, Any]] = []  # 创建测试列表；纯准备模式保持为空并不伪造通过结论。
    if arguments.execute:  # 只有用户显式指定 --execute 时才允许调用 subprocess 启动 MAPDL。
        try:  # 捕获数值判门自身异常，确保根 manifest 不停留在 RUNNING。
            manifest, tests = execute_run(run_dir, manifest)  # 顺序执行八个案例并计算八项门禁。
        except Exception as error:  # 捕获编排、解析或 QA 异常。
            manifest["status"] = "REJECTED"  # 将根状态明确改为拒绝。
            manifest["fatal_error"] = f"{type(error).__name__}: {error}"  # 保存异常类型和消息。
            manifest["finished_utc"] = utc_now().isoformat()  # 记录失败结束时间。
            manifest["final_memory_gate"] = memory_snapshot()  # 仍记录失败时当前内存门禁。
            manifest["next_action"] = "FIX_U01_AND_RERUN"  # 明确下一步只能修复并新建 run 重跑。
            write_json_atomic(run_dir / "manifest.json", manifest)  # 原子封存失败状态。
            tests = [{"test_id": f"U01_{index:02d}_FATAL", "passed": False, "reason": manifest["fatal_error"]} for index in range(1, 9)]  # 构造八项显式失败对象。
        status = {"run_id": "U01_UNIT_TESTS", "suite_id": manifest["suite_id"], "status": manifest["status"], "passed_count": sum(1 for test in tests if test["passed"]), "required_count": 8, "tests": tests, "full_solve_memory_ready": bool(manifest["final_memory_gate"]["full_solve_memory_ready"]), "next_action": manifest["next_action"]}  # 构造简明 U01 状态对象。
        write_json_atomic(run_dir / "U01_status.json", status)  # 原子写入正式八项状态门禁。
        write_gate_csv(run_dir / "qa" / "U01_gate_results.csv", tests)  # 排他创建门禁明细 CSV。
        write_result_packet(run_dir, manifest, tests)  # 写入用户可读 Result Packet 和证据边界。
    else:  # 纯准备模式不执行求解也不生成伪造的八项通过状态。
        status = {"run_id": "U01_UNIT_TESTS", "suite_id": manifest["suite_id"], "status": "PREPARED_NOT_STARTED", "passed_count": 0, "required_count": 8, "tests": [], "full_solve_memory_ready": bool(manifest["full_solve_memory_gate"]["full_solve_memory_ready"]), "next_action": "RERUN_WITH_EXPLICIT_EXECUTE_TO_CREATE_NEW_SUITE"}  # 构造准备态状态对象。
        write_json_atomic(run_dir / "U01_status.json", status)  # 写入明确未执行的状态，防止准备包被误当通过证据。
        write_new_text(run_dir / "result_packet.md", f"# U01 Unit Tests Result Packet\n\n- Suite: `{manifest['suite_id']}`\n- Status: `PREPARED_NOT_STARTED`\n- MAPDL was not started.\n")  # 写入准备态 Result Packet。
    artifact_records = collect_artifact_hashes(run_dir)  # 在所有状态和报告写入后收集最终产物摘要。
    artifact_text = "\n".join(f"{digest}  {relative}" for relative, digest in artifact_records) + "\n"  # 按 sha256sum 风格构造稳定清单文本。
    write_new_text(run_dir / "artifact_hashes.sha256", artifact_text)  # 排他创建最终产物哈希清单。
    print(run_dir)  # 在标准输出打印唯一 run 路径，供调用者和用户直接定位结果。
    if arguments.execute and manifest["status"] != "PASSED":  # 执行模式下任一门禁失败必须返回非零退出码。
        return 1  # 返回 1 表示 U01 未通过，但结果包和失败证据已完整封存。
    return 0  # 纯准备成功或执行后八项全通过时返回 0。


if __name__ == "__main__":  # 仅当脚本作为主程序运行时执行，导入审计函数不会意外启动 MAPDL。
    raise SystemExit(main())  # 把 main 返回值转换为进程退出码并正常终止。
