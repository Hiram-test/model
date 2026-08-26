# -*- coding: utf-8 -*-
"""审计附件 2-3 全模态精确对齐 V2.0 的交付结构与证据链。

本脚本只读取既有模型、日志和后处理产物，并在 ``audit`` 目录写出一份 JSON 与一份
Markdown 审计摘要。它不会启动 MAPDL，不会修改任何求解结果或变体文件，也不会把
历史日志末尾的 ``RUN COMPLETED`` 误判为“零错误”。

审计边界包括：

1. 权威基础输入、有限门架/横通道 include、空间化质量 include 的快照一致性；
2. 静力质量/反力闭合、模态结果集与全节点向量的连续性；
3. “请求 50 阶但实际 41 阶”造成的历史 ``SET,1,42`` 后处理错误；
4. runner 源码是否已加入实际结果集保护和严格 MAPDL 错误检查；
5. CSV、Markdown 与 JSON 的中文编码契约；
6. 生成器、质量、后处理和最新计算历程记录是否形成可追溯链。
"""

from __future__ import annotations

# hashlib 用于计算关键输入与快照的 SHA-256，证明源文件和 run 副本是否逐字节一致。
import hashlib
# json 用于输出机器可读的交付审计结果；JSON 保持标准无 BOM UTF-8。
import json
# re 用于解析 MAPDL 结果集列表、日志错误计数和模态向量文件名。
import re
# dataclass 为单项检查提供固定字段，避免报告与 JSON 使用不一致的状态名称。
from dataclasses import asdict, dataclass
# datetime 记录审计执行时刻，并保留本机时区，便于与求解日志对照。
from datetime import datetime
# Path 统一处理 Windows 中文路径和文件元数据，不手工拼接反斜杠。
from pathlib import Path
# Any 用于描述审计细节中既可能是数字、字符串，也可能是列表的值。
from typing import Any


# SCRIPT_DIR 是 V2.0 交付根目录；所有审计路径均从脚本位置推导。
SCRIPT_DIR = Path(__file__).resolve().parent
# PROJECT_ROOT 是张靖皋大桥工作区根目录，供定位 V1.0 权威基础输入。
PROJECT_ROOT = SCRIPT_DIR.parents[1]
# SOURCE_RUN_DIR 保存 V2.0 仍沿用的权威索网、支承、初始索力和荷载 include。
SOURCE_RUN_DIR = PROJECT_ROOT / "03_猫道动力分析" / "第一阶模态验证_V1.0"
# RUN_DIR 保存当前正式基线的输入快照、日志、结果集列表和模态向量。
RUN_DIR = SCRIPT_DIR / "run"
# BUILDER_OUTPUT_DIR 保存有限门架与横向通道的生成器封板结果。
BUILDER_OUTPUT_DIR = SCRIPT_DIR / "builder" / "generated"
# POST_DIR 保存模态自动识别、全局分配和图件产物。
POST_DIR = SCRIPT_DIR / "post"
# AUDIT_DIR 保存本脚本的审计结果以及站位/质量映射上游证据。
AUDIT_DIR = SCRIPT_DIR / "audit"

# JSON_OUTPUT 是机器可读审计清单，使用无 BOM UTF-8。
JSON_OUTPUT = AUDIT_DIR / "delivery_chain_audit_v2.json"
# MARKDOWN_OUTPUT 是人工审阅摘要，使用带 BOM UTF-8 避免 Windows 中文乱码。
MARKDOWN_OUTPUT = AUDIT_DIR / "交付结构与证据链审计_V2.0.md"

# AUTHORITATIVE_INPUTS 与 runner 使用同一组基础 include；旧门架/横通道 CP 文件故意不在内。
AUTHORITATIVE_INPUTS = (
    "full_line_beam4_crossbeam_mesh_xlong.inp",
    "convert_crossbeams_beam4_to_beam188.inp",
    "apply_mct_downpull_equivalent_xlong.inp",
    "apply_mct_constraints_xlong.inp",
    "apply_mct_authoritative_initial_state_link180.inp",
    "apply_modal_roty_stabilization_xlong.inp",
    "define_representative_rope_component.inp",
    "apply_authoritative_mct_deadload_v1.inp",
    "apply_authoritative_mct_gravity_v1.inp",
)

# MODE_FILE_PATTERN 提取公开协议 ``mode_XX_all_nodes.txt`` 中的实际阶次。
MODE_FILE_PATTERN = re.compile(r"^mode_(\d+)_all_nodes\.txt$", re.IGNORECASE)
# SET_LIST_PATTERN 解析 MAPDL ``SET,LIST`` 的“阶次、频率、荷载步、子步、累计步”五列。
SET_LIST_PATTERN = re.compile(
    r"^\s*(\d+)\s+([-+0-9.EeDd]+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$"
)
# ERROR_COUNT_PATTERN 解析 MAPDL 日志汇总；``\s+`` 兼容 ERROR 后的对齐空格。
ERROR_COUNT_PATTERN = re.compile(
    r"NUMBER OF ERROR\s+MESSAGES ENCOUNTERED\s*=\s*([0-9]+)"
)


@dataclass(frozen=True)
class AuditCheck:
    """保存一项可独立复核的交付检查。

    属性：
        check_id：稳定英文标识，供机器比较不同审计轮次。
        status：``PASS``、``WARN`` 或 ``FAIL``。
        summary：面向人工的简短中文结论。
        details：支持结论的路径、计数、哈希或错误标志等结构化细节。
    """

    check_id: str
    status: str
    summary: str
    details: dict[str, Any]


def sha256_file(path: Path) -> str:
    """流式计算一个文件的 SHA-256。

    参数：
        path：需要指纹化的普通文件。

    返回：
        64 位小写十六进制 SHA-256。

    说明：
        使用 1 MiB 分块，避免把大型 include 或日志一次性读入内存。
    """

    # digest 保存逐块更新的 SHA-256 内部状态。
    digest = hashlib.sha256()
    # 二进制读取不做换行或编码转换，确保哈希反映真实字节快照。
    with path.open("rb") as stream:
        # 循环直到 read 返回空字节；每一块都立即送入摘要器。
        while True:
            # chunk 大小兼顾磁盘吞吐和内存占用。
            chunk = stream.read(1024 * 1024)
            # 空块表示到达文件末尾，必须在 update 前退出。
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def inspect_text_encoding(path: Path, expect_bom: bool) -> dict[str, Any]:
    """检查文本是否为有效 UTF-8，以及 BOM 是否满足该文件类型契约。

    参数：
        path：待检查的 Markdown、CSV 或 JSON 文件。
        expect_bom：``True`` 表示必须带 UTF-8 BOM；``False`` 表示必须不带 BOM。

    返回：
        含存在性、UTF-8 有效性、BOM 状态和契约是否通过的字典。
    """

    # 文件缺失时不尝试读取，返回足够信息供调用方形成 FAIL。
    if not path.is_file():
        return {
            "path": str(path),
            "exists": False,
            "valid_utf8": False,
            "has_utf8_bom": False,
            "contract_pass": False,
        }
    # raw_bytes 用于同时判断 BOM 和执行严格 UTF-8 解码。
    raw_bytes = path.read_bytes()
    # has_bom 只检查标准三字节 UTF-8 BOM，不接受 UTF-16/ANSI 替代。
    has_bom = raw_bytes.startswith(b"\xef\xbb\xbf")
    # 严格解码捕获任何损坏字节；utf-8-sig 会在存在 BOM 时自动移除它。
    try:
        raw_bytes.decode("utf-8-sig")
        valid_utf8 = True
    except UnicodeDecodeError:
        valid_utf8 = False
    # contract_pass 要求文件有效且 BOM 与该文件类型的明确预期一致。
    contract_pass = valid_utf8 and has_bom == expect_bom
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": len(raw_bytes),
        "valid_utf8": valid_utf8,
        "has_utf8_bom": has_bom,
        "expected_utf8_bom": expect_bom,
        "contract_pass": contract_pass,
    }


def parse_set_list(path: Path) -> dict[str, Any]:
    """解析模态结果集列表并检查阶次连续性。

    参数：
        path：MAPDL ``SET,LIST`` 输出文件。

    返回：
        含结果集数量、起止阶次、频率范围和连续性布尔值的字典。
    """

    # 缺文件直接返回空统计，调用方据此判为 FAIL。
    if not path.is_file():
        return {"path": str(path), "exists": False, "mode_count": 0, "continuous": False}
    # rows 保存每个成功解析的“阶次、频率”二元组。
    rows: list[tuple[int, float]] = []
    # MAPDL 输出以 ASCII 为主；errors='replace' 只替换路径乱码，不影响数值行。
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        # match 只接受完整五列 SET 行，避免把页眉或其他数字误计为模态。
        match = SET_LIST_PATTERN.match(line)
        if match is None:
            continue
        # D 指数是 Fortran 常见格式；替换为 E 后交给 Python float。
        frequency = float(match.group(2).replace("D", "E").replace("d", "e"))
        rows.append((int(match.group(1)), frequency))
    # mode_numbers 按文件出现顺序保存阶次，正常情况应等于 1..N。
    mode_numbers = [row[0] for row in rows]
    # expected_numbers 在空表时同样为空；空表仍由 mode_count>0 条件判为不连续。
    expected_numbers = list(range(1, len(mode_numbers) + 1))
    # continuous 同时要求非空和严格从1连续，不能只比较相邻差。
    continuous = bool(mode_numbers) and mode_numbers == expected_numbers
    return {
        "path": str(path),
        "exists": True,
        "mode_count": len(rows),
        "first_mode": mode_numbers[0] if mode_numbers else None,
        "last_mode": mode_numbers[-1] if mode_numbers else None,
        "first_frequency_hz": rows[0][1] if rows else None,
        "last_frequency_hz": rows[-1][1] if rows else None,
        "continuous": continuous,
    }


def inspect_mode_vectors(directory: Path) -> dict[str, Any]:
    """检查全节点模态向量是否从 M1 连续到最后一阶且均非空。

    参数：
        directory：包含 ``mode_XX_all_nodes.txt`` 的 run 目录。

    返回：
        含发现阶次、连续性、空文件和总体积的字典。
    """

    # indexed_paths 以整数阶次为键，防止字符串排序把 mode_10 放到 mode_2 前面。
    indexed_paths: dict[int, Path] = {}
    # 只遍历 run 目录第一层，避免把其他子目录的回归向量混入正式结果。
    for path in directory.glob("mode_*_all_nodes.txt"):
        # match 严格使用公开文件名协议，忽略任何临时或变体命名。
        match = MODE_FILE_PATTERN.match(path.name)
        if match is None:
            continue
        indexed_paths[int(match.group(1))] = path
    # mode_numbers 数值排序后用于连续性判断与报告起止阶次。
    mode_numbers = sorted(indexed_paths)
    # expected_numbers 对非空集合要求从1到最大阶全部存在。
    expected_numbers = list(range(1, mode_numbers[-1] + 1)) if mode_numbers else []
    # empty_modes 明确列出零字节向量，防止“文件存在”掩盖导出失败。
    empty_modes = [
        mode_number
        for mode_number in mode_numbers
        if indexed_paths[mode_number].stat().st_size == 0
    ]
    # total_size_bytes 仅做体量审计，不对数百 MiB 向量逐个哈希以缩短审计时间。
    total_size_bytes = sum(indexed_paths[number].stat().st_size for number in mode_numbers)
    return {
        "directory": str(directory),
        "mode_count": len(mode_numbers),
        "first_mode": mode_numbers[0] if mode_numbers else None,
        "last_mode": mode_numbers[-1] if mode_numbers else None,
        "continuous": bool(mode_numbers) and mode_numbers == expected_numbers,
        "empty_modes": empty_modes,
        "total_size_bytes": total_size_bytes,
    }


def inspect_mapdl_log(path: Path) -> dict[str, Any]:
    """提取 MAPDL 主日志中的正常结束与错误终止标志。

    参数：
        path：正式基线 ``attachment23_v2.out``。

    返回：
        含错误计数、关键错误文本、SET42 命中和 RUN COMPLETED 命中的字典。
    """

    # 缺日志无法证明任何求解状态，返回 exists=False。
    if not path.is_file():
        return {"path": str(path), "exists": False}
    # latin-1 对任意字节都可逆，并保持所有 ASCII 关键字原样，适合混合编码 MAPDL 日志。
    text = path.read_bytes().decode("latin-1")
    # error_counts 可能在不同阶段出现多次；最大值代表本次日志已报告的最坏状态。
    error_counts = [int(value) for value in ERROR_COUNT_PATTERN.findall(text)]
    # maximum_error_count 在没有汇总行时为0，但后续显式错误标志仍可发现异常。
    maximum_error_count = max(error_counts, default=0)
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        # 完整主日志哈希把紧凑错误摘要绑定到不可替换的原始字节版本。
        "sha256": sha256_file(path),
        "run_completed": "RUN COMPLETED" in text,
        "explicit_error_block": "*** ERROR ***" in text,
        "problem_terminated_by_error": "PROBLEM TERMINATED BY INDICATED ERROR" in text,
        "load_set_not_found": "Load set not found on result file" in text,
        "set_42_attempted": "SET,1,42" in text or "SUBSTEP    42" in text,
        "maximum_error_count": maximum_error_count,
    }


def compare_snapshot_pairs() -> tuple[list[dict[str, Any]], bool]:
    """比较权威源 include 与 run 快照，以及两个 V2 include 的源/快照。

    参数：
        无。比较集合由脚本常量固定。

    返回：
        第一项是逐对路径、哈希和一致性；第二项表示全部文件存在且逐字节一致。
    """

    # pairs 先登记九个 V1 权威基础输入。
    pairs: list[tuple[Path, Path]] = [
        (SOURCE_RUN_DIR / name, RUN_DIR / name) for name in AUTHORITATIVE_INPUTS
    ]
    # 有限拓扑 include 的封板源位于 builder/generated，run 中保存求解快照。
    pairs.append(
        (
            BUILDER_OUTPUT_DIR / "apply_finite_gates_and_passages_v2.inp",
            RUN_DIR / "apply_finite_gates_and_passages_v2.inp",
        )
    )
    # 空间化质量 include 的封板源位于 V2 根目录，run 中保存求解快照。
    pairs.append(
        (
            SCRIPT_DIR / "apply_dynamic_mass21_spatialized_v2.inp",
            RUN_DIR / "apply_dynamic_mass21_spatialized_v2.inp",
        )
    )
    # rows 保存每一对的存在性和哈希，不因单个缺件提前停止其余审计。
    rows: list[dict[str, Any]] = []
    # all_match 初始为真，遇到任一缺件或哈希不等即置为假。
    all_match = True
    for source_path, snapshot_path in pairs:
        # 两个布尔值分开保存，报告可以准确指出缺源还是缺快照。
        source_exists = source_path.is_file()
        snapshot_exists = snapshot_path.is_file()
        # 只有两端都存在时才计算哈希，避免无意义的异常。
        source_hash = sha256_file(source_path) if source_exists else None
        snapshot_hash = sha256_file(snapshot_path) if snapshot_exists else None
        # pair_match 要求存在且哈希完全一致；仅同名或同大小不算通过。
        pair_match = source_exists and snapshot_exists and source_hash == snapshot_hash
        if not pair_match:
            all_match = False
        rows.append(
            {
                "source": str(source_path),
                "snapshot": str(snapshot_path),
                "source_exists": source_exists,
                "snapshot_exists": snapshot_exists,
                "source_sha256": source_hash,
                "snapshot_sha256": snapshot_hash,
                "match": pair_match,
            }
        )
    return rows, all_match


def read_compact_evidence(path: Path) -> dict[str, Any]:
    """读取小型文本证据并返回路径、正文和 SHA-256。

    参数：
        path：拓扑计数、质量闭合等小型文本文件。

    返回：
        文件不存在时仅给存在性；存在时追加去除首尾空白的正文和哈希。
    """

    # 缺失证据由调用方决定 FAIL，不在此函数抛出中断整个审计。
    if not path.is_file():
        return {"path": str(path), "exists": False}
    return {
        "path": str(path),
        "exists": True,
        "text": path.read_text(encoding="utf-8", errors="replace").strip(),
        "sha256": sha256_file(path),
    }


def make_markdown_report(audit: dict[str, Any]) -> str:
    """把机器审计字典压缩为人工可读 Markdown。

    参数：
        audit：即将写入 JSON 的完整审计结构。

    返回：
        带章节、状态表和路径的 Markdown 正文；编码由调用方统一处理。
    """

    # check_rows 把所有检查压缩为一张表；竖线替换防止摘要破坏 Markdown 列结构。
    check_rows = ["| 检查 | 状态 | 结论 |", "|---|---|---|"]
    for check in audit["checks"]:
        # safe_summary 只处理表格语法字符，不改变检查结论的语义。
        safe_summary = str(check["summary"]).replace("|", "／")
        check_rows.append(
            f"| `{check['check_id']}` | **{check['status']}** | {safe_summary} |"
        )
    # snapshot_mismatches 只列不一致项；为空时明确写“全部一致”。
    snapshot_mismatches = [
        row for row in audit["snapshot_bindings"] if not row["match"]
    ]
    if snapshot_mismatches:
        snapshot_text = "\n".join(
            f"- 源：`{row['source']}`；快照：`{row['snapshot']}`"
            for row in snapshot_mismatches
        )
    else:
        snapshot_text = f"- {len(audit['snapshot_bindings'])} 对源文件与 run 快照 SHA-256 全部一致。"
    # 直接引用结构化字段，避免在报告中重新解析日志而产生第二套判断逻辑。
    log = audit["mapdl_baseline_log"]
    sets = audit["modal_set_list"]
    vectors = audit["mode_vectors"]
    return f"""# 附件2-3 V2.0 交付结构与证据链审计

生成时间：{audit['generated_at']}

## 1. 总体状态

- 交付阶段：**{audit['delivery_status']}**
- 正式基线证据：**{audit['baseline_evidence_status']}**
- runner 修复：**{audit['runner_fix_status']}**
- 说明：本审计不启动 MAPDL，也不把当前中间结果冒充“14 个目标已精确对齐”。

## 2. 单项检查

{chr(10).join(check_rows)}

## 3. 输入快照绑定

{snapshot_text}

## 4. 历史基线错误的正确解释

- ``SET,LIST`` 实际结果集：{sets.get('mode_count', 0)} 阶，连续性：{sets.get('continuous', False)}。
- 全节点向量：{vectors.get('mode_count', 0)} 阶，连续性：{vectors.get('continuous', False)}，空文件：{vectors.get('empty_modes', [])}。
- 主日志同时包含 ``RUN COMPLETED``：{log.get('run_completed', False)}；错误数：{log.get('maximum_error_count')}；``SET 42``：{log.get('set_42_attempted')}。
- 因此，静力平衡和 M1～M41 特征值/向量可作为当前基线证据；整次历史批处理不能标成“零错误成功”。错误发生在无条件导出不存在的第42阶，runner 源码现已修复，但尚未用修复后的正式 runner 重跑基线。

## 5. 编码契约

- Markdown：UTF-8 with BOM；
- CSV：UTF-8 with BOM；
- JSON：UTF-8 without BOM；
- 检查细节见机器文件中的 ``encoding_checks``。

## 6. 历程与审计入口

- 最新计算历程：`{audit['latest_history_record']}`
- 机器审计：`{JSON_OUTPUT}`
- 本摘要：`{MARKDOWN_OUTPUT}`
- runner：`{SCRIPT_DIR / 'prepare_and_run_v2.py'}`
- 后处理：`{POST_DIR / 'modal_identification_pipeline.py'}`

## 7. 遗留边界

1. 修复后的 runner 尚未重跑正式基线，旧 ``attachment23_v2.out`` 的 1 个后处理错误必须永久保留在历程中。
2. 当前自动分配是形态特征匹配，不是真 MAC；附件未提供质量归一化源振型向量。
3. TS2、VS2 缺附件源振型图，波腹规则含拓扑推断；最终对齐结论必须同时给频率、方向、S/A、波腹和跨域证据。
4. 门架/横通道缺原设计节点释放与连接详图；等效刚度标定必须标注“等效连接参数”，不可伪称材料弹性模量实测值。
"""


def main() -> int:
    """执行全部只读检查并写出 JSON/Markdown 审计结果。

    参数：
        无。所有路径均由脚本所在 V2.0 根目录推导。

    返回：
        ``0`` 表示审计脚本完整执行并写出结果；具体交付风险由 JSON 中状态表达，
        历史已知后处理错误不会让脚本拒绝生成审计文件。
    """

    # 确保 audit 目录存在；该操作不会删除或覆盖任何上游证据。
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    # checks 按证据链顺序保存所有检查，最终同时进入 JSON 和 Markdown。
    checks: list[AuditCheck] = []

    # required_directories 代表交付最小结构；任何一个缺失都会破坏对应证据链。
    required_directories = [AUDIT_DIR, BUILDER_OUTPUT_DIR, POST_DIR, RUN_DIR]
    # missing_directories 保留实际缺件路径，便于机器和人工定位。
    missing_directories = [str(path) for path in required_directories if not path.is_dir()]
    checks.append(
        AuditCheck(
            "delivery_directories",
            "PASS" if not missing_directories else "FAIL",
            "audit/builder/post/run 四层交付结构完整。"
            if not missing_directories
            else "交付目录不完整。",
            {"missing": missing_directories},
        )
    )

    # snapshot_rows 逐对记录权威源与求解快照哈希；snapshot_all_match 是整体闭环。
    snapshot_rows, snapshot_all_match = compare_snapshot_pairs()
    checks.append(
        AuditCheck(
            "input_snapshot_sha256",
            "PASS" if snapshot_all_match else "FAIL",
            "九个权威基础输入及两个 V2 include 与 run 快照逐字节一致。"
            if snapshot_all_match
            else "至少一对源文件与 run 快照缺失或哈希不一致。",
            {"pair_count": len(snapshot_rows)},
        )
    )

    # compact_evidence 读取拓扑计数和静力质量/反力闭合，不解析大型二进制结果。
    topology_evidence = read_compact_evidence(RUN_DIR / "v2_topology_counts.txt")
    closure_evidence = read_compact_evidence(RUN_DIR / "v2_static_mass_closure.txt")
    # compact_pass 要求两项文件都存在且正文非空。
    compact_pass = bool(topology_evidence.get("text")) and bool(closure_evidence.get("text"))
    checks.append(
        AuditCheck(
            "static_compact_evidence",
            "PASS" if compact_pass else "FAIL",
            "拓扑计数与静力质量/反力闭合证据均存在。"
            if compact_pass
            else "拓扑计数或静力闭合证据缺失。",
            {"topology": topology_evidence, "closure": closure_evidence},
        )
    )

    # modal_sets 和 mode_vectors 分别验证结果文件目录表与实际 PRNSOL 向量。
    modal_sets = parse_set_list(RUN_DIR / "v2_modal_set_list.txt")
    mode_vectors = inspect_mode_vectors(RUN_DIR)
    # modal_continuity_pass 还要求两个来源计数一致，避免只完成一半导出。
    modal_continuity_pass = (
        modal_sets.get("continuous", False)
        and mode_vectors.get("continuous", False)
        and not mode_vectors.get("empty_modes")
        and modal_sets.get("mode_count") == mode_vectors.get("mode_count")
    )
    checks.append(
        AuditCheck(
            "modal_result_continuity",
            "PASS" if modal_continuity_pass else "FAIL",
            # 结论中的末阶从实际 SET 列表读取，使脚本在未来40阶或更多阶正式重跑后仍准确。
            (
                "SET 列表与全节点向量均从 M1 连续到 "
                f"M{modal_sets.get('last_mode')}，数量一致且无空文件。"
            )
            if modal_continuity_pass
            else "SET 列表与全节点向量不连续、数量不等或存在空文件。",
            {"set_list": modal_sets, "vectors": mode_vectors},
        )
    )

    # baseline_log 保留“有 RUN COMPLETED 但仍有错误”的完整组合，避免单标志误判。
    baseline_log = inspect_mapdl_log(RUN_DIR / "attachment23_v2.out")
    # known_export_error 要求历史问题的五个关键特征同时存在，证明诊断不是猜测。
    known_export_error = (
        baseline_log.get("run_completed")
        and baseline_log.get("explicit_error_block")
        and baseline_log.get("problem_terminated_by_error")
        and baseline_log.get("load_set_not_found")
        and baseline_log.get("set_42_attempted")
        and baseline_log.get("maximum_error_count") == 1
    )
    checks.append(
        AuditCheck(
            "historical_set42_error",
            "WARN" if known_export_error else "FAIL",
            "已确认历史日志在有效 M1～M41 导出后因 SET 42 产生 1 个后处理错误。"
            if known_export_error
            else "历史错误特征与预期不一致，需要重新人工核查日志。",
            baseline_log,
        )
    )

    # runner_text 只读当前源码，检查三个修复契约是否同时出现。
    runner_path = SCRIPT_DIR / "prepare_and_run_v2.py"
    runner_text = runner_path.read_text(encoding="utf-8") if runner_path.is_file() else ""
    # runner_markers 是源码层静态验证，不冒充 MAPDL 已重跑验证。
    runner_markers = {
        "default_40": "default=40" in runner_text,
        "actual_result_set_guard": "V2_AVAILABLE_MODES" in runner_text
        and "*GET,V2_AVAILABLE_MODES,ACTIVE,0,SET,NSET" in runner_text,
        "strict_error_check": "PROBLEM TERMINATED BY INDICATED ERROR" in runner_text
        and "NUMBER OF ERROR" in runner_text,
        "stale_text_cleanup": "clear_previous_text_evidence" in runner_text,
    }
    # runner_source_fixed 只有全部源码标志齐全时才通过。
    runner_source_fixed = all(runner_markers.values())
    checks.append(
        AuditCheck(
            "runner_source_fix",
            "PASS" if runner_source_fixed else "FAIL",
            "runner 已加入默认40阶、实际结果集截断、严格错误检查和旧文本清理。"
            if runner_source_fixed
            else "runner 修复契约不完整。",
            {"path": str(runner_path), "markers": runner_markers},
        )
    )

    # encoding_targets 明确每类“输出文件”的 BOM 契约。附件表转录 CSV 是不可变输入，
    # 其既有 SHA-256 已进入模态审计，因此不为显示便利改写字节，也不混入输出编码检查。
    markdown_paths = sorted(POST_DIR.rglob("*.md"))
    csv_paths = sorted(
        path
        for path in POST_DIR.glob("*.csv")
        if path.name != "reference_attachment_2_3_table4_1.csv"
    )
    json_paths = sorted(POST_DIR.glob("*.json"))
    # encoding_checks 对每个目标执行严格 UTF-8 和 BOM 检查。
    encoding_checks = [
        inspect_text_encoding(path, expect_bom=True) for path in markdown_paths
    ]
    encoding_checks.extend(
        inspect_text_encoding(path, expect_bom=True) for path in csv_paths
    )
    encoding_checks.extend(
        inspect_text_encoding(path, expect_bom=False) for path in json_paths
    )
    # reference_encoding 单独验证权威转录表仍为有效 UTF-8，但不要求也不禁止其历史 BOM 状态。
    reference_csv_path = POST_DIR / "reference_attachment_2_3_table4_1.csv"
    reference_encoding = inspect_text_encoding(reference_csv_path, expect_bom=False)
    # encoding_pass 要求至少有文件且每个文件都符合契约。
    encoding_pass = bool(encoding_checks) and all(
        item["contract_pass"] for item in encoding_checks
    )
    checks.append(
        AuditCheck(
            "post_text_encoding",
            "PASS" if encoding_pass else "FAIL",
            "post 人工文本/CSV/JSON 均满足明确 UTF-8 BOM 契约。"
            if encoding_pass
            else "至少一个 post 文本不满足 UTF-8/BOM 契约。",
            {"file_count": len(encoding_checks)},
        )
    )

    # upstream_audit_paths 覆盖站位、有限构件、质量空间化和模态识别四级机器审计。
    upstream_audit_paths = [
        AUDIT_DIR / "passage_station_mass_map_audit.json",
        BUILDER_OUTPUT_DIR / "build_audit.json",
        SCRIPT_DIR / "mass21_spatialization_audit_v2.json",
        POST_DIR / "modal_pipeline_audit.json",
        # 紧凑历史证据保存 SET42 错误段及完整日志哈希，避免未来正式重跑覆盖主日志后失去追溯。
        AUDIT_DIR / "attachment23_v2_历史SET42错误证据_20260712.txt",
    ]
    # upstream_audits 记录存在性与哈希，不依赖各 JSON 的内部字段命名。
    upstream_audits = [
        {
            "path": str(path),
            "exists": path.is_file(),
            "sha256": sha256_file(path) if path.is_file() else None,
        }
        for path in upstream_audit_paths
    ]
    # upstream_pass 要求四级审计全部存在。
    upstream_pass = all(item["exists"] for item in upstream_audits)
    checks.append(
        AuditCheck(
            "upstream_audit_chain",
            "PASS" if upstream_pass else "FAIL",
            "站位—有限构件—空间质量—模态识别及历史错误摘要证据齐全。"
            if upstream_pass
            else "上游机器审计链存在缺件。",
            {"evidence_count": len(upstream_audits)},
        )
    )

    # latest_history_path 是本轮统一历程入口；其内容明确区分已验证事实与待标定项。
    latest_history_path = SCRIPT_DIR / "附件2-3全模态精确对齐_V2.0_计算历程记录_20260712.md"
    # history_exists 只检查文件存在和非空，详细章节结构由人工记录本身承担。
    history_exists = latest_history_path.is_file() and latest_history_path.stat().st_size > 0
    checks.append(
        AuditCheck(
            "latest_history_record",
            "PASS" if history_exists else "FAIL",
            "V2.0 已建立统一计算历程入口。"
            if history_exists
            else "缺少 V2.0 统一计算历程记录。",
            {"path": str(latest_history_path)},
        )
    )

    # audit 是写出 JSON 的唯一真源；Markdown 由此对象派生，避免两份报告状态分叉。
    audit: dict[str, Any] = {
        "schema": "attachment_2_3_v2_delivery_chain_audit",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "delivery_status": "INTERIM_NOT_FINAL_14_MODE_ALIGNMENT",
        "baseline_evidence_status": "USABLE_M1_TO_M41_WITH_KNOWN_POST_EXPORT_ERROR",
        "runner_fix_status": "SOURCE_FIXED_NOT_FORMALLY_RERUN",
        "checks": [asdict(check) for check in checks],
        "snapshot_bindings": snapshot_rows,
        "compact_evidence": {
            "topology": topology_evidence,
            "static_closure": closure_evidence,
        },
        "modal_set_list": modal_sets,
        "mode_vectors": mode_vectors,
        "mapdl_baseline_log": baseline_log,
        "runner_source": {
            "path": str(runner_path),
            "sha256": sha256_file(runner_path) if runner_path.is_file() else None,
            "markers": runner_markers,
        },
        "encoding_contract": {
            "markdown": "UTF-8 with BOM",
            "csv": "UTF-8 with BOM",
            "json": "UTF-8 without BOM",
        },
        "encoding_checks": encoding_checks,
        "immutable_reference_csv_encoding": reference_encoding,
        "upstream_audits": upstream_audits,
        "latest_history_record": str(latest_history_path),
        "limitations": [
            "修复后的 runner 尚未正式重跑基线。",
            "附件缺质量归一化源模态向量，当前不是 MAC 校核。",
            "TS2/VS2 缺源振型图，形态规则含拓扑推断。",
            "门架与横通道缺节点释放/连接详图，等效连接刚度仍需标定。",
        ],
    }
    # JSON 采用标准无 BOM UTF-8，并以换行结束，兼顾严格解析器与版本差异查看。
    JSON_OUTPUT.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    # Markdown 面向 Windows 人工查看，统一使用 UTF-8 BOM 防止中文误判为 ANSI。
    MARKDOWN_OUTPUT.write_text(
        make_markdown_report(audit),
        encoding="utf-8-sig",
        newline="\n",
    )
    # 标准输出仅给两个审计入口和关键状态，便于命令行或 CI 捕获。
    print(f"JSON_AUDIT={JSON_OUTPUT}")
    print(f"MARKDOWN_AUDIT={MARKDOWN_OUTPUT}")
    print(f"DELIVERY_STATUS={audit['delivery_status']}")
    return 0


if __name__ == "__main__":
    # 只有直接执行时才写审计文件；被其他脚本导入时不产生任何文件副作用。
    raise SystemExit(main())
