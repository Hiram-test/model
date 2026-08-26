# S10 截面剪切单变量准备结果

- run：S10_SECTION_SHEAR_20260716T050342389124Z
- jobname：cw_S10_0716t050342_a4
- 状态：PREPARED_NOT_STARTED_USER_MEMORY_OVERRIDE
- 父基线：A30 等价于已求解 A10；A20 的 2,898 根 RHS 为零差异。
- 源证：U01 六类乘两方向十二对原始 CSV 已复算，U02 LS1 全历程结果集遍历已在 v261 小模型闭合。
- 唯一物理变化：SEC61..66 六条 ASEC 保持前六项不变，仅补零偏置、TKz/TKy 和 U01-v261 双向剪切因子。
- 受影响有限梁：17,679 根；TYPE、材料、质量、轴、拓扑、5,078 条 CERIG、荷载与索力均不变。
- 主流程：从头 LS1→LS2 保持→80阶无频带 LANB，MXPAND Elcalc=YES，NSOL+VENG。
- 未来输出：80阶全节点位移/转角、模态属性和六组件 SENE 16列 CSV。
- MAPDL：未启动；本编排器没有执行进程API。
- 资源：可用物理内存 3604267008 byte；D盘可用 38580228096 byte；启动策略=True。
