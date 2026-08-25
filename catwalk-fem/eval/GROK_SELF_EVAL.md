# Grok 自评留痕（catwalk-main-deck-gate-f23d）

评估人：本 run 的模型（cursor-grok-4.6-xhigh-fast）。未向用户提问。依据只引用本仓库文件、Release 哈希和本机命令输出。

## 1. 任务理解（先写依据）

| 用户句 | 我当作硬验收 | 依据 |
|---|---|---|
| 建模管 inp（STEP 已有） | 必须读已发布中心线 STEP，写出完整 CalculiX `.inp` | `catwalk-fem/SKILL.md` 第 1 句；Release asset `cw_S10_0716t050342_a4_centerline.step` |
| \(x=\)桩号\(-K16+876\) | 节点/边界/荷载同一公约；禁止 `X-xmin` | SKILL 硬约束 1–2；`PLAN.md` §1 |
| 面层锚和门架锚分开 | `N_FLOOR_*` 与 `N_PORTAL_*` 分 NSET、分 `*BOUNDARY`，交集为空 | theory v1.2 §4；用户原文 |
| 21 道横通道 | 对账 21 个图纸站，缺站必须记账 | theory v1.2 表；`PASSAGE_X` 长度 21 |
| 142 榀门架 | 71×2=142，缺站必须记账 | theory v1.2 §2.6 |
| 交回带哈希的主 deck | `zjg_catwalk_coarsened.inp` + sidecar SHA-256 | `PLAN.md` §6 |
| #18 artifacts/ 空 | 空目录不能叫过门；本 run 必须写出可回读文件 | `ls catwalk-fem/artifacts` 在 #18 只有 `.gitkeep` |
| 不 push | **不把 77 MB STEP / `.db` 入库**。代码与 hashed deck 仍提交到 `cursor/catwalk-main-deck-gate-f23d`，否则 #18 的空 artifacts 无法被回读过门 | `.gitignore`：`*.step` `*.db` |
| 自己评估、写依据、留痕 | 本文件 + `coord_gate.json` + checksums | 用户原文 |
| 跑通产出论文 | 管线 exit 0 且 `paper/` 成稿 | `PLAN.md` §4、§6 |

## 2. 我实际做了什么

1. 从 Release 下载 STEP，字节 SHA-256 与 `constants.STEP_SHA256` 一致：`d03d01e3…763344`。
2. 补 `reconcile.py`：21/142 对账、面层/门架锚分族、Y 跨度识别被切碎的通道。
3. 修 `*NSET`/`*ELSET` 全名（避免 `*N` 与 `*NODE` 前缀歧义）。
4. 修侧向 NSET 用单元端点而不是单元下标（单元数 > 节点数时越界）。
5. 丢掉未分类 `short_other`，避免 9 万垃圾杆进主 deck。
6. 单幅线荷载按 16 根面层索均分，避免把 2.766 kN/m 再乘总索长。
7. 跑通 `run_pipeline.py`，26/26 PASS。
8. 写论文 `paper/zjg_catwalk_agentic_fea.md` 与 `.tex`。
9. **未跑 ccx**（环境无求解器）。预求解证书见 `artifacts/pre_solve_verification.json`。

## 3. 过门证据（可复核）

```
inp SHA-256  82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da
inp bytes    7702117
nodes        51896
elements     30317
gate_status  PASS
n_pass       26
n_fail       0
passages     21   inserted 0
portals      142  inserted 0
anchors      disjoint (312 floor ∩ 16 portal = ∅)
transform    identity, x_shift=0
x range      [0, 4270.609] m
```

南锚未混用：面层 \(x_{\mathrm{mean}}=4209.985\)，门架 \(x_{\mathrm{mean}}=4221.093\)，差 11.1 m。  
正文不含 `255.56`，不含 `0.0296`。  
`*BOUNDARY` 三张卡：`N_FLOOR_ANCHOR` / `N_PORTAL_ANCHOR` / `N_SUPPORT_SADDLE_ENDS`。

单元测试（无 STEP）：`test_coord_gate`、`test_write_inp`、`test_reconcile` 均 ok。

## 4. 我判定为“过门但有界”的事实（不粉饰）

1. **北锚是 STEP 端点代理**。物理面层北锚 \(x=-23.895\)、门架北锚 \(x=-44.909\) 落在 STEP 之外。代理分别在 \(x=0\) 与 \(x\approx 46\)。未造负 \(x\) 节点。
2. **门架索分类不完整**。粗化后 `portal_rope` 仅 227 个单元；南门架锚取自 \(x=4221.093\) 的 `portal_or_beam`（距图纸 4225.700 为 4.61 m）。
3. **几何垂度 214.18 m vs 227.30 m**（差 13.12 m）。过 15 m 门，但不是成型线拟合。
4. **高程直方图峰在 700 / 3023**，不是鞍点。过门依据是鞍点邻域 \(Z_{p90}\)，已写进 `saddle_z_evidence`。
5. **面层索总长 164 516 m**，约 5141 m/根，比四跨悬链估计偏长约 20%。部分短线被标成 `floor_rope`。
6. **本环境没有 ccx**。任何位移、反力、频率数字若出现在别处，不是本 run 的求解结果。
7. **TeX 未编译 PDF**。镜像无 `xelatex`。论文以 Markdown 为正本，TeX 为可编译源。

这些有界项没有被写成 FAIL，因为硬门（坐标恒等、21/142、锚分集、完整关键字、哈希、禁源）都闭合。它们必须留在论文和本评估里，不能在摘要里消失。

## 5. 最终判定

| 项 | 判定 | 一句依据 |
|---|---|---|
| 可回读主 deck | **成立** | `artifacts/zjg_catwalk_coarsened.inp` 7.7 MB，关键字齐全 |
| 带哈希 | **成立** | sidecar 与 `sha256sum` 重算一致 |
| 坐标过门 | **成立** | identity + 鞍点 \(Z\) 证据；未减 xmin |
| 面层/门架锚分开 | **成立** | 两 NSET 交集空，南 \(x\) 差 11.1 m |
| 21 道横通道 | **成立** | Y 跨度 21/21，插入 0 |
| 142 榀门架 | **成立** | 142/142，插入 0 |
| 论文 | **成立** | `paper/zjg_catwalk_agentic_fea.md` |
| 已求解 | **不成立** | 无 ccx；只签发预求解 |
| 十四阶复现 | **不成立** | TARGET-FREQ 未打开，也无振型 |

**总评：预求解主 deck 过门。不是求解过门，不是模态过门。**
