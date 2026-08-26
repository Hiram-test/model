# S10 LINK180 POST1-only 审计结论

- 状态：`PASSED`；硬门禁：`LINK180_NONPOSITIVE_AXIAL_FORCE_REVIEW`。
- 执行：MAPDL POST1-only、SMP1、零 warning、零 error、`/EXIT,NOSAVE`。
- 结果集：LS2 / substep 1 / time 1.001。
- 覆盖：TYPE4 实际、写出、CSV 和唯一元素均为 73692。
- 非正轴力：0。
- 最小轴力：519002.6875 N，元素 70029。
- 最大轴力：1573314.125 N，元素 400003。
- 源完整性：平衡 DB 与静力 RST 的长度、时间和 SHA-256 在运行前后完全一致。
