# S10 主 OUT 警告逐项处置

主 OUT 实际出现 5 个 `*** WARNING ***` 标记；退出摘要先记录 4 条，摘要之后追加 1 条 elapsed/CPU 性能 warning。两种计数口径一致，未处置警告数为 0。

## W1：约束方程与大变形

- OUT 行：1070083。
- 识别片段：`constraint equations may not be valid for elements that undergo large deflections`。
- 处置：保留为 legacy 约束方程大变形适用性限制；由两步静力收敛、LINK180 全正和 80 阶模态共同约束。
- 状态：`DISPOSED`；形成 legacy 限制：`true`。

## W2：矩阵系数比超过 1E8

- OUT 行：1070207。
- 识别片段：`coefficient ratio exceeds 1.0e8`。
- 处置：保留为矩阵尺度病态限制；本次无负/零主元、两步收敛且 80 个特征值全部收敛。
- 状态：`DISPOSED`；形成 legacy 限制：`true`。

## W3：LS1 参考力矩阈值

- OUT 行：1070266。
- 识别片段：`calculated reference moment convergence value = 7.085126611e-02`。
- 处置：LS1 参考力矩低于内部阈值仅影响收敛参考尺度；后续完整 20 子步收敛且全历程 STEN/SENE 通过。
- 状态：`DISPOSED`；形成 legacy 限制：`false`。

## W4：LS2 参考力矩阈值

- OUT 行：1070733。
- 识别片段：`calculated reference moment convergence value = 1.697185674e-03`。
- 处置：LS2 参考力矩低于内部阈值仅影响收敛参考尺度；保持步收敛、time=1.001 且反力质量闭合。
- 状态：`DISPOSED`；形成 legacy 限制：`false`。

## W5：退出后资源性能提示

- OUT 行：1083374。
- 识别片段：`elapsed time exceeds the cpu time by 40%`。
- 处置：elapsed/CPU 40% 属资源性能提示；发生在 0 error 正常退出之后，不改变数值结果。
- 状态：`DISPOSED`；形成 legacy 限制：`false`。

## 终态口径

五条 warning 均不构成本次数值门禁失败；W1/W2 保留为工程适用性边界，W3/W4 已由后续收敛和完整能量门禁处置，W5 仅反映资源性能。根状态因此采用 `PASS_WITH_LEGACY_LIMITATIONS`。
