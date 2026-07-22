#!/usr/bin/env python3
# 本脚本必须由 FreeCADCmd 执行，用于在已验证的 N07 几何基线上增加只读 CAD 详图参考对象。

# 导入 hashlib，用于计算输入与输出文件的 SHA-256，保证交付可核验。
import hashlib
# 导入 json，用于读取米制几何 IR 并写出机器可读验证报告。
import json
# 导入 math，用于把索鞍候选半径转换为三点圆弧。
import math
# 导入 shutil，用于把冻结的 N07 输入复制为仓库交付基线。
import shutil
# 从 pathlib 导入 Path，用于以明确绝对路径访问仓库和交付目录。
from pathlib import Path
# 从 typing 导入 Any，用于说明通用 FreeCAD 对象和 JSON 值。
from typing import Any

# 导入 FreeCAD 应用模块，用于创建文档、属性、向量和关闭重开验证。
import FreeCAD as App
# 导入 FreeCAD Part 模块，用于创建圆弧、包络实体、控制面和 STEP 文件。
import Part

# 以脚本所在 tools 目录的父目录作为仓库根目录，避免依赖当前工作目录。
REPO_ROOT = Path(__file__).resolve().parents[1]
# 固定本次补模所基于的已关闭 N07 run；该 run 的尺度和拓扑已经独立回读验证。
RUN_ID = "RUN-ZHAQING-GEOMETRY-REBUILD-20260722-005"
# 固定被消费的 N07 工件目录，所有源路径均保持只读。
RUN_N07_ROOT = REPO_ROOT / ".bridge-fem" / "runs" / RUN_ID / "artifacts" / "N07"
# 固定本地 run 中的已验证 FreeCAD 基线文件路径，FreeCAD 内核单位为毫米。
RUN_BASE_FCSTD = RUN_N07_ROOT / "visualization" / "zhaqing_n07_geometry_mm.FCStd"
# 固定本地 run 中的米制求解器无关几何 IR 路径，用于读取稳定点和语义角色。
RUN_BASE_IR = RUN_N07_ROOT / "fem_geometry_ir.json"
# 固定仓库交付目录，脚本只允许在此目录覆盖自身生成的文件。
DELIVERABLE_ROOT = REPO_ROOT / "deliverables"
# 固定可随仓库分发的 N07 FreeCAD 基线文件名，使克隆仓库后仍可复现补模。
DELIVERED_BASE_FCSTD = DELIVERABLE_ROOT / "Zhaqing_Suspension_Bridge_Analysis_Reference_v0.1.FCStd"
# 固定可随仓库分发的米制 N07 几何 IR 文件名，使详图对象可回溯到稳定点。
DELIVERED_BASE_IR = DELIVERABLE_ROOT / "zhaqing_n07_fem_geometry_ir.json"
# 固定补模后的主 FreeCAD 交付文件名；该文件包含分析参考层和只读详图参考层。
OUTPUT_FCSTD = DELIVERABLE_ROOT / "Zhaqing_Suspension_Bridge_CAD_Reference_v0.2.FCStd"
# 固定通用 CAD 交换文件名；STEP 只用于查看，工程追溯仍以 FCStd 和 IR 为准。
OUTPUT_STEP = DELIVERABLE_ROOT / "Zhaqing_Suspension_Bridge_CAD_Reference_v0.2.step"
# 固定验证报告路径；报告保存对象数、尺寸见证、回读状态和文件哈希。
OUTPUT_REPORT = DELIVERABLE_ROOT / "detail_reference_verification.json"
# 固定米到毫米的唯一换算比例；FreeCAD/OCC 内核使用毫米。
M_TO_MM = 1000.0
# 固定索鞍候选见证弧的半角为二十度；该角度只控制可视长度，不解释真实接触范围。
SADDLE_WITNESS_HALF_ANGLE_DEG = 20.0
# 固定主锚局部包络纵向长度为十点五米，来源图 26 的 1050 cm 尺寸链。
MAIN_ANCHOR_LENGTH_M = 10.50
# 固定主锚局部包络横向宽度为七点二米，来源图 26 的 720 cm 尺寸链。
MAIN_ANCHOR_WIDTH_M = 7.20
# 固定主锚局部包络高度为七米，来源图 26 的 700 cm 立面尺寸。
MAIN_ANCHOR_HEIGHT_M = 7.00
# 固定主锚双索接口中心距为四点七米，来源图 26 的 470 cm 原生尺寸。
MAIN_ANCHOR_HOLE_SPACING_M = 4.70
# 固定主锚接口可视球半径为零点一五米；该值只改善可见性，不代表锚孔直径。
MAIN_ANCHOR_MARKER_RADIUS_M = 0.15
# 固定风锚候选包络第一平面尺寸为二点二米，来源图 33 的 220 cm 尺寸候选。
WIND_ANCHOR_LENGTH_M = 2.20
# 固定风锚候选包络第二平面尺寸为一点五米，来源图 33 的 150 cm 尺寸候选。
WIND_ANCHOR_WIDTH_M = 1.50
# 固定风锚上下控制高程差为三米，来源 4125.506 m 与 4122.506 m 标高差。
WIND_ANCHOR_HEIGHT_M = 3.00
# 固定塔柱候选截面边长为一点五米；该值来自塔图 150 cm 尺寸但截面归属尚未冻结。
TOWER_CANDIDATE_SECTION_M = 1.50
# 固定塔基础控制面相对桥面高程为负四点五米，来源塔图标高 4124.54 m。
TOWER_FOUNDATION_CONTROL_Z_M = -4.50
# 固定塔桩底相对桥面高程为负十一米，来源塔图标高 4118.04 m。
TOWER_PILE_BOTTOM_Z_M = -11.00
# 固定塔底部入岩见证长度为两米，来源塔图“嵌入微风化岩层不小于 2 m”。
TOWER_ROCK_EMBEDMENT_M = 2.00
# 固定塔控制面的展示边长为六点五米，来源塔图 650 cm 尺寸且仅作子视图待配准见证。
TOWER_CONTROL_PLANE_SIZE_M = 6.50


# 定义文件 SHA-256 计算函数，以一兆字节分块避免一次性读取较大 STEP 或 FCStd。
def sha256_file(path: Path) -> str:
    # 创建 SHA-256 摘要对象。
    digest = hashlib.sha256()
    # 以二进制只读方式打开目标文件。
    with path.open("rb") as stream:
        # 持续读取一兆字节数据块，直到到达文件末尾。
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            # 把当前数据块加入摘要计算。
            digest.update(chunk)
    # 返回小写十六进制摘要。
    return digest.hexdigest()


# 定义 JSON 对象读取函数，拒绝非对象顶层，避免错误输入被静默接受。
def read_json_object(path: Path) -> dict[str, Any]:
    # 以 UTF-8 读取完整 JSON 文本。
    payload = json.loads(path.read_text(encoding="utf-8"))
    # 顶层不是对象时立即终止。
    if not isinstance(payload, dict):
        # 抛出包含路径的类型错误。
        raise TypeError(f"JSON 顶层必须为对象：{path}")
    # 返回已验证的对象。
    return payload


# 定义源文件选择函数，优先使用仓库交付基线，首次运行时回退到冻结 run 工件。
def choose_source(delivered_path: Path, run_path: Path) -> Path:
    # 已存在交付基线时使用它，保证仓库克隆后的可复现性。
    if delivered_path.is_file():
        # 返回交付基线路径。
        return delivered_path
    # 本地冻结 run 工件存在时允许首次生成。
    if run_path.is_file():
        # 返回冻结 run 路径。
        return run_path
    # 两个受控来源均缺失时拒绝生成。
    raise FileNotFoundError(f"缺少交付基线和冻结 run 输入：{delivered_path}；{run_path}")


# 定义安全生成目标清理函数，只允许删除交付目录内的明确文件路径。
def remove_generated_file(path: Path) -> None:
    # 验证目标父目录就是交付目录，防止错误路径扩大删除范围。
    if path.resolve().parent != DELIVERABLE_ROOT.resolve():
        # 拒绝交付目录外的删除目标。
        raise RuntimeError(f"拒绝清理交付目录外文件：{path}")
    # 目标存在时删除旧的可再生成文件。
    if path.exists():
        # 删除单个明确文件，不执行递归操作。
        path.unlink()


# 定义字符串属性写入函数，统一详图对象的追溯字段。
def add_string_property(target: Any, name: str, value: str, description: str) -> None:
    # 属性尚不存在时创建字符串属性。
    if name not in target.PropertiesList:
        # 把属性放入 DetailReference 分组便于 FreeCAD 属性面板查看。
        target.addProperty("App::PropertyString", name, "DetailReference", description)
    # 把调用值规范为字符串后写入。
    setattr(target, name, str(value))


# 定义字符串列表属性写入函数，保存多个 sourceRef 或 CAD 句柄。
def add_string_list_property(target: Any, name: str, values: list[str], description: str) -> None:
    # 属性尚不存在时创建字符串列表属性。
    if name not in target.PropertiesList:
        # 把属性放入 DetailReference 分组。
        target.addProperty("App::PropertyStringList", name, "DetailReference", description)
    # 去重并稳定排序后写入，避免重复来源造成审计噪声。
    setattr(target, name, sorted({str(value) for value in values}))


# 定义长度属性写入函数，所有输入值都以米传入并显式带单位赋值。
def add_length_property(target: Any, name: str, value_m: float, description: str) -> None:
    # 属性尚不存在时创建长度属性。
    if name not in target.PropertiesList:
        # 把属性放入 DetailReference 分组。
        target.addProperty("App::PropertyLength", name, "DetailReference", description)
    # 使用带 m 单位的字符串赋值，禁止无单位浮点被解释为毫米。
    setattr(target, name, f"{float(value_m)} m")


# 定义通用对象追溯属性函数，保证每个新增 Shape 都明确用途和限制。
def tag_detail_object(target: Any, layer: str, status: str, source_refs: list[str], handles: list[str], description: str) -> None:
    # 标记对象属于只读详图参考层或未解析放置层。
    add_string_property(target, "GeometryLayer", layer, "对象所在几何层。")
    # 明确对象不得自动参与有限元刚度、质量或边界。
    add_string_property(target, "AnalysisParticipation", "NONE", "对象的分析参与状态；NONE 表示只用于 CAD 审查。")
    # 保存证据接受或未解析状态。
    add_string_property(target, "DetailReferenceStatus", status, "详图证据和放置状态。")
    # 保存图纸来源引用。
    add_string_list_property(target, "SourceRefs", source_refs, "支持对象的原始图纸 sourceRef。")
    # 保存原生 CAD 句柄或稳定证据定位。
    add_string_list_property(target, "EvidenceHandles", handles, "支持对象的 CAD 句柄或稳定证据定位。")
    # 保存人可读限制说明。
    add_string_property(target, "EngineeringLimit", description, "对象允许用途和限制。")


# 定义文档分组创建函数，使四类补模对象在 FreeCAD 树中可单独显示或隐藏。
def make_group(document: Any, internal_name: str, label: str, parent: Any | None = None) -> Any:
    # 创建稳定内部名称的文档对象组。
    group = document.addObject("App::DocumentObjectGroup", internal_name)
    # 设置中文可见标签。
    group.Label = label
    # 存在父组时把当前组加入父组。
    if parent is not None:
        # 建立父子树关系。
        parent.addObject(group)
    # 返回新组。
    return group


# 定义带 Shape 的 Part::Feature 创建函数，并统一可见颜色和透明度。
def make_feature(document: Any, group: Any, internal_name: str, label: str, shape: Any, colour: tuple[float, float, float], transparency: int) -> Any:
    # 创建 Part 特征对象。
    feature = document.addObject("Part::Feature", internal_name)
    # 设置用户可见标签。
    feature.Label = label
    # 写入调用方提供的几何 Shape。
    feature.Shape = shape
    # 仅在 ViewObject 可用时设置显示属性。
    if feature.ViewObject is not None:
        # 设置 RGB 显示颜色；颜色不改变工程语义。
        feature.ViewObject.ShapeColor = colour
        # 设置百分比透明度，范围为零到一百。
        feature.ViewObject.Transparency = int(transparency)
    # 把对象加入对应详图分组。
    group.addObject(feature)
    # 返回已创建对象。
    return feature


# 定义米制坐标到 FreeCAD 毫米向量的转换函数。
def vector_mm(coordinates_m: list[float]) -> Any:
    # 对三个坐标统一乘一千并创建 FreeCAD 向量。
    return App.Vector(float(coordinates_m[0]) * M_TO_MM, float(coordinates_m[1]) * M_TO_MM, float(coordinates_m[2]) * M_TO_MM)


# 定义索鞍半径见证弧生成函数；弧顶固定在鞍控点，但不声称它是真实接触中心线。
def saddle_witness_arc(crown_m: list[float], radius_m: float) -> Any:
    # 把半径从米转换为毫米。
    radius_mm = float(radius_m) * M_TO_MM
    # 把可视半角从度转换为弧度。
    half_angle_rad = math.radians(SADDLE_WITNESS_HALF_ANGLE_DEG)
    # 读取弧顶毫米坐标。
    crown_mm = vector_mm(crown_m)
    # 圆心位于弧顶正下方一个半径处，使中点成为圆弧冠顶。
    center_z_mm = float(crown_mm.z) - radius_mm
    # 计算左端点横坐标。
    left_x_mm = float(crown_mm.x) - radius_mm * math.sin(half_angle_rad)
    # 计算左右端点共同高程。
    end_z_mm = center_z_mm + radius_mm * math.cos(half_angle_rad)
    # 构造左端点向量，圆弧位于局部 X-Z 平面。
    left_point = App.Vector(left_x_mm, float(crown_mm.y), end_z_mm)
    # 构造右端点向量。
    right_point = App.Vector(float(crown_mm.x) + radius_mm * math.sin(half_angle_rad), float(crown_mm.y), end_z_mm)
    # 用左端、冠顶和右端三点创建圆弧边。
    return Part.Arc(left_point, crown_mm, right_point).toShape()


# 定义点角色过滤函数，从 IR 中读取指定语义角色的全部稳定点。
def points_with_role(ir_data: dict[str, Any], role: str) -> list[dict[str, Any]]:
    # 返回 roles 数组包含目标角色的点，并按 geometryId 稳定排序。
    return sorted([point for point in ir_data.get("points", []) if role in point.get("roles", [])], key=lambda point: str(point.get("geometryId", "")))


# 定义语义标签连接函数，便于按 LEFT 或 RIGHT 对接口点分组。
def semantic_text(point: dict[str, Any]) -> str:
    # 把全部语义标签用空格连接并转成大写。
    return " ".join(str(value) for value in point.get("semanticLabels", [])).upper()


# 定义三维坐标平均函数，用于计算一组接口点的参考中心。
def mean_coordinates(points: list[dict[str, Any]]) -> list[float]:
    # 空点集没有可定义中心，因此立即终止。
    if not points:
        # 抛出清晰错误。
        raise ValueError("不能计算空点集的平均坐标。")
    # 分别计算 X、Y、Z 三个分量的算术平均值。
    return [sum(float(point["coordinates"][index]) for point in points) / len(points) for index in range(3)]


# 定义两点距离函数，用于验证主锚双索接口四点七米中心距。
def distance_m(first: list[float], second: list[float]) -> float:
    # 计算三个坐标差平方和后开方。
    return math.sqrt(sum((float(first[index]) - float(second[index])) ** 2 for index in range(3)))


# 定义索鞍候选半径对象创建过程，四个鞍位各保留三种原图半径证据。
def add_saddle_details(document: Any, group: Any, ir_data: dict[str, Any]) -> list[Any]:
    # 读取四个索鞍控制点。
    saddle_points = points_with_role(ir_data, "SADDLE_CONTROL_POINT")
    # 数量不是四个时拒绝补模，防止模型拓扑与预期不一致。
    if len(saddle_points) != 4:
        # 抛出数量错误。
        raise RuntimeError(f"索鞍控制点数量应为4，实际为{len(saddle_points)}。")
    # 固定三组半径、来源句柄和显示颜色；R1450 在图中有两个文字句柄。
    radius_records = [(1.420, ["50AF"], (0.90, 0.20, 0.20)), (1.450, ["50B4", "50BE"], (0.95, 0.55, 0.10)), (1.560, ["50B9"], (0.60, 0.15, 0.75))]
    # 建立新增对象列表供后续验证和 STEP 导出。
    objects: list[Any] = []
    # 遍历四个鞍控点。
    for saddle_index, point in enumerate(saddle_points, start=1):
        # 读取当前鞍控点米制坐标。
        crown_m = [float(value) for value in point["coordinates"]]
        # 遍历三组原图半径候选。
        for radius_m, handles, colour in radius_records:
            # 生成稳定内部名称，半径以毫米整数编码。
            internal_name = f"DetailSaddle{saddle_index:02d}R{int(round(radius_m * M_TO_MM))}"
            # 创建候选圆弧 Shape。
            shape = saddle_witness_arc(crown_m, radius_m)
            # 创建可见 Part 对象，圆弧不需要透明度。
            feature = make_feature(document, group, internal_name, f"鞍位{saddle_index} 半径见证 R{int(round(radius_m * M_TO_MM))}", shape, colour, 0)
            # 写入候选半径长度属性。
            add_length_property(feature, "CandidateRadius", radius_m, "原图标注的候选半径；尚未唯一关联到槽底或中心线。")
            # 写入弧顶稳定点引用。
            add_string_property(feature, "CrownPointRef", str(point["geometryId"]), "当前见证弧冠顶对应的 N07 稳定鞍控点。")
            # 标记对象不得被解释为已接受接触中心线。
            tag_detail_object(feature, "UNRESOLVED_PLACEMENT", "NOT_ACCEPTED_AS_CONTACT_CENTERLINE", ["SRC-DWG-29-SADDLE"], handles, "仅证明原图存在该半径；R 标注与槽底、槽中心线、内外板轮廓尚未唯一关联。")
            # 把对象加入返回列表。
            objects.append(feature)
    # 返回十二条候选见证弧。
    return objects


# 定义主锚包络和锚孔接口见证创建过程，左右各创建一个包络和一个接口标记复合体。
def add_main_anchor_details(document: Any, group: Any, ir_data: dict[str, Any]) -> list[Any]:
    # 读取四个主锚接口点。
    anchor_points = points_with_role(ir_data, "MAIN_ANCHOR_INTERFACE_POINT")
    # 数量不是四个时拒绝补模。
    if len(anchor_points) != 4:
        # 抛出数量错误。
        raise RuntimeError(f"主锚接口点数量应为4，实际为{len(anchor_points)}。")
    # 建立新增对象列表。
    objects: list[Any] = []
    # 分别处理左、右主锚。
    for side in ("LEFT", "RIGHT"):
        # 选择语义标签包含当前侧别的两个接口点。
        side_points = [point for point in anchor_points if side in semantic_text(point)]
        # 每侧必须恰有两个索接口点。
        if len(side_points) != 2:
            # 抛出侧别分组错误。
            raise RuntimeError(f"{side} 主锚接口点数量应为2，实际为{len(side_points)}。")
        # 计算两个接口点的参考中心。
        center_m = mean_coordinates(side_points)
        # 以参考中心为包络中心；放置仅用于全桥审查，不解释真实锚体朝向和局部原点。
        base_mm = App.Vector((center_m[0] - MAIN_ANCHOR_LENGTH_M / 2.0) * M_TO_MM, (center_m[1] - MAIN_ANCHOR_WIDTH_M / 2.0) * M_TO_MM, (center_m[2] - MAIN_ANCHOR_HEIGHT_M / 2.0) * M_TO_MM)
        # 创建十点五乘七点二乘七米的透明局部包络实体。
        body_shape = Part.makeBox(MAIN_ANCHOR_LENGTH_M * M_TO_MM, MAIN_ANCHOR_WIDTH_M * M_TO_MM, MAIN_ANCHOR_HEIGHT_M * M_TO_MM, base_mm)
        # 创建主锚包络对象。
        body = make_feature(document, group, f"DetailMainAnchor{side.title()}", f"{side} 主锚局部包络", body_shape, (0.55, 0.36, 0.18), 78)
        # 记录三个已协调局部包络尺寸。
        add_length_property(body, "EnvelopeLength", MAIN_ANCHOR_LENGTH_M, "图26局部包络纵向长度。")
        # 记录局部包络宽度。
        add_length_property(body, "EnvelopeWidth", MAIN_ANCHOR_WIDTH_M, "图26局部包络横向宽度。")
        # 记录局部包络高度。
        add_length_property(body, "EnvelopeHeight", MAIN_ANCHOR_HEIGHT_M, "图26局部包络立面高度。")
        # 标记全局位置和朝向仍需跨图配准。
        tag_detail_object(body, "UNRESOLVED_PLACEMENT", "ACCEPTED_LOCAL_ENVELOPE_GLOBAL_PLACEMENT_REFERENCE_ONLY", ["SRC-DWG-26-ANCHORAGE", "SRC-DWG-01-GENERAL-ARRANGEMENT"], ["1B7C", "1E54", "1C02", "1E16", "1B9F"], "局部尺寸已由原生尺寸链接受；当前包络以接口点均值居中，不能用于施工放样或锚体朝向签认。")
        # 用两个可见球体标出当前双索接口点，不把球半径解释为锚孔直径。
        marker_shape = Part.makeCompound([Part.makeSphere(MAIN_ANCHOR_MARKER_RADIUS_M * M_TO_MM, vector_mm([float(value) for value in point["coordinates"]])) for point in side_points])
        # 创建接口见证对象。
        marker = make_feature(document, group, f"DetailMainAnchor{side.title()}Interfaces", f"{side} 主锚双索接口见证", marker_shape, (0.90, 0.70, 0.15), 0)
        # 记录接受的双索接口中心距。
        add_length_property(marker, "AcceptedHoleSpacing", MAIN_ANCHOR_HOLE_SPACING_M, "图26原生470cm锚孔中心距。")
        # 记录稳定点引用。
        add_string_list_property(marker, "InterfacePointRefs", [str(point["geometryId"]) for point in side_points], "两个主锚接口的 N07 稳定点。")
        # 标记球体只用于位置见证。
        tag_detail_object(marker, "DETAIL_REFERENCE", "ACCEPTED_INTERFACE_SPACING", ["SRC-DWG-26-ANCHORAGE"], ["1D1A"], "双索接口中心距为已接受事实；球体半径仅为显示尺寸，不代表孔径。")
        # 追加主锚包络对象。
        objects.append(body)
        # 追加接口见证对象。
        objects.append(marker)
    # 返回四个主锚详图对象。
    return objects


# 定义四个风锚候选包络创建过程，竖向控制高程接受，平面位置与尺寸归属保留未解析状态。
def add_wind_anchor_details(document: Any, group: Any, ir_data: dict[str, Any]) -> list[Any]:
    # 读取四个风锚接口点。
    anchor_points = points_with_role(ir_data, "WIND_ANCHOR_INTERFACE_POINT")
    # 数量不是四个时拒绝补模。
    if len(anchor_points) != 4:
        # 抛出数量错误。
        raise RuntimeError(f"风锚接口点数量应为4，实际为{len(anchor_points)}。")
    # 建立新增对象列表。
    objects: list[Any] = []
    # 遍历四个风锚接口点。
    for index, point in enumerate(anchor_points, start=1):
        # 读取接口米制坐标，其中 Z=-3.534m 来自图33接受标高。
        coordinates_m = [float(value) for value in point["coordinates"]]
        # 以接口点为包络顶面中心，并向下延伸三米至 z=-6.534m。
        base_mm = App.Vector((coordinates_m[0] - WIND_ANCHOR_LENGTH_M / 2.0) * M_TO_MM, (coordinates_m[1] - WIND_ANCHOR_WIDTH_M / 2.0) * M_TO_MM, (coordinates_m[2] - WIND_ANCHOR_HEIGHT_M) * M_TO_MM)
        # 创建二点二乘一点五乘三米的候选包络。
        body_shape = Part.makeBox(WIND_ANCHOR_LENGTH_M * M_TO_MM, WIND_ANCHOR_WIDTH_M * M_TO_MM, WIND_ANCHOR_HEIGHT_M * M_TO_MM, base_mm)
        # 创建风锚 Part 对象。
        body = make_feature(document, group, f"DetailWindAnchor{index:02d}", f"风锚{index} 候选包络", body_shape, (0.85, 0.42, 0.08), 70)
        # 记录候选平面长度。
        add_length_property(body, "CandidateEnvelopeLength", WIND_ANCHOR_LENGTH_M, "图33的220cm局部尺寸候选；子视图归属尚未冻结。")
        # 记录候选平面宽度。
        add_length_property(body, "CandidateEnvelopeWidth", WIND_ANCHOR_WIDTH_M, "图33的150cm局部尺寸候选；子视图归属尚未冻结。")
        # 记录接受的上下控制高程差。
        add_length_property(body, "AcceptedVerticalControlDifference", WIND_ANCHOR_HEIGHT_M, "4125.506m与4122.506m的接受标高差。")
        # 记录当前接口稳定点。
        add_string_property(body, "InterfacePointRef", str(point["geometryId"]), "当前风锚接口对应的 N07 稳定点。")
        # 标记平面位置和尺寸归属仍为有界候选。
        tag_detail_object(body, "UNRESOLVED_PLACEMENT", "ACCEPTED_VERTICAL_CONTROL_UNRESOLVED_PLAN", ["SRC-DWG-33-WIND-ANCHORAGE", "SRC-DWG-32-WIND-CABLE"], ["ABF5", "AB44", "AA62", "AB2C"], "接口和下部标高已接受；X/Y来自风缆角度下界情景，220/150cm尺寸的子视图归属未冻结。")
        # 追加当前风锚对象。
        objects.append(body)
    # 返回四个风锚包络对象。
    return objects


# 定义塔柱候选截面、基础控制面和入岩见证对象创建过程。
def add_tower_details(document: Any, column_group: Any, foundation_group: Any, ir_data: dict[str, Any]) -> list[Any]:
    # 读取四个塔柱基础接口点。
    base_points = points_with_role(ir_data, "TOWER_FOUNDATION_INTERFACE")
    # 读取四个塔柱结构顶点。
    top_points = points_with_role(ir_data, "TOWER_STRUCTURAL_TOP")
    # 两类点均必须为四个。
    if len(base_points) != 4 or len(top_points) != 4:
        # 抛出塔点数量错误。
        raise RuntimeError(f"塔基/塔顶点数量应为4/4，实际为{len(base_points)}/{len(top_points)}。")
    # 建立以毫米级 X/Y 键索引塔顶点的映射。
    top_by_xy = {(round(float(point["coordinates"][0]), 6), round(float(point["coordinates"][1]), 6)): point for point in top_points}
    # 建立新增对象列表。
    objects: list[Any] = []
    # 遍历四个塔柱基础接口点。
    for index, base_point in enumerate(base_points, start=1):
        # 读取基础点米制坐标。
        base_coordinates_m = [float(value) for value in base_point["coordinates"]]
        # 以 X/Y 坐标读取对应塔顶点。
        top_point = top_by_xy[(round(base_coordinates_m[0], 6), round(base_coordinates_m[1], 6))]
        # 读取塔顶米制坐标。
        top_coordinates_m = [float(value) for value in top_point["coordinates"]]
        # 计算当前塔柱参考高度，单位米。
        column_height_m = top_coordinates_m[2] - base_coordinates_m[2]
        # 高度必须为正数。
        if column_height_m <= 0.0:
            # 拒绝颠倒的塔柱控制点。
            raise RuntimeError(f"塔柱{index}高度无效：{column_height_m}m。")
        # 以塔轴为中心放置一点五米见方的候选截面包络。
        column_base_mm = App.Vector((base_coordinates_m[0] - TOWER_CANDIDATE_SECTION_M / 2.0) * M_TO_MM, (base_coordinates_m[1] - TOWER_CANDIDATE_SECTION_M / 2.0) * M_TO_MM, base_coordinates_m[2] * M_TO_MM)
        # 创建塔柱透明包络实体。
        column_shape = Part.makeBox(TOWER_CANDIDATE_SECTION_M * M_TO_MM, TOWER_CANDIDATE_SECTION_M * M_TO_MM, column_height_m * M_TO_MM, column_base_mm)
        # 创建塔柱 Part 对象。
        column = make_feature(document, column_group, f"DetailTowerColumn{index:02d}", f"塔柱{index} 候选截面包络", column_shape, (0.08, 0.55, 0.25), 82)
        # 记录候选截面边长。
        add_length_property(column, "CandidateSectionSide", TOWER_CANDIDATE_SECTION_M, "塔图150cm尺寸候选；Ⅰ-Ⅰ/Ⅱ-Ⅱ归属尚未唯一协调。")
        # 记录塔柱参考高度。
        add_length_property(column, "ReferenceHeight", column_height_m, "N07塔基接口至塔结构顶的参考高度。")
        # 记录轴线稳定点引用。
        add_string_list_property(column, "AxisPointRefs", [str(base_point["geometryId"]), str(top_point["geometryId"])], "塔柱轴线的基础和顶部稳定点。")
        # 标记截面只作可视候选包络。
        tag_detail_object(column, "UNRESOLVED_PLACEMENT", "ACCEPTED_AXIS_AND_ELEVATIONS_UNRESOLVED_SECTION", ["SRC-DWG-19-TOWER"], ["6766", "67F5", "6721", "66FD"], "塔轴、塔顶和桩底标高已接受；1.50m截面仅为待配准见证，不得用于截面刚度。")
        # 创建底部两米入岩见证体，截面略大于候选塔柱以便观察。
        rock_side_m = TOWER_CANDIDATE_SECTION_M + 0.20
        # 以塔轴为中心建立入岩见证体基点。
        rock_base_mm = App.Vector((base_coordinates_m[0] - rock_side_m / 2.0) * M_TO_MM, (base_coordinates_m[1] - rock_side_m / 2.0) * M_TO_MM, TOWER_PILE_BOTTOM_Z_M * M_TO_MM)
        # 创建两米高入岩见证体。
        rock_shape = Part.makeBox(rock_side_m * M_TO_MM, rock_side_m * M_TO_MM, TOWER_ROCK_EMBEDMENT_M * M_TO_MM, rock_base_mm)
        # 创建入岩见证对象。
        rock = make_feature(document, foundation_group, f"DetailTowerRockEmbedment{index:02d}", f"塔柱{index} 入岩≥2m见证", rock_shape, (0.45, 0.35, 0.25), 58)
        # 记录入岩下界长度。
        add_length_property(rock, "MinimumRockEmbedment", TOWER_ROCK_EMBEDMENT_M, "塔图要求的最小入岩长度。")
        # 标记见证体不代表真实岩面或桩截面。
        tag_detail_object(rock, "DETAIL_REFERENCE", "ACCEPTED_MINIMUM_EMBEDMENT_WITNESS", ["SRC-DWG-19-TOWER"], ["6714", "6715"], "仅见证入岩长度下界；岩面起伏、桩截面和基础刚度均未在本模型中定义。")
        # 追加塔柱包络。
        objects.append(column)
        # 追加入岩见证体。
        objects.append(rock)
    # 读取两个塔位的唯一 X 坐标。
    tower_x_values_m = sorted({round(float(point["coordinates"][0]), 6) for point in base_points})
    # 左右塔位数量必须为两个。
    if len(tower_x_values_m) != 2:
        # 抛出塔位数量错误。
        raise RuntimeError(f"塔位X坐标应为2个，实际为{tower_x_values_m}。")
    # 遍历左右两个塔位。
    for tower_index, tower_x_m in enumerate(tower_x_values_m, start=1):
        # 遍历基础控制面和桩底控制面两个接受标高。
        for level_name, level_z_m, handles, colour in (("FoundationControl", TOWER_FOUNDATION_CONTROL_Z_M, ["673E"], (0.20, 0.55, 0.80)), ("PileBottom", TOWER_PILE_BOTTOM_Z_M, ["66FD"], (0.55, 0.30, 0.20))):
            # 以塔轴中线为中心创建六点五米见方的水平控制面。
            plane_origin = App.Vector((tower_x_m - TOWER_CONTROL_PLANE_SIZE_M / 2.0) * M_TO_MM, (-TOWER_CONTROL_PLANE_SIZE_M / 2.0) * M_TO_MM, level_z_m * M_TO_MM)
            # 创建水平平面 Shape。
            plane_shape = Part.makePlane(TOWER_CONTROL_PLANE_SIZE_M * M_TO_MM, TOWER_CONTROL_PLANE_SIZE_M * M_TO_MM, plane_origin)
            # 创建控制面对象。
            plane = make_feature(document, foundation_group, f"DetailTower{tower_index:02d}{level_name}", f"塔{tower_index} {level_name} z={level_z_m:.2f}m", plane_shape, colour, 72)
            # 记录控制面标高相对桥面值。
            add_length_property(plane, "RelativeElevationMagnitude", abs(level_z_m), "控制面相对桥面高程的绝对值；符号见标签和属性说明。")
            # 记录带符号高程字符串，避免长度属性丢失方向语义。
            add_string_property(plane, "RelativeElevation", f"{level_z_m:.3f} m", "以桥面设计高程为零的带符号控制高程。")
            # 标记平面边长只用于展示，控制高程为接受事实。
            tag_detail_object(plane, "DETAIL_REFERENCE", "ACCEPTED_ELEVATION_DISPLAY_EXTENT_REFERENCE_ONLY", ["SRC-DWG-19-TOWER"], handles, "控制高程已由原图接受；6.50m平面边长只用于显示子视图尺度，不定义真实基础边界。")
            # 追加控制面对象。
            objects.append(plane)
    # 返回十二个塔柱、基础和入岩详图对象。
    return objects


# 定义文档包围盒汇总函数，忽略空 Shape 并返回毫米坐标六界。
def combined_bbox(objects: list[Any]) -> dict[str, float]:
    # 收集具有非空 Shape 的对象包围盒。
    boxes = [obj.Shape.BoundBox for obj in objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
    # 没有有效包围盒时拒绝继续。
    if not boxes:
        # 抛出空几何错误。
        raise RuntimeError("没有可汇总的 Shape 包围盒。")
    # 返回六个毫米边界值。
    return {"xmin_mm": min(box.XMin for box in boxes), "xmax_mm": max(box.XMax for box in boxes), "ymin_mm": min(box.YMin for box in boxes), "ymax_mm": max(box.YMax for box in boxes), "zmin_mm": min(box.ZMin for box in boxes), "zmax_mm": max(box.ZMax for box in boxes)}


# 定义主程序，按输入冻结、补模、导出、关闭重开和报告顺序执行。
def main() -> int:
    # 创建交付目录；已存在时不改变其中其他文件。
    DELIVERABLE_ROOT.mkdir(parents=True, exist_ok=True)
    # 选择首次运行可用的 FreeCAD 基线来源。
    source_fcstd = choose_source(DELIVERED_BASE_FCSTD, RUN_BASE_FCSTD)
    # 选择首次运行可用的几何 IR 来源。
    source_ir = choose_source(DELIVERED_BASE_IR, RUN_BASE_IR)
    # 交付基线尚不存在时复制冻结 FCStd，不覆盖已经发布的基线。
    if not DELIVERED_BASE_FCSTD.is_file():
        # 复制文件元数据和内容。
        shutil.copy2(source_fcstd, DELIVERED_BASE_FCSTD)
    # 交付 IR 尚不存在时复制冻结 JSON，不覆盖已经发布的基线。
    if not DELIVERED_BASE_IR.is_file():
        # 复制文件元数据和内容。
        shutil.copy2(source_ir, DELIVERED_BASE_IR)
    # 后续始终读取仓库交付基线，保证报告路径稳定。
    source_fcstd = DELIVERED_BASE_FCSTD
    # 后续始终读取仓库交付 IR。
    source_ir = DELIVERED_BASE_IR
    # 读取米制几何 IR。
    ir_document = read_json_object(source_ir)
    # 读取 IR 数据主体。
    ir_data = ir_document["data"]
    # 安全删除本脚本以前生成的三个可再生产物。
    remove_generated_file(OUTPUT_FCSTD)
    # 删除旧 STEP 产物。
    remove_generated_file(OUTPUT_STEP)
    # 删除旧验证报告。
    remove_generated_file(OUTPUT_REPORT)
    # 打开只读基线文档；后续 saveAs 写入新文件，不覆盖基线。
    document = App.openDocument(str(source_fcstd))
    # 创建详图参考总组。
    root_group = make_group(document, "DetailReferenceRoot", "DETAIL_REFERENCE｜只读详图参考")
    # 创建索鞍半径证据组。
    saddle_group = make_group(document, "DetailReferenceSaddles", "索鞍半径候选见证", root_group)
    # 创建主锚局部包络组。
    main_anchor_group = make_group(document, "DetailReferenceMainAnchors", "主锚局部包络与接口", root_group)
    # 创建风锚候选包络组。
    wind_anchor_group = make_group(document, "DetailReferenceWindAnchors", "风锚标高与候选包络", root_group)
    # 创建塔柱候选截面组。
    tower_column_group = make_group(document, "DetailReferenceTowerColumns", "塔柱候选截面包络", root_group)
    # 创建塔基础和入岩见证组。
    tower_foundation_group = make_group(document, "DetailReferenceTowerFoundations", "塔基础控制面与入岩见证", root_group)
    # 创建十二条索鞍半径候选弧。
    saddle_objects = add_saddle_details(document, saddle_group, ir_data)
    # 创建四个主锚详图对象。
    main_anchor_objects = add_main_anchor_details(document, main_anchor_group, ir_data)
    # 创建四个风锚候选包络。
    wind_anchor_objects = add_wind_anchor_details(document, wind_anchor_group, ir_data)
    # 创建塔柱、基础面和入岩见证对象。
    tower_objects = add_tower_details(document, tower_column_group, tower_foundation_group, ir_data)
    # 汇总全部新增详图对象。
    detail_objects = saddle_objects + main_anchor_objects + wind_anchor_objects + tower_objects
    # 新增对象总数应为三十二个，数量变化必须显式审查。
    if len(detail_objects) != 32:
        # 抛出对象数不一致错误。
        raise RuntimeError(f"详图参考对象应为32个，实际为{len(detail_objects)}。")
    # 重计算文档，确保全部 Shape 和属性进入稳定状态。
    document.recompute()
    # 保存为新的 v0.2 FCStd 文件。
    document.saveAs(str(OUTPUT_FCSTD))
    # 选择原有曲线、原有表面和全部新增详图 Shape 作为 STEP 导出对象。
    export_objects = [obj for obj in document.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull() and (("GeometryKind" in obj.PropertiesList and str(obj.GeometryKind) in {"CURVE", "SURFACE"}) or "DetailReferenceStatus" in obj.PropertiesList)]
    # 原有759条曲线、6个面和32个详图对象合计应为797个 STEP 导出对象。
    if len(export_objects) != 797:
        # 抛出导出对象数不一致错误。
        raise RuntimeError(f"STEP导出对象应为797个，实际为{len(export_objects)}。")
    # 导出通用 STEP 文件。
    Part.export(export_objects, str(OUTPUT_STEP))
    # 记录原文档内部名称，供关闭使用。
    source_document_name = document.Name
    # 关闭刚生成的文档，强制下一步从磁盘重新反序列化。
    App.closeDocument(source_document_name)
    # 从磁盘重新打开 v0.2 FCStd。
    reopened = App.openDocument(str(OUTPUT_FCSTD))
    # 读取重新打开后的全部详图对象。
    reopened_details = [obj for obj in reopened.Objects if "DetailReferenceStatus" in obj.PropertiesList]
    # 统计无效或空 Shape 对象。
    invalid_detail_objects = [obj.Name for obj in reopened_details if not hasattr(obj, "Shape") or obj.Shape.isNull() or not obj.Shape.isValid()]
    # 重新打开后详图对象仍必须为三十二个。
    detail_count_valid = len(reopened_details) == 32
    # 所有详图 Shape 必须有效。
    detail_shapes_valid = not invalid_detail_objects
    # 从 IR 重新读取左右主锚双索接口点，用实际坐标验证四点七米中心距。
    main_anchor_points = points_with_role(ir_data, "MAIN_ANCHOR_INTERFACE_POINT")
    # 计算左右两侧接口中心距。
    main_anchor_spacings_m = [distance_m([float(value) for value in side_points[0]["coordinates"]], [float(value) for value in side_points[1]["coordinates"]]) for side_points in ([point for point in main_anchor_points if "LEFT" in semantic_text(point)], [point for point in main_anchor_points if "RIGHT" in semantic_text(point)])]
    # 两侧中心距相对4.70m的误差必须小于一纳米量级的数值容差。
    main_anchor_spacing_valid = all(abs(value - MAIN_ANCHOR_HOLE_SPACING_M) <= 1.0e-9 for value in main_anchor_spacings_m)
    # 检查十二条索鞍弧的半径属性集合恰好覆盖四套1420、1450、1560mm。
    saddle_radius_values_mm = sorted(round(float(obj.CandidateRadius.Value), 6) for obj in reopened_details if "CandidateRadius" in obj.PropertiesList)
    # 形成期望的十二个毫米半径值。
    expected_saddle_radius_values_mm = sorted([1420.0, 1450.0, 1560.0] * 4)
    # 比较候选半径集合。
    saddle_radii_valid = saddle_radius_values_mm == expected_saddle_radius_values_mm
    # 汇总重新打开 FCStd 中全部具有 Shape 的对象包围盒。
    reopened_shape_objects = [obj for obj in reopened.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
    # 计算 FCStd 六界包围盒。
    fcstd_bbox = combined_bbox(reopened_shape_objects)
    # 记录重新打开文档内部名称。
    reopened_name = reopened.Name
    # 关闭重新打开的 FCStd。
    App.closeDocument(reopened_name)
    # 创建独立 STEP 回读文档。
    step_document = App.newDocument("ZhaqingStepAudit")
    # 把 STEP 文件插入独立文档。
    Part.insert(str(OUTPUT_STEP), step_document.Name)
    # 重计算 STEP 文档。
    step_document.recompute()
    # 收集 STEP 中全部非空 Shape 对象。
    step_shape_objects = [obj for obj in step_document.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
    # 统计 STEP 无效 Shape。
    invalid_step_objects = [obj.Name for obj in step_shape_objects if not obj.Shape.isValid()]
    # STEP 至少必须包含一个可读 Shape。
    step_nonempty = bool(step_shape_objects)
    # STEP 中全部 Shape 必须有效。
    step_shapes_valid = not invalid_step_objects
    # 汇总 STEP 包围盒。
    step_bbox = combined_bbox(step_shape_objects)
    # 比较 STEP 与 FCStd 六界，允许一微米即0.001mm交换误差。
    bbox_keys = ["xmin_mm", "xmax_mm", "ymin_mm", "ymax_mm", "zmin_mm", "zmax_mm"]
    # 计算六界最大绝对差，单位毫米。
    step_bbox_max_error_mm = max(abs(float(step_bbox[key]) - float(fcstd_bbox[key])) for key in bbox_keys)
    # 判断 STEP 包围盒是否满足一微米容差。
    step_bbox_valid = step_bbox_max_error_mm <= 0.001
    # 关闭 STEP 回读文档。
    App.closeDocument(step_document.Name)
    # 汇总全部强制检查状态。
    checks = {"detailObjectCount": detail_count_valid, "detailShapesValid": detail_shapes_valid, "saddleRadiusWitnesses": saddle_radii_valid, "mainAnchorHoleSpacing": main_anchor_spacing_valid, "stepNonempty": step_nonempty, "stepShapesValid": step_shapes_valid, "stepBoundingBoxRoundTrip": step_bbox_valid}
    # 只有全部检查为真时总状态才为 PASS。
    overall_status = "PASS" if all(checks.values()) else "FAIL"
    # 构造验证报告；JSON 不支持注释，字段含义由 deliverables/README.md 说明。
    report = {"schemaVersion": "1.0.0", "status": overall_status, "modelPurpose": "GEOMETRY_REVIEW_ONLY", "runId": RUN_ID, "freecadVersion": ".".join(App.Version()[:3]), "sourceBaseline": {"fcstd": DELIVERED_BASE_FCSTD.relative_to(REPO_ROOT).as_posix(), "fcstdSha256": sha256_file(DELIVERED_BASE_FCSTD), "ir": DELIVERED_BASE_IR.relative_to(REPO_ROOT).as_posix(), "irSha256": sha256_file(DELIVERED_BASE_IR)}, "outputs": {"fcstd": OUTPUT_FCSTD.relative_to(REPO_ROOT).as_posix(), "fcstdSha256": sha256_file(OUTPUT_FCSTD), "step": OUTPUT_STEP.relative_to(REPO_ROOT).as_posix(), "stepSha256": sha256_file(OUTPUT_STEP)}, "counts": {"detailObjects": len(reopened_details), "saddleRadiusWitnessArcs": len(saddle_objects), "mainAnchorDetailObjects": len(main_anchor_objects), "windAnchorEnvelopes": len(wind_anchor_objects), "towerAndFoundationDetailObjects": len(tower_objects), "stepExportObjects": len(export_objects), "stepImportedShapeObjects": len(step_shape_objects)}, "dimensionWitnesses": {"saddleRadii_mm": saddle_radius_values_mm, "mainAnchorInterfaceSpacings_m": main_anchor_spacings_m, "mainAnchorEnvelope_m": [MAIN_ANCHOR_LENGTH_M, MAIN_ANCHOR_WIDTH_M, MAIN_ANCHOR_HEIGHT_M], "windAnchorVerticalControlDifference_m": WIND_ANCHOR_HEIGHT_M, "towerFoundationControlZ_m": TOWER_FOUNDATION_CONTROL_Z_M, "towerPileBottomZ_m": TOWER_PILE_BOTTOM_Z_M, "towerMinimumRockEmbedment_m": TOWER_ROCK_EMBEDMENT_M}, "roundTrip": {"fcstdBoundingBox_mm": fcstd_bbox, "stepBoundingBox_mm": step_bbox, "stepBoundingBoxMaxError_mm": step_bbox_max_error_mm, "tolerance_mm": 0.001}, "checks": checks, "invalidDetailObjects": invalid_detail_objects, "invalidStepObjects": invalid_step_objects, "engineeringBounds": ["索鞍R1420/R1450/R1560只作为原图半径见证，尚未接受为接触中心线。", "主锚局部包络尺寸已接受，但当前全局放置和朝向只用于参考。", "风锚上下标高已接受，X/Y和平面尺寸子视图归属仍为有界候选。", "塔轴和控制标高已接受，1.50m候选截面及6.50m控制面范围不构成截面刚度或基础实体。", "所有新增对象AnalysisParticipation均为NONE。"]}
    # 以 UTF-8 和两空格缩进写出验证报告，并在文件末尾保留换行。
    OUTPUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 验证失败时返回非零退出码，阻止错误模型被继续发布。
    if overall_status != "PASS":
        # 打印完整失败报告供日志审查。
        print(json.dumps(report, ensure_ascii=False, indent=2))
        # 返回失败退出码一。
        return 1
    # 打印成功摘要供自动化捕获。
    print(json.dumps({"status": overall_status, "fcstd": str(OUTPUT_FCSTD), "step": str(OUTPUT_STEP), "report": str(OUTPUT_REPORT), "detailObjects": len(reopened_details), "stepBoundingBoxMaxError_mm": step_bbox_max_error_mm}, ensure_ascii=False, indent=2))
    # 返回成功退出码零。
    return 0


# 仅当 FreeCADCmd 直接执行本文件时调用主程序。
if __name__ == "__main__":
    # 把主程序退出码交给 Python 运行时。
    raise SystemExit(main())
