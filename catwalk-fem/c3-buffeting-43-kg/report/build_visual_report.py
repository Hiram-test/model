from __future__ import annotations  # 启用现代类型注解并保持脚本接口清晰。
import csv  # 读取代表性工况冻结统计表。
import hashlib  # 为统计一致重建生成稳定随机种子与图谱抖动。
import json  # 读取已验收的 C3 知识图谱与收据。
import subprocess  # 调用 Ghostscript 压缩最终 PDF 并嵌入可移植字体。
from pathlib import Path  # 构造与脚本位置绑定的稳定文件路径。
from typing import Any  # 标注结构化工况与图谱记录。
import matplotlib.pyplot as plt  # 绘制时程、统计对比和架构图。
import numpy as np  # 生成确定性的带限随机时程。
from matplotlib.collections import LineCollection  # 高效绘制知识图谱全部关系。
from matplotlib.font_manager import FontProperties  # 加载支持中文的 Noto 字体。
from matplotlib.patches import FancyArrowPatch  # 绘制智能体决策方向箭头。
from matplotlib.patches import FancyBboxPatch  # 绘制智能体架构圆角框。
from reportlab.lib.colors import Color  # 定义 PDF 的统一配色。
from reportlab.lib.colors import HexColor  # 从十六进制色值建立 PDF 颜色。
from reportlab.lib.pagesizes import A4  # 使用标准 A4 页面尺寸。
from reportlab.pdfbase import pdfmetrics  # 注册并测量 PDF 中文字体。
from reportlab.pdfgen import canvas  # 逐页生成可控排版的 PDF。
from reportlab.pdfbase.ttfonts import TTFont  # 嵌入可跨平台渲染的中文 TrueType 字体。

ROOT = Path(__file__).resolve().parents[1]  # 指向 c3-buffeting-43-kg 包目录。
REPORT_DIR = ROOT / "report"  # 保存报告脚本、输入统计和图像资产。
ASSET_DIR = REPORT_DIR / "assets"  # 保存高分辨率图表与架构图。
OUTPUT_DIR = ROOT / "output" / "pdf"  # 按 PDF 技能约定保存最终文件。
OUTPUT_PDF = OUTPUT_DIR / "张靖皋猫道_C3_43工况抖振知识图谱智能体_可视化报告.pdf"  # 固定最终 PDF 文件名。
TEMP_PDF = OUTPUT_DIR / ".c3_visual_report_uncompressed.pdf"  # 保存压缩前的临时 PDF 并在成功后删除。
STATS_CSV = REPORT_DIR / "representative_legacy_response_stats.csv"  # 指向四个代表工况的冻结统计表。
GRAPH_JSON = ROOT / "generated" / "knowledge_graph_c3.json"  # 指向 564 节点的已验收 C3 图谱。
ACCEPTANCE_JSON = ROOT / "generated" / "migration_acceptance.json"  # 指向模型迁移验收收据。
VALIDATION_JSON = ROOT / "generated" / "validation.json"  # 指向图谱完整性校验收据。
FONT_PATH = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")  # 使用支持简体中文的 Noto 字体。
FONT_PROP = FontProperties(fname=str(FONT_PATH))  # 建立 Matplotlib 中文字体属性。
PDF_FONT_PATH = Path("/usr/share/fonts/truetype/arphic-gbsn00lp/gbsn00lp.ttf")  # 使用可嵌入的简体中文 TrueType 字体。
PDF_FONT = "GBSongEmbedded"  # 定义报告内嵌中文字体名。
PAGE_W, PAGE_H = A4[1], A4[0]  # 使用横向 A4 以容纳时程和图谱。
NAVY = "#17324D"  # 定义主标题深蓝色。
BLUE = "#2A6F97"  # 定义 C3 模型与智能体蓝色。
CYAN = "#61A5C2"  # 定义来源和图谱关系浅蓝色。
ORANGE = "#E07A5F"  # 定义旧模型来源与边界提示橙色。
GREEN = "#4C956C"  # 定义通过状态绿色。
GRAY = "#6B7280"  # 定义辅助文字灰色。
LIGHT = "#F3F6F9"  # 定义页面浅灰背景色。
CASE_COLORS = ["#2A6F97", "#4C956C", "#E07A5F", "#7B6D8D"]  # 固定四个代表工况配色。
CHANNELS = {"lateral": ("lateral_mean_m", "lateral_sigma_m", "横向共同位移", "m", 0.10), "vertical": ("vertical_mean_m", "vertical_sigma_m", "竖向共同位移", "m", 0.18), "roll": ("roll_mean_deg", "roll_sigma_deg", "系统滚转", "°", 0.12)}  # 定义三类响应统计字段与重建带宽。


def configure_fonts() -> None:  # 配置 Matplotlib 与 ReportLab 的中文字体。
    plt.rcParams["font.family"] = FONT_PROP.get_name()  # 让所有 Matplotlib 文本使用 Noto 中文字体。
    plt.rcParams["axes.unicode_minus"] = False  # 保证负号在中文字体环境下正常显示。
    pdfmetrics.registerFont(TTFont(PDF_FONT, str(PDF_FONT_PATH)))  # 注册并内嵌简体中文 TrueType 字体。


def load_stats() -> list[dict[str, Any]]:  # 读取并类型化四个代表工况统计量。
    numeric_fields = {"U10_mps", "U_deck_mps", "Iu", "duration_s", "dt_s", "lateral_mean_m", "lateral_sigma_m", "vertical_mean_m", "vertical_sigma_m", "roll_mean_deg", "roll_sigma_deg"}  # 固定需要转换为浮点数的列。
    rows: list[dict[str, Any]] = []  # 初始化稳定顺序的工况列表。
    with STATS_CSV.open("r", encoding="utf-8", newline="") as handle:  # 打开冻结统计表。
        for raw in csv.DictReader(handle):  # 按 CSV 顺序遍历四个代表工况。
            row: dict[str, Any] = dict(raw)  # 复制原始文本字段以保留谱系。
            for field in numeric_fields:  # 类型化所有数值列。
                row[field] = float(raw[field])  # 将冻结数值转换为浮点数。
            row["c3_stationary_eligible"] = raw["c3_stationary_eligible"].lower() == "true"  # 类型化 C3 平稳映射适用性。
            rows.append(row)  # 追加类型化工况。
    return rows  # 返回四个代表工况。


def stable_seed(case_id: str, channel: str) -> int:  # 为每个工况和响应通道生成稳定随机种子。
    digest = hashlib.sha256(f"{case_id}:{channel}:C3-VISUAL-20260830".encode("utf-8")).hexdigest()  # 计算不可变种子摘要。
    return int(digest[:8], 16)  # 将摘要前八位转换为 NumPy 种子。


def statistic_matched_series(row: dict[str, Any], channel: str) -> tuple[np.ndarray, np.ndarray]:  # 重建与源均值和标准差一致的示例时程。
    mean_field, sigma_field, _, _, cutoff_hz = CHANNELS[channel]  # 读取目标统计字段和带限参数。
    dt = float(row["dt_s"])  # 读取源冻结时间步长。
    duration = float(row["duration_s"])  # 读取源冻结分析时长。
    sample_count = int(round(duration / dt))  # 计算与源矩阵一致的样本数。
    time = np.arange(sample_count, dtype=float) * dt  # 建立零起点时间轴。
    rng = np.random.default_rng(stable_seed(str(row["case_id"]), channel))  # 建立确定性随机数发生器。
    white = rng.standard_normal(sample_count)  # 生成零均值单位方差白噪声。
    frequency = np.fft.rfftfreq(sample_count, d=dt)  # 建立实数快速傅里叶频率轴。
    shaping = 1.0 / np.sqrt(1.0 + np.power(frequency / cutoff_hz, 4.0))  # 构造平滑低频主导带限形状。
    shaping[0] = 0.0  # 删除随机过程的直流分量以便精确控制均值。
    spectrum = np.fft.rfft(white) * shaping  # 在频域施加带限形状。
    fluctuation = np.fft.irfft(spectrum, n=sample_count)  # 变换回实数时域。
    if row["reconstruction_style"] == "nonstationary_envelope_illustration":  # 对下击暴流参考案加入非平稳包络。
        primary = np.exp(-0.5 * np.power((time - 250.0) / 55.0, 2.0))  # 构造主峰风暴包络。
        secondary = np.exp(-0.5 * np.power((time - 390.0) / 85.0, 2.0))  # 构造衰减阶段次峰包络。
        envelope = 0.22 + 1.55 * primary + 0.48 * secondary  # 合成始终非负的非平稳强度包络。
        fluctuation = fluctuation * envelope  # 将源平稳替代统计转成仅用于展示的非平稳形态。
    fluctuation = fluctuation - float(np.mean(fluctuation))  # 精确移除有限样本均值。
    fluctuation = fluctuation / float(np.std(fluctuation, ddof=0))  # 精确归一化有限样本标准差。
    response = float(row[mean_field]) + float(row[sigma_field]) * fluctuation  # 匹配源 Double-MCT 汇总的均值与标准差。
    return time, response  # 返回完整 600 秒示例时程。


def style_axis(axis: Any) -> None:  # 统一时程和统计图坐标轴风格。
    axis.grid(True, color="#D7DEE6", linewidth=0.55, alpha=0.85)  # 添加轻量网格帮助读数。
    axis.spines["top"].set_visible(False)  # 移除顶部边框减轻视觉噪声。
    axis.spines["right"].set_visible(False)  # 移除右侧边框减轻视觉噪声。
    axis.spines["left"].set_color("#93A1AF")  # 使用中性灰色左边框。
    axis.spines["bottom"].set_color("#93A1AF")  # 使用中性灰色下边框。
    axis.tick_params(labelsize=8, colors="#374151")  # 统一刻度文字尺寸与颜色。


def plot_time_histories(rows: list[dict[str, Any]], channel: str, output_path: Path) -> None:  # 绘制四个代表工况的单通道时程。
    _, _, channel_name, unit, _ = CHANNELS[channel]  # 读取通道显示名称和单位。
    figure, axes = plt.subplots(2, 2, figsize=(15.2, 7.6), sharex=True)  # 建立四工况对比布局。
    for index, (row, axis) in enumerate(zip(rows, axes.flat)):  # 遍历四个工况与四个子图。
        time, response = statistic_matched_series(row, channel)  # 重建该工况的统计一致时程。
        mean_field, sigma_field, _, _, _ = CHANNELS[channel]  # 读取目标均值和标准差字段。
        plot_stride = 5  # 将绘图点降采样到每秒四点以保持矢量清晰度。
        axis.plot(time[::plot_stride], response[::plot_stride], color=CASE_COLORS[index], linewidth=0.75, alpha=0.92)  # 绘制 600 秒响应时程。
        axis.axhline(float(row[mean_field]), color="#111827", linewidth=0.8, linestyle="--", alpha=0.75)  # 绘制源均值参考线。
        axis.fill_between([0.0, 600.0], [float(row[mean_field]) - float(row[sigma_field])] * 2, [float(row[mean_field]) + float(row[sigma_field])] * 2, color=CASE_COLORS[index], alpha=0.09)  # 标出源均值正负一倍标准差范围。
        status = "平稳统计一致重建" if row["c3_stationary_eligible"] else "非平稳包络示意"  # 生成准确的子图状态文字。
        axis.set_title(f"{row['display_name']}  |  U10={row['U10_mps']:.1f} m/s  |  {status}", fontsize=10.2, fontproperties=FONT_PROP, color=NAVY, pad=8)  # 标注工况、风速与证据类型。
        axis.set_ylabel(f"{channel_name} / {unit}", fontsize=9, fontproperties=FONT_PROP)  # 标注响应量与单位。
        axis.set_xlim(0.0, 600.0)  # 固定所有工况为 600 秒窗口。
        style_axis(axis)  # 应用统一坐标轴风格。
    for axis in axes[-1, :]:  # 仅对底行子图添加横轴标签。
        axis.set_xlabel("时间 / s", fontsize=9, fontproperties=FONT_PROP)  # 标注时间单位。
    figure.suptitle(f"代表性抖振{channel_name}时程", fontsize=17, fontproperties=FONT_PROP, color=NAVY, y=0.985)  # 添加整页图题。
    figure.text(0.5, 0.008, "Double-MCT冻结统计量约束的确定性重建；非 C3 原生时程求解结果", ha="center", fontsize=10, fontproperties=FONT_PROP, color=ORANGE)  # 在图内固定证据边界。
    figure.tight_layout(rect=[0.02, 0.035, 0.98, 0.955])  # 留出图题与边界说明空间。
    figure.savefig(output_path, dpi=260, facecolor="white", bbox_inches="tight")  # 保存高分辨率图像供 PDF 嵌入。
    plt.close(figure)  # 释放绘图资源。


def plot_response_statistics(rows: list[dict[str, Any]], output_path: Path) -> None:  # 绘制三类响应标准差的代表工况对比。
    figure, axes = plt.subplots(1, 3, figsize=(15.2, 4.8))  # 建立三通道并排对比布局。
    labels = [row["display_name"] for row in rows]  # 收集四个工况显示名称。
    short_labels = ["苏通100年", "ASCE7 IV", "海燕峰值", "东方之星"]  # 使用紧凑标签提升图面可读性。
    for axis, channel in zip(axes, ("lateral", "vertical", "roll")):  # 遍历三类响应通道。
        _, sigma_field, channel_name, unit, _ = CHANNELS[channel]  # 读取标准差字段和显示信息。
        values = [float(row[sigma_field]) for row in rows]  # 提取四个工况的冻结标准差。
        bars = axis.bar(short_labels, values, color=CASE_COLORS, width=0.68)  # 绘制工况标准差柱状图。
        axis.set_title(f"{channel_name}标准差 / {unit}", fontsize=12, fontproperties=FONT_PROP, color=NAVY)  # 标注响应量与单位。
        axis.tick_params(axis="x", rotation=18)  # 轻微旋转工况标签防止重叠。
        style_axis(axis)  # 应用统一坐标轴风格。
        for bar, value in zip(bars, values):  # 为每根柱添加数值标签。
            axis.text(bar.get_x() + bar.get_width() / 2.0, bar.get_height(), f"{value:.2f}", ha="center", va="bottom", fontsize=8.5, color="#374151")  # 显示冻结标准差数值。
    figure.suptitle("代表工况 Double-MCT 响应统计量对比", fontsize=17, fontproperties=FONT_PROP, color=NAVY, y=1.01)  # 添加整页统计图题。
    figure.text(0.5, -0.02, "这些统计量只作为旧模型谱系与可视化输入；C3 CaseResponse 仍为 NOT_MATERIALIZED", ha="center", fontsize=10, fontproperties=FONT_PROP, color=ORANGE)  # 固定 C3 证据边界。
    figure.tight_layout(rect=[0.015, 0.04, 0.985, 0.94])  # 调整图面留白。
    figure.savefig(output_path, dpi=260, facecolor="white", bbox_inches="tight")  # 保存高分辨率统计图。
    plt.close(figure)  # 释放绘图资源。


def node_group(node_type: str) -> str:  # 将图谱节点类型归入五个可视化语义域。
    if node_type in {"Project", "C3Model", "C3ModalRun", "C3Mode", "C3CaseResponse"}:  # 识别 C3 核心模型域。
        return "C3模型"  # 返回 C3 核心模型组。
    if node_type in {"SourceAuthority", "SourceAuthorityRecord", "GitHubEventLibrary", "GitHubEvent", "WindGroup", "C3WindCase"}:  # 识别工况权威域。
        return "43工况权威"  # 返回工况权威组。
    if node_type in {"Agent", "AgentTrace", "AgentDecision", "PhysicsBoundary", "WarningPolicy", "ValidationGate"}:  # 识别智能体决策域。
        return "智能体决策"  # 返回智能体决策组。
    if node_type in {"EvidenceArtifact", "EvidenceSource", "ResultEvidenceBundle", "MigrationRule", "Limitation"}:  # 识别证据和规则域。
        return "证据与规则"  # 返回证据规则组。
    return "旧模型谱系"  # 将其余节点归入旧模型来源域。


def plot_knowledge_graph(output_path: Path) -> None:  # 绘制全部 564 节点和 1168 边的图谱缩略图。
    graph = json.loads(GRAPH_JSON.read_text(encoding="utf-8"))  # 读取已验收 C3 图谱。
    groups = ["旧模型谱系", "43工况权威", "证据与规则", "智能体决策", "C3模型"]  # 固定从来源到 C3 的阅读顺序。
    colors = {"旧模型谱系": ORANGE, "43工况权威": CYAN, "证据与规则": "#8D99AE", "智能体决策": "#7B6D8D", "C3模型": BLUE}  # 定义五个语义域配色。
    grouped_nodes = {group: [] for group in groups}  # 初始化各语义域节点列表。
    for node in graph["nodes"]:  # 遍历全部图谱节点。
        grouped_nodes[node_group(str(node["type"]))].append(node)  # 按节点类型归入语义域。
    positions: dict[str, tuple[float, float]] = {}  # 初始化节点二维位置索引。
    for group_index, group in enumerate(groups):  # 依次布局五个语义域。
        nodes = sorted(grouped_nodes[group], key=lambda item: str(item["id"]))  # 按稳定节点 ID 排序。
        count = max(len(nodes), 1)  # 防止空组导致除零。
        for node_index, node in enumerate(nodes):  # 布局当前语义域内全部节点。
            digest = hashlib.sha256(str(node["id"]).encode("utf-8")).hexdigest()  # 为节点位置生成稳定抖动摘要。
            jitter_x = (int(digest[:4], 16) / 65535.0 - 0.5) * 0.28  # 生成水平小幅抖动避免节点完全重叠。
            jitter_y = (int(digest[4:8], 16) / 65535.0 - 0.5) * 0.018  # 生成垂直小幅抖动增强密度可见性。
            x_value = float(group_index) + jitter_x  # 将语义域放置在独立竖向带中。
            y_value = 0.04 + 0.92 * (node_index + 0.5) / count + jitter_y  # 在竖向带内均匀分布节点。
            positions[str(node["id"])] = (x_value, y_value)  # 保存稳定节点位置。
    segments = [(positions[str(edge["source"])], positions[str(edge["target"])]) for edge in graph["edges"] if str(edge["source"]) in positions and str(edge["target"]) in positions]  # 生成全部有效关系线段。
    figure, axis = plt.subplots(figsize=(15.4, 7.4))  # 建立横向图谱画布。
    axis.add_collection(LineCollection(segments, colors="#7C8B99", linewidths=0.22, alpha=0.09, zorder=1))  # 绘制全部 1168 条关系。
    for group in groups:  # 逐组绘制全部节点。
        points = np.array([positions[str(node["id"])] for node in grouped_nodes[group]])  # 收集当前组节点坐标。
        if len(points) > 0:  # 检查当前组是否含节点。
            axis.scatter(points[:, 0], points[:, 1], s=12.0, color=colors[group], edgecolors="white", linewidths=0.18, alpha=0.88, label=f"{group} ({len(points)})", zorder=2)  # 绘制当前组全部节点并记录计数。
    for group_index, group in enumerate(groups):  # 在每个语义域顶部添加名称。
        axis.text(group_index, 1.035, group, ha="center", va="bottom", fontsize=12, fontproperties=FONT_PROP, color=NAVY, weight="bold")  # 标注语义域名称。
    axis.set_xlim(-0.55, 4.55)  # 固定横向范围包含五个语义域。
    axis.set_ylim(0.0, 1.08)  # 固定纵向范围并留出组标题空间。
    axis.axis("off")  # 隐藏无意义的数值坐标轴。
    axis.set_title("C3 × 43 工况知识图谱全图缩略图", fontsize=18, fontproperties=FONT_PROP, color=NAVY, pad=22)  # 添加图谱标题。
    axis.legend(loc="lower center", bbox_to_anchor=(0.5, -0.08), ncol=5, frameon=False, prop=FONT_PROP, fontsize=9)  # 添加五域节点数量图例。
    axis.text(0.01, 0.015, f"564 节点  |  1168 边  |  43 工况  |  172 智能体决策", transform=axis.transAxes, fontsize=11, fontproperties=FONT_PROP, color="#374151", bbox={"boxstyle": "round,pad=0.45", "facecolor": "white", "edgecolor": "#CAD3DC", "alpha": 0.94})  # 添加图谱核心计数摘要。
    figure.tight_layout(rect=[0.01, 0.04, 0.99, 0.96])  # 调整图谱与图例留白。
    figure.savefig(output_path, dpi=300, facecolor="white", bbox_inches="tight")  # 保存高分辨率完整图谱缩略图。
    plt.close(figure)  # 释放绘图资源。


def add_box(axis: Any, x_value: float, y_value: float, width: float, height: float, title: str, body: str, facecolor: str, edgecolor: str = NAVY, title_size: float = 11.5, body_size: float = 8.8) -> None:  # 向架构图添加统一圆角信息框。
    patch = FancyBboxPatch((x_value, y_value), width, height, boxstyle="round,pad=0.012,rounding_size=0.018", linewidth=1.35, edgecolor=edgecolor, facecolor=facecolor, zorder=2)  # 构造圆角框。
    axis.add_patch(patch)  # 将圆角框加入架构图。
    axis.text(x_value + width / 2.0, y_value + height * 0.68, title, ha="center", va="center", fontsize=title_size, fontproperties=FONT_PROP, color=NAVY, weight="bold", zorder=3)  # 绘制框标题。
    axis.text(x_value + width / 2.0, y_value + height * 0.33, body, ha="center", va="center", fontsize=body_size, fontproperties=FONT_PROP, color="#374151", linespacing=1.35, zorder=3)  # 绘制框正文。


def add_arrow(axis: Any, start: tuple[float, float], end: tuple[float, float], color: str = "#61758A", width: float = 1.4) -> None:  # 向架构图添加统一方向箭头。
    arrow = FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=13, linewidth=width, color=color, connectionstyle="arc3,rad=0.0", zorder=1)  # 构造单向箭头。
    axis.add_patch(arrow)  # 将箭头加入架构图。


def plot_agent_architecture(output_path: Path) -> None:  # 绘制四智能体的实际决策架构图。
    figure, axis = plt.subplots(figsize=(15.4, 7.4))  # 建立横向智能体架构画布。
    axis.set_xlim(0.0, 1.0)  # 固定归一化横坐标范围。
    axis.set_ylim(0.0, 1.0)  # 固定归一化纵坐标范围。
    axis.axis("off")  # 隐藏无意义坐标轴。
    axis.set_title("四智能体证据链与决策架构", fontsize=19, fontproperties=FONT_PROP, color=NAVY, pad=18)  # 添加架构图标题。
    add_box(axis, 0.04, 0.79, 0.27, 0.12, "工况权威", "43×37 源矩阵\n+ C3 overlay", "#E8F3F8", CYAN)  # 添加工况权威输入框。
    add_box(axis, 0.365, 0.79, 0.27, 0.12, "C3 模型证据", "deck + solver\n+ FT14 模态收据", "#E7F0F7", BLUE)  # 添加 C3 模型证据输入框。
    add_box(axis, 0.69, 0.79, 0.27, 0.12, "旧模型谱系", "36 项源资产\n数值仅 provenance", "#FCEFEA", ORANGE)  # 添加旧模型谱系输入框。
    agent_x = [0.025, 0.265, 0.505, 0.745]  # 固定四智能体横向位置。
    agent_titles = ["AuthorityAgent", "SolverEvidenceAgent", "PhysicsBoundaryAgent", "WarningPolicyAgent"]  # 固定四智能体名称和顺序。
    agent_bodies = ["确认身份、源顺序\n与 C3 顺序", "绑定 14 阶模态\n标记响应缺口", "分离源分类\n与 C3 eligibility", "汇总证据状态\n保持不派发"]  # 固定四智能体职责。
    agent_faces = ["#E8F3F8", "#E7F0F7", "#F2EDF7", "#EDF7F0"]  # 定义四智能体框背景色。
    for index, x_value in enumerate(agent_x):  # 依次绘制四智能体框。
        add_box(axis, x_value, 0.51, 0.205, 0.16, agent_titles[index], agent_bodies[index], agent_faces[index], BLUE, 10.7, 8.5)  # 添加当前智能体框。
        if index < 3:  # 检查是否需要连接下一智能体。
            add_arrow(axis, (x_value + 0.205, 0.59), (agent_x[index + 1], 0.59), BLUE, 1.7)  # 绘制四步顺序箭头。
    add_arrow(axis, (0.175, 0.79), (0.127, 0.67), CYAN, 1.35)  # 将工况权威输入连接到 AuthorityAgent。
    add_arrow(axis, (0.50, 0.79), (0.367, 0.67), BLUE, 1.35)  # 将 C3 模型证据连接到 SolverEvidenceAgent。
    add_arrow(axis, (0.825, 0.79), (0.607, 0.67), ORANGE, 1.35)  # 将旧模型谱系连接到 PhysicsBoundaryAgent。
    add_box(axis, 0.03, 0.28, 0.20, 0.12, "权威决策", "C3_CASE_AUTHORITY_\nCONFIRMED", "#F8FBFD", CYAN, 10.5, 8.2)  # 添加权威决策输出框。
    add_box(axis, 0.265, 0.28, 0.20, 0.12, "求解证据决策", "MODAL_EVIDENCE_ONLY\nresponse 未物化", "#F8FBFD", BLUE, 10.5, 8.2)  # 添加求解证据决策输出框。
    add_box(axis, 0.50, 0.30, 0.205, 0.095, "33 个平稳适用案", "AWAITING_C3_CASE_RESPONSE", "#EDF7F0", GREEN, 10.0, 7.7)  # 添加平稳工况分支。
    add_box(axis, 0.50, 0.17, 0.205, 0.095, "10 个包络参考案", "REFERENCE_ONLY_C3_ENVELOPE", "#FCEFEA", ORANGE, 10.0, 7.7)  # 添加包络参考分支。
    add_box(axis, 0.75, 0.23, 0.205, 0.16, "最终输出", "43/43 NOT_ARMED\ndispatch=false", "#EDF7F0", GREEN, 11.2, 9.0)  # 添加最终预警输出框。
    add_arrow(axis, (0.127, 0.51), (0.127, 0.40), CYAN, 1.2)  # 连接 AuthorityAgent 与权威决策。
    add_arrow(axis, (0.367, 0.51), (0.367, 0.40), BLUE, 1.2)  # 连接 SolverEvidenceAgent 与求解证据决策。
    add_arrow(axis, (0.607, 0.51), (0.607, 0.395), GREEN, 1.2)  # 连接 PhysicsBoundaryAgent 与平稳分支。
    add_arrow(axis, (0.607, 0.51), (0.607, 0.265), ORANGE, 1.2)  # 连接 PhysicsBoundaryAgent 与包络分支。
    add_arrow(axis, (0.705, 0.345), (0.75, 0.335), GREEN, 1.2)  # 将平稳分支连接到最终输出。
    add_arrow(axis, (0.705, 0.218), (0.75, 0.285), ORANGE, 1.2)  # 将包络分支连接到最终输出。
    add_box(axis, 0.17, 0.035, 0.66, 0.075, "物化结果", "564 节点知识图谱  +  43 条四步 trace  +  172 个 AgentDecision  +  可查询事实包", "#F3F6F9", "#9AA8B5", 10.5, 8.5)  # 添加图谱与追踪物化结果框。
    add_arrow(axis, (0.852, 0.23), (0.74, 0.11), "#61758A", 1.2)  # 将最终输出连接到物化结果。
    figure.text(0.5, 0.005, "决策架构读取已验收图谱；不把 Double-MCT 数值写入 C3 CaseResponse", ha="center", fontsize=10, fontproperties=FONT_PROP, color=ORANGE)  # 固定架构图证据边界。
    figure.tight_layout(rect=[0.01, 0.02, 0.99, 0.95])  # 调整架构图留白。
    figure.savefig(output_path, dpi=300, facecolor="white", bbox_inches="tight")  # 保存高分辨率智能体架构图。
    plt.close(figure)  # 释放绘图资源。


def draw_wrapped_text(pdf: canvas.Canvas, text: str, x_value: float, y_value: float, max_width: float, font_size: float, leading: float, color: Color | None = None) -> float:  # 在 PDF 中按实际字宽自动换行中文文本。
    pdf.setFont(PDF_FONT, font_size)  # 设置中文字体与字号。
    pdf.setFillColor(color or HexColor("#374151"))  # 设置正文颜色。
    current = ""  # 初始化当前行文本。
    lines: list[str] = []  # 初始化换行结果。
    for character in text:  # 按字符扫描以兼容无空格中文。
        candidate = current + character  # 尝试将当前字符加入本行。
        if pdfmetrics.stringWidth(candidate, PDF_FONT, font_size) <= max_width or not current:  # 检查加入字符后是否仍在宽度内。
            current = candidate  # 接受当前字符。
        else:  # 处理超出可用宽度的情况。
            lines.append(current)  # 固定上一行。
            current = character  # 以当前字符开始新行。
    if current:  # 检查最后一行是否非空。
        lines.append(current)  # 追加最后一行。
    for line in lines:  # 逐行绘制换行文本。
        pdf.drawString(x_value, y_value, line)  # 在当前基线绘制一行。
        y_value -= leading  # 下移到下一行基线。
    return y_value  # 返回最后一行后的纵坐标。


def draw_page_chrome(pdf: canvas.Canvas, title: str, section: str, page_number: int) -> None:  # 绘制统一页眉、页脚和页码。
    pdf.setFillColor(HexColor(NAVY))  # 设置页眉深蓝色。
    pdf.rect(0.0, PAGE_H - 44.0, PAGE_W, 44.0, fill=1, stroke=0)  # 绘制整页页眉色带。
    pdf.setFillColor(HexColor("#FFFFFF"))  # 设置页眉文字白色。
    pdf.setFont(PDF_FONT, 15.0)  # 设置页眉标题字号。
    pdf.drawString(34.0, PAGE_H - 29.0, title)  # 绘制页眉标题。
    pdf.setFont(PDF_FONT, 9.0)  # 设置页眉章节字号。
    pdf.drawRightString(PAGE_W - 34.0, PAGE_H - 28.0, section)  # 绘制右侧章节名称。
    pdf.setStrokeColor(HexColor("#D6DEE6"))  # 设置页脚分隔线颜色。
    pdf.line(34.0, 28.0, PAGE_W - 34.0, 28.0)  # 绘制页脚分隔线。
    pdf.setFillColor(HexColor(GRAY))  # 设置页脚文字颜色。
    pdf.setFont(PDF_FONT, 8.5)  # 设置页脚文字字号。
    pdf.drawString(34.0, 14.0, "Hiram-test/model | feat/c3-buffeting-43-kg | 证据边界随图固定")  # 绘制来源说明。
    pdf.drawRightString(PAGE_W - 34.0, 14.0, f"{page_number:02d}")  # 绘制页码。


def draw_image_fit(pdf: canvas.Canvas, image_path: Path, x_value: float, y_value: float, max_width: float, max_height: float) -> None:  # 按比例将图像放入指定 PDF 区域。
    from PIL import Image  # 延迟导入 Pillow 以读取图像尺寸。
    with Image.open(image_path) as image:  # 打开目标图像并自动关闭文件。
        width_px, height_px = image.size  # 读取图像像素尺寸。
    scale = min(max_width / width_px, max_height / height_px)  # 计算不裁切的最大缩放比例。
    draw_width = width_px * scale  # 计算 PDF 中的图像宽度。
    draw_height = height_px * scale  # 计算 PDF 中的图像高度。
    draw_x = x_value + (max_width - draw_width) / 2.0  # 水平居中图像。
    draw_y = y_value + (max_height - draw_height) / 2.0  # 垂直居中图像。
    pdf.drawImage(str(image_path), draw_x, draw_y, width=draw_width, height=draw_height, preserveAspectRatio=True, mask="auto")  # 嵌入高分辨率图像。


def draw_badge(pdf: canvas.Canvas, x_value: float, y_value: float, width: float, text: str, fill: str, text_color: str = "#FFFFFF") -> None:  # 绘制封面和摘要页状态徽章。
    pdf.setFillColor(HexColor(fill))  # 设置徽章背景色。
    pdf.roundRect(x_value, y_value, width, 28.0, 7.0, fill=1, stroke=0)  # 绘制圆角徽章背景。
    pdf.setFillColor(HexColor(text_color))  # 设置徽章文字颜色。
    pdf.setFont(PDF_FONT, 10.0)  # 设置徽章文字字号。
    pdf.drawCentredString(x_value + width / 2.0, y_value + 9.0, text)  # 居中绘制徽章文字。


def draw_cover(pdf: canvas.Canvas) -> None:  # 绘制报告封面。
    pdf.setFillColor(HexColor("#F7F9FB"))  # 设置封面浅灰背景。
    pdf.rect(0.0, 0.0, PAGE_W, PAGE_H, fill=1, stroke=0)  # 填充整页背景。
    pdf.setFillColor(HexColor(NAVY))  # 设置封面左侧主色。
    pdf.rect(0.0, 0.0, 86.0, PAGE_H, fill=1, stroke=0)  # 绘制封面左侧深蓝色带。
    pdf.setFillColor(HexColor(BLUE))  # 设置封面顶部强调色。
    pdf.rect(86.0, PAGE_H - 16.0, PAGE_W - 86.0, 16.0, fill=1, stroke=0)  # 绘制封面顶部细色带。
    pdf.setFillColor(HexColor(NAVY))  # 设置封面主标题颜色。
    pdf.setFont(PDF_FONT, 29.0)  # 设置封面主标题字号。
    pdf.drawString(126.0, 420.0, "张靖皋猫道 C3 × 43 工况")  # 绘制主标题第一行。
    pdf.drawString(126.0, 374.0, "抖振知识图谱与智能体决策可视化")  # 绘制主标题第二行。
    pdf.setFillColor(HexColor(GRAY))  # 设置封面副标题颜色。
    pdf.setFont(PDF_FONT, 15.0)  # 设置封面副标题字号。
    pdf.drawString(128.0, 330.0, "代表性时程响应 · 知识图谱缩略图 · 四智能体决策架构")  # 绘制封面副标题。
    draw_badge(pdf, 128.0, 260.0, 160.0, "模型迁移验收 35/35 PASS", GREEN)  # 绘制迁移验收徽章。
    draw_badge(pdf, 302.0, 260.0, 142.0, "图谱校验 15/15 PASS", BLUE)  # 绘制图谱校验徽章。
    draw_badge(pdf, 458.0, 260.0, 176.0, "C3 响应 NOT_MATERIALIZED", ORANGE)  # 绘制 C3 响应边界徽章。
    pdf.setFillColor(HexColor("#DCE6EE"))  # 设置封面信息框背景色。
    pdf.roundRect(126.0, 102.0, 606.0, 112.0, 10.0, fill=1, stroke=0)  # 绘制封面证据信息框。
    pdf.setFillColor(HexColor("#334155"))  # 设置证据信息文字颜色。
    pdf.setFont(PDF_FONT, 10.5)  # 设置证据信息字号。
    pdf.drawString(148.0, 181.0, "C3 模型：C3-UB-FT14-PARSER-SAFE · UCOR6 + UCAB3 · 14 阶模态")  # 绘制 C3 模型身份。
    pdf.drawString(148.0, 155.0, "迁移提交：7f47a569b80d7034610ca4723ded71fb205763fb")  # 绘制迁移提交号。
    pdf.drawString(148.0, 129.0, "Double-MCT 来源提交：3b135b2c1a1b5c961ce68a101a0414fa0b525d85")  # 绘制旧模型来源提交号。
    pdf.setFillColor(HexColor(ORANGE))  # 设置封面边界说明颜色。
    pdf.setFont(PDF_FONT, 10.0)  # 设置封面边界说明字号。
    pdf.drawString(126.0, 62.0, "本报告的结构响应时程为 Double-MCT 冻结统计量约束的确定性重建，仅用于展示；不是 C3 原生抖振求解结果。")  # 明确封面证据边界。
    pdf.showPage()  # 结束封面页。


def draw_case_overview(pdf: canvas.Canvas, rows: list[dict[str, Any]]) -> None:  # 绘制代表工况与重建方法摘要页。
    draw_page_chrome(pdf, "代表工况与证据边界", "01 / 数据来源", 2)  # 绘制摘要页页眉页脚。
    pdf.setFillColor(HexColor(NAVY))  # 设置页内标题颜色。
    pdf.setFont(PDF_FONT, 17.0)  # 设置页内标题字号。
    pdf.drawString(38.0, PAGE_H - 78.0, "四个代表工况")  # 绘制页内标题。
    column_x = [38.0, 278.0, 370.0, 444.0, 526.0, 612.0, 728.0]  # 固定表格列起点。
    headers = ["工况", "U10", "C3层", "C3处置", "源分类", "响应来源", "状态"]  # 定义摘要表表头。
    widths = [236.0, 88.0, 70.0, 78.0, 82.0, 112.0, 74.0]  # 定义摘要表列宽。
    top_y = PAGE_H - 112.0  # 定义表格顶部纵坐标。
    pdf.setFillColor(HexColor(NAVY))  # 设置表头背景色。
    pdf.rect(34.0, top_y - 26.0, PAGE_W - 68.0, 28.0, fill=1, stroke=0)  # 绘制表头背景。
    pdf.setFillColor(HexColor("#FFFFFF"))  # 设置表头文字颜色。
    pdf.setFont(PDF_FONT, 9.0)  # 设置表头文字字号。
    for x_value, header in zip(column_x, headers):  # 逐列绘制表头。
        pdf.drawString(x_value, top_y - 17.0, header)  # 绘制当前表头文字。
    for row_index, row in enumerate(rows):  # 逐行绘制四个代表工况。
        row_y = top_y - 26.0 - (row_index + 1) * 42.0  # 计算当前数据行纵坐标。
        pdf.setFillColor(HexColor("#F2F6F9" if row_index % 2 == 0 else "#FFFFFF"))  # 设置交替行背景色。
        pdf.rect(34.0, row_y, PAGE_W - 68.0, 42.0, fill=1, stroke=0)  # 绘制当前数据行背景。
        values = [str(row["display_name"]), f"{row['U10_mps']:.1f}", str(row["c3_layer"]), "平稳待响应" if row["c3_stationary_eligible"] else "包络参考", str(row["source_stationarity"]), "Double-MCT统计重建", "NOT_MATERIALIZED"]  # 组装当前数据行显示值。
        pdf.setFillColor(HexColor("#374151"))  # 设置数据行文字颜色。
        pdf.setFont(PDF_FONT, 8.3)  # 设置数据行文字字号。
        for column_index, (x_value, value) in enumerate(zip(column_x, values)):  # 逐列绘制当前数据行。
            max_chars = max(int(widths[column_index] / 8.5), 6)  # 估算当前列可容纳字符数。
            shown = value if len(value) <= max_chars else value[: max_chars - 1] + "…"  # 对过长内容进行稳定截断。
            pdf.drawString(x_value, row_y + 15.0, shown)  # 绘制当前单元格文字。
    pdf.setFillColor(HexColor("#E8F3F8"))  # 设置方法框背景色。
    pdf.roundRect(38.0, 104.0, 760.0, 154.0, 10.0, fill=1, stroke=0)  # 绘制方法与边界说明框。
    pdf.setFillColor(HexColor(NAVY))  # 设置方法框标题颜色。
    pdf.setFont(PDF_FONT, 13.0)  # 设置方法框标题字号。
    pdf.drawString(58.0, 231.0, "时程生成口径")  # 绘制方法框标题。
    method_text = "每个通道采用固定种子的带限高斯过程，有限样本均值和标准差精确匹配 I08_43CASE_MASTER.csv 的 Double-MCT 汇总值；苏通、ASCE7、海燕采用平稳重建，东方之星采用非平稳包络示意。重建曲线用于表现响应形态、工况差异和智能体查询界面，不用于 C3 工程验收。"  # 定义方法说明文本。
    draw_wrapped_text(pdf, method_text, 58.0, 205.0, 716.0, 10.3, 18.0, HexColor("#374151"))  # 绘制自动换行的方法说明。
    pdf.setFillColor(HexColor(ORANGE))  # 设置关键边界提示颜色。
    pdf.setFont(PDF_FONT, 10.5)  # 设置关键边界提示字号。
    pdf.drawString(58.0, 122.0, "C3 原生响应：43/43 NOT_MATERIALIZED；Double-MCT 数值：PROVENANCE_ONLY；预警：43/43 NOT_ARMED，dispatch=false。")  # 绘制关键证据边界。
    pdf.showPage()  # 结束代表工况摘要页。


def draw_chart_page(pdf: canvas.Canvas, image_path: Path, title: str, section: str, page_number: int, caption: str) -> None:  # 绘制带高分辨率图表的统一报告页。
    draw_page_chrome(pdf, title, section, page_number)  # 绘制图表页页眉页脚。
    draw_image_fit(pdf, image_path, 32.0, 56.0, PAGE_W - 64.0, PAGE_H - 116.0)  # 将图表按比例放入页面主体。
    pdf.setFillColor(HexColor(ORANGE))  # 设置图注边界提示颜色。
    pdf.setFont(PDF_FONT, 8.8)  # 设置图注字号。
    pdf.drawCentredString(PAGE_W / 2.0, 39.0, caption)  # 居中绘制图注。
    pdf.showPage()  # 结束当前图表页。


def draw_final_page(pdf: canvas.Canvas, acceptance: dict[str, Any], validation: dict[str, Any]) -> None:  # 绘制报告结论与谱系页。
    draw_page_chrome(pdf, "结论与可复现谱系", "08 / 收口", 9)  # 绘制结论页页眉页脚。
    pdf.setFillColor(HexColor(NAVY))  # 设置结论页主标题颜色。
    pdf.setFont(PDF_FONT, 18.0)  # 设置结论页主标题字号。
    pdf.drawString(42.0, PAGE_H - 82.0, "本报告形成三类可直接使用的展示材料")  # 绘制结论页主标题。
    cards = [("代表性响应", "4 个工况 × 3 类响应；统计一致、固定种子、可重复构建。", BLUE), ("图谱缩略图", "直接读取 564 节点、1168 边的 C3 已验收图谱。", CYAN), ("决策架构", "严格对应四智能体顺序：权威 → 求解证据 → 物理边界 → 预警策略。", GREEN)]  # 定义三类交付卡片。
    for index, (title, body, color) in enumerate(cards):  # 逐项绘制三类交付卡片。
        x_value = 42.0 + index * 256.0  # 计算当前卡片横坐标。
        pdf.setFillColor(HexColor("#F5F8FA"))  # 设置卡片背景色。
        pdf.setStrokeColor(HexColor(color))  # 设置卡片边框颜色。
        pdf.roundRect(x_value, 328.0, 230.0, 120.0, 10.0, fill=1, stroke=1)  # 绘制当前卡片。
        pdf.setFillColor(HexColor(color))  # 设置卡片标题颜色。
        pdf.setFont(PDF_FONT, 13.0)  # 设置卡片标题字号。
        pdf.drawString(x_value + 18.0, 414.0, title)  # 绘制卡片标题。
        draw_wrapped_text(pdf, body, x_value + 18.0, 384.0, 194.0, 9.5, 16.0, HexColor("#374151"))  # 绘制卡片正文。
    pdf.setFillColor(HexColor("#EEF4F7"))  # 设置验收摘要框背景色。
    pdf.roundRect(42.0, 196.0, 742.0, 92.0, 10.0, fill=1, stroke=0)  # 绘制验收摘要框。
    pdf.setFillColor(HexColor(NAVY))  # 设置验收摘要标题颜色。
    pdf.setFont(PDF_FONT, 12.0)  # 设置验收摘要标题字号。
    pdf.drawString(62.0, 259.0, "远端验收状态")  # 绘制验收摘要标题。
    acceptance_true = sum(bool(value) for value in acceptance["checks"].values())  # 统计迁移验收通过项数。
    validation_true = sum(bool(value) for value in validation["checks"].values())  # 统计图谱校验通过项数。
    pdf.setFillColor(HexColor("#374151"))  # 设置验收摘要正文颜色。
    pdf.setFont(PDF_FONT, 10.5)  # 设置验收摘要正文字号。
    pdf.drawString(62.0, 231.0, f"模型迁移：{acceptance['status']}（{acceptance_true}/{len(acceptance['checks'])}）    图谱校验：{validation['status']}（{validation_true}/{len(validation['checks'])}）    图谱：564 节点 / 1168 边")  # 绘制验收摘要数值。
    pdf.setFillColor(HexColor(ORANGE))  # 设置最终边界说明颜色。
    pdf.setFont(PDF_FONT, 11.0)  # 设置最终边界说明字号。
    final_boundary = "当前可确认的是模型、权威、谱系、图谱和四智能体决策链已经迁移到 C3；C3 43 工况风荷载映射与结构响应仍未执行。本 PDF 中的时程不能用于替代后续 C3 原生求解。"  # 定义最终证据边界文本。
    draw_wrapped_text(pdf, final_boundary, 46.0, 150.0, 734.0, 11.0, 20.0, HexColor(ORANGE))  # 绘制最终证据边界。
    pdf.setFillColor(HexColor(GRAY))  # 设置谱系路径文字颜色。
    pdf.setFont(PDF_FONT, 8.7)  # 设置谱系路径文字字号。
    pdf.drawString(46.0, 78.0, "响应统计源：results/I08_43CASE_MASTER.csv @ 3b135b2c1a1b5c961ce68a101a0414fa0b525d85")  # 绘制响应统计来源。
    pdf.drawString(46.0, 58.0, "C3 图谱源：generated/knowledge_graph_c3.json @ 7f47a569b80d7034610ca4723ded71fb205763fb")  # 绘制 C3 图谱来源。
    pdf.showPage()  # 结束结论页。


def build_report() -> Path:  # 构建全部图像资产并生成九页 PDF。
    configure_fonts()  # 配置中文字体。
    ASSET_DIR.mkdir(parents=True, exist_ok=True)  # 创建报告图像资产目录。
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # 创建最终 PDF 输出目录。
    rows = load_stats()  # 读取四个代表工况统计量。
    acceptance = json.loads(ACCEPTANCE_JSON.read_text(encoding="utf-8"))  # 读取模型迁移验收收据。
    validation = json.loads(VALIDATION_JSON.read_text(encoding="utf-8"))  # 读取图谱校验收据。
    lateral_path = ASSET_DIR / "representative_lateral_histories.png"  # 定义横向响应图路径。
    vertical_path = ASSET_DIR / "representative_vertical_histories.png"  # 定义竖向响应图路径。
    roll_path = ASSET_DIR / "representative_roll_histories.png"  # 定义滚转响应图路径。
    statistics_path = ASSET_DIR / "representative_response_statistics.png"  # 定义统计对比图路径。
    graph_path = ASSET_DIR / "knowledge_graph_thumbnail.png"  # 定义知识图谱缩略图路径。
    architecture_path = ASSET_DIR / "agent_decision_architecture.png"  # 定义智能体架构图路径。
    plot_time_histories(rows, "lateral", lateral_path)  # 生成横向响应时程图。
    plot_time_histories(rows, "vertical", vertical_path)  # 生成竖向响应时程图。
    plot_time_histories(rows, "roll", roll_path)  # 生成滚转响应时程图。
    plot_response_statistics(rows, statistics_path)  # 生成三类响应统计对比图。
    plot_knowledge_graph(graph_path)  # 生成全部节点和边的图谱缩略图。
    plot_agent_architecture(architecture_path)  # 生成四智能体决策架构图。
    pdf = canvas.Canvas(str(TEMP_PDF), pagesize=(PAGE_W, PAGE_H), pageCompression=1)  # 创建待优化的横向 A4 PDF。
    pdf.setTitle("张靖皋猫道 C3 43工况抖振知识图谱智能体可视化报告")  # 写入 PDF 标题元数据。
    pdf.setAuthor("Hiram-test/model")  # 写入 PDF 作者元数据。
    pdf.setSubject("代表性抖振响应、知识图谱缩略图和智能体决策架构")  # 写入 PDF 主题元数据。
    draw_cover(pdf)  # 绘制第 1 页封面。
    draw_case_overview(pdf, rows)  # 绘制第 2 页代表工况与证据边界。
    draw_chart_page(pdf, lateral_path, "代表性横向抖振响应", "02 / 时程响应", 3, "图 1  Double-MCT 统计一致重建；C3 CaseResponse 未物化")  # 绘制第 3 页横向响应。
    draw_chart_page(pdf, vertical_path, "代表性竖向抖振响应", "03 / 时程响应", 4, "图 2  Double-MCT 统计一致重建；东方之星仅作非平稳包络示意")  # 绘制第 4 页竖向响应。
    draw_chart_page(pdf, roll_path, "代表性系统滚转响应", "04 / 时程响应", 5, "图 3  Double-MCT 统计一致重建；不得作为 C3 原生滚转结果")  # 绘制第 5 页滚转响应。
    draw_chart_page(pdf, statistics_path, "代表工况响应统计量", "05 / 统计对比", 6, "图 4  冻结均值与标准差来源于 I08_43CASE_MASTER.csv")  # 绘制第 6 页统计对比。
    draw_chart_page(pdf, graph_path, "知识图谱缩略图", "06 / 图谱", 7, "图 5  直接读取迁移后图谱的全部 564 节点和 1168 条关系")  # 绘制第 7 页知识图谱缩略图。
    draw_chart_page(pdf, architecture_path, "智能体决策架构", "07 / 智能体", 8, "图 6  四智能体按固定顺序执行，并保持 NOT_ARMED 与 dispatch=false")  # 绘制第 8 页智能体架构。
    draw_final_page(pdf, acceptance, validation)  # 绘制第 9 页结论与谱系。
    pdf.save()  # 写入并关闭压缩前 PDF。
    ghostscript_command = ["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4", "-dPDFSETTINGS=/screen", "-dNOPAUSE", "-dQUIET", "-dBATCH", "-dDetectDuplicateImages=true", "-dEmbedAllFonts=true", "-dSubsetFonts=true", f"-sOutputFile={OUTPUT_PDF}", str(TEMP_PDF)]  # 定义字体可移植且适合 GitHub 分发的压缩命令。
    subprocess.run(ghostscript_command, check=True)  # 生成体积受控且字体嵌入的最终 PDF。
    TEMP_PDF.unlink(missing_ok=True)  # 成功压缩后删除已被替代的临时 PDF。
    return OUTPUT_PDF  # 返回最终 PDF 路径。


def main() -> int:  # 提供可重复执行的命令行入口。
    output_path = build_report()  # 生成全部图像和最终 PDF。
    print(output_path)  # 输出最终文件路径供 CI 或人工定位。
    return 0  # 返回成功状态码。


if __name__ == "__main__":  # 仅在直接执行脚本时构建报告。
    raise SystemExit(main())  # 将构建结果返回操作系统。
