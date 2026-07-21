---
name: engineering-drawing-data-extraction
description: >
  从桥梁或猫道 CAD、向量 PDF、扫描 PDF 和图像中提取几何实体、文字、尺寸、材料表、构件表、视图、比例、图层、块和来源定位。
  当需要把图纸转换为机器可读证据，同时保留 CAD 句柄、PDF 页码区域和识别置信度时使用。
---

# 任务

你负责将已冻结源文件转换为“可定位、可验证、未做跨图合并”的图纸实体库。该节点专注忠实提取，不提前决定构件的结构角色和有限元处置。

# 输入契约

- analysis charter；
- source manifest 与当前批准版本；
- xref dependency graph；
- 批准的 CAD/PDF/图像/表格解析器；
- 项目单位与坐标候选；
- OCR 使用阈值和人工复读规则。

每个实体、文字、尺寸和表格单元都必须保存 sourceRef、页/布局定位、解析工具和提取置信度。

# 输出工件

- `drawing_entities.json`；
- `extracted_tables.json`；
- `view_register.json`；
- `dimension_candidates.json`；
- `text_candidates.json`；
- `extraction_coverage_report.json`；
- `extraction_issues.json`；
- 关键证据裁剪图或向量快照。

# 不可违反的规则

1. CAD 原生向量和文字优先于 OCR。
2. PDF 先判断向量页和栅格页；只对栅格区域执行 OCR。
3. OCR 结果必须保存字符级或字段级置信度、像素区域和原图引用。
4. 图纸标注尺寸与几何量测分别存储，禁止在本节点覆盖其中任一项。
5. 未标定比例的图像不得通过像素距离推导工程尺寸。
6. 小数点、负号、直径符号、角度、上下标、钢筋符号和单位必须进行专门校验。
7. CAD 块实例要保存块定义、插入点、比例、旋转和嵌套变换。
8. 实体句柄、layer、linetype、color、layout、viewport 和 xref 来源全部保留。
9. 重复视图、详图和表格行暂不去重，只建立候选关联。
10. 任何解析器丢弃的对象类型要进入 unsupported entity register。

# 工作顺序

## 1. 页面和布局分割

识别 CAD model space、paper space、layout、viewport；识别 PDF 页面尺寸、旋转、标题栏、图框、图号和比例。为每个逻辑图纸分配 SHEET-ID。

## 2. 视图识别

识别平面、立面、纵断面、横断面、节点详图、轴测图、索系线形图、材料表和说明页。每个视图记录 VIEW-ID、页面区域、比例、方向标记和候选坐标轴。

## 3. 几何提取

提取 line、polyline、arc、circle、ellipse、spline、hatch boundary、3D face、mesh、solid、region、point、dimension geometry 和 block instance。保存原始坐标、变换链和几何容差。

对于 PDF 向量，保存 path、stroke、fill、clipping 和 text transform；避免把所有线段提前拼接成轮廓。

## 4. 文字与尺寸

提取文字内容、字体、方向、位置、样式和关联引线。尺寸对象保存：显示文字、测量值、端点、单位、精度、前后缀、公差和 override 状态。

扫描图 OCR 至少进行：

- 方向校正；
- 局部二值化或增强；
- 文字与线框分离；
- 数字字段二次识别；
- 与几何或表格行列结构交叉验证。

关键尺寸若仅有低置信 OCR，标记 CRITICAL 或 MAJOR，不直接进入 accepted dimension。

## 5. 表格提取

保留行列坐标、合并单元格、表头层级、单位行、脚注和跨页关系。材料表、构件表、螺栓表、钢筋表和工程量表分别分类。

每个单元格记录原文、标准化值、单位、置信度和 source locator。

## 6. 覆盖率统计

按图纸页和视图统计：

- 可解析实体数与失败数；
- 文字和尺寸覆盖率；
- 表格单元格覆盖率；
- unsupported 对象；
- OCR 低置信字段；
- 已知尺寸的提取一致性。

## 7. 快照验证

为关键尺寸、材料、构件编号和坐标点生成裁剪图。对 CAD 可生成实体高亮快照。后续节点通过 evidenceId 打开相同区域复核。

# 质量门

G2 通过条件：

1. 所有批准图纸页和布局均已处理；
2. 关键视图、标题栏、图号和修订信息已识别；
3. 关键尺寸和材料字段具有原生提取或经双重校核的 OCR；
4. 已知尺寸的量测比例与声明单位一致；
5. unsupported 对象已评估其工程影响；
6. 提取覆盖率达到 charter 规定阈值；
7. 每个候选值都可定位到源文件和页面/实体区域。

若控制几何只能依赖未标定图像、关键材料字段无法辨认或解析器丢失关键对象，G2=`BLOCKED`。

# 失败处理

同一文件允许使用第二批准解析器复核。两套结果的实体数、extents、文字、尺寸和表格差异要生成对比报告。解析器冲突不能通过简单取平均解决，应在 G2 或 G3 形成问题。

# 完成检查

1. 是否区分原生向量、原生文字和 OCR？
2. 是否保留每个实体的原始 locator 和变换链？
3. 是否保存尺寸显示值与几何测量值？
4. 是否处理块、xref、layout 和 viewport？
5. 是否对表格保留行列与脚注结构？
6. 是否对关键数字执行二次识别和几何校核？
7. 是否统计 unsupported 对象和覆盖率？
8. 是否为关键证据生成可视快照？
