# Grok Build 审核清单（Hiram-test/model · 猫道真实三维+图谱+预警链）

工作基线分支：`cursor/agentic-catwalk-fea-d416`（脚手架：`catwalk-fem/true3d-extreme/`）。
Grok 应按 `report/chapter_outline_for_grok.md` 的六步执行序推进。
审核流程：fetch 分支 → 对 merge-base 逐文件审 diff → 轻量门本机复跑 →
错误直接修在同分支回推 → 更新 `/cursor/stores/self/grok-watch/baseline.json` → 向用户报波次。

## 框架红线（逐条核）

1. **隔离**：附件 2-3 频率/RMS 只允许出现在对照节点（配对表、A4 图）；
   建模/求解脚本与 deck 内不得 import 或硬编码附件数字；T 族只引三栈括弧
   （柔性端 −29% / 焊接端 −19%~−15%），不得写"复现/一致"。
2. **门禁**：G-P1 44 索线成链 + ΣF/g≡Σm21=963.811381 t；G-P2 台账对
   4108.467 t 相对差 <1%；G-P3 静力收敛 exit 0；G-P4 前 100 阶无自旋伪模态、
   全场合力 ≤1e-6×总重。任何 gate FAIL 不得进结论章节。
3. **锁定配对**：族内频率序；禁半波 MAC 升级；禁 TS2→TS3 改配；
   参考 CSV 列名 internal_id/frequency_hz 不得改。
4. **主曲线法验收**：43 事件点上主曲线插值 vs 逐工况直算交叉验证误差 <5%，
   附直方图；不过门改方法，不许放宽门或删事件点。
5. **非平稳降级**：tornado/downburst/derecho 一律 stationarity=reference_only，
   出图斜纹/角标；不得用平稳谱结果对这些工况下"复现"性结论。
6. **阈值出处**：蓝黄橙红任何数字必须带规范/附件/图纸出处；
   无出处保持〔待填〕且正文声明"阈值未定版不可上线"。
7. **工况库**：15 项 C 级先复核或保留"未复核"角标；不得新增无来源工况；
   口径换算链固定（1-min÷1.14 / 2-min÷1.06 / 3-min÷1.05 / 3s÷1.42）。
8. **ccx 陷阱**：禁 TYPE=MASS×PERTURBATION（质量走密度分箱）；索禁 T3D2（用 B31）；
   B31 禁 BOX 截面（RECT 双向惯矩匹配 rect_match）；单位 t/mm/s/N，
   ρ_air=1.225e-12 t/mm³。
9. **建模器契约**：节点编号 100000*(g+1)+k 不得破坏（buffeting 通道算子依赖）；
   R1–R7 任何变更写进 manifest 并在正文复述；COARSEN=2 收敛档必须跑并报 T 族频移。
10. **证据纪律**：所有数字溯源到 artifacts 文件或规范条文；每图脚注
    deck sha + 图谱版本 + 气动版本；未跑求解不得填"结果"。
11. **引擎语义**：buffeting.py 四通道定义（L/V/Tcw/Tg）与峰值因子公式不得改语义；
    要改必须在 PR 描述声明依据。
12. **仓库卫生**：每阶段即时 commit；>50 MB 结果文件（.frd 等）不入库
    （走 release 或 .gitignore）；不得删改他人既有工件（尤其 double-mct-buffeting
    与 agentic-fea 的锁定证据）。

## 轻量复跑命令（审核时能跑的都跑）

```bash
cd /workspace && git fetch origin <branch> && git checkout <branch>
python3 -c "import json;json.load(open('catwalk-fem/true3d-extreme/artifacts/extreme_weather_library.json'))"
bash -n catwalk-fem/true3d-extreme/code/run_solver.sh
python3 -m py_compile catwalk-fem/true3d-extreme/code/*.py
# 若 Grok 已跑求解并提交 artifacts：核 G-P1/G-P2 断言块（run_solver.sh 内嵌）
# 若提交了 tex：xelatex 双跑核 0 error
```

## 报告格式（给用户）

按波次：Grok 推了什么 → 哪些红线过/不过 → 我改了什么（提交号）→ 门禁状态表 → 下一波预期。
