# D10 from C20 TOPPIN ROTX

Parent: C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z
32 LINK180 stays SEC/REAL as d10_draft, 12 tower CPs removed.
Gate toppins (ROTX) and bottom hoop ALL retained.
Node 109082, element 173022 = C20 172994 -4 +32.

## 静力（已封）

- LS1 20 子步 / 42 迭代，CNVG=1，最大位移 −138.74 mm
- LS2 1 子步 / 1 迭代，CNVG=1
- |STEN/SENE| = 2.64e-34
- 质量 4108.639824770034 t，误差 2.73e-12 t
- FZ 相对误差 1.65e-11

## 模态（Lanczos 已封，POST1 恢复中）

Block Lanczos 80 阶与 C20 TOPPIN ROTX 前 25 阶差 1e-5 Hz。
物理 TA1 仍在 M3=0.07337 Hz（与 LA 杂交），不是下压索把反对称扭转抬到 0.0996 Hz。

## 为何 D10 无效（有频率证据，不是口头推断）

1. 32 根索的组内总面积 = 原 4 根等效索面积，INISTATE 应力相同，总轴力相同。把 1 根拆成 8 根不改变组轴向刚度。
2. 删除的 12 组 CP 只约束塔处 16 索刚体平动。反对称扭转 TA 的控制截面在主跨四端口，不在塔耳板。
3. C20 已证明门架上销 ROTX 只插入 0.223 Hz 起的门架局部簇，不抬 TA1。
4. 因此 TA1 停在纯张力反对称根 2f\*≈0.07344 Hz，有效抗扭恢复仍约 1.5% κ_soft。

排除（本轮已算过，不再作为下一枪）：

- 再铰门架销 / 再加 COMBIN14
- 再加密下压面积或改塔 CP

保留到后续阶段、本轮不抢先改模型：

- 扶手/栏杆索若未以 LINK 进入刚度（目前门架横通道 DENS=0，质量在 MASS21），可能欠抗扭，但那是质量-刚度分离的下一层，不是 D10 的开关
- 索力纵向分布、M20 转动惯量：补惯量会降频，不能把 0.074 抬到 0.100

## 下一工况（已准备，等 D10 POST1 结束后启动）

**E10_PASSAGE_UXYZ**：1386 条横通道 CERIG `ALL` → `UXYZ`，底抱箍 284 条 `ALL` 与上销 ROTX 不改。
假设：21 站四端口刚臂把相对转动短路，反对称滚转看不见横通道 λ1。释放转动后 TA1 才有机会离开 2f\*。
