# 章节大纲：猫道抖振图谱与系统预警（供 Grok Build 填充）

> **基线锁**：必须叠在祖先 `3a4250e9f01f41c198967eaa685e497134573049` 上继续（见 `WAVE4_REQUIRED_ANCESTOR`）。
> 开工：`git merge-base --is-ancestor 3a4250e9f01f41c198967eaa685e497134573049 HEAD` 成功后，再跑 `code/test_review_gates.py`。
> 不得从 `078e76b` / `STRUCTURAL_OK` 树另起炉灶。


> **文档性质**：填充脚手架。每小节给出【目的】【输入】【方法要点】【产出】【Grok 填写指令】。
> 仓库根：`catwalk-fem/true3d-extreme/`。所有数字必须来自列出的工件或规范，
> **禁止编造频率 / RMS / 阈值**；占位符一律写 `〔待填:XXX〕`。
> 既有硬约束：附件 2-3 频率与 RMS 只允许在"对照"位置读取；T 族既有三栈括弧
> （柔性端 −29% / 焊接端 −19%~−15%）只能引用，不得宣布复现。

---

## 第一节 结构基本计算

### 1.1 模型来源与简化契约

- 【目的】交代真实三维模型从哪来、简化到什么程度、误差怎么控制。
- 【输入】`artifacts/true3d_model_manifest.json`（R1–R7 契约与质量台账）、
  `code/parse_s10.py` docstring（S10 实测事实：44 索线、双步道带、
  门架索 +8.5 m、1430 横梁排、142 榀门架、21 品通道、塔位 714.5/2995.3 m）、
  release `catwalk-attachment23-v2.0-s10-20260716`（.db 700 MB 权威源）。
- 【方法要点】S10 V2.0（109k 节点）→ ccx ~7k B31；R1 带并索、R2 纵向粗化、
  R3 参数化门架、R4 涂抹横梁、R5 双弦等效通道、R6 质量折密度、R7 弃 ROTY。
- 【产出】模型事实表 + 契约表 + 质量台账闭合语句（寴 4108.467 t）。
- 【Grok 填写指令】跑 `bash code/run_solver.sh` 后把 manifest 数字填进表格；
  COARSEN=2 收敛档跑一遍，报告 T 族频移作为 R1/R2 误差量化。
