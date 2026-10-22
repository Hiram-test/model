# 多源实测误差形式化参数更新原型

本原型把图纸、点云和传感器分别编译为三类确定性对象，再执行简支梁静力参数更新：

1. 图纸经视觉语义解析形成结构 IR，明确梁、支承、荷载、截面、测点和允许更新的参数类型。
2. 点云形成实际几何场，先修正跨度、截面惯性矩和初始线形，避免几何误差被弹性模量吸收。
3. 传感器形成带确定性误差界的响应区间。
4. 实测误差必须满足边界形式、对称形式和参数响应签名，才能触发参数更新。
5. 更新后必须通过后置条件：全部计算响应进入传感器误差带；不相容时返回 `REJECTED`，不输出“最佳拟合参数”。

## 当前可运行结论

示例图纸给出 `b=0.30 m`、`h=0.50 m`，点云测得实际平均截面为 `0.30 m × 0.48 m`。当前模型弹性模量为 `230 GPa`，传感器数据来自 `200 GPa` 的实际梁并附加有界测量误差。

运行结果：

- 点云/图纸惯性矩比：`0.884736`；
- 允许的弹性模量区间：`[199.422, 200.426] GPa`；
- 执行代表值：`199.923 GPa`；
- 忽略点云截面、仅依据图纸几何时，会把材料参数错误更新为约 `176.879 GPa`；
- 人为加入左右不对称的传感器误差后，系统拒绝全局弹性模量更新。

## 运行

```bash
python -m pip install -r requirements.txt
python run_demo.py
python -m pytest -q
```

输出位于：

- `results/demo/drawing_semantics.generated.json`：从原始 SVG 编译得到的结构语义 IR；
- `results/demo/formal_update_receipt.json`：完整机器判定凭证；
- `results/demo/REPORT.md`：简洁工程报告。

## 数据接口

### 图纸视觉语义

`examples/beam_static_drawing.svg` 是示例原始图纸。默认运行时，`drawing_adapter.py` 直接从 SVG 的可见线条、支承符号、滚轮、荷载线、尺寸文字与测点圆标中编译 `results/demo/drawing_semantics.generated.json`，并保留每个关键实体的证据框。对于扫描图、PDF 或现场照片，视觉模型必须输出同一结构 IR；数值程序只接受状态为 `VERIFIED` 的 IR，不读取自然语言解释。

### 点云

`examples/pointcloud.csv` 使用统一坐标系，列为：

```text
point_id,x_m,y_m,z_m
```

当前版本在各纵向站位提取矩形截面的宽度、深度、惯性矩和中心线。点云跨度与图纸相差超过 10 mm 时直接停止。

### 传感器

`examples/sensors_static.csv` 的列为：

```text
sensor_id,x_m,displacement_mm,bound_mm
```

`bound_mm` 是确定性误差界，不表示标准差或置信区间。

## 代码结构

- `drawing_adapter.py`：从源 SVG 图纸识别梁、支承、荷载、截面标注和测点，生成带证据框的结构 IR；
- `contracts.py`：图纸、点云、传感器三类输入合同及 fail-closed 校验；
- `mechanics.py`：简支梁静力求解、误差形式检查和参数可行区间演算；
- `pipeline.py`：多源形式化顺序、更新凭证与工程报告生成；
- `formal_update.py`：稳定的公共 API 门面；
- `run_demo.py`：命令行入口；
- `tests/test_formal_update.py`：原始 SVG 编译、几何优先、拒绝不相容误差、视觉语义 fail-closed、逐行注释检查；
- `THEORY.md`：简洁理论推导；
- `VISION_SEMANTIC_CONTRACT.md`：视觉语义输出规范；
- `schema/drawing_semantics.schema.json`：结构 IR 的 JSON Schema。

## 当前边界

当前版本限定为线弹性 Euler–Bernoulli 简支梁、全跨均布荷载、矩形截面和全局均匀弹性模量。点云需预先进入统一工程坐标系。示例 SVG 使用轻量、确定性的源文件语义编译器端到端运行；编译结果状态为 `COMPILED_FROM_SVG`，不是人工图纸审核，也不是猫道附件复现。扫描图、PDF 和现场照片仍通过同一 IR 合同接入视觉模型，从而避免大模型进入连续数值闭环。

扩展到猫道时，图纸 IR 可直接接入现有构件台账，点云负责索线形、门架和锚固几何，GNSS/倾角/索力等观测形成确定性响应区间，CalculiX 生成参数响应签名。更新规则仍保持“前置条件—参数可行集—后置条件”的结构。

## 相关技术基础

- Ghahremani, Khaloo, Mo, and Lattanzi, “Damage Detection and Finite-Element Model Updating of Structural Components through Point Cloud Analysis,” *Journal of Aerospace Engineering*, 2018, DOI: `10.1061/(ASCE)AS.1943-5525.0000885`。
- Eberle and Oberguggenberger, “A new method for estimating the bending stiffness curve of non-uniform Euler–Bernoulli beams using static deflection data,” *Applied Mathematical Modelling*, 2022, DOI: `10.1016/j.apm.2021.12.042`。
- Khan et al., “From Drawings to Decisions: A Hybrid Vision-Language Framework for Parsing 2D Engineering Drawings into Structured Manufacturing Knowledge,” arXiv:`2506.17374`。
- Cerone, Lasserre, Piga, and Regruto, “A unified framework for solving a general class of conditional and robust set-membership estimation problems,” arXiv:`1408.0532`。
