# 双 MCT—门架索—横通道等效杆：CalculiX 线性模态卡（云 Cursor 独立实现）

发卡日期：2026-08-27。本目录把仓库既有的双 MCT 等效模型（`structural_results/` CSV + MCT 源）
翻译成可跑的 CalculiX `*FREQUENCY` 卡，并附独立 scipy 复核与 GitHub Actions 运行。
**not_a_scientific_claim**：本页只声明"卡可跑、翻译与源数据一致"，不声明任何科学结论；
求解器能出数不等于模型对物理对。

## 一、垂度核对（SAG_CHECK）

几何逐字取自 `structural_results/double_mct_nodes.csv`（即 MCT 源坐标平移复制双幅），
未拉直、未用弦线代替折线、未抬高跨中：

| 项目 | 数值 |
| --- | --- |
| 塔顶 Z（卡内 = MCT 源，节点 729） | 350.3121 m |
| 主跨跨中 Z（卡内 = MCT 源，节点 301，x≈1855 m） | 113.3430 m |
| 塔顶−跨中高差（保住的垂度） | 236.97 m |
| 全部 2250 节点坐标与 MCT 源逐点最大差 | 0.00e+00 m |

明细见 `SAG_CHECK.csv` / `SAG_CHECK.md`（由发卡脚本一并生成）。

## 二、约束（没有钉全网 UY）

只施加 MCT `*CONSTRAINT` 的平动支承，双幅各一份：共 **108 个约束自由度**，
其中 UY 只在 **44 个支承自由度** 上固定（锚碇/塔顶/边跨支点），全网 6750 个平动
自由度的其余部分 UY 自由。卡内无任何整体 UY=0。

## 三、模型口径

- 两幅完整 MCT 平面，中心距 42.9 m；每幅 729 承重索 + 394 门架索 TENSTR、50 普通门架秩一轴杆。
- TENSTR = T3D2（真实 EA）+ 3 个同节点对 SPRING2（k=N/L，dx/dy/dz 各一），
  合成参考切线刚度 `EA/L·dd^T + N/L·(I−dd^T)`（轴向多出 +N/EA ≤0.6%，见 audit）。
  初张力取 `double_mct_source_elements.csv` 的 `initial_force_kn`（源自 MCT *INIFORCE）。
- 质量：**全部集中**（每节点一个 MASS 单元 = 绳单元半长质量 + MCT 第一个 *CONLOAD 块），
  总质量 4108.467 t，与参考闭合值逐位一致；所有单元密度置 1e-9。
- 21 道四端口：按明确指示**不用弹簧拆 12×12**（避免新增自由度）。每站以 K12 主对角块发 3 根
  零质量 T3D2 等效杆：同幅 B–T 弦向杆 k=|K12(B_UZ,T_UZ)|=2.5178e7 N/m ×2、
  跨幅 B_L–B_R 横杆 k=|K12(B_L_UY,B_R_UY)|=3.9956e7 N/m。被舍弃的次要块
  （T–T 横向 1.3e3、同幅 B–T 横向 −2.42e5 N/m 等）记录在 `deck_audit.json`。
  **代价**：相对完整 12×12 参考模型，谱里多出若干近重复的门架索/边跨软分支
  （如 0.03653 Hz 成对模态，主跨承重链振幅≈0）。
- 支承与集中质量直接从 MCT 源读取；未发明新支座。

## 四、求了几阶、证据

单步线性 `*STEP` `*FREQUENCY`：**申请并求出 60 阶**（要求 ≥20），
0.03653–0.20 Hz。证据：`double_mct_frequency.dat`（特征值+参与质量）、
`double_mct_frequency.sta`、`double_mct_frequency.frd.gz`（60 阶振型，解压即 .frd）、
`run_log.txt`。Actions 每次运行重新发卡、重跑 ccx 并上传未压缩 .sta/.dat/.frd 工件
（workflow：`.github/workflows/double-mct-ccx.yml`）。

## 五、独立复核（mode_comparison.csv）

- `independent_scipy_check.py` 用同一批 CSV 独立装配 K、M 并 eigsh 求解：
  **ccx 与 scipy 60 阶逐阶最大偏差 0.0001%** —— CalculiX 翻译与源数据一致。
- 参考 80 阶表（完整 12×12 四端口）前 20 阶与 ccx 谱最近邻配对全部 |Δf| ≤ 1.19%
  （LS1 +0.20%、VA1 0.00%、TA1 −0.06%、LA1 +0.08%、TS1 +0.22%、VS1 +0.03%、LS2 +0.09%…），
  见 `mode_comparison.csv` 第二段。此配对表为新增文件，未改动
  `modal_validation/gate_corrected_reference_table4_1_matching.csv`。

## 六、这版 ccx 的两个坑（复现记录）

1. **T3D2 展开质量膨胀**：Debian ccx 2.20 对细长 T3D2（带真实密度）展开后一致质量约放大
   6.6 倍（3 节点索例：22 387 kg vs 理论 3 396 kg），频率整体错误。对策：密度置 1e-9，
   质量全部走集中 MASS 单元；3 节点索例随即与 scipy 7 位一致。
2. **ARPACK 低频簇停滞**：同一卡申请 25 阶时，最低 13 阶（0.0365–0.110 Hz 紧密簇）被整体跳过，
   谱从 0.1155 Hz 起报；申请 60 阶后低频簇全部找回且与 scipy 逐位一致。
   故本卡固定申请 60 阶。
3. 另：`*SPRING`/`*MASS` 数据行必须带小数点（纯整数行会被判"card without data"），
   发卡脚本统一 `%.10e`。

## 七、复现

```bash
cd catwalk-fem/double-mct-buffeting/ccx
python3 make_ccx_frequency_deck.py     # 只用标准库；重发 .inp + SAG_CHECK + deck_audit.json
ccx -i double_mct_frequency            # ~18 s，出 .dat/.frd/.sta
pip install numpy scipy && python3 independent_scipy_check.py   # 复核 + mode_comparison.csv
```
