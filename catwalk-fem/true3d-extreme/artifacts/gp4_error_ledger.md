# G-P4 错误账

停笔。`conclusion_allowed=false`。本文件不是结论章节，不宣布科学成功。

## 门禁

| 门 | 结果 | 数 |
|---|---|---|
| G-P1 | PASS | 44 索线，F/g ≡ MASS21 = 963.811381 t |
| G-P2 | PASS | 4108.466 t vs S10 4108.467 t，rel 2.4e-7 |
| UY | PASS | 84/5018，frac 0.0167；禁止全网钉死 |
| G-P3 | PASS | 单增量 3 次牛顿，`.sta` 收敛，Job finished |
| G-P4 | **FAIL** | 见下 |

## G-P4 两条独立失败

1. 前 100 阶仍有 4 个残差刚体（~1.7e-4 / 2.0e-4 / 3.9e-4 / 1.3e-3 Hz），已从 `modal_basis.npz` 剔除；不是膨胀 B31 自旋。
2. 末牛顿残差 195.342234 N，自重 4.0287617e7 N，resid/W = 4.85e-6，大于锁死的 `FORCE_OVER_W_MAX=1e-6`。未放宽。RF 全场合力因 ccx 2.21 `TOTALS` 段错误用残差作代理。

首个结构模态 0.03904477 Hz（LS1 向）。deck `5ebc64fae00a`，COARSEN=4。

## 本轮因此不做

- 不写结论章节
- 不重配正式十四行
- 不重跑 C4 / COARSEN=2
- 不把 UY 钉到全网
- 不把 resid/W 门改成 1e-5

## 外部输入占位

- 气动、破断力：已从 `attach23_extract.json` 写入 `config/site_wind.json`
- RMS 沿跨图：PDF 本树不在；`attach23_rms_digitized.csv` 只有表 5-1 三点，禁止插值
- C 级 15 项：保持 `unverified_C`

wave-4 SHA `3a4250e9` 仍是本分支 git 祖先（`merge-base --is-ancestor` exit 0）。禁止把缺失对象或单提交压扁当成通过，禁止 rebase 退回旧树。
