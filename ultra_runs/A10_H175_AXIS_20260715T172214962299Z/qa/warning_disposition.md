# A10 主 OUT 警告逐项处置

主 OUT 实际出现 5 个 `*** WARNING ***` 标记。MAPDL 摘要先记录 4 条，摘要之后又输出 1 条 elapsed/CPU 性能警告，因此两种计数口径并不矛盾。全部五条均已识别并处置；未处置警告数为 0。

## W1：legacy 约束方程与大变形

- OUT 行：1060589。
- 识别片段：`constraint equations may not be valid for elements that undergo large deflections`。
- 处置：保留为 legacy CERIG 大变形兼容性限制；由 LS1/LS2 收敛、质量反力闭合、LINK180 全正与 80 阶模态结果共同约束。
- 支撑证据：LS1/LS2 均收敛；质量误差小于 1E-6 tonne；反力相对误差小于 1E-4；LINK180 73692 项全部正；80 阶模态完整。
- 处置状态：`DISPOSED`；形成 legacy 限制：`true`。

## W2：矩阵系数比超过 1E8

- OUT 行：1060713。
- 识别片段：`coefficient ratio exceeds 1.0e8`。
- 处置：保留为刚度尺度病态限制；0 negative/zero pivot、两步收敛和 80 特征值收敛证明本次结果可用。
- 支撑证据：主 OUT 为 0 ERROR、0 negative pivot、0 zero pivot；两步静力和 80 个特征值均收敛。
- 处置状态：`DISPOSED`；形成 legacy 限制：`true`。

## W3：LS1 参考弯矩阈值

- OUT 行：1060772。
- 识别片段：`reference moment convergence value = 7.05020414e-02`。
- 处置：LS1 参考弯矩低于内部阈值仅改变收敛参考尺度；该载荷步随后收敛且端点门禁全部通过。
- 支撑证据：该警告后 LS1 继续迭代并收敛；LS1 SENE 为正，端点 STEN/SENE 远小于 1E-2。
- 处置状态：`DISPOSED`；形成 legacy 限制：`false`。

## W4：LS2 参考弯矩阈值

- OUT 行：1061238。
- 识别片段：`reference moment convergence value = 1.741355963e-03`。
- 处置：LS2 参考弯矩低于内部阈值仅改变收敛参考尺度；保持步在一次平衡迭代后收敛。
- 支撑证据：该警告所在 LS2 在一次平衡迭代后收敛；LS2 时间为 1.001，端点 STEN/SENE 远小于 1E-8。
- 处置状态：`DISPOSED`；形成 legacy 限制：`false`。

## W5：退出后 elapsed/CPU 性能提示

- OUT 行：1066728。
- 识别片段：`elapsed time exceeds the cpu time by 33%`。
- 处置：退出后 elapsed/CPU 33% 差异属于内存与磁盘性能提示；发生在 0 error 正常退出之后，不改变数值结果。
- 支撑证据：警告发生于 `EXIT MAPDL WITHOUT SAVING DATABASE` 和 0 ERROR 摘要之后，仅反映资源与 I/O 效率。
- 处置状态：`DISPOSED`；形成 legacy 限制：`false`。

## 终态口径

五条 warning 均不构成此次数值门禁失败，但 W1 与 W2 仍是工程适用性边界；另有 STEN 仅端点可恢复的证据边界。因此根状态采用 `PASS_WITH_LEGACY_LIMITATIONS`，不得改写为无条件 `PASS`。
