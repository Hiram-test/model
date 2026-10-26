# 扎青详细整桥：原生非线性求解与完整时程输出

`detailed_bridge.py` 根据已保存的图纸尺寸建立 78 块 10 mm 钢桥面板、468 根 16b 槽钢、箱形横梁、纵梁、承托角钢、端板与加劲板，并保留塔、主缆、吊索和抗风索。本次网格为 30,555 节点、26,674 单元；所有原生节点都进入结果文件。塔柱轴线 ±2750 mm、鞍座/主跨主缆/吊索平面 ±2550 mm、主缆锚固平面 ±2350 mm 分别建模，鞍座偏心通过明确的刚性连接表达。

这是图纸尺寸和已声明连接、材料、初应力假设共同定义的研究模型。连接采用线性化刚性臂；真实连接滑移/开闭、材料塑性和实际气动力系数仍属于独立物理建模事项。模型不做模态投影，也不在输出中删去节点或时间步。

## 非线性壳分支

默认使用 `ShellNLDKGQ`。`--shell-element ASDShellQ4` 是保留完全相同几何、网格、材料和荷载的独立有限元公式对照，并显式启用 `-corotational`。OpenSees 官方将该选项定义为大位移/有限转动运动学：

https://opensees.github.io/OpenSeesDocumentation/user/manual/model/elements/ASDShellQ4.html

两个公式的计算记录分别保存，不把它们当作同一标签来源混入训练数据。实际公式会写入模型和求解记录。

## 收敛与时间历程

首先进行完整恒载和初始索力的几何非线性平衡。初始原生位移增量测试为 `1e-9 mm`；提交后以真实节点力重新检查平衡。后续固定荷载 Newton 更新使用独立最大自由度残差：力以 N、力矩除以 5500 mm 后以等效 N 计量，最终阈值 `1e-3 N`。同时记录残差节点、分量、相对自重值及实际提交位移变化。后续清理的验收依据是力平衡和所有索单元受拉，不能把初始位移测试参数说成最后提交状态也通过了相同位移阈值。

动力采用完整自由度 Newmark 平均加速度法，原生 Newton 求解，并独立组装 `Fint + M*a + 0.02*M*v - P`。多点约束按其真实变换的转置传递力与力矩；原生和独立组装的一致性单独检查。恒载保持不变，外生横向/竖向风速驱动运动相对气动力。当前气动力系数和阻尼是明确的研究假设，不能作为扎青风洞实测值解释。

## 完整输出

`fields.h5` 采用无损双精度压缩，每个接受时间步立即落盘：

- `targets`：所有节点的三个位移、三个转角、三个速度和三个角速度，共 12 个监督通道。
- `controls`：外生横向、竖向风速；由有限元运动反馈得到的力放在独立审计数组中。
- `applied_force_moment`、`acceleration`：全部节点的实际施加气动力/力矩和原生加速度。
- `cable_axial_force_N`：全部主缆、吊索、抗风索的真实轴力；元素编号与类型一同保存，目前属于审计输出而非上述 12 通道监督目标。
- `rigid_connection_edges`：原生主/从节点关系；图语义中另设 `RIGID_CONNECTIONS`，不会把它当成普通材料单元。
- `saddle_motion.jsonl`：四个实际鞍座运动、两侧主缆轴力、当前方向和有限转动，供局部模型传递边界。
- `step_audits.jsonl`：每步独立平衡和索力检查。

只有完整达到请求时间、所有增量通过门槛，才把 `.partial.h5` 改名为 `fields.h5` 并生成 `case_manifest.json`。中断或失败保留部分场和失败原因，不能作为完整监督样本。

```bash
python3 automation/zhaqing_global_local/global/transient_cases.py --source SOURCE.inp --state STATE.json --output CASE --detailed-model --subdivision 1 --case-id wind_train01 --split train --steps 3200 --dt 0.00625 --speed 12 --seed 1001 --storage hdf5 # 请求完整20秒、3200个实际动力增量，并保留全部网格节点。
python3 automation/zhaqing_global_local/global/test_field_stream.py # 检查无损保存、不完整历程拒绝和索力通道完整性；这些软件测试不替代桥梁物理验证。
```

运行需要 OpenSeesPy、NumPy 和 h5py；当前环境的 MPI 绑定使用 `MPIR_CVAR_CH3_NETWORK_IFACE=lo`、`MPICH_INTERFACE_HOSTNAME=127.0.0.1`。训练/验证/测试以完整独立荷载历程划分，所有时窗、相同荷载的网格或单元公式变体须留在同一分区。
