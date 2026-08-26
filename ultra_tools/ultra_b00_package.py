"""构建 B00 0–0.35 Hz、59 阶结果的可审计 ZIP，硬限制小于 500,000,000 byte。"""  # 模块说明限定输入、输出、压缩范围和容量门禁。

from __future__ import annotations  # 启用延迟类型注解，避免运行期解析复杂容器类型。

import csv  # 用于生成不带非法注释的包内文件清单和大文件排除清单。
import hashlib  # 用于流式计算包内来源文件、排除大文件和最终 ZIP 的 SHA-256。
import io  # 用于在内存中构造 UTF-8 CSV 文本后一次性排他写盘。
import json  # 用于写出机器可读的关键结果摘要和最终 ZIP 状态。
import re  # 用于确定性识别模态 CSV 数值行、SET 列表和节点结果行。
import zipfile  # 用于以 ZIP_DEFLATED 最高压缩级别构建标准 ZIP64 交付包。
from datetime import datetime, timezone  # 用于记录带 UTC 时区的交付构建时间。
from pathlib import Path  # 用于统一处理中文项目路径、包内相对路径和排他创建目标。
from typing import Final  # 用于标记不应在运行中改变的容量、数量和路径常量。


SCRIPT_PATH: Final[Path] = Path(__file__).resolve()  # 当前打包脚本绝对路径同时作为包内修正证据。
TOOLS_DIR: Final[Path] = SCRIPT_PATH.parent  # ultra_tools 目录承载当前修正后的 B00 生成器。
PROJECT_ROOT: Final[Path] = TOOLS_DIR.parent  # V2.0 项目根目录承载原始 run 与最终 ZIP。
RUN_NAME: Final[str] = "B00_LEGACY_COMPLETE_20260715T111105670409Z"  # 固定选择本次已经求解的唯一 B00 run，禁止通配最新目录。
RUN_DIR: Final[Path] = PROJECT_ROOT / "ultra_runs" / RUN_NAME  # 原始 B00 run 根目录用于读取谱系、状态和 solver 结果。
SOLVER_DIR: Final[Path] = RUN_DIR / "solver"  # 原始 59 阶求解与导出目录是包内计算结果的唯一来源。
STATIC_QA_DIR: Final[Path] = Path(r"C:\ansys_work\B00_STATIC_QA_20260715T1311Z")  # C 盘只读 POST1 补证目录提供最终静力闭合证据。
CANCELLED_80_DIR: Final[Path] = Path(r"C:\ansys_work\B00_80MODE_20260715T1303Z")  # 已按用户要求停止的 80 阶临时目录只提供修正输入，不提供不完整结果。
DELIVERY_DIR: Final[Path] = RUN_DIR / "delivery_59mode_20260715"  # run 内交付说明目录保存清洗结果、报告和最终 ZIP 状态。
ARCHIVE_NAME: Final[str] = "B00_0-0.35Hz_59阶_修正输入与计算结果_20260715.zip"  # 最终 ZIP 名明确频带、阶数、修正和结果范围。
ARCHIVE_PATH: Final[Path] = PROJECT_ROOT / ARCHIVE_NAME  # 最终 ZIP 放在 V2.0 项目根目录便于直接交付。
ARCHIVE_ROOT: Final[str] = "B00_0-0.35Hz_59阶交付"  # ZIP 内单一顶层目录防止解压文件散落。
MAX_ARCHIVE_BYTES: Final[int] = 500_000_000  # 硬限制采用 500,000,000 byte，严格低于用户要求的 512 MB。
EXPECTED_MODE_COUNT: Final[int] = 59  # 0–0.35 Hz 频带内实际存在且用户确认保留的模态数为 59。
EXPECTED_TOPOLOGY_NODES: Final[int] = 109_086  # 完整模型拓扑节点总数来自 b00_topology_counts.txt。
EXPECTED_RESULT_NODES: Final[int] = 91_407  # PRNSOL 对每阶输出的实际求解自由度节点数由全文件核验固定。
EXPECTED_ORIENTATION_NODES: Final[int] = 17_679  # 每个 TYPE70 BEAM188 对应一个无位移自由度方向节点，数量等于拓扑与结果节点之差。
EXPECTED_STATIC_TIME: Final[float] = 1.001  # 最终静力状态伪时间单位为 s，来源为 RST 最后结果集。
EXPECTED_MASS_TONNE: Final[float] = 4108.46690758  # 全模型封板质量基准单位为 tonne。
MASS_TOLERANCE_TONNE: Final[float] = 1.0e-6  # 总质量绝对误差门槛单位为 tonne。
ENERGY_RATIO_LIMIT: Final[float] = 1.0e-8  # 最终静力 STEN/SENE 无量纲比值门槛。
REACTION_RATIO_LIMIT: Final[float] = 1.0e-4  # 竖向支反力相对闭合误差无量纲门槛。
SET_FREQUENCY_TOLERANCE_HZ: Final[float] = 5.1e-9  # SET 列表有限打印精度允许的逐阶频率绝对差单位为 Hz。
NUMERIC_TOKEN: Final[str] = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?"  # 通用十进制和科学计数法正则不接受非数值字段。
SET_LINE_PATTERN: Final[re.Pattern[str]] = re.compile(rf"^\s*(\d+)\s+({NUMERIC_TOKEN})\s+(\d+)\s+(\d+)\s+(\d+)\s*$")  # SET LIST 行固定解析 SET、频率、载荷步、子步和累计序号。
VECTOR_DATA_PATTERN: Final[re.Pattern[bytes]] = re.compile(rb"^\s*\d+\s+[-+0-9.]")  # PRNSOL 数据行以节点号和首个数值开头，排除重复页眉时间戳。
MODE_FILE_PATTERN: Final[re.Pattern[str]] = re.compile(r"mode_(\d+)_all_nodes\.txt\Z")  # 位移文件名必须使用连续十进制模态号。
ROTATION_FILE_PATTERN: Final[re.Pattern[str]] = re.compile(r"mode_(\d+)_rotations\.txt\Z")  # 转角文件名必须使用连续十进制模态号。


class PackageError(RuntimeError):  # 定义打包硬门禁失败异常，避免产生看似成功的不完整 ZIP。
    """表示源证据、数量、数值、哈希或容量未满足交付契约。"""  # 异常说明列出触发范围和阻断语义。


def require(condition: bool, message: str) -> None:  # 定义统一硬门禁函数，输入布尔条件和失败原因，不返回业务数据。
    """条件为假时抛出 PackageError；条件为真时无副作用返回。"""  # 函数说明明确输入、输出和异常路径。
    if not condition:  # 只有交付契约未满足时进入拒绝分支。
        raise PackageError(message)  # 抛出包含精确原因的异常并阻止创建最终 ZIP。


def sha256_file(path: Path) -> str:  # 定义流式文件哈希函数，输入现有文件路径，输出小写 SHA-256。
    """以 8 MiB 分块读取文件并返回 64 位小写十六进制 SHA-256。"""  # 函数说明给出块单位、输出格式和内存约束。
    digest = hashlib.sha256()  # 创建独立 SHA-256 状态，避免不同文件摘要相互污染。
    chunk_bytes = 8 * 1024 * 1024  # 每块固定 8 MiB，在大二进制吞吐和内存占用之间取平衡。
    with path.open("rb") as handle:  # 以二进制只读模式打开来源文件，不改变时间戳和内容。
        while True:  # 持续读取直到遇到空块表示文件结束。
            chunk = handle.read(chunk_bytes)  # 读取至多 8 MiB 原始字节供摘要更新。
            if not chunk:  # 空字节串仅在已经到达文件末尾时成立。
                break  # 结束分块循环并保留完整文件摘要状态。
            digest.update(chunk)  # 按原始字节顺序更新 SHA-256 状态。
    return digest.hexdigest()  # 返回 64 位小写十六进制摘要供 CSV 和最终状态使用。


def read_text(path: Path) -> str:  # 定义文本读取函数，输入现有路径，输出容错解码后的字符串。
    """优先 UTF-8 解码；对 MAPDL 本地代码页回显以替换字符保留可审计文本。"""  # 函数说明给出编码策略和不修改源文件约束。
    return path.read_text(encoding="utf-8", errors="replace")  # 一次读取文本并用替换字符承载不可解码的注释字节。


def write_new_text(path: Path, text: str) -> None:  # 定义排他文本写入函数，输入目标路径和 UTF-8 文本，无返回值。
    """创建父目录并以 UTF-8、LF、排他模式写入，禁止覆盖既有交付证据。"""  # 函数说明给出编码、换行和不可覆盖约束。
    path.parent.mkdir(parents=True, exist_ok=True)  # 只创建当前交付目录下缺失父目录，不删除或覆盖任何文件。
    with path.open("x", encoding="utf-8", newline="\n") as handle:  # 以排他创建模式打开目标，存在时立即失败。
        handle.write(text)  # 写入已经构造完成的全部 UTF-8 文本并在退出上下文时刷新缓冲区。


def write_new_json(path: Path, payload: object) -> None:  # 定义机器 JSON 排他写入函数，输入路径和可序列化对象，无返回值。
    """以 UTF-8、两空格缩进和末尾换行写入有效 JSON；字段说明由相邻 README 提供。"""  # 函数说明遵守 JSON 不插入注释的有效性约束。
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"  # 保留中文、使用两空格缩进并补单一 LF 结尾。
    write_new_text(path, rendered)  # 复用排他文本写入保证目录创建和不可覆盖语义。


def render_csv(header: list[str], rows: list[list[object]]) -> str:  # 定义 CSV 渲染函数，输入表头和行对象，输出 RFC 风格文本。
    """使用 csv.writer 生成 CRLF CSV，避免手工转义逗号、引号和中文路径。"""  # 函数说明给出输入、输出和转义策略。
    buffer = io.StringIO(newline="")  # 创建仅驻留内存的文本缓冲，不产生中间磁盘文件。
    writer = csv.writer(buffer, lineterminator="\r\n")  # 使用标准 CSV 引号规则和 CRLF 行结束符提高兼容性。
    writer.writerow(header)  # 第一行写入调用方定义的字段名，字段语义由相邻 Markdown 说明。
    for row in rows:  # 按调用方稳定顺序逐行写入全部数据记录。
        writer.writerow(row)  # 由 csv 模块自动转义每个字段并保留数值的字符串表示。
    return buffer.getvalue()  # 返回完整 CSV 文本供排他写入函数一次落盘。


def parse_modal_properties(path: Path) -> tuple[list[str], list[list[float]]]:  # 定义原始属性清洗函数，输入污染 CSV，输出纯行和数值矩阵。
    """仅保留恰有 15 个可解析数值字段的行，并强制模态号连续 1..59。"""  # 函数说明给出筛选规则、输出和硬门禁。
    clean_lines: list[str] = []  # 按原文件出现顺序保存纯数值行且不改变数值文本精度。
    numeric_rows: list[list[float]] = []  # 保存对应浮点矩阵用于模态号、频率和有限性核验。
    for raw_line in read_text(path).splitlines():  # 逐个物理行扫描原文件，包含命令回显和真实数值记录。
        stripped = raw_line.strip()  # 去除行首尾空白但保留逗号分隔字段内部表示。
        fields = stripped.split(",")  # 以逗号拆分候选记录，真实记录应恰含 15 个字段。
        if len(fields) != 15:  # 非 15 列行属于 MAPDL 命令回显、空行或其他说明。
            continue  # 跳过非数据行，不把污染文本写入 canonical CSV。
        try:  # 尝试把全部 15 个字段解析为有限浮点值。
            values = [float(field) for field in fields]  # 逐字段转为 Python 双精度用于结构核验。
        except ValueError:  # 任一字段不是标准数值时进入污染行分支。
            continue  # 跳过不可解析候选行并继续扫描后续物理行。
        clean_lines.append(stripped)  # 保留原始高精度数值文本作为 canonical 输出行。
        numeric_rows.append(values)  # 保存浮点视图供后续频率和模态号闭合。
    require(len(clean_lines) == EXPECTED_MODE_COUNT, f"模态属性纯数值行不是 {EXPECTED_MODE_COUNT} 条。")  # 强制频带内每阶恰有一条属性记录。
    mode_numbers = [int(round(row[0])) for row in numeric_rows]  # 把第一列整数型浮点显示恢复为模态号序列。
    require(mode_numbers == list(range(1, EXPECTED_MODE_COUNT + 1)), "模态属性编号不是连续 1..59。")  # 禁止缺阶、重阶或乱序。
    frequencies = [row[1] for row in numeric_rows]  # 第二列是高精度频率，单位 Hz。
    require(all(frequencies[index] < frequencies[index + 1] for index in range(len(frequencies) - 1)), "59 阶频率不是严格递增。")  # 相邻频率必须单调且不重复。
    return clean_lines, numeric_rows  # 返回原精度纯行和数值矩阵供写盘与 SET 对比。


def parse_set_frequencies(path: Path) -> list[float]:  # 定义 SET LIST 解析函数，输入原生索引文本，输出按 SET 排序的频率列表。
    """解析五列结果集记录并强制 SET、子步和累计序号连续 1..59。"""  # 函数说明给出列语义、输出单位和闭合条件。
    parsed: list[tuple[int, float, int, int, int]] = []  # 保存 SET、Hz、载荷步、子步和累计序号五元组。
    for line in read_text(path).splitlines():  # 逐行扫描原生 SET LIST，自动跳过标题和空行。
        match = SET_LINE_PATTERN.match(line)  # 只接受完整匹配的五列数值记录。
        if match is None:  # 标题、分隔线和说明行不匹配结果集格式。
            continue  # 跳过非结果集行并继续扫描。
        parsed.append((int(match.group(1)), float(match.group(2)), int(match.group(3)), int(match.group(4)), int(match.group(5))))  # 把五个捕获字段按声明类型写入列表。
    require(len(parsed) == EXPECTED_MODE_COUNT, f"SET LIST 结果集不是 {EXPECTED_MODE_COUNT} 条。")  # 强制索引结果集数与频带实际阶数一致。
    expected_sequence = list(range(1, EXPECTED_MODE_COUNT + 1))  # 构造连续 1..59 的唯一合法序列。
    require([row[0] for row in parsed] == expected_sequence, "SET 编号不是连续 1..59。")  # 核对第一列 SET 编号。
    require([row[3] for row in parsed] == expected_sequence, "SET 子步编号不是连续 1..59。")  # 核对第四列模态子步编号。
    require([row[4] for row in parsed] == expected_sequence, "SET 累计序号不是连续 1..59。")  # 核对第五列累计序号。
    return [row[1] for row in parsed]  # 返回 SET 打印精度频率列表，单位 Hz。


def count_vector_rows(path: Path) -> int:  # 定义 PRNSOL 数据行计数函数，输入单个向量文本，输出实际节点结果行数。
    """以二进制正则计数节点数据行，排除每页重复的 MAPDL 时间戳和页眉。"""  # 函数说明给出识别规则和输出含义。
    count = 0  # 初始化当前文件的实际节点结果行计数为零。
    with path.open("rb") as handle:  # 以二进制只读模式流式扫描，避免 7.5 MB 文件重复解码。
        for line in handle:  # 按原始换行逐行遍历当前 PRNSOL 文本。
            if VECTOR_DATA_PATTERN.match(line):  # 只有节点号后紧跟数值的行才属于结果数据。
                count += 1  # 对当前真实节点结果行累计一次。
    return count  # 返回不含页眉时间戳的实际节点数据行数。


def collect_vector_files() -> tuple[list[Path], list[Path], dict[str, int]]:  # 定义振型文件闭合函数，输出两类路径和逐文件节点行数。
    """发现 01..59 位移/转角文件，核验连续编号、非空、等大小和每份 91,407 行。"""  # 函数说明给出输入来源、输出和全部硬门禁。
    displacement_by_mode: dict[int, Path] = {}  # 以模态号索引位移文件，便于检测重复和缺号。
    rotation_by_mode: dict[int, Path] = {}  # 以模态号索引转角文件，便于检测重复和缺号。
    for path in SOLVER_DIR.glob("mode_*_all_nodes.txt"):  # 只扫描符合位移文件前缀和后缀的原 solver 文件。
        match = MODE_FILE_PATTERN.fullmatch(path.name)  # 从完整文件名提取十进制模态号。
        require(match is not None, f"无法解析位移文件名：{path.name}")  # 拒绝近似但不符合契约的文件名。
        mode = int(match.group(1))  # 把捕获的十进制文本转换为整数模态号。
        require(mode not in displacement_by_mode, f"位移模态 {mode} 出现重复文件。")  # 禁止同阶多个候选文件造成歧义。
        displacement_by_mode[mode] = path  # 保存当前模态到唯一位移文件的映射。
    for path in SOLVER_DIR.glob("mode_*_rotations.txt"):  # 只扫描符合转角文件前缀和后缀的原 solver 文件。
        match = ROTATION_FILE_PATTERN.fullmatch(path.name)  # 从完整文件名提取十进制模态号。
        require(match is not None, f"无法解析转角文件名：{path.name}")  # 拒绝近似但不符合契约的文件名。
        mode = int(match.group(1))  # 把捕获的十进制文本转换为整数模态号。
        require(mode not in rotation_by_mode, f"转角模态 {mode} 出现重复文件。")  # 禁止同阶多个候选文件造成歧义。
        rotation_by_mode[mode] = path  # 保存当前模态到唯一转角文件的映射。
    expected_modes = list(range(1, EXPECTED_MODE_COUNT + 1))  # 构造连续 1..59 的唯一合法文件编号序列。
    require(sorted(displacement_by_mode) == expected_modes, "位移向量文件编号不是连续 01..59。")  # 核对位移文件完整性。
    require(sorted(rotation_by_mode) == expected_modes, "转角向量文件编号不是连续 01..59。")  # 核对转角文件完整性。
    displacement_files = [displacement_by_mode[mode] for mode in expected_modes]  # 按模态号升序生成位移文件列表。
    rotation_files = [rotation_by_mode[mode] for mode in expected_modes]  # 按模态号升序生成转角文件列表。
    all_sizes = {path.stat().st_size for path in displacement_files + rotation_files}  # 收集 118 个文件的字节大小集合。
    require(all(size > 0 for size in all_sizes), "存在空振型向量文件。")  # 所有向量文件必须非空。
    require(len(all_sizes) == 1, "118 个振型向量文件的字节大小不一致。")  # 本次固定格式导出应产生相同大小文件。
    row_counts: dict[str, int] = {}  # 初始化文件名到实际节点结果行数的审计映射。
    for path in displacement_files + rotation_files:  # 逐个扫描全部 118 个向量文件而不是只抽样首尾阶。
        row_count = count_vector_rows(path)  # 计算当前文件排除页眉后的真实节点结果行数。
        require(row_count == EXPECTED_RESULT_NODES, f"{path.name} 的节点结果行数为 {row_count}，不是 {EXPECTED_RESULT_NODES}。")  # 每份文件必须覆盖同一求解自由度节点集合。
        row_counts[path.name] = row_count  # 保存已通过门禁的行数供机器摘要和报告使用。
    return displacement_files, rotation_files, row_counts  # 返回升序文件列表和完整逐文件行数映射。


def extract_value(text: str, label: str) -> float:  # 定义静力证据数值提取函数，输入文本和字段名，输出浮点值。
    """在行首或逗号后匹配 LABEL=数值；缺失字段时 fail-closed。"""  # 函数说明给出匹配边界、输出和异常路径。
    pattern = re.compile(rf"(?:^|,\s*){re.escape(label)}\s*=\s*({NUMERIC_TOKEN})", re.MULTILINE)  # 构造避免标签子串误匹配的多行正则。
    match = pattern.search(text)  # 在完整证据文本中查找第一个精确字段实例。
    require(match is not None, f"静力证据缺少字段 {label}。")  # 缺少任何必需字段都阻止打包。
    return float(match.group(1))  # 把捕获数值转换为双精度供门禁和摘要使用。


def parse_static_evidence(path: Path) -> dict[str, float]:  # 定义静力补证解析函数，输入纯数据文件，输出字段字典。
    """核验最终时间、能量比、质量、464 支承和反力闭合；接受已知账本 LS=1。"""  # 函数说明给出全部硬门禁及账本例外。
    text = read_text(path)  # 读取 *CFOPEN 生成的纯数据静力证据文本。
    values = {  # 构造统一字段字典供 JSON、Markdown 和门禁共同使用。
        "result_load_step": extract_value(text, "RESULT_LS"),  # 原 RST 最终结果账本载荷步实际为 1。
        "time": extract_value(text, "TIME"),  # 最终静力伪时间单位为 s。
        "sene_n_mm": extract_value(text, "SENE"),  # 全模型势能单位为 N·mm。
        "sten_n_mm": extract_value(text, "STEN"),  # 全模型稳定化耗散能单位为 N·mm。
        "sten_sene_ratio": extract_value(text, "STEN_SENE_RATIO"),  # 稳定化能量比无量纲。
        "mass_tonne": extract_value(text, "MASS"),  # 全模型 X 向平动质量单位为 tonne。
        "mass_expected_tonne": extract_value(text, "EXPECTED"),  # 封板质量基准单位为 tonne。
        "mass_abs_error_tonne": extract_value(text, "ABS_ERROR"),  # 质量绝对误差单位为 tonne。
        "uz_support_count": extract_value(text, "UZ_SUPPORT_COUNT"),  # UZ 支承节点整数数量。
        "rf_expected_n": extract_value(text, "RF_EXPECTED"),  # 理论重力反力单位为 N。
        "rf_actual_n": extract_value(text, "RF_ACTUAL"),  # 实际 UZ 支反力单位为 N。
        "rf_error_n": extract_value(text, "RF_ERROR"),  # 支反力有符号差单位为 N。
        "rf_relative_error": extract_value(text, "RF_RELATIVE_ERROR"),  # 支反力相对误差无量纲。
    }  # 结束静力数值字典。
    require(abs(values["time"] - EXPECTED_STATIC_TIME) <= 1.0e-12, "最终静力时间不是 1.001 s。")  # 时间采用 1E-12 s 绝对容差。
    require(values["sten_sene_ratio"] <= ENERGY_RATIO_LIMIT, "最终静力 STEN/SENE 超过 1E-8。")  # 稳定化残余能量必须通过硬门禁。
    require(abs(values["mass_expected_tonne"] - EXPECTED_MASS_TONNE) <= 1.0e-9, "静力证据质量基准漂移。")  # 证据内基准必须与封板值一致。
    require(values["mass_abs_error_tonne"] <= MASS_TOLERANCE_TONNE, "总质量绝对误差超过 1E-6 tonne。")  # 质量必须通过封板容差。
    require(int(round(values["uz_support_count"])) == 464, "UZ 支承节点数不是 464。")  # 支承数量必须恰好闭合。
    require(values["rf_relative_error"] <= REACTION_RATIO_LIMIT, "竖向支反力相对误差超过 1E-4。")  # 重力反力必须通过相对误差门禁。
    return values  # 返回全部已通过门禁的静力数值供摘要与报告使用。


def add_entry(entries: list[tuple[str, Path, str]], arc_relative: str, source: Path, role: str) -> None:  # 定义 ZIP 条目注册函数，输入列表、包内相对路径、来源和角色。
    """检查来源为非空文件且包内路径唯一，然后追加到稳定条目列表。"""  # 函数说明给出输入、输出副作用和硬门禁。
    require(source.is_file(), f"包内来源文件不存在：{source}")  # 所有注册来源必须是现有普通文件。
    require(source.stat().st_size > 0, f"包内来源文件为空：{source}")  # 禁止把空锁文件或空临时文件收入交付包。
    full_arcname = f"{ARCHIVE_ROOT}/{arc_relative}"  # 为每个条目添加单一顶层目录前缀。
    require(all(existing[0] != full_arcname for existing in entries), f"ZIP 内路径重复：{full_arcname}")  # 防止不同来源静默覆盖同名条目。
    entries.append((full_arcname, source, role))  # 按调用顺序追加唯一条目并保留中文角色说明。


def build_readme(first_frequency: float, last_frequency: float, static_values: dict[str, float]) -> str:  # 定义用户 README 构造函数，输入频率边界和静力数值，输出 Markdown。
    """返回包内入口说明，明确结论、权威层级、内容和超大二进制省略策略。"""  # 函数说明给出输入、输出和报告用途。
    return f"""# B00 0–0.35 Hz、59 阶交付包

## 结论

- 本包保留的是用户确认采用的 **0–0.35 Hz 频带内 59 阶**结果；59 阶来自频率上限，不是内存截断。
- 频率范围为 `{first_frequency:.17g}`–`{last_frequency:.17g}` Hz，59 个频率严格递增。
- 最终静力可恢复状态为 `TIME={static_values['time']:.16g}`；原结果账本仍记为 load step 1，这是已说明并在生成器中修正的编号缺陷。
- 静力补证通过：STEN/SENE=`{static_values['sten_sene_ratio']:.16e}`，质量误差=`{static_values['mass_abs_error_tonne']:.16e}` tonne，UZ 支承 464 个，反力相对误差=`{static_values['rf_relative_error']:.16e}`。
- 59 对位移/转角文本均完整收入，每份含 91,407 个具有求解自由度的节点结果；另有 17,679 个 BEAM188 方向节点不具有位移结果，二者合计 109,086 个拓扑节点。

## 权威层级

1. `00_说明/关键结果摘要.json`、`00_说明/未对齐项与修正.md` 和 `00_说明/包内文件清单.csv` 是本次整理后的权威说明。
2. `03_静力结果/静力补证/` 是对原 RST 的只读 POST1 重算证据，0 ERROR、0 WARNING。
3. `04_模态结果/b00_modal_properties_clean.csv` 是从原始污染文件中确定性提取的 59 行、15 列 canonical 数据。
4. 原 `B00_status.json` 和 `result_packet.md` 仍保留准备期状态，仅作为历史谱系证据，不代表最终执行状态。

## 包内主要内容

- `01_原始输入/`：本次原 solver 的全部 14 个 INP。
- `02_修正输入与代码/`：修正前/后生成器、取消的无上限 80 阶续算输入、静力补证 INP。
- `03_静力结果/`：master RST、主日志、拓扑/约束证据和最终静力补证。
- `04_模态结果/`：modal DB、59 阶 SET、原始/清洗属性、续算日志和状态。
- `05_振型向量/`：59 对全节点位移与转角文本。
- `06_谱系与历史状态/`：manifest、准备期状态、哈希和字段字典。

## 容量策略

为满足 ZIP 小于 512 MB，RSTP、MODE、FULL、ESAV、EMAT、RDB/R001、worker RST 等大二进制不收入本包；`00_说明/未收入大文件_SHA256.csv` 逐项记录其原路径、字节数和 SHA-256。master 静力 RST、modal DB 与全部文本振型已收入，足以复核本次 59 阶交付结果。

## 工程有效性边界

legacy 模型包含 5,078 条 CERIG 且启用 `NLGEOM,ON`；MAPDL 已给出大变形约束方程警告。因此本包可作为 legacy 基线计算与审计证据，但不应宣称为已消除该建模兼容性问题的严格工程有效结果。
"""  # 返回完整 Markdown 入口文档并以单一换行结束。


def build_discrepancy_report(first_frequency: float, last_frequency: float, max_frequency_difference: float, static_values: dict[str, float]) -> str:  # 定义差异报告构造函数，输入关键数值，输出 Markdown。
    """返回逐项描述原问题、证据、当前处理和剩余边界的报告。"""  # 函数说明给出输入、输出和用户要求的“哪里没对上”语义。
    return f"""# 未对齐项与本次修正

| 项目 | 原始现象 | 原因 | 本次处理 | 当前结论 |
|---|---|---|---|---|
| 静力载荷步编号 | 主 run 在 `SET,2,LAST` 报 `Load set not found`，主输出最终 1 ERROR | 两次 `SOLVE` 之间执行了 `FINISH` 后重新 `/SOLU`，第二次求解仍写为 load step 1 | 修正生成器，使 LS1 后保持同一 `/SOLU`；对现有 RST 另做只读 POST1 补证 | 现有最终状态实际为 LS1/SS1/TIME={static_values['time']:.16g}，物理闭合通过，但历史账本编号不追写 |
| 80 阶请求与 59 阶结果 | `REQUESTED=80, AVAILABLE=59, EXPORTED=59` | 原 `MODOPT,LANB,80,0,0.35` 只允许 0–0.35 Hz；第 59 阶 `{last_frequency:.17g}` Hz 已接近上限 | 生成器改为无频率上限并增加严格阶数门禁；用户随后确认无需超出 0.35 Hz，80 阶临时续算已停止 | 本包按用户决定交付频带内 59 阶；不是内存导致缺阶 |
| 模态属性 CSV | 原文件 2,111 行，混入 `*IF/*GET` 命令回显 | 使用 `/OUTPUT` 时未抑制批处理回显 | 生成器增加 `/NOPR`/`/GOPR`；本包确定性提取恰 59 条、每条 15 列纯数值行 | canonical 文件为 `b00_modal_properties_clean.csv`；频率 `{first_frequency:.17g}`–`{last_frequency:.17g}` Hz |
| SET 与高精度频率 | SET LIST 仅显示有限小数位 | 原生索引表输出精度低于 E24.16 属性文件 | 逐阶比对 59 项 | 最大绝对差 `{max_frequency_difference:.16e}` Hz，小于 5.1E-9 Hz 容差，仅为显示舍入 |
| `all_nodes` 文件行数 | 每份 PRNSOL 文本只有 91,407 个节点结果，不是拓扑 109,086 行 | TYPE70 的 17,679 个 BEAM188 方向节点无位移自由度，PRNSOL 不输出其结果 | 全量扫描 118 个文件并核对每份 91,407 行 | 91,407 + 17,679 = 109,086，拓扑闭合；文件名含义应理解为“全部有结果节点” |
| 静力 gate 被旁路 | 模态续算从源第 473 行开始，直接进入扰动，原 `SOLVER_EXPORT_COMPLETED` 不能证明静力门禁 | 原主 run 在静力 POST1 中途错误退出 | 新增只读静力 POST1 作业并用 `*CFOPEN` 写纯证据 | STEN/SENE=`{static_values['sten_sene_ratio']:.16e}`，质量误差=`{static_values['mass_abs_error_tonne']:.16e}` tonne，反力相对误差=`{static_values['rf_relative_error']:.16e}`，均通过 |
| 反力 `*VWRITE` | 原生成器把四个长字段写在同一记录 | 长记录不利于跨版本解析和审计 | 修正生成器，拆为“期望/实际”和“误差/相对误差”两行 | 静力补证文件使用分行格式并已成功运行 |
| 根状态元数据 | `B00_status.json` 仍写 `PREPARED_NOT_STARTED` | prepare-only 脚本设计为封板后不再覆写 | 原文件保留为历史证据；本包另写关键结果摘要和最终 ZIP 状态 | 不再把准备期 JSON 当作运行终态 |
| legacy 建模兼容性 | 5,078 条 CERIG 与 `NLGEOM,ON` 同时存在 | MAPDL 对大变形下约束方程给出警告 | 未擅自改变 legacy 模型线；在交付说明中明确边界 | 数值结果可作 legacy 基线，不宣称已消除工程有效性风险 |
| 无上限 80 阶临时续算 | C 盘临时续算已进入 Block Lanczos，但尚未形成最终模态结果 | 用户确认 0–0.35 Hz 内 59 阶即可，明确取消继续计算 | 已停止该作业全部相关进程；仅收入其修正 INP，不收入任何不完整 scratch | 不把临时 80 阶作业视为计算结果，也不混入本包 59 阶数据 |
"""  # 返回完整 Markdown 差异台账并以单一换行结束。


def main() -> None:  # 定义唯一打包主流程，无参数，产出交付目录、ZIP 和外部状态 JSON。
    """验证 59 阶与静力证据、生成说明、压缩选定文件并执行 500 MB 硬门禁。"""  # 主流程说明给出输入、输出和终止条件。
    require(RUN_DIR.is_dir(), f"固定 B00 run 不存在：{RUN_DIR}")  # 固定 run 目录必须存在且不可通配替代。
    require(SOLVER_DIR.is_dir(), f"固定 solver 目录不存在：{SOLVER_DIR}")  # 原始 solver 结果目录必须存在。
    require(STATIC_QA_DIR.is_dir(), f"静力补证目录不存在：{STATIC_QA_DIR}")  # 静力 POST1 补证必须已完成。
    require(CANCELLED_80_DIR.is_dir(), f"80 阶修正输入目录不存在：{CANCELLED_80_DIR}")  # 当前修正输入必须可纳入交付。
    require(not DELIVERY_DIR.exists(), f"交付说明目录已存在，拒绝覆盖：{DELIVERY_DIR}")  # 禁止覆盖任何既有交付目录。
    require(not ARCHIVE_PATH.exists(), f"目标 ZIP 已存在，拒绝覆盖：{ARCHIVE_PATH}")  # 禁止覆盖任何既有 ZIP。
    DELIVERY_DIR.mkdir(parents=False, exist_ok=False)  # 在已存在的 run 下排他创建唯一交付说明目录。

    raw_properties_path = SOLVER_DIR / "b00_modal_properties.csv"  # 原始污染模态属性文件用于 canonical 提取。
    clean_lines, numeric_rows = parse_modal_properties(raw_properties_path)  # 提取并核验 59 条高精度、15 列数值记录。
    clean_properties_path = DELIVERY_DIR / "b00_modal_properties_clean.csv"  # canonical CSV 保存位置位于交付说明目录。
    write_new_text(clean_properties_path, "\n".join(clean_lines) + "\n")  # 写出无表头纯数值 CSV 并保留原始 E24.16 精度。
    modal_frequencies = [row[1] for row in numeric_rows]  # 从 canonical 第二列取得 59 个高精度频率，单位 Hz。
    set_frequencies = parse_set_frequencies(SOLVER_DIR / "b00_modal_set_list.txt")  # 解析原生 SET LIST 的 59 个显示频率。
    frequency_differences = [abs(high_precision - printed) for high_precision, printed in zip(modal_frequencies, set_frequencies, strict=True)]  # 逐阶计算高精度与 SET 显示值差，单位 Hz。
    max_frequency_difference = max(frequency_differences)  # 读取 59 项中的最大绝对显示差供门禁和报告。
    require(max_frequency_difference <= SET_FREQUENCY_TOLERANCE_HZ, "SET LIST 与高精度频率差超过 5.1E-9 Hz。")  # 只允许原生打印舍入量级差异。

    displacement_files, rotation_files, vector_row_counts = collect_vector_files()  # 全量核验 59 对振型文件和每份节点结果行数。
    require(EXPECTED_RESULT_NODES + EXPECTED_ORIENTATION_NODES == EXPECTED_TOPOLOGY_NODES, "结果节点与方向节点不能闭合拓扑节点数。")  # 核对 91,407 + 17,679 = 109,086。
    topology_text = read_text(SOLVER_DIR / "b00_topology_counts.txt")  # 读取运行期拓扑计数证据。
    require("NODE_COUNT=     109086." in topology_text, "拓扑证据节点数不是 109086。")  # 防止常量与原运行证据脱节。
    require("TYPE70=      17679." in topology_text, "拓扑证据 TYPE70 数不是 17679。")  # 防止方向节点解释与原运行证据脱节。

    static_evidence_path = STATIC_QA_DIR / "b00_static_final_evidence.txt"  # 纯数据静力补证文件是最终物理门禁来源。
    static_values = parse_static_evidence(static_evidence_path)  # 解析并硬核验时间、能量、质量、支承和反力。
    static_out_text = read_text(STATIC_QA_DIR / "b00_static_final_qa.out")  # 读取静力补证主输出核对正常结束摘要。
    require("NUMBER OF WARNING MESSAGES ENCOUNTERED=          0" in static_out_text, "静力补证 warning 数不是 0。")  # 补证必须零警告。
    require("NUMBER OF ERROR   MESSAGES ENCOUNTERED=          0" in static_out_text, "静力补证 error 数不是 0。")  # 补证必须零错误。
    require("RUN COMPLETED" in static_out_text, "静力补证没有 RUN COMPLETED。")  # 补证必须正常退出。

    modal_out_path = SOLVER_DIR / "cw_b00_0715t111105_ca_modal_resume.out"  # 59 阶成功续算主输出是模态运行终态证据。
    modal_out_text = read_text(modal_out_path)  # 读取模态续算主输出核对零错误和正常完成。
    require("NUMBER OF ERROR   MESSAGES ENCOUNTERED=          0" in modal_out_text, "59 阶模态续算 error 数不是 0。")  # 模态续算必须零错误。
    require("RUN COMPLETED" in modal_out_text, "59 阶模态续算没有 RUN COMPLETED。")  # 模态续算必须正常退出。
    require("Fewer modes than the requested number of modes ( 80 ) were computed." in modal_out_text, "模态日志缺少频带内少于 80 阶的明确 warning。")  # 固化 59 阶来自频带截断的运行期证据。

    generated_utc = datetime.now(timezone.utc).isoformat()  # 记录本次交付构建 UTC 时间并保留时区偏移。
    summary_payload = {  # 构造 JSON 机器摘要；字段逐项由相邻 README 和本行中文注释说明。
        "schema_version": 1,  # 首版 B00 59 阶交付摘要结构。
        "generated_utc": generated_utc,  # 交付包构建时间使用 ISO 8601 UTC。
        "source_run": RUN_NAME,  # 绑定唯一原始 B00 run 名称。
        "scope": "0-0.35 Hz band, 59 modes",  # 明确本包不宣称无上限 80 阶结果。
        "user_accepted_59_modes_in_band": True,  # 记录用户明确确认无需继续 80 阶续算。
        "mode_count": EXPECTED_MODE_COUNT,  # canonical、SET 和向量文件共同闭合的阶数。
        "frequency_first_hz": modal_frequencies[0],  # 第一阶高精度频率单位为 Hz。
        "frequency_last_hz": modal_frequencies[-1],  # 第 59 阶高精度频率单位为 Hz。
        "frequencies_strictly_increasing": True,  # 59 个高精度频率已逐项严格递增核验。
        "set_frequency_max_abs_difference_hz": max_frequency_difference,  # SET 显示与高精度属性最大差单位为 Hz。
        "modal_properties_rows": len(clean_lines),  # canonical CSV 物理行数为 59。
        "modal_properties_columns": 15,  # 每阶列数固定为 mode、FREQ、GENM、6 PFACT、6 EFFM。
        "displacement_file_count": len(displacement_files),  # 全节点位移文件数为 59。
        "rotation_file_count": len(rotation_files),  # 全节点转角文件数为 59。
        "result_nodes_per_vector_file": EXPECTED_RESULT_NODES,  # 每份 PRNSOL 文本实际有结果节点数为 91,407。
        "beam188_orientation_nodes_without_displacement_results": EXPECTED_ORIENTATION_NODES,  # 无位移自由度方向节点数为 17,679。
        "topology_node_count": EXPECTED_TOPOLOGY_NODES,  # 完整拓扑节点数为 109,086。
        "static_final": static_values,  # 嵌入已通过门禁的最终静力数值和单位化字段。
        "original_static_main_out_errors": 1,  # 原主 run 因 SET,2,LAST 后处理失败最终记录 1 个 error。
        "modal_resume_errors": 0,  # 59 阶成功续算最终记录 0 个 error。
        "static_post1_qa_errors": 0,  # 只读静力补证最终记录 0 个 error。
        "cancelled_unbounded_80_mode_run_included": False,  # 已停止临时作业的不完整 scratch 不混入结果。
        "legacy_cerig_nlgeom_engineering_validity_resolved": False,  # legacy CERIG 与大变形兼容性风险仍未消除。
    }  # 结束机器摘要对象。
    summary_path = DELIVERY_DIR / "关键结果摘要.json"  # JSON 摘要保存在交付说明目录并由 README 解释字段。
    write_new_json(summary_path, summary_payload)  # 排他写入有效 JSON，不插入非法注释。

    readme_path = DELIVERY_DIR / "README.md"  # 用户入口 Markdown 保存位置。
    write_new_text(readme_path, build_readme(modal_frequencies[0], modal_frequencies[-1], static_values))  # 写入结论、内容、容量和工程边界说明。
    discrepancy_path = DELIVERY_DIR / "未对齐项与修正.md"  # 用户要求的差异台账保存位置。
    write_new_text(discrepancy_path, build_discrepancy_report(modal_frequencies[0], modal_frequencies[-1], max_frequency_difference, static_values))  # 写入逐项原因、修正和剩余边界。
    fields_path = DELIVERY_DIR / "canonical字段说明.md"  # canonical CSV 相邻字段字典保存位置。
    fields_text = """# b00_modal_properties_clean.csv 字段说明

该 CSV 无表头，共 59 行、每行 15 列；不在 CSV 内插入注释以保持有效性。

1. mode：模态号，整数 1..59。
2. frequency_hz：频率，单位 Hz，E24.16 文本精度。
3. generalized_mass：MAPDL 官方 generalized mass。
4–9. pfx、pfy、pfz、pfrotx、pfroty、pfrotz：六个全局方向 participation factor。
10–15. emx、emy、emz、emrotx、emroty、emrotz：六个全局方向 effective mass。
"""  # 字段字典逐项解释无表头 CSV 的列序、单位和来源。
    write_new_text(fields_path, fields_text)  # 排他写入 canonical CSV 相邻 Markdown 说明。

    entries: list[tuple[str, Path, str]] = []  # 初始化 ZIP 条目列表，元素依次为包内路径、来源路径和角色说明。
    for input_path in sorted(SOLVER_DIR.glob("*.inp"), key=lambda path: path.name.lower()):  # 按文件名稳定排序收入原 solver 全部 14 个 INP。
        add_entry(entries, f"01_原始输入/{input_path.name}", input_path, "原 B00 solver 输入")  # 把每个原始 INP 放入统一输入目录。

    old_generator_path = RUN_DIR / "orchestrator_snapshot" / "ultra_b00_prepare.py"  # 原 run 快照保留修正前生成逻辑。
    current_generator_path = TOOLS_DIR / "ultra_b00_prepare.py"  # 当前工具目录保存本次修正后的生成器。
    add_entry(entries, "02_修正输入与代码/修正前_ultra_b00_prepare.py", old_generator_path, "修正前 prepare-only 生成器快照")  # 收入修正前版本供逐字节比较。
    add_entry(entries, "02_修正输入与代码/修正后_ultra_b00_prepare.py", current_generator_path, "修正后 prepare-only 生成器")  # 收入修正后版本供未来重建。
    add_entry(entries, "02_修正输入与代码/打包脚本_ultra_b00_package.py", SCRIPT_PATH, "本次可复现打包与 QA 脚本")  # 收入当前脚本作为清洗、核验和 ZIP 生成证据。
    add_entry(entries, "02_修正输入与代码/已取消80阶续算/b00_legacy_complete_modal_resume.inp", CANCELLED_80_DIR / "b00_legacy_complete_modal_resume.inp", "取消作业的修正入口 INP")  # 收入不含结果的无上限 80 阶入口。
    add_entry(entries, "02_修正输入与代码/已取消80阶续算/b00_legacy_complete_modal_resume_source.inp", CANCELLED_80_DIR / "b00_legacy_complete_modal_resume_source.inp", "取消作业的无频率上限严格 80 阶源 INP")  # 收入修正源用于说明本次更改。
    add_entry(entries, "02_修正输入与代码/静力补证/b00_static_final_qa.inp", STATIC_QA_DIR / "b00_static_final_qa.inp", "只读 POST1 静力补证输入")  # 收入实际成功运行的静力补证 INP。

    add_entry(entries, "03_静力结果/cw_B00_0715t111105_ca.rst", SOLVER_DIR / "cw_B00_0715t111105_ca.rst", "master 静力结果文件")  # 收入可移植的 master RST 作为核心静力二进制。
    add_entry(entries, "03_静力结果/cw_b00_0715t111105_ca.out", SOLVER_DIR / "cw_b00_0715t111105_ca.out", "原静力主输出，含 SET2 后处理错误")  # 收入原主日志以保留错误证据。
    for evidence_name in ("b00_topology_counts.txt", "b00_constraint_equations.txt", "b00_coupled_dof.txt", "b00_displacement_constraints.txt"):  # 枚举四份运行期拓扑与约束证据。
        add_entry(entries, f"03_静力结果/原运行证据/{evidence_name}", SOLVER_DIR / evidence_name, "原运行拓扑或约束证据")  # 按原文件名收入静力证据子目录。
    for qa_name in ("b00_static_final_qa.inp", "b00_static_final_qa.out", "b00_static_final_qa.err", "b00_static_final_qa.log", "b00_static_final_evidence.txt", "b00_static_set_list.txt"):  # 枚举静力补证输入、日志和纯数据结果。
        add_entry(entries, f"03_静力结果/静力补证/{qa_name}", STATIC_QA_DIR / qa_name, "只读 POST1 静力补证")  # 收入补证全链路且不重复原 RST 副本。

    add_entry(entries, "04_模态结果/cw_B00_0715t111105_ca_modal.db", SOLVER_DIR / "cw_B00_0715t111105_ca_modal.db", "完成 59 阶导出的 modal 数据库")  # 收入高压缩率 modal DB 作为核心模态二进制。
    add_entry(entries, "04_模态结果/cw_b00_0715t111105_ca_modal_resume.out", modal_out_path, "59 阶模态续算主输出")  # 收入 0 error 正常完成的续算日志。
    for worker_index in range(1, 4):  # 枚举 DMP worker 1..3 的输出与错误日志。
        add_entry(entries, f"04_模态结果/worker/cw_B00_0715t111105_ca{worker_index}.out", SOLVER_DIR / f"cw_B00_0715t111105_ca{worker_index}.out", "DMP worker 输出")  # 收入当前 worker 主输出。
        add_entry(entries, f"04_模态结果/worker/cw_B00_0715t111105_ca{worker_index}.err", SOLVER_DIR / f"cw_B00_0715t111105_ca{worker_index}.err", "DMP worker 错误流")  # 收入当前 worker 错误流摘要。
    add_entry(entries, "04_模态结果/worker/cw_B00_0715t111105_ca0.err", SOLVER_DIR / "cw_B00_0715t111105_ca0.err", "master 错误流，含历史主 run 错误和模态 warning")  # 收入 master 错误流供审计。
    add_entry(entries, "04_模态结果/worker/cw_B00_0715t111105_ca0.log", SOLVER_DIR / "cw_B00_0715t111105_ca0.log", "master DMP 日志")  # 收入 master 日志供进程追溯。
    for result_name in ("b00_gate_status.txt", "b00_modal_export_manifest.txt", "b00_modal_set_list.txt", "b00_modal_properties.csv"):  # 枚举原 solver 模态状态、索引和属性文件。
        add_entry(entries, f"04_模态结果/原始/{result_name}", SOLVER_DIR / result_name, "原始模态状态或属性证据")  # 收入原始文件且不把污染 CSV 伪装为 canonical。
    add_entry(entries, "04_模态结果/b00_modal_properties_clean.csv", clean_properties_path, "59 行 15 列 canonical 模态属性")  # 收入确定性清洗后的权威属性 CSV。
    add_entry(entries, "04_模态结果/b00_modal_properties_clean_字段说明.md", fields_path, "canonical CSV 相邻字段字典")  # 收入 CSV 字段、单位和列序说明。

    for path in displacement_files:  # 按模态号升序收入 59 个位移向量文件。
        add_entry(entries, f"05_振型向量/位移/{path.name}", path, "全有结果节点位移 PRNSOL")  # 保留原文件名和全部 91,407 行节点结果。
    for path in rotation_files:  # 按模态号升序收入 59 个转角向量文件。
        add_entry(entries, f"05_振型向量/转角/{path.name}", path, "全有结果节点转角 PRNSOL")  # 保留原文件名和全部 91,407 行节点结果。

    root_evidence_names = ("manifest.json", "B00_status.json", "artifact_hashes.sha256", "source_hashes.sha256", "launch_command.txt", "result_packet.md")  # 枚举根级谱系和历史准备状态文件。
    for evidence_name in root_evidence_names:  # 按固定顺序收入全部根级历史证据。
        add_entry(entries, f"06_谱系与历史状态/{evidence_name}", RUN_DIR / evidence_name, "原 run 谱系或准备期历史状态")  # README 已明确这些状态不代表最终运行终态。
    for qa_name in ("preflight.json", "field_dictionary.md"):  # 枚举准备期 QA 快照和字段字典。
        add_entry(entries, f"06_谱系与历史状态/qa/{qa_name}", RUN_DIR / "qa" / qa_name, "准备期 QA 历史证据")  # 收入 QA 文件供来源追溯。

    included_sources = {source.resolve() for _, source, _ in entries}  # 构造当前已收入来源绝对路径集合用于大文件排除筛选。
    excluded_rows: list[list[object]] = []  # 初始化未收入大文件的路径、大小、哈希和原因记录。
    excluded_minimum_bytes = 50 * 1024 * 1024  # 仅对不小于 50 MiB 的未收入 solver 文件计算并封存摘要。
    for path in sorted((candidate for candidate in SOLVER_DIR.iterdir() if candidate.is_file()), key=lambda candidate: candidate.name.lower()):  # 稳定遍历 solver 顶层全部普通文件。
        if path.resolve() in included_sources:  # 已收入 RST、modal DB 和文本结果不属于排除清单。
            continue  # 跳过已收入来源，避免同时声称包含和排除。
        size_bytes = path.stat().st_size  # 读取当前候选原始字节数用于 50 MiB 门槛。
        if size_bytes < excluded_minimum_bytes:  # 小于 50 MiB 的临时小文件既非核心结果也不需昂贵哈希替代。
            continue  # 跳过小型未选文件并继续扫描。
        excluded_rows.append([str(path), size_bytes, sha256_file(path), "为满足小于512MB而省略的大型求解器二进制或分区文件"])  # 计算完整摘要并记录绝对源路径、字节数和原因。
    excluded_path = DELIVERY_DIR / "未收入大文件_SHA256.csv"  # 大文件排除清单保存位置。
    write_new_text(excluded_path, render_csv(["source_path", "bytes", "sha256", "reason"], excluded_rows))  # 写出有效 CSV 并由 README 解释字段。

    add_entry(entries, "00_说明/README.md", readme_path, "交付包入口说明")  # 收入用户首先阅读的结论和范围说明。
    add_entry(entries, "00_说明/未对齐项与修正.md", discrepancy_path, "问题、原因、修正和剩余边界台账")  # 收入用户要求的未对齐项说明。
    add_entry(entries, "00_说明/关键结果摘要.json", summary_path, "机器可读关键结果摘要")  # 收入不带非法注释的 JSON 摘要。
    add_entry(entries, "00_说明/未收入大文件_SHA256.csv", excluded_path, "省略大二进制的大小和 SHA-256 清单")  # 收入大文件替代校验清单。

    inventory_rows: list[list[object]] = []  # 初始化包内条目路径、来源、大小、SHA-256 和角色记录。
    for arcname, source, role in entries:  # 按最终 ZIP 稳定顺序逐项计算已收入来源摘要。
        inventory_rows.append([arcname, str(source), source.stat().st_size, sha256_file(source), role])  # 写入单条完整可追溯记录。
    inventory_path = DELIVERY_DIR / "包内文件清单.csv"  # 包内文件清单保存位置；为避免自引用不列出自身摘要。
    write_new_text(inventory_path, render_csv(["archive_path", "source_path", "bytes", "sha256", "role"], inventory_rows))  # 写出全部先前注册条目清单。
    add_entry(entries, "00_说明/包内文件清单.csv", inventory_path, "包内条目清单；按设计不自列自身摘要")  # 最后加入清单本身并明确自引用例外。

    with zipfile.ZipFile(ARCHIVE_PATH, mode="x", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as archive:  # 排他创建标准 ZIP64 并使用最高 Deflate 压缩级别。
        for arcname, source, _role in entries:  # 按稳定注册顺序逐个压缩全部核心结果和说明文件。
            archive.write(source, arcname=arcname)  # 读取原文件并写入唯一包内路径，不修改来源内容。
    archive_bytes = ARCHIVE_PATH.stat().st_size  # 读取最终 ZIP 实际字节数用于用户硬门禁。
    require(archive_bytes < MAX_ARCHIVE_BYTES, f"最终 ZIP 为 {archive_bytes} byte，不小于 500,000,000 byte。")  # 超过 500 MB 时拒绝宣告完成。
    archive_sha256 = sha256_file(ARCHIVE_PATH)  # 对最终 ZIP 全字节计算交付摘要。
    final_status = {  # 构造 ZIP 外部机器状态，便于无需解压即可核对路径、大小和摘要。
        "status": "COMPLETED",  # 仅在全部 QA、压缩和容量门禁通过后写 COMPLETED。
        "archive_path": str(ARCHIVE_PATH),  # 最终 ZIP 绝对路径。
        "archive_bytes": archive_bytes,  # 最终 ZIP 精确字节数。
        "archive_mib": archive_bytes / (1024**2),  # 最终 ZIP 二进制 MiB 大小。
        "maximum_bytes_exclusive": MAX_ARCHIVE_BYTES,  # 硬上限为 500,000,000 byte 且比较为严格小于。
        "sha256": archive_sha256,  # 最终 ZIP 64 位小写 SHA-256。
        "zip_entry_count": len(entries),  # ZIP 内普通文件条目总数。
        "excluded_large_file_count": len(excluded_rows),  # 以哈希清单替代的 >=50 MiB 大文件数量。
        "generated_utc": generated_utc,  # 与包内关键摘要一致的构建 UTC 时间。
    }  # 结束最终 ZIP 状态对象。
    status_path = DELIVERY_DIR / "交付ZIP状态.json"  # ZIP 外部状态 JSON 保存位置。
    write_new_json(status_path, final_status)  # 排他写入最终路径、大小、条目数和哈希。
    print(json.dumps(final_status, ensure_ascii=False, indent=2))  # 向调用终端打印同一状态供即时人工核验。


if __name__ == "__main__":  # 仅直接执行本脚本时进入打包流程，导入审阅不会产生文件。
    main()  # 执行唯一主流程并由未捕获 PackageError 以非零退出阻止假成功。
