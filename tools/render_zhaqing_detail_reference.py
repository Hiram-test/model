#!/usr/bin/env python3
# 本脚本读取已交付的 N07 米制几何 IR，绘制补模后的立面、平面和三维参考预览。

# 导入 json，用于读取求解器无关几何 IR。
import json
# 导入 math，用于生成与 FreeCAD 模型一致的索鞍候选圆弧。
import math
# 从 pathlib 导入 Path，用于稳定定位仓库交付文件。
from pathlib import Path
# 从 typing 导入 Any，用于标注通用 JSON 对象。
from typing import Any

# 导入 matplotlib 并使用无窗口后端，保证脚本可在自动化环境运行。
import matplotlib
# 选择 Agg 后端，避免依赖桌面图形会话。
matplotlib.use("Agg")
# 导入 pyplot，用于创建三视图和保存 PNG。
import matplotlib.pyplot as plt
# 从 matplotlib.patches 导入 Patch，用于构造不依赖具体线对象的图例。
from matplotlib.patches import Patch

# 以 tools 目录的父目录作为仓库根目录。
REPO_ROOT = Path(__file__).resolve().parents[1]
# 固定已交付的米制几何 IR 输入路径。
IR_PATH = REPO_ROOT / "deliverables" / "zhaqing_n07_fem_geometry_ir.json"
# 固定增强预览输出路径。
OUTPUT_PATH = REPO_ROOT / "deliverables" / "cad_detail_preview.png"
# 固定主锚局部包络长度为十点五米，来源图26的1050cm尺寸链。
MAIN_ANCHOR_LENGTH_M = 10.50
# 固定主锚局部包络宽度为七点二米，来源图26的720cm尺寸链。
MAIN_ANCHOR_WIDTH_M = 7.20
# 固定主锚局部包络高度为七米，来源图26的700cm立面尺寸。
MAIN_ANCHOR_HEIGHT_M = 7.00
# 固定风锚候选包络长度为二点二米，来源图33的220cm候选尺寸。
WIND_ANCHOR_LENGTH_M = 2.20
# 固定风锚候选包络宽度为一点五米，来源图33的150cm候选尺寸。
WIND_ANCHOR_WIDTH_M = 1.50
# 固定风锚上下控制高程差为三米，来源两个接受标高之差。
WIND_ANCHOR_HEIGHT_M = 3.00
# 固定塔柱候选截面边长为一点五米；截面归属尚未冻结。
TOWER_SECTION_M = 1.50
# 固定索鞍见证弧半角为二十度，只控制预览长度。
SADDLE_HALF_ANGLE_DEG = 20.0
# 固定索鞍三组原图半径，单位米。
SADDLE_RADII_M = [1.420, 1.450, 1.560]
# 固定三组索鞍半径的显示颜色。
SADDLE_COLOURS = ["#D83B3B", "#F09A24", "#7A42A8"]
# 固定分析参考线颜色为灰蓝色，降低其与新增详图对象的视觉竞争。
BASE_COLOUR = "#60758A"
# 固定主锚包络显示颜色为棕色。
MAIN_ANCHOR_COLOUR = "#8C5A2B"
# 固定风锚包络显示颜色为橙色。
WIND_ANCHOR_COLOUR = "#D97818"
# 固定塔柱候选包络显示颜色为绿色。
TOWER_COLOUR = "#208F55"
# 固定基础控制面显示颜色为蓝色。
FOUNDATION_COLOUR = "#2B78B8"


# 定义 JSON 对象读取函数，并拒绝非对象顶层。
def read_json_object(path: Path) -> dict[str, Any]:
    # 以 UTF-8 读取并解析 JSON。
    payload = json.loads(path.read_text(encoding="utf-8"))
    # 顶层不是对象时终止。
    if not isinstance(payload, dict):
        # 抛出清晰类型错误。
        raise TypeError(f"JSON顶层必须为对象：{path}")
    # 返回已验证对象。
    return payload


# 定义按角色选择稳定点函数。
def points_with_role(ir_data: dict[str, Any], role: str) -> list[dict[str, Any]]:
    # 返回 roles 包含目标角色的点，并按 geometryId 稳定排序。
    return sorted([point for point in ir_data.get("points", []) if role in point.get("roles", [])], key=lambda point: str(point.get("geometryId", "")))


# 定义语义标签连接函数，供主锚左右侧分组。
def semantic_text(point: dict[str, Any]) -> str:
    # 把标签连接并转为大写。
    return " ".join(str(value) for value in point.get("semanticLabels", [])).upper()


# 定义三维点平均函数，用于计算两个主锚接口点的包络中心。
def mean_coordinates(points: list[dict[str, Any]]) -> list[float]:
    # 分别计算三个坐标分量的平均值。
    return [sum(float(point["coordinates"][index]) for point in points) / len(points) for index in range(3)]


# 定义轴对齐包络的十二条边端点生成函数。
def box_edges(minimum: list[float], maximum: list[float]) -> list[tuple[list[float], list[float]]]:
    # 构造八个角点，索引顺序按二进制XYZ组合排列。
    corners = [[x_value, y_value, z_value] for x_value in (minimum[0], maximum[0]) for y_value in (minimum[1], maximum[1]) for z_value in (minimum[2], maximum[2])]
    # 定义只相差一个坐标分量的十二对角点索引。
    index_pairs = [(0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3), (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)]
    # 返回十二条边的首尾坐标。
    return [(corners[first], corners[second]) for first, second in index_pairs]


# 定义分析参考线二维绘制函数，坐标索引由调用方指定。
def draw_base_2d(axis: Any, curves: list[dict[str, Any]], point_by_id: dict[str, dict[str, Any]], first_index: int, second_index: int) -> None:
    # 遍历全部 N07 曲线。
    for curve in curves:
        # 读取曲线两端稳定点。
        start = point_by_id[str(curve["endRefs"][0])]["coordinates"]
        # 读取终点。
        end = point_by_id[str(curve["endRefs"][1])]["coordinates"]
        # 绘制灰蓝色细线作为分析参考背景。
        axis.plot([float(start[first_index]), float(end[first_index])], [float(start[second_index]), float(end[second_index])], color=BASE_COLOUR, linewidth=0.55, alpha=0.46)


# 定义分析参考线三维绘制函数。
def draw_base_3d(axis: Any, curves: list[dict[str, Any]], point_by_id: dict[str, dict[str, Any]]) -> None:
    # 遍历全部 N07 曲线。
    for curve in curves:
        # 读取起点三维坐标。
        start = point_by_id[str(curve["endRefs"][0])]["coordinates"]
        # 读取终点三维坐标。
        end = point_by_id[str(curve["endRefs"][1])]["coordinates"]
        # 绘制三维灰蓝色细线。
        axis.plot([float(start[0]), float(end[0])], [float(start[1]), float(end[1])], [float(start[2]), float(end[2])], color=BASE_COLOUR, linewidth=0.45, alpha=0.34)


# 定义包络二维投影绘制函数。
def draw_box_2d(axis: Any, minimum: list[float], maximum: list[float], first_index: int, second_index: int, colour: str, linewidth: float, alpha: float) -> None:
    # 遍历包络十二条三维边。
    for start, end in box_edges(minimum, maximum):
        # 绘制指定二维投影边。
        axis.plot([start[first_index], end[first_index]], [start[second_index], end[second_index]], color=colour, linewidth=linewidth, alpha=alpha)


# 定义包络三维线框绘制函数。
def draw_box_3d(axis: Any, minimum: list[float], maximum: list[float], colour: str, linewidth: float, alpha: float) -> None:
    # 遍历十二条包络边。
    for start, end in box_edges(minimum, maximum):
        # 绘制三维边。
        axis.plot([start[0], end[0]], [start[1], end[1]], [start[2], end[2]], color=colour, linewidth=linewidth, alpha=alpha)


# 定义索鞍候选弧米制采样函数，与 FreeCAD 三点弧共享冠顶和半角。
def saddle_arc_points(crown: list[float], radius_m: float) -> list[list[float]]:
    # 创建从负二十度到正二十度的四十一个均匀参数。
    parameters = [math.radians(-SADDLE_HALF_ANGLE_DEG + 2.0 * SADDLE_HALF_ANGLE_DEG * index / 40.0) for index in range(41)]
    # 返回位于 X-Z 平面的圆弧采样点，Y保持鞍控点坐标。
    return [[crown[0] + radius_m * math.sin(parameter), crown[1], crown[2] - radius_m + radius_m * math.cos(parameter)] for parameter in parameters]


# 定义主程序，生成立面、平面和等轴三维预览。
def main() -> int:
    # 输入 IR 必须存在。
    if not IR_PATH.is_file():
        # 抛出输入缺失错误。
        raise FileNotFoundError(IR_PATH)
    # 读取 IR 数据主体。
    ir_data = read_json_object(IR_PATH)["data"]
    # 建立稳定点 ID 到点记录的映射。
    point_by_id = {str(point["geometryId"]): point for point in ir_data["points"]}
    # 读取全部分析参考曲线。
    curves = list(ir_data["curves"])
    # 配置中文字体优先使用 Windows 微软雅黑，并允许负号正常显示。
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    # 禁止 Unicode 负号被错误替换。
    plt.rcParams["axes.unicode_minus"] = False
    # 创建宽十八英寸、高十英寸的三视图画布。
    figure = plt.figure(figsize=(18.0, 10.0), constrained_layout=True)
    # 创建两行两列网格，右侧三维图跨越两行。
    grid = figure.add_gridspec(2, 2, width_ratios=[1.18, 1.0])
    # 创建左上纵向立面轴。
    elevation_axis = figure.add_subplot(grid[0, 0])
    # 创建左下平面轴。
    plan_axis = figure.add_subplot(grid[1, 0])
    # 创建右侧三维轴。
    model_axis = figure.add_subplot(grid[:, 1], projection="3d")
    # 绘制立面分析参考线，使用 X 和 Z 坐标。
    draw_base_2d(elevation_axis, curves, point_by_id, 0, 2)
    # 绘制平面分析参考线，使用 X 和 Y 坐标。
    draw_base_2d(plan_axis, curves, point_by_id, 0, 1)
    # 绘制三维分析参考线。
    draw_base_3d(model_axis, curves, point_by_id)
    # 读取四个索鞍控制点。
    saddle_points = points_with_role(ir_data, "SADDLE_CONTROL_POINT")
    # 遍历四个鞍位。
    for point in saddle_points:
        # 读取鞍控点米制坐标。
        crown = [float(value) for value in point["coordinates"]]
        # 遍历三组候选半径和颜色。
        for radius_m, colour in zip(SADDLE_RADII_M, SADDLE_COLOURS):
            # 生成当前候选弧采样点。
            arc_points = saddle_arc_points(crown, radius_m)
            # 在立面中绘制候选弧。
            elevation_axis.plot([item[0] for item in arc_points], [item[2] for item in arc_points], color=colour, linewidth=2.0, alpha=0.95)
            # 在三维中绘制候选弧。
            model_axis.plot([item[0] for item in arc_points], [item[1] for item in arc_points], [item[2] for item in arc_points], color=colour, linewidth=1.8, alpha=0.95)
    # 读取四个主锚接口点。
    main_anchor_points = points_with_role(ir_data, "MAIN_ANCHOR_INTERFACE_POINT")
    # 分别处理左右主锚。
    for side in ("LEFT", "RIGHT"):
        # 选择当前侧别的两个接口点。
        side_points = [point for point in main_anchor_points if side in semantic_text(point)]
        # 计算包络中心。
        center = mean_coordinates(side_points)
        # 计算主锚包络最小角点。
        minimum = [center[0] - MAIN_ANCHOR_LENGTH_M / 2.0, center[1] - MAIN_ANCHOR_WIDTH_M / 2.0, center[2] - MAIN_ANCHOR_HEIGHT_M / 2.0]
        # 计算最大角点。
        maximum = [center[0] + MAIN_ANCHOR_LENGTH_M / 2.0, center[1] + MAIN_ANCHOR_WIDTH_M / 2.0, center[2] + MAIN_ANCHOR_HEIGHT_M / 2.0]
        # 绘制主锚立面包络。
        draw_box_2d(elevation_axis, minimum, maximum, 0, 2, MAIN_ANCHOR_COLOUR, 1.8, 0.90)
        # 绘制主锚平面包络。
        draw_box_2d(plan_axis, minimum, maximum, 0, 1, MAIN_ANCHOR_COLOUR, 1.8, 0.90)
        # 绘制主锚三维包络。
        draw_box_3d(model_axis, minimum, maximum, MAIN_ANCHOR_COLOUR, 1.5, 0.90)
        # 在立面标注主锚侧别。
        elevation_axis.text(center[0], maximum[2] + 0.35, f"{side} 主锚 10.5×7.2×7.0m", color=MAIN_ANCHOR_COLOUR, fontsize=9, ha="center")
    # 读取四个风锚接口点。
    wind_anchor_points = points_with_role(ir_data, "WIND_ANCHOR_INTERFACE_POINT")
    # 遍历风锚接口点。
    for index, point in enumerate(wind_anchor_points, start=1):
        # 读取接口坐标。
        coordinates = [float(value) for value in point["coordinates"]]
        # 计算向下三米的候选包络最小角点。
        minimum = [coordinates[0] - WIND_ANCHOR_LENGTH_M / 2.0, coordinates[1] - WIND_ANCHOR_WIDTH_M / 2.0, coordinates[2] - WIND_ANCHOR_HEIGHT_M]
        # 计算包络最大角点。
        maximum = [coordinates[0] + WIND_ANCHOR_LENGTH_M / 2.0, coordinates[1] + WIND_ANCHOR_WIDTH_M / 2.0, coordinates[2]]
        # 绘制风锚立面包络。
        draw_box_2d(elevation_axis, minimum, maximum, 0, 2, WIND_ANCHOR_COLOUR, 1.35, 0.90)
        # 绘制风锚平面包络。
        draw_box_2d(plan_axis, minimum, maximum, 0, 1, WIND_ANCHOR_COLOUR, 1.35, 0.90)
        # 绘制风锚三维包络。
        draw_box_3d(model_axis, minimum, maximum, WIND_ANCHOR_COLOUR, 1.15, 0.90)
        # 在平面标注风锚编号。
        plan_axis.text(coordinates[0], coordinates[1] + (1.4 if coordinates[1] >= 0.0 else -1.4), f"风锚{index}", color=WIND_ANCHOR_COLOUR, fontsize=8, ha="center")
    # 读取四个塔基接口点。
    tower_base_points = points_with_role(ir_data, "TOWER_FOUNDATION_INTERFACE")
    # 读取四个塔结构顶点并按XY建立映射。
    tower_top_by_xy = {(round(float(point["coordinates"][0]), 6), round(float(point["coordinates"][1]), 6)): point for point in points_with_role(ir_data, "TOWER_STRUCTURAL_TOP")}
    # 遍历四个塔柱轴。
    for base_point in tower_base_points:
        # 读取塔基坐标。
        base = [float(value) for value in base_point["coordinates"]]
        # 读取匹配塔顶坐标。
        top = [float(value) for value in tower_top_by_xy[(round(base[0], 6), round(base[1], 6))]["coordinates"]]
        # 计算候选塔柱包络最小角点。
        minimum = [base[0] - TOWER_SECTION_M / 2.0, base[1] - TOWER_SECTION_M / 2.0, base[2]]
        # 计算候选塔柱包络最大角点。
        maximum = [base[0] + TOWER_SECTION_M / 2.0, base[1] + TOWER_SECTION_M / 2.0, top[2]]
        # 绘制塔柱立面包络。
        draw_box_2d(elevation_axis, minimum, maximum, 0, 2, TOWER_COLOUR, 1.45, 0.80)
        # 绘制塔柱平面包络。
        draw_box_2d(plan_axis, minimum, maximum, 0, 1, TOWER_COLOUR, 1.25, 0.80)
        # 绘制塔柱三维包络。
        draw_box_3d(model_axis, minimum, maximum, TOWER_COLOUR, 1.25, 0.80)
    # 在立面绘制两个基础控制高程见证线段，每段宽六点五米。
    for tower_x_m in (0.0, 82.0):
        # 绘制z=-4.50m基础控制面投影。
        elevation_axis.plot([tower_x_m - 3.25, tower_x_m + 3.25], [-4.50, -4.50], color=FOUNDATION_COLOUR, linewidth=2.2, alpha=0.95)
        # 绘制z=-11.00m桩底控制面投影。
        elevation_axis.plot([tower_x_m - 3.25, tower_x_m + 3.25], [-11.00, -11.00], color="#874A32", linewidth=2.2, alpha=0.95)
    # 设置立面标题，明确新增对象为只读参考。
    elevation_axis.set_title("纵向立面｜索鞍半径、主锚、风锚、塔与基础参考层", fontsize=12)
    # 设置立面X轴标签和单位。
    elevation_axis.set_xlabel("桥纵向 X / m")
    # 设置立面Z轴标签和单位。
    elevation_axis.set_ylabel("相对桥面 Z / m")
    # 设置立面显示范围，覆盖两端主锚和桩底。
    elevation_axis.set_xlim(-32.0, 113.0)
    # 设置立面高程范围。
    elevation_axis.set_ylim(-12.5, 11.5)
    # 开启立面浅色网格。
    elevation_axis.grid(True, linewidth=0.35, alpha=0.35)
    # 设置平面标题。
    plan_axis.set_title("平面｜四个外风锚与左右主锚位置", fontsize=12)
    # 设置平面X轴标签。
    plan_axis.set_xlabel("桥纵向 X / m")
    # 设置平面Y轴标签。
    plan_axis.set_ylabel("桥横向 Y / m")
    # 设置平面纵向范围。
    plan_axis.set_xlim(-32.0, 113.0)
    # 设置平面横向范围，覆盖四个外风锚。
    plan_axis.set_ylim(-18.0, 18.0)
    # 开启平面网格。
    plan_axis.grid(True, linewidth=0.35, alpha=0.35)
    # 设置三维标题。
    model_axis.set_title("CAD Reference v0.2｜新增对象不参与分析", fontsize=12)
    # 设置三维X轴标签。
    model_axis.set_xlabel("X / m")
    # 设置三维Y轴标签。
    model_axis.set_ylabel("Y / m")
    # 设置三维Z轴标签。
    model_axis.set_zlabel("Z / m")
    # 设置等轴查看角度，使锚碇和桥面同时可见。
    model_axis.view_init(elev=22.0, azim=-58.0)
    # 设置三维包围比例，反映全桥长宽高数量级。
    model_axis.set_box_aspect((145.0, 36.0, 24.0))
    # 构造五类对象图例。
    legend_handles = [Patch(facecolor=BASE_COLOUR, alpha=0.55, label="N07分析参考几何"), Patch(facecolor=SADDLE_COLOURS[0], alpha=0.85, label="索鞍半径候选见证"), Patch(facecolor=MAIN_ANCHOR_COLOUR, alpha=0.80, label="主锚局部包络"), Patch(facecolor=WIND_ANCHOR_COLOUR, alpha=0.80, label="风锚候选包络"), Patch(facecolor=TOWER_COLOUR, alpha=0.80, label="塔柱候选截面包络")]
    # 把图例放在右侧三维子图的空白上部，避免与总标题和左侧标题重叠。
    model_axis.legend(handles=legend_handles, loc="upper right", bbox_to_anchor=(0.98, 0.98), frameon=False, fontsize=9)
    # 在右侧空白区添加用途边界说明，避免占用左侧视图标题空间。
    figure.text(0.735, 0.965, "DETAIL_REFERENCE / UNRESOLVED_PLACEMENT\n非制造模型｜非完整FEM", ha="center", va="top", fontsize=11, color="#444444")
    # 以180 DPI保存PNG，得到适合直接查看的清晰预览。
    figure.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight", facecolor="white")
    # 关闭画布释放内存和文件句柄。
    plt.close(figure)
    # 打印输出路径和文件大小供自动化日志使用。
    print(json.dumps({"status": "PASS", "preview": str(OUTPUT_PATH), "bytes": OUTPUT_PATH.stat().st_size}, ensure_ascii=False, indent=2))
    # 返回成功退出码零。
    return 0


# 仅当脚本直接执行时调用主程序。
if __name__ == "__main__":
    # 把主程序退出码交给运行时。
    raise SystemExit(main())
