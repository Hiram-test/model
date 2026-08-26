"""从冻结 A10/A30 轴基线派生 S10 六类 ASEC 剪切参数单变量输入，并且绝不启动 MAPDL。"""  # 模块只负责源证校验、六行改写、双副本和准备期审计。

from __future__ import annotations  # 延迟解析类型注解，保持当前 Python 运行时兼容性。

import argparse  # 解析可选安全运行名和用户已明确给出的内存门槛覆盖标志。
import csv  # 写六条截面差异和十一项输入哈希审计 CSV。
import hashlib  # 计算文本和文件 SHA-256，证明单变量与双副本闭合。
import io  # 在内存中生成合法 CSV，避免平台换行改变。
import json  # 读取父清单/U01 状态并写机器证据。
import math  # 校验剪切因子与尺寸均为有限正数。
import re  # 严格定位六个 SECTYPE/SECDATA 并约束运行名和 jobname。
import secrets  # 生成两位十六进制作业后缀，降低同秒碰撞概率。
import shutil  # 逐字节复制十项不变量输入和源码快照。
from datetime import datetime, timezone  # 生成 UTC 微秒运行身份。
from pathlib import Path  # 统一管理 Windows 绝对路径和相对清单标签。
from typing import Any  # 描述 JSON/CSV 中的异构标量字段。

import ultra_b00_prepare as b00  # 复用已经审计的纯文本静力—保持—80阶模态控制模板和只读资源函数。


SCRIPT_PATH = Path(__file__).resolve()  # 固定本编排器绝对路径供源码哈希与快照使用。
TOOLS_DIR = SCRIPT_PATH.parent  # ultra_tools 是当前编排器和 U01 模板的唯一目录。
PROJECT_DIR = TOOLS_DIR.parent  # 指向“附件2-3全模态精确对齐_V2.0”项目根目录。
ULTRA_RUNS_DIR = PROJECT_DIR / "ultra_runs"  # 所有正式试算包只能写入该目录。
A10_RUN_NAME = "A10_H175_AXIS_20260715T172214962299Z"  # A30 实际复用的已求解轴基线身份。
A20_RUN_NAME = "A20_RHS5030_AXIS_20260715T214637371159Z"  # RHS 已正确且零差异的源证身份。
A30_RUN_NAME = "A30_ALL_AXES_20260715T230922215766Z"  # 固定使用最终独立 QA 封板且产物账本闭合的 A30=A10 输入/结果等价父包。
U01_RUN_NAME = "U01_UNIT_TESTS_20260715T225028311569Z"  # 12 对 native-vs-ASEC 双向短梁真实通过的唯一权威 U01 来源。
HISTORY_QA_RUN_NAME = "U02_LS1_HISTORY_MICROQA_20260715T225026Z"  # SET,FIRST/NEXT 与全历程 VENG 峰值捕获已由 v261 小模型验证的固定作业。
A10_DIR = ULTRA_RUNS_DIR / A10_RUN_NAME  # 冻结 A10 输入和已执行结果目录。
A20_DIR = ULTRA_RUNS_DIR / A20_RUN_NAME  # A20 零差异目录。
A30_DIR = ULTRA_RUNS_DIR / A30_RUN_NAME  # A30 等价父包目录。
U01_DIR = ULTRA_RUNS_DIR / U01_RUN_NAME  # U01 八项小算例目录。
U01_STATUS_PATH = U01_DIR / "U01_status.json"  # U01 总状态机器证据。
U01_MANIFEST_PATH = U01_DIR / "manifest.json"  # U01 可执行身份、源链和最终状态清单。
U01_SECTION_TEMPLATE_PATH = TOOLS_DIR / "u01_templates" / "u01_sections.inp"  # 六类生产剪切因子的直接 APDL 源证。
U01_SECTION_PROPERTIES_PATH = U01_DIR / "post" / "sections__u01_section_properties.csv"  # 六类原生属性与冻结目标值的纯数值对照。
U01_SECTION_DEFLECTIONS_PATH = U01_DIR / "post" / "sections__u01_section_deflections.csv"  # 六类 ASEC 对解析式的辅助自洽挠度证据。
U01_SECTION_NATIVE_DEFLECTIONS_PATH = U01_DIR / "post" / "sections__u01_section_native_deflections.csv"  # 六类两方向 native-vs-ASEC 直接剪切挠度证据。
U01_SECTION_TORSION_AUDIT_PATH = U01_DIR / "post" / "sections__u01_section_torsion_audit.csv"  # 12 对短梁 ROTX 与根部 MX 寄生扭转证据。
HISTORY_QA_DIR = ULTRA_RUNS_DIR / HISTORY_QA_RUN_NAME  # LS1 全历程控制链小模型的独立封板目录。
HISTORY_QA_MANIFEST_PATH = HISTORY_QA_DIR / "manifest.json"  # LS1 全历程小模型计数、版本与边界清单。
HISTORY_QA_STATUS_PATH = HISTORY_QA_DIR / "history_microqa_status.txt"  # LS1 全历程小模型唯一 PASSED 状态文件。
AXIS_INCLUDE_NAME = "apply_finite_gates_and_passages_v2.inp"  # 唯一允许发生物理变化的依赖文件名。
MAIN_INPUT_NAME = "s10_section_shear_main.inp"  # S10 solver 目录中的唯一主输入文件名。
RUN_PREFIX = "S10_SECTION_SHEAR"  # 运行目录前缀对应试算矩阵的 S10_SECTION_SHEAR。
RUN_ID = "S10_SECTION_SHEAR"  # manifest 中的固定运行标识。
MODEL_LINE = "A30_AXES_PLUS_ASEC_SHEAR_ONLY"  # 模型线强调只在 A30 轴基线上增加截面剪切定义。
REQUESTED_MODES = 80  # 所有诊断全桥试算严格提取 80 阶且不设频率上限。
DEPENDENCY_COUNT = 11  # A10/A30 主输入固定包含 11 个有序依赖。
TARGET_SECTION_COUNT = 6  # S10 只允许修改 SECNUM 61 至 66 共六条 SECDATA。
TARGET_BEAM_COUNT = 17679  # 六个组件合计覆盖全部 TYPE70 有限梁 17,679 根。
A10_INCLUDE_SHA256 = "68d9dc11395baa39a8c3d9abaac113865949873fa704de8443f6b54e6055aa3c"  # 冻结 A10/A30 轴基线 include 身份。
B00_TEMPLATE_SHA256 = "61f355198b4e6ca6bf94ef312087ed08ee25ccd48477eb72fa9c7169b6533814"  # 已加入 LS1 全历程 VENG/峰值门禁并经 U02 小模型验证的控制模板身份。
U01_STATUS_SHA256 = "b2aeafde85d4bda34bd645e6cdce3329c7be86b6ffe42cfe9ed131105196b7b4"  # 最终 U01 8/8 与 12 对短梁逐对结果状态身份。
U01_MANIFEST_SHA256 = "a5c76e1f3123c3fc6955fd712a026d77862e586e916d5a2d8badfea4d30307dc"  # 最终 U01 运行环境、源证和产物集合清单身份。
U01_SECTION_TEMPLATE_SHA256 = "fbd4fa531c1a010c9ad6f1a7904c40add02d23545d0118f0cc5e5c0e0d20e620"  # 含 native-vs-ASEC 双向短梁与合法 ROT,X 读取的 v261 截面模板身份。
U01_SECTION_PROPERTIES_SHA256 = "c84dc9358fb50efc49b8026341a42a7463ddb7727c78b216193853f5e381657c"  # 六类 13 列属性原始 CSV 身份。
U01_SECTION_DEFLECTIONS_SHA256 = "88cc0816cdeab88b18f80ee9dc3495a344ec27b9d7904e05399506acbeb530a7"  # 六类 7 列解析挠度原始 CSV 身份。
U01_SECTION_NATIVE_DEFLECTIONS_SHA256 = "0f931538cb07cbebf8a710d358e2d2fd933d4cb4737cbc636b82b9266278f0de"  # 六类两方向 14 列 native-vs-ASEC 原始 CSV 身份。
U01_SECTION_TORSION_AUDIT_SHA256 = "e48d4e5d32c380f95916df3f5d4c68cc1937d09f7d18a2d4741bd37ab470a6d1"  # 六类两方向寄生 ROTX/MX 原始 CSV 身份。
HISTORY_QA_MANIFEST_SHA256 = "c892ebde94d288c86fca4287bfb248b98b33371b272d40abdda52eb1dbfd3d5e"  # U02 六 SET、五 LS1 子步控制链清单身份。
HISTORY_QA_STATUS_SHA256 = "38ac6385d81b01fc55794662c20b3f5e27490e0cb0db35549bf939caa03ea153"  # U02 唯一 STATUS=PASSED 文本身份。
A30_MANIFEST_SHA256 = "2177796d80b849454e45fa5664003df4669f302c11298e27916a63a3c61d0b71"  # 最终 A30 输入/结果等价清单身份，由独立 QA 包逐字节固定。
RUN_NAME_PATTERN = re.compile(r"S10_SECTION_SHEAR_\d{8}T\d{12}Z\Z", re.ASCII)  # 只接受 UTC 微秒格式的安全目录名。
JOBNAME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}\Z", re.ASCII)  # MAPDL jobname 必须为不超过 32 字符的 ASCII 标识符。
SECTYPE_PATTERN = re.compile(r"SECTYPE,(6[1-6]),BEAM,ASEC,[^,\r\n!]+(?:\s*!.*)?\Z", re.IGNORECASE)  # 严格定位 SEC61..66 的 ASEC 定义。
SECDATA_PATTERN = re.compile(r"SECDATA,([^!\r\n]+?)(?:\s*!.*)?\Z", re.IGNORECASE)  # 解析一行 SECDATA 数值字段并排除行尾注释。
ENERGY_BEGIN = "! S10_ENERGY_BLOCK_BEGIN"  # 所有非物理能量输出注入块的可剥离起始标记。
ENERGY_END = "! S10_ENERGY_BLOCK_END"  # 所有非物理能量输出注入块的可剥离结束标记。
ENERGY_FILE_STEM = "s10_section_modal_sene"  # 未来 80 行六组件 SENE CSV 的固定文件干名。
SECTION_PAIR_RELATIVE_LIMIT = 5.0e-3  # native-vs-ASEC 总挠度与剪切挠度相对差均须严格小于 0.5%。
PARASITIC_ROTX_LIMIT_RAD = 1.0e-10  # 纯横向质心荷载下短梁端部寄生绕梁轴转角上限，单位 rad。
PARASITIC_ROOT_MX_LIMIT_N_MM = 1.0e-5  # 纯横向质心荷载下短梁根部寄生绕梁轴力矩上限，单位 N·mm。


SECTION_EXTENSIONS: dict[int, dict[str, str]] = {  # 为六类冻结 ASEC 固定字段 7..14，不接受命令行调参。
    61: {"tkz": "175", "tky": "175", "tsxz": "0.6712958043168660", "tsxy": "0.2363842696133852", "name": "H175"},  # H175 在 A10 中 local-y 竖直，因此原生 y/z 剪切因子交叉映射。
    62: {"tkz": "160", "tky": "160", "tsxz": "0.4260313674231808", "tsxy": "0.4260313674224075", "name": "RHS160x160x4"},  # 方管两方向尺寸相同但保留 v261 双精度原生值。
    63: {"tkz": "152", "tky": "152", "tsxz": "0.5014069989778299", "tsxy": "0.5014069989777504", "name": "PHI152x6"},  # 圆管采用 U01 实测值而非仅作审计基准的 0.5。
    64: {"tkz": "102", "tky": "102", "tsxz": "0.5013879262913112", "tsxy": "0.5013879262914291", "name": "PHI102x4"},  # 保留 U01 v261 原生截面双向剪切因子。
    65: {"tkz": "51", "tky": "51", "tsxz": "0.5060286117392122", "tsxy": "0.5060286117392480", "name": "PHI51x4"},  # 该短管与 0.5 相差约 1.19%，必须使用 U01 封板值。
    66: {"tkz": "30", "tky": "50", "tsxz": "0.2874280543410113", "tsxy": "0.6098841965465526", "name": "RHS50x30x4"},  # A20 证明 local-z=30 mm 竖高、local-y=50 mm 宽度。
}  # 结束六类不可调生产值映射。


COMPONENTS: tuple[tuple[int, str, int], ...] = (  # 按截面号固定六个互斥有限梁组件及预期元素数。
    (61, "GATE_BOTTOM_E", 2698),  # H175 门架下横梁共 2,698 根。
    (62, "GATE_TOPPOST_E", 1562),  # RHS160 门架上梁与立柱共 1,562 根。
    (63, "PASS_CHORD152_E", 4011),  # Φ152 横通道主弦杆共 4,011 根。
    (64, "PASS_FRAME102_E", 1890),  # Φ102 横通道端架/横架/接口杆共 1,890 根。
    (65, "PASS_BRACE51_E", 4620),  # Φ51 横通道腹杆共 4,620 根。
    (66, "PASS_RHS5030_E", 2898),  # RHS50×30 横通道纵向杆共 2,898 根。
)  # 六组数量之和必须等于 TYPE70 的 17,679 根。


def require(condition: bool, message: str) -> None:  # 输入布尔门禁和失败说明；失败时立即终止。
    """所有 S10 源证、文本差异和准备期门禁均 fail-closed。"""  # 函数说明给出异常语义。
    if not condition:  # 只有条件为假时进入拒绝路径。
        raise RuntimeError(message)  # 抛出明确异常并阻止创建误导性运行包。


def sha256_text(text: str) -> str:  # 输入 Unicode 文本并返回其 UTF-8 字节 SHA-256。
    """用于尚未落盘的受控 include 和主输入身份计算。"""  # 函数说明给出编码和用途。
    return hashlib.sha256(text.encode("utf-8")).hexdigest()  # 一次性编码小于 5 MB 的输入文本并返回摘要。


def read_json(path: Path) -> dict[str, Any]:  # 输入 JSON 路径并返回顶层对象。
    """允许可选 UTF-8 BOM，顶层不是对象时拒绝。"""  # 函数说明给出格式约束。
    require(path.is_file(), f"缺少 JSON 证据：{path}")  # 文件必须存在。
    value = json.loads(path.read_text(encoding="utf-8-sig"))  # 解析 UTF-8 JSON。
    require(isinstance(value, dict), f"JSON 顶层不是对象：{path}")  # 只接受具名字段对象。
    return value  # 返回已验证字典。


def write_new_text(path: Path, text: str) -> None:  # 输入新路径和完整文本并以不可覆盖模式写入。
    """固定 UTF-8/LF；目标存在时拒绝，防止覆盖旧运行证据。"""  # 函数说明给出写入边界。
    require(not path.exists(), f"拒绝覆盖既有文件：{path}")  # 写入前检查同名目标。
    path.parent.mkdir(parents=True, exist_ok=True)  # 只创建新 S10 目录内父路径。
    with path.open("x", encoding="utf-8", newline="\n") as stream:  # x 模式提供操作系统级不可覆盖保证。
        stream.write(text)  # 一次写出完整文本。


def write_new_json(path: Path, value: dict[str, Any]) -> None:  # 输入新路径和 JSON 对象并写格式化文本。
    """JSON 不支持注释，字段说明由 qa/field_dictionary.md 提供。"""  # 函数说明遵守有效 JSON 约束。
    write_new_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")  # 使用两空格缩进和末尾换行。


def copy_new_verified(source: Path, destination: Path) -> str:  # 输入源和新目标路径并返回闭合 SHA-256。
    """复制前后均复算哈希；任何字节差异或同名目标都拒绝。"""  # 函数说明给出输出和异常路径。
    require(source.is_file(), f"待复制源不存在：{source}")  # 源必须是普通文件。
    require(not destination.exists(), f"拒绝覆盖复制目标：{destination}")  # 目标必须尚不存在。
    destination.parent.mkdir(parents=True, exist_ok=True)  # 创建新运行包内父目录。
    source_hash = b00.sha256_file(source)  # 复制前计算源摘要。
    shutil.copy2(source, destination)  # 逐字节复制并保留基本元数据。
    require(b00.sha256_file(destination) == source_hash, f"复制哈希不一致：{source.name}")  # 从磁盘重新核对目标。
    return source_hash  # 返回同时代表源与目标的摘要。


def transform_section_shear(source_text: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:  # 输入冻结 A10 include 并返回六行增强文本、逐行审计和汇总。
    """只向 SEC61..66 的六条 SECDATA 追加字段7..14；前六项和全部其他字节保持不变。"""  # 函数说明给出唯一允许差异。
    require("\r\n" in source_text, "A10 include 不是预期 CRLF 文本")  # 保留冻结 Windows 换行身份。
    require("\n" not in source_text.replace("\r\n", ""), "A10 include 含混合换行")  # 拒绝裸 LF 隐藏差异。
    lines = source_text.splitlines(keepends=True)  # 保留每行 CRLF 供精确替换。
    modified_lines = list(lines)  # 创建内存副本，源文本保持只读。
    current_section: int | None = None  # 跟踪最近一个 SEC61..66 ASEC 定义。
    seen_sections: set[int] = set()  # 记录已改写截面号，防止重复或缺失。
    audit_rows: list[dict[str, Any]] = []  # 保存六条旧/新命令及字段门禁。
    changed_indices: list[int] = []  # 保存发生差异的零基行索引。
    for line_index, raw_line in enumerate(lines):  # 按冻结原顺序扫描全部 APDL 行。
        command = raw_line.rstrip("\r\n")  # 仅移除行尾换行供正则匹配。
        section_match = SECTYPE_PATTERN.fullmatch(command)  # 尝试识别目标 ASEC 定义。
        if section_match is not None:  # 命中时更新当前截面状态。
            current_section = int(section_match.group(1))  # 保存 61..66 截面号。
            continue  # SECTYPE 本身绝不修改。
        data_match = SECDATA_PATTERN.fullmatch(command)  # 尝试识别 SECDATA 数值行。
        if data_match is None or current_section not in SECTION_EXTENSIONS:  # 非目标数据行不参与变换。
            continue  # 保持原字节并扫描下一行。
        section_id = int(current_section)  # 收窄当前目标截面号。
        require(section_id not in seen_sections, f"SEC{section_id} 出现重复 SECDATA")  # 每个目标只允许一条数据行。
        require("!" not in command, f"SEC{section_id} 旧 SECDATA 含未知行尾注释")  # 旧行应是纯六字段冻结命令。
        fields = [field.strip() for field in command.split(",")]  # 拆出命令名和六个冻结数值字符串。
        require(len(fields) == 7 and fields[0].upper() == "SECDATA", f"SEC{section_id} 旧 SECDATA 不是六参数")  # 前六物理属性必须完整且无额外字段。
        require(all(math.isfinite(float(field)) for field in fields[1:]), f"SEC{section_id} 前六项含非有限数")  # 拒绝 NaN/无穷。
        extension = SECTION_EXTENSIONS[section_id]  # 读取该截面的不可调 U01 字段。
        appended_fields = ["0", "0", "0", "0", extension["tkz"], extension["tky"], extension["tsxz"], extension["tsxy"]]  # CGy/CGz/SHy/SHz 为对称截面的零偏置，随后是尺寸和双向剪切因子。
        require(all(math.isfinite(float(field)) for field in appended_fields), f"SEC{section_id} 追加字段含非有限数")  # 所有生产值必须有限。
        require(float(extension["tkz"]) > 0.0 and float(extension["tky"]) > 0.0, f"SEC{section_id} 外包络尺寸非正")  # TKz/TKy 单位 mm 且必须为正。
        require(float(extension["tsxz"]) > 0.0 and float(extension["tsxy"]) > 0.0, f"SEC{section_id} 剪切因子非正")  # TS 是无量纲正修正因子。
        new_command = command + "," + ",".join(appended_fields) + f" ! S10：SEC{section_id}仅补对称截面偏置、TKz/TKy与U01-v261双向剪切因子"  # 保持旧命令前缀逐字不变并追加中文用途说明。
        modified_lines[line_index] = new_command + "\r\n"  # 只替换当前一行并保持 CRLF。
        seen_sections.add(section_id)  # 标记当前截面已完成唯一改写。
        changed_indices.append(line_index)  # 记录差异行位置。
        audit_rows.append({"section_id": section_id, "section_name": extension["name"], "line_number": line_index + 1, "old_command": command, "new_command": new_command, "frozen_first_six_fields_identical": new_command.startswith(command + ","), "cgy_mm": 0.0, "cgz_mm": 0.0, "shy_mm": 0.0, "shz_mm": 0.0, "tkz_mm": float(extension["tkz"]), "tky_mm": float(extension["tky"]), "tsxz": float(extension["tsxz"]), "tsxy": float(extension["tsxy"]), "u01_source": str(U01_SECTION_TEMPLATE_PATH), "status": "PASS"})  # 保存六字段不变、追加值、单位和源证。
        current_section = None  # 当前目标 SECDATA 已消费，防止后续非相邻数据误归属。
    require(seen_sections == set(SECTION_EXTENSIONS), f"S10 截面覆盖不完整：{sorted(seen_sections)}")  # 必须恰好覆盖 61..66。
    require(len(changed_indices) == TARGET_SECTION_COUNT, f"S10 改变行数不是 {TARGET_SECTION_COUNT}")  # 物理文本差异必须为六行。
    require(all(bool(row["frozen_first_six_fields_identical"]) for row in audit_rows), "S10 有截面前六字段发生变化")  # A/I/J 等冻结值绝不允许改变。
    modified_text = "".join(modified_lines)  # 重组完整 CRLF 文本。
    restored_lines = list(modified_lines)  # 创建规范化回退副本。
    for row, line_index in zip(audit_rows, changed_indices, strict=True):  # 按同序六行恢复旧命令。
        restored_lines[line_index] = str(row["old_command"]) + "\r\n"  # 把唯一允许差异还原为 A10 原字节。
    restored_text = "".join(restored_lines)  # 重组规范化文本。
    require(restored_text == source_text, "S10 六行回退后不等于冻结 A10 include")  # 证明没有任何额外物理或文本变化。
    summary = {"schema_version": 1, "status": "PASSED", "physical_change_family_count": 1, "physical_change_family": "ASEC_TRANSVERSE_SHEAR_FACTORS_FOR_SECTIONS_61_TO_66", "changed_line_count": len(changed_indices), "changed_section_ids": sorted(seen_sections), "frozen_first_six_fields_unchanged": True, "appended_field_order": ["CGy", "CGz", "SHy", "SHz", "TKz", "TKy", "TSxz", "TSxy"], "source_sha256": sha256_text(source_text), "modified_sha256": sha256_text(modified_text), "canonicalized_sha256": sha256_text(restored_text), "canonicalized_equals_source": True, "target_beam_count": TARGET_BEAM_COUNT}  # 汇总单变量范围和哈希闭合。
    return modified_text, audit_rows, summary  # 返回内存改写、六行证据和汇总。


def rows_to_csv(rows: list[dict[str, Any]]) -> str:  # 输入同构字典行并返回 UTF-8 CSV 文本。
    """CSV 不插非法注释；字段语义由配套 Markdown 说明。"""  # 函数说明遵守 CSV 格式约束。
    require(bool(rows), "拒绝生成空 CSV")  # 至少需要一行。
    buffer = io.StringIO(newline="")  # 创建禁用平台换行替换的内存缓冲。
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()), lineterminator="\n")  # 固定首行字段顺序和 LF。
    writer.writeheader()  # 写唯一表头。
    writer.writerows(rows)  # 按输入顺序写全部记录。
    return buffer.getvalue()  # 返回完整合法 CSV 文本。


def read_numeric_csv(path: Path, expected_rows: int, expected_columns: int) -> list[list[float]]:  # 输入纯数值 CSV 路径和固定形状并返回有限浮点矩阵。
    """跳过空行但不接受标题、非有限数、缺列、增列或记录数漂移。"""  # 函数说明给出输入格式、返回类型和 fail-closed 边界。
    require(path.is_file(), f"缺少纯数值 CSV：{path}")  # 读取前确认目标是现存普通文件。
    rows: list[list[float]] = []  # 初始化按原始顺序保存的数值矩阵。
    with path.open("r", encoding="utf-8-sig", newline="") as stream:  # 以只读 UTF-8 模式打开并禁用平台换行改写。
        reader = csv.reader(stream)  # 使用标准 CSV 解析器处理逗号与字段空白。
        for line_number, raw_row in enumerate(reader, start=1):  # 逐行保留一基行号供异常定位。
            if not raw_row or all(not field.strip() for field in raw_row):  # 仅允许完全空白行被忽略。
                continue  # 空行不计入固定记录数。
            require(len(raw_row) == expected_columns, f"CSV列数漂移：{path.name}:{line_number} 实际{len(raw_row)} 预期{expected_columns}")  # 每条记录必须恰好满足固定列数。
            try:  # 将当前行全部字段转为浮点并捕获格式错误。
                values = [float(field.strip()) for field in raw_row]  # 去除字段外围空白后解析科学计数法。
            except ValueError as exc:  # 非数值标题或损坏字段进入明确拒绝路径。
                raise RuntimeError(f"CSV含非数值字段：{path.name}:{line_number}") from exc  # 保留原异常链并中止准备。
            require(all(math.isfinite(value) for value in values), f"CSV含NaN或无穷：{path.name}:{line_number}")  # 所有物理量和误差必须为有限数。
            rows.append(values)  # 保存已验证当前行。
    require(len(rows) == expected_rows, f"CSV记录数漂移：{path.name} 实际{len(rows)} 预期{expected_rows}")  # 固定六类截面记录数不得漂移。
    return rows  # 返回已完成形状、类型和有限性验证的矩阵。


def validate_u01_asec_template_values() -> dict[str, Any]:  # 无输入并返回六类生产 ASEC 扩展字段的模板复算摘要。
    """直接解析 U01 模板中 SEC61..66 的 14 个 SECDATA 数值，证明 S10 常量没有脱离源证。"""  # 函数说明强调不只信任状态 JSON。
    template_text = U01_SECTION_TEMPLATE_PATH.read_text(encoding="utf-8-sig")  # 只读加载已固定哈希的 U01 APDL 模板。
    parsed: dict[int, list[float]] = {}  # 保存截面号到 14 个数值字段的映射。
    current_section: int | None = None  # 跟踪最近命中的目标 ASEC 截面号。
    for line_number, raw_line in enumerate(template_text.splitlines(), start=1):  # 按原始行序扫描模板并保留一基行号。
        command = raw_line.strip()  # 移除外围空白以匹配 APDL 命令，不改变源文件。
        section_match = SECTYPE_PATTERN.fullmatch(command)  # 尝试识别 SEC61..66 的 ASEC 定义。
        if section_match is not None:  # 命中目标 SECTYPE 时进入等待对应 SECDATA 的状态。
            current_section = int(section_match.group(1))  # 保存当前 61..66 截面号。
            continue  # SECTYPE 行自身没有数值字段，继续扫描下一行。
        if current_section is None or not command.upper().startswith("SECDATA,"):  # 非目标上下文或非数据行不参与解析。
            continue  # 保持扫描直到目标 SECDATA 出现。
        require(current_section not in parsed, f"U01模板 SEC{current_section} 出现重复 SECDATA")  # 每个目标截面只允许唯一数据行。
        data_command = command.split("!", 1)[0].strip()  # 去除 APDL 行尾说明，仅保留实际命令字段。
        fields = [field.strip() for field in data_command.split(",")]  # 拆出命令名与全部数值字符串。
        require(len(fields) == 15 and fields[0].upper() == "SECDATA", f"U01模板 SEC{current_section} 不是14参数：行{line_number}")  # ASEC 必须含固定六项和八个扩展项。
        values = [float(field) for field in fields[1:]]  # 将 14 个科学计数或十进制字段解析为浮点。
        require(all(math.isfinite(value) for value in values), f"U01模板 SEC{current_section} 含非有限数")  # 模板物理参数必须全部有限。
        parsed[current_section] = values  # 保存该截面完整 14 项字段。
        current_section = None  # 消费唯一 SECDATA 后清空状态，防止误关联后续命令。
    require(set(parsed) == set(SECTION_EXTENSIONS), f"U01模板 ASEC 覆盖漂移：{sorted(parsed)}")  # 必须恰好覆盖 SEC61..66。
    for section_id, extension in SECTION_EXTENSIONS.items():  # 逐截面核对 S10 将写入的八个扩展字段。
        expected_extension = [0.0, 0.0, 0.0, 0.0, float(extension["tkz"]), float(extension["tky"]), float(extension["tsxz"]), float(extension["tsxy"])]  # 按 CGy、CGz、SHy、SHz、TKz、TKy、TSxz、TSxy 构造预期值。
        actual_extension = parsed[section_id][6:14]  # 从模板完整 14 项中提取字段 7 至 14。
        require(len(actual_extension) == len(expected_extension), f"SEC{section_id} 扩展字段长度异常")  # 防止切片或模板字段数漂移。
        for field_index, (actual, expected) in enumerate(zip(actual_extension, expected_extension, strict=True), start=7):  # 按一基 SECDATA 字段号逐项闭合。
            require(math.isclose(actual, expected, rel_tol=1.0e-13, abs_tol=1.0e-15), f"SEC{section_id} 字段{field_index} 与 U01 模板不一致：{actual} != {expected}")  # 双精度源值只允许舍入尾差。
    return {"section_count": len(parsed), "section_ids": sorted(parsed), "template_sha256": b00.sha256_file(U01_SECTION_TEMPLATE_PATH), "field_order": ["A", "Iyy", "Iyz", "Izz", "Iw", "J", "CGy", "CGz", "SHy", "SHz", "TKz", "TKy", "TSxz", "TSxy"], "status": "PASSED"}  # 返回可写入 S10 清单的模板复算摘要。


def validate_u01_section_evidence(u01_status: dict[str, Any]) -> dict[str, Any]:  # 输入已验证 U01 状态并返回原始 CSV 与逐对结果复算摘要。
    """联合解析四份原始 CSV、12 对状态明细和寄生扭转指标；任何一处不闭合均拒绝 S10。"""  # 函数说明给出证据联合范围。
    require(b00.sha256_file(U01_MANIFEST_PATH) == U01_MANIFEST_SHA256, "U01 清单文件哈希漂移")  # 固定 U01 的版本、八案例集合、执行状态和源产物身份。
    require(b00.sha256_file(U01_SECTION_PROPERTIES_PATH) == U01_SECTION_PROPERTIES_SHA256, "U01 截面属性 CSV 哈希漂移")  # 固定六类 A/Iyy/Izz/J 与剪切映射原始数值。
    require(b00.sha256_file(U01_SECTION_DEFLECTIONS_PATH) == U01_SECTION_DEFLECTIONS_SHA256, "U01 解析挠度 CSV 哈希漂移")  # 固定六类 ASEC 双向解析挠度辅助证据。
    require(b00.sha256_file(U01_SECTION_NATIVE_DEFLECTIONS_PATH) == U01_SECTION_NATIVE_DEFLECTIONS_SHA256, "U01 native 对照 CSV 哈希漂移")  # 固定六类乘两方向共十二对直接挠度证据。
    require(b00.sha256_file(U01_SECTION_TORSION_AUDIT_PATH) == U01_SECTION_TORSION_AUDIT_SHA256, "U01 寄生扭转 CSV 哈希漂移")  # 固定十二对 ROTX 与根部 MX 证据。
    properties = read_numeric_csv(U01_SECTION_PROPERTIES_PATH, 6, 13)  # 读取六类属性、剪切映射与冻结目标的 13 列记录。
    analytic_deflections = read_numeric_csv(U01_SECTION_DEFLECTIONS_PATH, 6, 7)  # 读取六类 ASEC 对解析式的 7 列辅助记录。
    native_deflections = read_numeric_csv(U01_SECTION_NATIVE_DEFLECTIONS_PATH, 6, 14)  # 读取六类两方向 native-vs-ASEC 的 14 列核心记录。
    torsion_audit = read_numeric_csv(U01_SECTION_TORSION_AUDIT_PATH, 6, 9)  # 读取六类两方向 ASEC/native 寄生 ROTX 与 MX 的 9 列记录。
    expected_indices = list(range(1, 7))  # 六类截面索引必须连续为 1 至 6。
    for matrix_name, matrix in (("properties", properties), ("analytic", analytic_deflections), ("native", native_deflections), ("torsion", torsion_audit)):  # 对四份原始矩阵统一核对首列身份。
        actual_indices = [int(round(row[0])) for row in matrix]  # 把 Fortran 浮点整数列规范化为 Python 整数。
        require(actual_indices == expected_indices and all(math.isclose(row[0], float(index), abs_tol=1.0e-12) for row, index in zip(matrix, expected_indices, strict=True)), f"U01 {matrix_name} 截面索引不是1..6")  # 顺序、唯一性与整数性必须同时闭合。
    analytic_error_max = max(max(row[3], row[6]) for row in analytic_deflections)  # 复算两方向 ASEC 对解析式的最大相对挠度误差。
    native_total_error_max = max(max(row[3], row[9]) for row in native_deflections)  # 复算两方向 native-vs-ASEC 总挠度最大相对差。
    native_shear_error_max = max(max(row[6], row[12]) for row in native_deflections)  # 复算扣除各自弯曲项后的两方向剪切挠度最大相对差。
    require(analytic_error_max < SECTION_PAIR_RELATIVE_LIMIT, f"U01 ASEC解析挠度误差超过0.5%：{analytic_error_max}")  # 辅助解析门禁必须严格小于 0.5%。
    require(native_total_error_max < SECTION_PAIR_RELATIVE_LIMIT, f"U01 native总挠度差超过0.5%：{native_total_error_max}")  # 两方向总挠度直接对照必须通过。
    require(native_shear_error_max < SECTION_PAIR_RELATIVE_LIMIT, f"U01 native剪切挠度差超过0.5%：{native_shear_error_max}")  # 任务书核心剪切门禁必须通过。
    orientation_flags = [int(round(row[13])) for row in native_deflections]  # 读取 H175 物理旋转标志列。
    require(orientation_flags == [1, 0, 0, 0, 0, 0], f"U01 H175旋转标志漂移：{orientation_flags}")  # 仅 H175 native 允许相对 ASEC 绕梁轴旋转 90 度。
    rotx_columns = (1, 3, 5, 7)  # 扭转审计中 ASEC-Y、ASEC-Z、native-Y、native-Z 的 ROTX 列索引。
    mx_columns = (2, 4, 6, 8)  # 扭转审计中对应四个根部 MX 列索引。
    parasitic_rotx_max = max(abs(row[column]) for row in torsion_audit for column in rotx_columns)  # 复算全部 24 个端部 ROTX 的最大绝对值，单位 rad。
    parasitic_mx_max = max(abs(row[column]) for row in torsion_audit for column in mx_columns)  # 复算全部 24 个根部 MX 的最大绝对值，单位 N·mm。
    require(parasitic_rotx_max <= PARASITIC_ROTX_LIMIT_RAD, f"U01寄生ROTX超限：{parasitic_rotx_max}")  # 纯横向质心荷载不得激发可见扭转转角。
    require(parasitic_mx_max <= PARASITIC_ROOT_MX_LIMIT_N_MM, f"U01寄生根部MX超限：{parasitic_mx_max}")  # 纯横向质心荷载不得激发可见扭矩。
    section_tests = [test for test in u01_status.get("tests", []) if isinstance(test, dict) and test.get("test_id") == "U01_03_SECTIONS"]  # 从八项状态中定位唯一截面门禁。
    require(len(section_tests) == 1 and section_tests[0].get("passed") is True, "U01截面门禁未唯一通过")  # 属性、解析、native 对照和寄生扭转必须共同 PASS。
    section_test = section_tests[0]  # 收窄唯一截面测试对象供逐字段核验。
    require(int(section_test.get("section_mapdl_warning_count", -1)) == 0, "U01 sections MAPDL 存在警告")  # 原生截面命令不得以警告降级执行。
    require(int(section_test.get("pair_count", -1)) == 12, "U01 native-vs-ASEC 对数不是12")  # 六类乘两方向必须恰为十二对。
    require(float(section_test.get("maximum_property_relative_error", 1.0)) < 1.0e-3, "U01截面属性误差超过0.1%")  # A、I 与冻结目标属性门禁必须通过。
    require(math.isclose(float(section_test.get("maximum_native_comparison_relative_error", -1.0)), native_shear_error_max, rel_tol=1.0e-9, abs_tol=1.0e-12), "U01状态与原始剪切挠度CSV最大值不闭合")  # 状态摘要不得脱离原始 CSV。
    require(math.isclose(float(section_test.get("maximum_native_total_deflection_relative_error", -1.0)), native_total_error_max, rel_tol=1.0e-9, abs_tol=1.0e-12), "U01状态与原始总挠度CSV最大值不闭合")  # 总挠度摘要也必须可复算。
    require(math.isclose(float(section_test.get("maximum_parasitic_rotx_rad", -1.0)), parasitic_rotx_max, rel_tol=1.0e-9, abs_tol=1.0e-18), "U01状态与原始ROTX CSV最大值不闭合")  # 寄生转角摘要必须可复算。
    require(math.isclose(float(section_test.get("maximum_parasitic_root_mx_n_mm", -1.0)), parasitic_mx_max, rel_tol=1.0e-9, abs_tol=1.0e-15), "U01状态与原始MX CSV最大值不闭合")  # 寄生扭矩摘要必须可复算。
    pair_results = section_test.get("pair_results")  # 读取 12 对具名明细供方向与物理轴验证。
    require(isinstance(pair_results, list) and len(pair_results) == 12, "U01 pair_results 不是12项")  # 状态必须保留每个截面和方向的明细。
    expected_pairs = {(section_index, direction) for section_index in expected_indices for direction in ("GLOBAL_Y", "GLOBAL_Z")}  # 构造六类乘两方向的唯一键集合。
    actual_pairs: set[tuple[int, str]] = set()  # 初始化实际逐对唯一键集合。
    for pair in pair_results:  # 逐一核对 12 对短梁方向、误差和轴映射。
        require(isinstance(pair, dict), "U01 pair_results 含非对象项")  # 每对明细必须是具名字段对象。
        section_index = int(pair.get("section_index", -1))  # 读取一基截面索引。
        direction = str(pair.get("direction", ""))  # 读取全局横向荷载方向标签。
        actual_pairs.add((section_index, direction))  # 保存实际唯一键供集合闭合。
        require(float(pair.get("total_deflection_relative_difference", 1.0)) < SECTION_PAIR_RELATIVE_LIMIT, f"U01逐对总挠度超限：{section_index}/{direction}")  # 每一对而非仅最大值都必须通过。
        require(float(pair.get("shear_deflection_relative_difference", 1.0)) < SECTION_PAIR_RELATIVE_LIMIT, f"U01逐对剪切挠度超限：{section_index}/{direction}")  # 每一对剪切差严格小于 0.5%。
        expected_mapping = "NATIVE_ROTATED_90_DEG_ABOUT_BEAM_X" if section_index == 1 else "NATIVE_AND_ASEC_K_PLUS_Z"  # H175 需要物理 90 度映射，其余原生与 ASEC 同向。
        require(pair.get("axis_mapping") == expected_mapping, f"U01逐对轴映射错误：{section_index}/{direction}")  # 方向映射不得由频率或误差反推。
        require(int(pair.get("asec_section_id", -1)) == 60 + section_index, f"U01 ASEC编号错误：{section_index}/{direction}")  # 生产 ASEC 必须固定为 61..66。
    require(actual_pairs == expected_pairs, f"U01逐对方向集合不闭合：{sorted(actual_pairs)}")  # 十二个唯一组合必须无漏项无重复。
    template_audit = validate_u01_asec_template_values()  # 直接解析模板并闭合 S10 六组剪切常量。
    artifact_closure = b00.verify_artifact_closure(U01_DIR)  # 复算 U01 除自引用账本外全部一百八十二项现场文件集合与逐文件哈希。
    return {"status": "PASSED", "pair_count": len(actual_pairs), "native_total_error_max": native_total_error_max, "native_shear_error_max": native_shear_error_max, "analytic_error_max": analytic_error_max, "parasitic_rotx_max_rad": parasitic_rotx_max, "parasitic_root_mx_max_n_mm": parasitic_mx_max, "properties_row_count": len(properties), "template_audit": template_audit, "raw_csv_sha256": {"properties": b00.sha256_file(U01_SECTION_PROPERTIES_PATH), "analytic_deflections": b00.sha256_file(U01_SECTION_DEFLECTIONS_PATH), "native_deflections": b00.sha256_file(U01_SECTION_NATIVE_DEFLECTIONS_PATH), "torsion_audit": b00.sha256_file(U01_SECTION_TORSION_AUDIT_PATH)}, "artifact_closure": {"passed": bool(artifact_closure["passed"]), "ledger_entry_count": int(artifact_closure["ledger_entry_count"]), "actual_file_count_excluding_ledger": int(artifact_closure["actual_file_count_excluding_ledger"])}}  # 返回逐对复算、固定哈希和完整 U01 产物闭合摘要供后续清单复用。


def validate_history_microqa() -> dict[str, Any]:  # 无输入并返回 LS1 全历程控制链小模型的闭合摘要。
    """固定 U02 版本、哈希、五子步计数和零警告错误，证明全桥前的结果集遍历语法已在 v261 执行。"""  # 函数说明给出验证范围和结论边界。
    require(b00.sha256_file(HISTORY_QA_MANIFEST_PATH) == HISTORY_QA_MANIFEST_SHA256, "U02 LS1历程清单哈希漂移")  # 固定小模型清单字节身份。
    require(b00.sha256_file(HISTORY_QA_STATUS_PATH) == HISTORY_QA_STATUS_SHA256, "U02 LS1历程状态哈希漂移")  # 固定唯一 PASSED 状态字节身份。
    manifest = read_json(HISTORY_QA_MANIFEST_PATH)  # 读取 U02 版本、计数、错误和结论边界。
    require(manifest.get("run_name") == HISTORY_QA_RUN_NAME and manifest.get("status") == "PASSED", "U02 LS1历程身份或状态错误")  # 目录、清单和状态必须一致。
    require(manifest.get("mapdl_version") == "ANSYS 2026 R1 / v261", "U02 MAPDL版本不是v261")  # 小模型必须与 S10 未来求解版本相同。
    require(int(manifest.get("return_code", -1)) == 0 and int(manifest.get("warning_count", -1)) == 0 and int(manifest.get("error_count", -1)) == 0, "U02存在返回码、WARNING或ERROR")  # 控制语法不得以警告或错误通过。
    require(int(manifest.get("static_result_set_count", -1)) == 6 and int(manifest.get("ls1_exported_history_count", -1)) == 5 and int(manifest.get("ls2_expected_substep_count", -1)) == 1, "U02结果集或历程计数不闭合")  # 五个 LS1 子步加一个 LS2 端点必须恰为六 SET。
    require(manifest.get("production_physics_claimed") is False and manifest.get("taskbook_threshold_applied_to_micro_model") is False, "U02结论边界字段错误")  # 小模型只证明控制链，不冒充全桥物理门禁。
    require(HISTORY_QA_STATUS_PATH.read_text(encoding="utf-8-sig").strip() == "STATUS=PASSED", "U02状态文本内容不是唯一PASSED")  # 状态文件不得混入其他阶段或拒绝原因。
    artifact_closure = b00.verify_artifact_closure(HISTORY_QA_DIR)  # 从磁盘复算 U02 除账本自身外全部产物集合和哈希。
    return {"status": "PASSED", "run_name": HISTORY_QA_RUN_NAME, "manifest_sha256": HISTORY_QA_MANIFEST_SHA256, "status_sha256": HISTORY_QA_STATUS_SHA256, "artifact_ledger_entry_count": artifact_closure["ledger_entry_count"], "actual_file_count_excluding_ledger": artifact_closure["actual_file_count_excluding_ledger"], "validated_capability": "OUTRES_VENG_ALL_SET_FIRST_NEXT_SENE_STEN_HISTORY_AND_PEAK"}  # 返回非物理控制链证据摘要。


def energy_block(tag: str, body: list[tuple[str, str]]) -> list[str]:  # 输入块标签和命令/说明对并返回带可剥离标记的 APDL 行。
    """每条命令使用独立中文前置注释；起止标记允许准备期证明输出增量非物理。"""  # 函数说明给出结构约束。
    lines = [f"{ENERGY_BEGIN} {tag}"]  # 写块起始标记和唯一标签。
    for command, explanation in body:  # 按执行顺序遍历命令与中文说明。
        b00.add_apdl(lines, command, explanation)  # 复用注释紧邻命令的生成规则。
    lines.append(f"{ENERGY_END} {tag}")  # 写匹配的块结束标记。
    return lines  # 返回完整 APDL 行列表。


def append_energy_reject(lines: list[str], parameter: str, operator: str, threshold: str, reason: str, close_csv: bool) -> None:  # 输入条件并追加 S10 专用 fail-closed 分支。
    """条件成立时可选关闭 CSV、写唯一拒绝状态并立即无保存退出。"""  # 函数说明给出异常执行路径。
    b00.add_apdl(lines, f"*IF,{parameter},{operator},{threshold},THEN", f"当 {parameter} {operator} {threshold} 时进入拒绝分支，原因 {reason}。")  # 生成比较条件。
    if close_csv:  # 只有已打开能量 CSV 的模态循环需要先关闭文件句柄。
        b00.add_apdl(lines, "*CFCLOS", "拒绝退出前关闭六组件 SENE CSV，确保已写记录落盘。")  # 刷新并关闭 CSV。
    b00.add_apdl(lines, "/OUTPUT,s10_gate_status,txt", "把 S10 唯一拒绝原因写入状态文件。")  # 打开状态输出。
    b00.add_apdl(lines, f"/COM,STATUS=REJECTED REASON={reason}", f"写机器可读固定原因 {reason}。")  # 写拒绝原因。
    b00.add_apdl(lines, "/OUTPUT", "恢复主输出，避免退出摘要滞留在状态文件。")  # 关闭状态重定向。
    b00.add_apdl(lines, "/EXIT,NOSAVE", "能量门禁失败时立即退出且不覆盖数据库。")  # 终止批处理。
    b00.add_apdl(lines, "*ENDIF", "结束当前 S10 能量拒绝分支。")  # 闭合条件结构。


def energy_output_request_block() -> list[str]:  # 无输入并返回模态求解前 VENG 恢复块。
    """在 OUTRES,NSOL,ALL 后、SOLVE 前恢复全部模态元素能量结果。"""  # 函数说明给出插入位置和目的。
    return energy_block("VENG_REQUEST", [("OUTRES,VENG,ALL", "为全部实际模态保存元素能量，供 ETABLE,SENE 六组件统计。")])  # 返回唯一 VENG 命令块。


def energy_setup_block() -> list[str]:  # 无输入并返回六组件数量门禁与 CSV 打开块。
    """先验证六组数量合计 17,679，再打开无标题纯数值 CSV。"""  # 函数说明给出前置门禁。
    lines = [f"{ENERGY_BEGIN} SETUP"]  # 写 setup 起始标记。
    b00.add_apdl(lines, "ALLSEL,ALL", "恢复全部实体，准备逐组件元素计数。")  # 初始化选择集。
    count_parameters: list[str] = []  # 保存六个计数参数名供合计。
    for section_id, component_name, expected_count in COMPONENTS:  # 逐截面组件建立数量门禁。
        parameter = f"S10_N{section_id}"  # 使用截面号形成唯一计数参数。
        count_parameters.append(parameter)  # 保存供合计表达式使用。
        b00.add_apdl(lines, f"CMSEL,S,{component_name}", f"选择 SEC{section_id} 对应组件 {component_name}。")  # 选择当前组件。
        b00.add_apdl(lines, f"*GET,{parameter},ELEM,0,COUNT", f"读取 {component_name} 元素数，预期 {expected_count} 根。")  # 获取数量。
        append_energy_reject(lines, parameter, "NE", str(expected_count), f"SECTION_{section_id}_COMPONENT_COUNT_MISMATCH", False)  # 数量不符时拒绝。
    b00.add_apdl(lines, "S10_NSUM=" + "+".join(count_parameters), "计算六组有限梁组件元素数总和，预期 17679。")  # 合计六组件数量。
    append_energy_reject(lines, "S10_NSUM", "NE", str(TARGET_BEAM_COUNT), "SECTION_COMPONENT_TOTAL_COUNT_MISMATCH", False)  # 总数不符时拒绝。
    b00.add_apdl(lines, "ALLSEL,ALL", "组件数量门禁通过后恢复全部模型。")  # 恢复全选。
    b00.add_apdl(lines, f"*CFOPEN,{ENERGY_FILE_STEM},csv", "打开 80 行无标题纯数值六组件 SENE CSV。")  # 打开能量文件。
    lines.append(f"{ENERGY_END} SETUP")  # 写 setup 结束标记。
    return lines  # 返回完整 setup 块。


def energy_mode_block(mode_index: int) -> list[str]:  # 输入一基模态阶次并返回该阶六组件能量计算块。
    """输出阶次、总SENE、六组SENE、六组比例和六组能量和/总量比例，共16列。"""  # 函数说明给出列结构和单位。
    suffix = f"{mode_index:04d}"  # 使用四位序号避免参数重名。
    lines = [f"{ENERGY_BEGIN} MODE_{suffix}"]  # 写当前阶块起始标记。
    b00.add_apdl(lines, "ALLSEL,ALL", f"第 {mode_index} 阶恢复全部元素选择。")  # 确保总能量覆盖全模型。
    b00.add_apdl(lines, "ETABLE,ERAS", f"第 {mode_index} 阶清空旧单元表定义。")  # 避免上一阶结果残留。
    b00.add_apdl(lines, "ETABLE,S10SENE,SENE", f"第 {mode_index} 阶建立单元总应变能列，单位 N·mm。")  # 建立 SENE 列。
    b00.add_apdl(lines, "SSUM", f"第 {mode_index} 阶对全模型 S10SENE 求和。")  # 求总能量。
    total_parameter = f"S10_T{suffix}"  # 定义当前阶总能量参数名。
    b00.add_apdl(lines, f"*GET,{total_parameter},SSUM,0,ITEM,S10SENE", f"读取第 {mode_index} 阶全模型总 SENE。")  # 获取总能量。
    append_energy_reject(lines, total_parameter, "LE", "0", f"MODE_{suffix}_TOTAL_SENE_NONPOSITIVE", True)  # 总能量必须严格为正。
    energy_parameters: list[str] = []  # 保存六组件能量参数。
    ratio_parameters: list[str] = []  # 保存六组件占比参数。
    for section_id, component_name, _expected_count in COMPONENTS:  # 按固定截面顺序统计六组件。
        energy_parameter = f"S10_E{section_id}_{suffix}"  # 定义当前组件能量参数名。
        ratio_parameter = f"S10_R{section_id}_{suffix}"  # 定义当前组件比例参数名。
        energy_parameters.append(energy_parameter)  # 保存供输出与合计。
        ratio_parameters.append(ratio_parameter)  # 保存供输出。
        b00.add_apdl(lines, f"CMSEL,S,{component_name}", f"第 {mode_index} 阶选择 {component_name}。")  # 选择当前组件。
        b00.add_apdl(lines, "SSUM", f"第 {mode_index} 阶对 {component_name} 的 S10SENE 求和。")  # 求组件能量。
        b00.add_apdl(lines, f"*GET,{energy_parameter},SSUM,0,ITEM,S10SENE", f"读取第 {mode_index} 阶 {component_name} SENE，单位 N·mm。")  # 获取组件能量。
        append_energy_reject(lines, energy_parameter, "LT", "0", f"MODE_{suffix}_SECTION_{section_id}_SENE_NEGATIVE", True)  # 组件能量不允许为负。
        b00.add_apdl(lines, f"{ratio_parameter}={energy_parameter}/{total_parameter}", f"计算第 {mode_index} 阶 {component_name} 占总 SENE 的无量纲比例。")  # 计算占比。
    sum_parameter = f"S10_ES_{suffix}"  # 定义六组件能量合计参数。
    sum_ratio_parameter = f"S10_RS_{suffix}"  # 定义六组件合计占总能量比例参数。
    b00.add_apdl(lines, f"{sum_parameter}=" + "+".join(energy_parameters), f"计算第 {mode_index} 阶六类有限梁组件 SENE 合计。")  # 合计六组件能量。
    b00.add_apdl(lines, f"{sum_ratio_parameter}={sum_parameter}/{total_parameter}", f"计算第 {mode_index} 阶六组件合计占全模型 SENE 比例。")  # 计算合计比例。
    output_parameters = [str(mode_index), total_parameter] + energy_parameters + ratio_parameters + [sum_parameter, sum_ratio_parameter]  # 固定16列顺序：2+6+6+2。
    b00.add_vwrite(lines, "*VWRITE," + ",".join(output_parameters), "(F8.0,15(',',E24.16))", f"写出第 {mode_index} 阶16列纯数值SENE记录；能量单位N·mm，比例无量纲。")  # 输出当前阶一行。
    b00.add_apdl(lines, "ALLSEL,ALL", f"第 {mode_index} 阶能量输出后恢复全部模型。")  # 避免组件选择污染节点导出。
    lines.append(f"{ENERGY_END} MODE_{suffix}")  # 写当前阶块结束标记。
    return lines  # 返回当前阶完整 APDL 块。


def energy_close_block() -> list[str]:  # 无输入并返回正常关闭 CSV 的块。
    """在第80阶完成后、最终 modal SAVE 前关闭文件句柄。"""  # 函数说明给出插入位置。
    return energy_block("CLOSE", [("*CFCLOS", "正常关闭六组件 SENE CSV 并刷新全部 80 行。")])  # 返回唯一关闭命令块。


def relabel_b00_main_as_s10(text: str) -> str:  # 输入 B00 控制模板并返回 S10 身份化文本。
    """机械替换大写/小写证据前缀；不改变数值、求解命令或依赖顺序。"""  # 函数说明给出非物理变换范围。
    return text.replace("B00", "S10").replace("b00", "s10")  # 同时改参数、标题和输出文件前缀。


def augment_main_with_energy(base_text: str) -> tuple[str, dict[str, Any]]:  # 输入 S10 身份化主输入并返回能量增强文本和审计。
    """插入VENG、六组件setup、80阶能量块和close；剥离后必须逐字等于基线。"""  # 函数说明给出唯一非物理增量。
    require(base_text.endswith("\n"), "B00 控制模板未以 LF 结尾")  # 保留生成器文本契约。
    lines = base_text.splitlines()  # 按 LF 拆分且不保留行尾。
    all_none_indices = [index for index, line in enumerate(lines) if line == "OUTRES,ALL,NONE"]  # 查找唯一结果关闭锚点。
    require(len(all_none_indices) == 1, "S10 基线 OUTRES,ALL,NONE 数量不是1")  # VENG 插入锚点必须唯一。
    all_none_index = all_none_indices[0]  # 取得零基锚点。
    require(lines[all_none_index + 2] == "OUTRES,NSOL,ALL", "ALL,NONE 后未按模板恢复 NSOL")  # 验证注释/命令结构。
    veng_index = all_none_index + 3  # VENG 块插在 NSOL 后、SOLVE 前。
    lines[veng_index:veng_index] = energy_output_request_block()  # 插入元素能量输出请求。
    gopr_indices = [index for index, line in enumerate(lines) if line == "/GOPR"]  # 查找属性 CSV 后唯一回显恢复点。
    require(len(gopr_indices) == 1, "S10 基线 /GOPR 数量不是1")  # setup 锚点必须唯一。
    setup_index = gopr_indices[0] + 1  # 在 /GOPR 后、节点循环前插入 setup。
    setup = energy_setup_block()  # 生成六组件数量门禁与 CSV 打开块。
    lines[setup_index:setup_index] = setup  # 插入 setup。
    search_start = setup_index + len(setup)  # 下阶 SET 查找从 setup 后开始。
    inserted_modes: list[int] = []  # 记录成功注入的阶次。
    for mode_index in range(1, REQUESTED_MODES + 1):  # 严格遍历 1..80。
        set_command = f"SET,1,{mode_index}"  # 当前阶节点导出的唯一结果集激活命令。
        matches = [index for index in range(search_start, len(lines)) if lines[index] == set_command]  # 在剩余文本查找唯一 SET。
        require(len(matches) == 1, f"第{mode_index}阶 SET 锚点数量不是1")  # 防止漏阶或重复注入。
        set_index = matches[0]  # 取得 SET 行索引。
        require(lines[set_index + 2] == "ALLSEL,ALL", f"第{mode_index}阶 SET 后结构漂移")  # 模板每条命令前一行注释，ALLSEL 应位于+2。
        insertion_index = set_index + 3  # 在当前阶 ALLSEL 后插入能量块。
        block = energy_mode_block(mode_index)  # 生成当前阶16列能量逻辑。
        lines[insertion_index:insertion_index] = block  # 插入块。
        inserted_modes.append(mode_index)  # 记录阶次。
        search_start = insertion_index + len(block)  # 下次从当前块后继续查找。
    save_indices = [index for index, line in enumerate(lines) if line.startswith("SAVE,") and line.endswith("_modal,db")]  # 查找唯一模态数据库保存命令。
    require(len(save_indices) == 1, "S10 modal SAVE 数量不是1")  # close 块必须锚定唯一保存点。
    final_allsel = [index for index in range(search_start, save_indices[0]) if lines[index] == "ALLSEL,ALL"]  # 查找第80阶后最终全选命令。
    require(len(final_allsel) == 1, "第80阶后最终 ALLSEL 数量不是1")  # 关闭位置必须唯一。
    close_index = final_allsel[0] - 1  # 在最终 ALLSEL 中文说明前插入 close 块。
    lines[close_index:close_index] = energy_close_block()  # 插入正常关闭 CSV 块。
    augmented_text = "\n".join(lines) + "\n"  # 按模板 LF 约定重组完整文本。
    stripped_lines: list[str] = []  # 累积剥离标记块后的基线行。
    inside_block = False  # 标记当前是否位于 S10 能量块内。
    block_count = 0  # 统计 VENG、setup、80阶和close共83块。
    for line in augmented_text.splitlines():  # 按最终顺序逐行剥离。
        if line.startswith(ENERGY_BEGIN):  # 起始标记进入跳过状态。
            require(not inside_block, "S10 能量块发生嵌套")  # 禁止嵌套。
            inside_block = True  # 开始跳过当前块。
            block_count += 1  # 累计一个块。
            continue  # 起始标记不进入基线。
        if line.startswith(ENERGY_END):  # 结束标记退出跳过状态。
            require(inside_block, "S10 能量结束标记孤立")  # 必须有对应起始标记。
            inside_block = False  # 结束当前块。
            continue  # 结束标记不进入基线。
        if not inside_block:  # 只保留注入块外行。
            stripped_lines.append(line)  # 按原顺序保存基线行。
    require(not inside_block, "S10 能量块文件末尾未闭合")  # 全部块必须闭合。
    stripped_text = "\n".join(stripped_lines) + "\n"  # 重建剥离后的主输入。
    require(stripped_text == base_text, "剥离能量块后不等于 S10 控制基线")  # 证明能量逻辑只是非物理输出增量。
    require(inserted_modes == list(range(1, REQUESTED_MODES + 1)), "S10 能量阶次不是连续1..80")  # 80阶无遗漏无重复。
    require(block_count == REQUESTED_MODES + 3, f"S10 能量块数量不是83：{block_count}")  # 数量闭合。
    require("MXPAND,80,,,YES" in augmented_text, "S10 未保留 MXPAND Elcalc=YES")  # SENE 可用性前提。
    require("MODOPT,LANB,80\n" in augmented_text and "MODOPT,LANB,80," not in augmented_text, "S10 未使用无频带80阶LANB")  # 禁止固定频带截断。
    all_none_position = augmented_text.rfind("OUTRES,ALL,NONE")  # 定位最终 ALL,NONE。
    nsol_position = augmented_text.find("OUTRES,NSOL,ALL", all_none_position)  # 定位其后 NSOL。
    veng_position = augmented_text.find("OUTRES,VENG,ALL", all_none_position)  # 定位其后 VENG。
    solve_position = augmented_text.find("SOLVE", veng_position)  # 定位其后模态 SOLVE。
    require(all_none_position < nsol_position < veng_position < solve_position, "S10 OUTRES顺序不闭合")  # 节点与能量结果必须在求解前恢复。
    audit = {"schema_version": 1, "status": "PASSED", "physical_change": False, "requested_modes": REQUESTED_MODES, "energy_block_count": block_count, "energy_exported_modes": inserted_modes, "components": [{"section_id": section_id, "component": component, "expected_count": count} for section_id, component, count in COMPONENTS], "component_total_expected": TARGET_BEAM_COUNT, "csv_columns": ["mode_index", "total_sene_n_mm"] + [f"sec{section_id}_sene_n_mm" for section_id, _component, _count in COMPONENTS] + [f"sec{section_id}_sene_ratio" for section_id, _component, _count in COMPONENTS] + ["six_components_sene_sum_n_mm", "six_components_sene_sum_ratio"], "output": f"solver/{ENERGY_FILE_STEM}.csv", "stripped_equals_base": True, "base_main_sha256": sha256_text(base_text), "stripped_main_sha256": sha256_text(stripped_text), "final_main_sha256": sha256_text(augmented_text)}  # 汇总输出结构和剥离证明。
    return augmented_text, audit  # 返回增强主输入和非物理输出审计。


def validate_parents() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:  # 无输入并返回 A10/A30/U01 清单、截面复算、历程微测和 A30 产物闭合摘要。
    """固定父身份、A20零差异、A30等价、U01截面和U02历程控制链；任何哈希漂移均拒绝。"""  # 函数说明给出完整 fail-closed 前置范围。
    require(b00.sha256_file(Path(b00.__file__).resolve()) == B00_TEMPLATE_SHA256, "当前 B00 控制模板哈希漂移")  # 绑定 A10 已采用的控制生成器版本。
    require(b00.sha256_file(U01_STATUS_PATH) == U01_STATUS_SHA256, "U01 状态文件哈希漂移")  # 固定 8/8 状态字节。
    require(b00.sha256_file(U01_SECTION_TEMPLATE_PATH) == U01_SECTION_TEMPLATE_SHA256, "U01 截面模板哈希漂移")  # 固定生产剪切值来源。
    require(b00.sha256_file(A30_DIR / "manifest.json") == A30_MANIFEST_SHA256, "A30 等价清单哈希漂移")  # 固定父包证据。
    a30_artifact_closure_raw = b00.verify_artifact_closure(A30_DIR)  # 复算最终 A30 除账本自身外九项文件集合和逐文件 SHA-256。
    a30_artifact_closure = {"status": "PASSED", "passed": bool(a30_artifact_closure_raw["passed"]), "ledger_entry_count": int(a30_artifact_closure_raw["ledger_entry_count"]), "actual_file_count_excluding_ledger": int(a30_artifact_closure_raw["actual_file_count_excluding_ledger"])}  # 压缩 A30 闭合结果，避免把逐文件明细重复写入 S10 清单。
    a10_manifest = read_json(A10_DIR / "manifest.json")  # 读取实际执行输入的准备清单。
    a20_status = read_json(A20_DIR / "A20_status.json")  # 读取 RHS 零差异状态。
    a30_manifest = read_json(A30_DIR / "manifest.json")  # 读取 A30=A10 等价证明。
    u01_manifest = read_json(U01_MANIFEST_PATH)  # 读取已固定哈希的 U01 版本和八案例总清单。
    u01_status = read_json(U01_STATUS_PATH)  # 读取 U01 八项结果。
    require(a20_status.get("status") == "COMPLETED_NO_SOLVE_ALREADY_CORRECT" and int(a20_status.get("physical_change_required_count", -1)) == 0, "A20 不是零差异完成状态")  # RHS 必须已正确。
    require(a30_manifest.get("status") == "COMPLETED_BY_INPUT_IDENTITY_WITH_A10_RESULTS", "A30 不是输入/结果等价完成状态")  # S10 只从已封板轴基线派生。
    require(u01_manifest.get("status") == "PASSED" and u01_manifest.get("mapdl_version") == "2026 R1 / v261", "U01 清单不是 v261 正式通过状态")  # 剪切源证必须来自未来 S10 同版本 MAPDL。
    require(u01_status.get("status") == "PASSED" and int(u01_status.get("passed_count", -1)) == 8, "U01 不是8/8通过")  # 所有小算例必须通过。
    section_tests = [test for test in u01_status.get("tests", []) if test.get("test_id") == "U01_03_SECTIONS"]  # 定位唯一截面门禁。
    require(len(section_tests) == 1 and section_tests[0].get("passed") is True, "U01截面门禁未通过")  # 属性、剪切、挠度必须同时PASS。
    require(float(section_tests[0].get("maximum_shear_mapping_relative_error", 1.0)) < 0.005, "U01剪切映射误差超过0.5%")  # 应用任务书门槛。
    u01_section_evidence = validate_u01_section_evidence(u01_status)  # 真正执行四份原始 CSV、十二对响应、模板字段和 U01 全产物闭合门禁。
    history_microqa_evidence = validate_history_microqa()  # 真正执行 U02 五个 LS1 子步遍历语法、固定哈希和全产物闭合门禁。
    return a10_manifest, a30_manifest, u01_status, u01_section_evidence, history_microqa_evidence, a30_artifact_closure  # 返回全部父对象和可写入准备包的 fail-closed 复算摘要。


def validate_run_name(value: str) -> str:  # 输入可选运行名并返回已验证原值。
    """只接受 S10_SECTION_SHEAR_YYYYMMDDTHHMMSSffffffZ，拒绝路径字符。"""  # 函数说明给出格式边界。
    if RUN_NAME_PATTERN.fullmatch(value) is None:  # 非法格式进入 argparse 错误路径。
        raise argparse.ArgumentTypeError("run name must match S10_SECTION_SHEAR_YYYYMMDDTHHMMSSffffffZ")  # 返回预期格式。
    return value  # 合法值原样返回。


def prepare_run(optional_run_name: str | None, user_override_memory_gate: bool) -> Path:  # 输入可选运行名和内存覆盖事实并返回新 S10 目录。
    """完成只读父验证、六行内存改写、双副本和审计封板；无论资源状态都不启动 MAPDL。"""  # 函数说明给出副作用边界。
    a10_manifest, a30_manifest, u01_status, u01_section_evidence, history_microqa_evidence, a30_artifact_closure = validate_parents()  # 固定最终 A30、U01 原始截面证据、U02 历程控制链和全部产物闭合事实。
    dependencies_value = a10_manifest.get("dependencies")  # 读取 A10 的11项实际输入清单。
    require(isinstance(dependencies_value, list) and len(dependencies_value) == DEPENDENCY_COUNT, "A10依赖不是11项")  # 固定依赖规模。
    dependencies: list[dict[str, Any]] = dependencies_value  # 类型门禁后收窄为有序列表。
    require([int(item["order"]) for item in dependencies] == list(range(1, DEPENDENCY_COUNT + 1)), "A10依赖order不是1..11")  # 固定装配顺序。
    basenames = [str(item["basename"]) for item in dependencies]  # 提取稳定文件名列表。
    require(len(set(basenames)) == DEPENDENCY_COUNT and basenames.count(AXIS_INCLUDE_NAME) == 1, "A10依赖文件名不唯一或目标include数量错误")  # 唯一受控文件必须恰好一个。
    source_include_path = A10_DIR / "input_snapshot" / AXIS_INCLUDE_NAME  # S10唯一物理源固定为A10输入快照。
    require(b00.sha256_file(source_include_path) == A10_INCLUDE_SHA256, "A10轴基线include哈希漂移")  # 固定68d9dc身份。
    source_text = source_include_path.read_bytes().decode("utf-8")  # 以原始字节解码并保留CRLF。
    modified_text, section_rows, section_summary = transform_section_shear(source_text)  # 在内存中只改六条SECDATA。
    modified_hash = sha256_text(modified_text)  # 计算新include摘要。
    require(modified_hash != A10_INCLUDE_SHA256, "S10 include未产生剪切字段差异")  # S10必须有真实受控差异。
    created_at = datetime.now(timezone.utc)  # 取得唯一UTC时间。
    run_name = optional_run_name or f"{RUN_PREFIX}_{created_at.strftime('%Y%m%dT%H%M%S%f')}Z"  # 生成含微秒的运行名。
    require(RUN_NAME_PATTERN.fullmatch(run_name) is not None, f"S10运行名非法：{run_name}")  # 防止路径逃逸。
    run_dir = ULTRA_RUNS_DIR / run_name  # 构造正式新目录。
    require(not run_dir.exists(), f"拒绝覆盖既有S10 run：{run_dir}")  # 新目录必须不存在。
    jobname = f"cw_S10_{created_at.strftime('%m%d')}t{created_at.strftime('%H%M%S')}_{secrets.token_hex(1)}"  # 生成ASCII唯一jobname。
    require(JOBNAME_PATTERN.fullmatch(jobname) is not None and len(jobname) <= 32, f"S10 jobname非法：{jobname}")  # 落实MAPDL命名限制。
    base_b00_main = b00.build_main_input(jobname, REQUESTED_MODES, dependencies)  # 用A10已审计模板构造从头静力—保持—模态控制。
    base_s10_main = relabel_b00_main_as_s10(base_b00_main)  # 只改证据身份为S10。
    final_main_text, energy_audit = augment_main_with_energy(base_s10_main)  # 增加六组件80阶SENE输出。
    main_hash = sha256_text(final_main_text)  # 计算最终主输入摘要。
    memory = b00.memory_snapshot()  # 只读记录当前物理内存快照。
    disk = b00.disk_snapshot()  # 只读记录D盘可用空间。
    disk_ready = bool(disk.get("disk_ready"))  # 磁盘32GiB门禁不能被内存覆盖替代。
    memory_ready = bool(memory.get("memory_ready"))  # 记录8GiB实测内存门禁。
    launch_policy_satisfied = disk_ready and (memory_ready or user_override_memory_gate)  # 用户覆盖只替代内存门禁。
    status_value = "PREPARED_NOT_STARTED_USER_MEMORY_OVERRIDE" if user_override_memory_gate and disk_ready else ("PREPARED_NOT_STARTED" if memory_ready and disk_ready else "PREPARED_WAITING_RESOURCE_GATE")  # 准备状态不冒充READY/RUNNING。
    input_snapshot_dir = run_dir / "input_snapshot"  # 第一套不可执行输入快照目录。
    solver_dir = run_dir / "solver"  # 未来唯一MAPDL工作目录和第二套输入副本。
    qa_dir = run_dir / "qa"  # 单差异、哈希和预检证据目录。
    lineage_dir = run_dir / "lineage"  # 父清单与模板源码快照目录。
    orchestrator_dir = run_dir / "orchestrator_snapshot"  # 实际S10编排器源码快照目录。
    run_dir.mkdir(parents=True, exist_ok=False)  # 全部内存门禁通过后首次创建唯一新run。
    input_hash_rows: list[dict[str, Any]] = []  # 保存十一项A10/S10双副本哈希闭合记录。
    source_entries: list[tuple[str, str]] = []  # 保存源证和生成输入身份账本项。
    for dependency in dependencies:  # 按order1..11复制并审计全部父输入。
        order = int(dependency["order"])  # 读取装配顺序。
        basename = str(dependency["basename"])  # 读取include文件名。
        parent_snapshot = A10_DIR / "input_snapshot" / basename  # 第一父源固定为A10输入快照。
        parent_solver = A10_DIR / "solver" / basename  # 第二父源证明实际求解使用相同字节。
        require(parent_snapshot.is_file() and parent_solver.is_file(), f"A10依赖双副本缺失：{basename}")  # 两份必须存在。
        parent_snapshot_hash = b00.sha256_file(parent_snapshot)  # 复算父快照摘要。
        parent_solver_hash = b00.sha256_file(parent_solver)  # 复算实际求解副本摘要。
        require(parent_snapshot_hash == parent_solver_hash == str(dependency["a10_input_snapshot_sha256"]) == str(dependency["a10_solver_sha256"]), f"A10依赖哈希不闭合：{basename}")  # 四向闭合。
        snapshot_destination = input_snapshot_dir / basename  # 定义S10第一目标副本。
        solver_destination = solver_dir / basename  # 定义S10第二目标副本。
        if basename == AXIS_INCLUDE_NAME:  # 唯一物理变化文件进入受控写入路径。
            write_new_text(snapshot_destination, modified_text)  # 写S10新快照。
            write_new_text(solver_destination, modified_text)  # 写逐字相同的求解副本。
            snapshot_hash = b00.sha256_file(snapshot_destination)  # 从磁盘复算第一副本。
            solver_hash = b00.sha256_file(solver_destination)  # 从磁盘复算第二副本。
            require(snapshot_hash == solver_hash == modified_hash, "S10受控include双副本哈希不闭合")  # 两份必须等于内存摘要。
            role = "controlled_section_shear_change"  # 标记唯一物理差异家族所在依赖。
        else:  # 其余十项必须逐字复制A10。
            snapshot_hash = copy_new_verified(parent_snapshot, snapshot_destination)  # 复制第一副本。
            solver_hash = copy_new_verified(parent_solver, solver_destination)  # 复制第二副本。
            require(snapshot_hash == solver_hash == parent_snapshot_hash, f"S10 invariant复制漂移：{basename}")  # 继承字节身份。
            role = "invariant"  # 标记不变量角色。
        input_hash_rows.append({"order": order, "basename": basename, "role": role, "a10_parent_sha256": parent_snapshot_hash, "s10_input_snapshot_sha256": snapshot_hash, "s10_solver_sha256": solver_hash, "passed": snapshot_hash == solver_hash})  # 保存双副本证据。
        source_entries.append((parent_snapshot_hash, str(parent_snapshot)))  # 记录父源身份。
        source_entries.append((snapshot_hash, f"input_snapshot/{basename}"))  # 记录S10快照身份。
        source_entries.append((solver_hash, f"solver/{basename}"))  # 记录S10求解副本身份。
    main_snapshot_path = input_snapshot_dir / MAIN_INPUT_NAME  # 定义主输入第一副本。
    main_solver_path = solver_dir / MAIN_INPUT_NAME  # 定义实际工作目录主输入。
    write_new_text(main_snapshot_path, final_main_text)  # 写主输入快照。
    write_new_text(main_solver_path, final_main_text)  # 写逐字相同的solver主输入。
    require(b00.sha256_file(main_snapshot_path) == b00.sha256_file(main_solver_path) == main_hash, "S10主输入双副本哈希不闭合")  # 主输入身份闭合。
    source_entries.extend([(main_hash, f"input_snapshot/{MAIN_INPUT_NAME}"), (main_hash, f"solver/{MAIN_INPUT_NAME}")])  # 把主输入双副本加入源账本。
    copy_new_verified(SCRIPT_PATH, orchestrator_dir / SCRIPT_PATH.name)  # 快照实际S10编排器。
    copy_new_verified(Path(b00.__file__).resolve(), lineage_dir / "ultra_b00_prepare.py")  # 快照所用控制模板源码。
    copy_new_verified(A30_DIR / "manifest.json", lineage_dir / "a30_manifest.json")  # 快照A30等价父清单。
    copy_new_verified(A30_DIR / "A30_status.json", lineage_dir / "a30_status.json")  # 快照最终 A30 根状态与下一步 S10 身份。
    copy_new_verified(A30_DIR / "artifact_hashes.sha256", lineage_dir / "a30_artifact_hashes.sha256")  # 快照已复算通过的 A30 九项产物账本。
    copy_new_verified(A20_DIR / "A20_status.json", lineage_dir / "a20_status.json")  # 快照A20零差异状态。
    copy_new_verified(U01_STATUS_PATH, lineage_dir / "u01_status.json")  # 快照U01总状态。
    copy_new_verified(U01_MANIFEST_PATH, lineage_dir / "u01_manifest.json")  # 快照 U01 v261 八案例正式清单。
    copy_new_verified(U01_SECTION_TEMPLATE_PATH, lineage_dir / "u01_sections.inp")  # 快照六类剪切直接源证。
    copy_new_verified(U01_SECTION_PROPERTIES_PATH, lineage_dir / "u01_section_properties.csv")  # 快照六类原生与 ASEC 属性原始数值。
    copy_new_verified(U01_SECTION_DEFLECTIONS_PATH, lineage_dir / "u01_section_deflections.csv")  # 快照六类 ASEC 双向解析挠度原始数值。
    copy_new_verified(U01_SECTION_NATIVE_DEFLECTIONS_PATH, lineage_dir / "u01_section_native_deflections.csv")  # 快照六类乘两方向 native-vs-ASEC 直接对照原始数值。
    copy_new_verified(U01_SECTION_TORSION_AUDIT_PATH, lineage_dir / "u01_section_torsion_audit.csv")  # 快照十二对寄生 ROTX 与根部 MX 原始数值。
    copy_new_verified(U01_DIR / "artifact_hashes.sha256", lineage_dir / "u01_artifact_hashes.sha256")  # 快照已复算通过的一百八十二项 U01 产物账本。
    copy_new_verified(HISTORY_QA_MANIFEST_PATH, lineage_dir / "u02_history_manifest.json")  # 快照 U02 六 SET 与五个 LS1 子步控制链清单。
    copy_new_verified(HISTORY_QA_STATUS_PATH, lineage_dir / "u02_history_status.txt")  # 快照 U02 唯一 STATUS=PASSED 状态。
    copy_new_verified(HISTORY_QA_DIR / "artifact_hashes.sha256", lineage_dir / "u02_artifact_hashes.sha256")  # 快照已复算通过的 U02 十九项产物账本。
    launch_text, launch_argv = b00.build_launch_command(jobname, solver_dir, main_solver_path)  # 只生成未来DMP4命令文本和参数数组。
    launch_text = launch_text.replace("B00", "S10").replace("b00", "s10")  # 把说明身份机械改为S10，不改变可执行参数。
    write_new_text(run_dir / "launch_command.txt", launch_text)  # 写明确NOT_EXECUTED的命令证据。
    write_new_text(qa_dir / "section_shear_changes.csv", rows_to_csv(section_rows))  # 写六条旧→新字段台账。
    write_new_text(qa_dir / "input_hash_audit.csv", rows_to_csv(input_hash_rows))  # 写十一项父/新双副本哈希台账。
    model_single_difference = {"schema_version": 1, "status": "PASSED", "parent_effective_model": A30_RUN_NAME, "parent_executed_input_source": A10_RUN_NAME, **section_summary, "forbidden_changes": {"area": False, "iyy_iyz_izz": False, "warping_constant": False, "torsion_constant_j": False, "material": False, "density": False, "beam_orientation_nodes": False, "mesh_topology": False, "mass": False, "loads_and_initial_state": False, "cerig_or_cp": False, "keyopt": False}, "invariant_dependency_count": sum(1 for row in input_hash_rows if row["role"] == "invariant"), "controlled_dependency_count": sum(1 for row in input_hash_rows if row["role"] == "controlled_section_shear_change")}  # 构造唯一物理变化合同。
    write_new_json(qa_dir / "model_single_difference_audit.json", model_single_difference)  # 写单差异机器证明。
    write_new_json(qa_dir / "main_control_flow_audit.json", energy_audit)  # 写从头求解与能量输出审计。
    preflight = {"schema_version": 1, "status": "PASSED_PREPARE_ONLY", "run_name": run_name, "jobname": jobname, "parent_a30_status": a30_manifest.get("status"), "a30_artifact_closure": a30_artifact_closure, "u01_status": u01_status.get("status"), "u01_section_evidence": u01_section_evidence, "history_microqa_evidence": history_microqa_evidence, "section_change_count": len(section_rows), "input_dependency_count": len(input_hash_rows), "input_double_copy_all_match": all(bool(row["passed"]) for row in input_hash_rows), "memory_snapshot": memory, "disk_snapshot": disk, "user_memory_gate_override": user_override_memory_gate, "launch_policy_satisfied": launch_policy_satisfied, "mapdl_execution_attempted": False, "mapdl_started": False}  # 汇总父包闭合、截面复算、历程控制链、单变量和资源准备门禁。
    write_new_json(qa_dir / "preflight.json", preflight)  # 写预检证据。
    status_payload = {"schema_version": 1, "run_id": RUN_ID, "run_name": run_name, "jobname": jobname, "status": status_value, "created_at_utc": created_at.isoformat(), "parent_run": A30_RUN_NAME, "effective_input_parent": A10_RUN_NAME, "prepare_gate_passed": True, "physical_change_family": section_summary["physical_change_family"], "changed_section_count": TARGET_SECTION_COUNT, "modes_requested": REQUESTED_MODES, "mapdl_started": False, "execution_attempted": False, "memory_gate_overridden_by_user": user_override_memory_gate, "disk_ready": disk_ready, "launch_policy_satisfied": launch_policy_satisfied, "next_action": "INDEPENDENT_AUDIT_THEN_EXPLICIT_DMP4_LAUNCH"}  # 写准确的准备状态。
    write_new_json(run_dir / "S10_status.json", status_payload)  # 写根级状态文件。
    manifest = {"schema_version": 1, "run_id": RUN_ID, "run_name": run_name, "model_line": MODEL_LINE, "status": status_value, "created_at_utc": created_at.isoformat(), "parent_a30": A30_RUN_NAME, "parent_a20": A20_RUN_NAME, "effective_input_parent_a10": A10_RUN_NAME, "u01_source": U01_RUN_NAME, "u02_history_source": HISTORY_QA_RUN_NAME, "a30_artifact_closure": a30_artifact_closure, "u01_section_evidence": u01_section_evidence, "history_microqa_evidence": history_microqa_evidence, "jobname": jobname, "main_input": f"solver/{MAIN_INPUT_NAME}", "main_input_sha256": main_hash, "modes_requested": REQUESTED_MODES, "frequency_bounds_hz": None, "from_scratch_static": True, "ls1_time": 1.0, "ls2_time": 1.001, "modal_restart": "ANTYPE,,RESTART,2,,PERTURB", "modal_solver": "LANB", "mxpand_element_calculation": True, "physical_change_contract": model_single_difference, "energy_export": energy_audit, "dependencies": input_hash_rows, "resources": {"memory": memory, "disk": disk, "user_memory_gate_override": user_override_memory_gate, "launch_policy_satisfied": launch_policy_satisfied}, "prepare_only": True, "mapdl_execution_attempted": False, "mapdl_started": False, "future_launch_argv": launch_argv, "outputs": ["S10_status.json", "manifest.json", "result_packet.md", "launch_command.txt", "source_hashes.sha256", "artifact_hashes.sha256", "input_snapshot/", "solver/", "qa/", "lineage/", "orchestrator_snapshot/"]}  # 汇总含最终 A30、U01/U02 原始源证闭合的 S10 完整准备清单。
    write_new_json(run_dir / "manifest.json", manifest)  # 写根级manifest。
    field_dictionary = """# S10 字段字典

JSON 和 CSV 语法本身不支持注释，因此字段、单位与状态含义集中说明如下。

- `physical_change_family=ASEC_TRANSVERSE_SHEAR_FACTORS_FOR_SECTIONS_61_TO_66`：唯一物理变化是六条 SECDATA 追加字段7至14。
- `CGy/CGz/SHy/SHz=0`：六类对称截面的质心与剪切中心偏置为零，单位 mm。
- `TKz/TKy`：ASEC 外包络在 local-z/local-y 的尺寸，单位 mm；用于方向与截面映射审计。
- `TSxz/TSxy`：U01 在 MAPDL 2026 R1 中读取并由短梁挠度验证的无量纲剪切修正因子。
- `frozen_first_six_fields_identical=true`：A、Iyy、Iyz、Izz、Iw、J 的原数值字符串逐字保持。
- `status=PREPARED_*`：只表示输入封板，绝不表示 MAPDL 已启动或结果通过。
- `s10_section_modal_sene.csv`：每行16列，依次为阶次、全模型SENE、SEC61..66六组SENE、六组占比、六组能量和、六组能量和占比；能量单位N·mm，比例无量纲。
- `artifact_hashes.sha256`：最后生成且排除自身，之后不得修改本准备包。
"""  # 解释不可注释机器文件的字段、单位、固定值和状态。
    write_new_text(qa_dir / "field_dictionary.md", field_dictionary)  # 写配套字段说明。
    result_packet = f"""# S10 截面剪切单变量准备结果

- run：{run_name}
- jobname：{jobname}
- 状态：{status_value}
- 父基线：A30 等价于已求解 A10；A20 的 2,898 根 RHS 为零差异。
- 源证：U01 六类乘两方向十二对原始 CSV 已复算，U02 LS1 全历程结果集遍历已在 v261 小模型闭合。
- 唯一物理变化：SEC61..66 六条 ASEC 保持前六项不变，仅补零偏置、TKz/TKy 和 U01-v261 双向剪切因子。
- 受影响有限梁：17,679 根；TYPE、材料、质量、轴、拓扑、5,078 条 CERIG、荷载与索力均不变。
- 主流程：从头 LS1→LS2 保持→80阶无频带 LANB，MXPAND Elcalc=YES，NSOL+VENG。
- 未来输出：80阶全节点位移/转角、模态属性和六组件 SENE 16列 CSV。
- MAPDL：未启动；本编排器没有执行进程API。
- 资源：可用物理内存 {memory.get('available_physical_bytes')} byte；D盘可用 {disk.get('free_bytes')} byte；启动策略={launch_policy_satisfied}。
"""  # 概括单变量、流程、输出和准备边界。
    write_new_text(run_dir / "result_packet.md", result_packet)  # 写人类可读准备结果。
    source_entries.extend([(b00.sha256_file(SCRIPT_PATH), str(SCRIPT_PATH)), (B00_TEMPLATE_SHA256, str(Path(b00.__file__).resolve())), (A30_MANIFEST_SHA256, str(A30_DIR / "manifest.json")), (U01_STATUS_SHA256, str(U01_STATUS_PATH)), (U01_MANIFEST_SHA256, str(U01_MANIFEST_PATH)), (U01_SECTION_TEMPLATE_SHA256, str(U01_SECTION_TEMPLATE_PATH)), (U01_SECTION_PROPERTIES_SHA256, str(U01_SECTION_PROPERTIES_PATH)), (U01_SECTION_DEFLECTIONS_SHA256, str(U01_SECTION_DEFLECTIONS_PATH)), (U01_SECTION_NATIVE_DEFLECTIONS_SHA256, str(U01_SECTION_NATIVE_DEFLECTIONS_PATH)), (U01_SECTION_TORSION_AUDIT_SHA256, str(U01_SECTION_TORSION_AUDIT_PATH)), (HISTORY_QA_MANIFEST_SHA256, str(HISTORY_QA_MANIFEST_PATH)), (HISTORY_QA_STATUS_SHA256, str(HISTORY_QA_STATUS_PATH))])  # 加入编排器、模板、最终 A30、U01 四份原始 CSV 和 U02 历程控制链全部固定身份。
    source_text_ledger = "".join(f"{digest}  {label}\n" for digest, label in source_entries)  # 按追加顺序生成源哈希账本。
    write_new_text(run_dir / "source_hashes.sha256", source_text_ledger)  # 写源与双副本清单。
    b00.write_artifact_ledger(run_dir)  # 最后枚举并哈希除账本自身外全部准备产物。
    return run_dir  # 返回已封板但未执行的S10目录。


def parse_arguments() -> argparse.Namespace:  # 无输入并返回受约束命令行参数对象。
    """只接受可选运行名和显式内存覆盖；不接受任何剪切数值调参。"""  # 函数说明给出接口边界。
    parser = argparse.ArgumentParser(description="Prepare and audit S10 section-shear-only full-bridge input; never starts MAPDL.")  # 创建prepare-only命令行接口。
    parser.add_argument("--run-name", type=validate_run_name, default=None, help="Optional exact S10_SECTION_SHEAR_<UTC-microseconds>Z directory name.")  # 支持确定性测试目录。
    parser.add_argument("--user-override-memory-gate", action="store_true", help="Record the user's existing memory-gate override; never starts MAPDL.")  # 只记录用户先前授权，不触发执行。
    return parser.parse_args()  # 解析并拒绝未知参数。


def main() -> int:  # 无输入并返回进程退出码，0表示准备包封板完成。
    """执行S10 prepare-only主流程并输出唯一目录；不启动、排队或监控求解器。"""  # 函数说明再次明确执行禁令。
    arguments = parse_arguments()  # 读取受约束参数。
    run_dir = prepare_run(arguments.run_name, bool(arguments.user_override_memory_gate))  # 完成准备与审计封板。
    print(json.dumps({"run_dir": str(run_dir), "status": "PREPARED_NOT_STARTED", "mapdl_started": False}, ensure_ascii=False))  # 向调用者输出机器摘要。
    return 0  # 成功准备时返回0。


if __name__ == "__main__":  # 只有直接执行时才运行入口，导入时无副作用。
    raise SystemExit(main())  # 把main返回值传递为进程退出码。
