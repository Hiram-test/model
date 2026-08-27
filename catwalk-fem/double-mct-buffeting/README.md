# 双 MCT—门架索—横通道等效杆抖振复算包

定稿日期：2026-08-05

本包对应《附件 2-3 后续计算：双 MCT—门架索—横通道等效杆抖振响应》数学例题讲义。它取代此前所有单索、刚性 system-roll 或普通门架横剪代理版本。

## 模型口径

- 两个完整 MCT 平面，中心距 42.9 m。
- 每幅保留 729 个承重索 TENSTR、394 个门架索 TENSTR、源支承、初张力和质量。
- 每幅 50 个普通门架用有限门架自由转角凝聚得到的秩一轴杆替换；等效 `EA=199405719.09780553 N`。
- 21 个横通道站删除左右原 property-3 TRUSS，再各装配一个四端口 12×12 门架—横通道凝聚矩阵。
- 四端口顺序为 `B_L,T_L,B_R,T_R`，各保留 `UX,UY,UZ`，完整非对角项均保留。
- 凝聚件新增密度为零；总质量闭合为 4108.467045 t。

## 名义抖振工况

- 平均猫道高度风速：44.9 m/s；30.1 m/s 仅为 U10 字面敏感性。
- 风频带：1/600–2 Hz；600 s；dt=0.05 s。
- 结构阻尼比：1%。
- 左右幅同一顺桥位置共用风场；沿跨相干衰减常数 C=7。
- 150 阶模态、5 组固定随机种子，频域周期稳态响应。
- 三分力直接来自附件离散 CSV，采用零攻角 PCHIP 导数的一阶准定常阵风核。

关键名义结果：跨中横向均值 47.855 m，标准差 18.153 m；主跨单根承重索 `mean+3.5σ=760.988 kN`，对 2380 kN 破断力的比值为 3.128。

## 推荐复现顺序

在包根目录对应的原工作区结构中运行：

```bash
python output/double_mct_equivalent_passage_model.py --modes 80 --output output/double_mct_results_gate_corrected_final
python output/double_mct_buffeting_frequency_domain.py --output output/double_mct_buffeting_results_gate_corrected_final --modes 150 --seed-count 5
python output/build_double_mct_report_assets.py
```

PDF 使用 XeLaTeX 编译两遍：

```bash
xelatex -interaction=nonstopmode -halt-on-error -output-directory output/pdf output/pdf/double_mct_catwalk_buffeting_worked_examples_final_cn.tex
xelatex -interaction=nonstopmode -halt-on-error -output-directory output/pdf output/pdf/double_mct_catwalk_buffeting_worked_examples_final_cn.tex
```

## 目录

- `report/`：定稿 PDF、TeX 与报告图表。
- `code/`：结构、抖振、图表、模态独立核查和反力独立恢复脚本。
- `inputs/`：权威 MCT、21 站映射、普通门架审计、四端口矩阵、三分力 CSV 和附件反力映射。
- `structural_results/`：模态、拓扑、节点/单元审计和模型审计。
- `modal_validation/`：附件表 4-1 的 14 行独立配对、残差、机制筛查和能量分类。
- `buffeting_results/`：名义响应、索力、反力、风场检查和保存的 150 阶响应状态。
- `sensitivity/`：风速、频带、相干、阻尼与模态数敏感性摘要。
- `reaction_validation/`：108 个约束 DOF 的独立恢复、附件 Y/Z 对照和审计。
- `SHA256SUMS.txt`：交付包内文件指纹。

## 滚转升级（2026-08-27，理论推导修复）

针对扭转族偏差的理论推导修复见 `report/double_mct_torsion_theory_fix_cn.pdf`：
双索组等效（±b_B/±b_T）、双簇平动端口凝聚（`code/condense_h10_cluster_ports.py`）、
二期质量空间化（`code/double_mct_roll_upgraded_model.py`，结果在 `roll_upgraded_results/`）。
主跨 L/V 行改善、呼吸与门架索解耦分支治愈；T 族三行几乎不动，并被证明处于
"审计部件扭转可达域"之外——附件 T 行隐含每品门架 ~1.5e4 N·m/rad 的滚转连接柔度，
比审计钢结构刚接低 2–4 个数量级（详见 PDF 第 9 节与 `roll_upgraded_results/roll_upgraded_findings.md`）。

## 解释边界

- 14 模态总体 MAE 5.92%，非扭转族 3.12%，扭转族 16.21%。
- 从 M37 起存在门架索横向解耦敏感分支；局部 roll 虽在 100–150 阶数值收敛，仍不能当作真实门架横剪已经恢复。
- 150 阶最高频率 0.579 Hz，只支持当前低频位移和索力复算，不支持 2 Hz 加速度、舒适度、疲劳或局部应力验收。
- 多数锚/塔边跨支反力在当前主跨加载路径下近零，不能冒充附件完整四跨反力复现。
- 附件缺失阻尼、摩阻风速、相干常数、左右幅相关性和随机相位，因此绝对 RMS 必须随敏感性范围一并使用。

原附件 PDF 未复制进本包；其 SHA-256 为 `d17d4061c5726c10b88cc80f3f292b16f0dbf3408e032a30840b1bcaad9173d3`。
