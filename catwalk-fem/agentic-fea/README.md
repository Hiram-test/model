# Agentic Catwalk FEA（19-skill 全流程执行，2026-08-28）

从图纸/MCT 源出发，按仓库 `bridge-fem-skill-suite` 的 19 个技能节点（S00–S18，Gate G0–G16）
走通张靖皋南航道桥施工猫道的 agentic FEA 全流程：CalculiX 2.21 全三维双幅模型、
NLGEOM 静力 + 80 阶预应力摄动模态、锁定规则表 4-1 正式配对、附件 2-3 指标汇编。

**终稿报告：`report/agentic_catwalk_fea_cn.pdf`**

## 关键数字

- 质量台账 4108.468 t（对审计值闭合 1.2 kg）；单元体积对 A·L 差 1.6e-5；全场合力 ~10 N / 4e7 N。
- 静力：全载荷单增量牛顿 3 迭代收敛（残差 0.066%）；80 阶模态 22.8 s。
- 表 4-1：MAE 5.59% / RMS 7.75%；非 T 3.93%；**T 族 11.70%**（TA1 −18.5 / TS1 −8.6 / TS2 −7.9%）；VS2 −15.6%。
- 跨栈括弧（TA1）：ROM 柔性端 0.0711（−28.7%）→ **ccx 焊接端 0.0811（−18.5%）** →
  f99 E20 弹簧 0.0844（−15.2%）→ 附件 0.0996（在全部公开输入可达域之外，第三次独立确认）。

## ccx 2.21 求解器陷阱（本次二分定位并归档）

1. `TYPE=MASS` × `*FREQUENCY,PERTURBATION` → `add_bo_st` 致命错（质量改走逐单元密度分箱）。
2. T3D2 膨胀产生截面自旋伪模态（前 80 阶全伪）→ 索用 B31 方形等积截面。
3. SPC 反力迁移至膨胀 knot 节点（原节点 RF≡0）→ 反力核验用全场 FORC 合力。
4. BOX 截面仅限 B32R，而 B32R 与摄动步冲突 → 通道梁 RECT 等效。

另：MCT 线形+INIFORCE 即平衡态，**全载荷单增量**直接收敛；渐变加载制造
"满预应力×欠重力"非物理中间态而发散。

## 目录

- `code/`：deck 生成、后处理、配对、图件、工件发射（复现命令见 PDF 附录）。
- `solver/`：`double_mct_ccx.inp` 主 deck 及 dat/sta/cvg（.frd 79 MB 不入库）。
- `artifacts/`：模态分类、表 4-1 配对、统计、图件；`skills/` 下 S01–S18 + gate_ledger。
- `report/`：终稿 PDF 与 TeX。
