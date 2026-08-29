# Runbook

## A. 当前可执行的无求解器烟测

```bash
python scripts/build_trial.py  # 重新生成全部 CCX 草案。
python scripts/zeroform_controller.py --smoke  # 验证外层几何修正方向，不产生工程迭代。
python scripts/smoke_check.py  # 执行输入、拓扑、禁用预应力和 fail-closed 检查。
```

预期状态：

- `tests/smoke_report.json` 为 `PASS_STATIC_SMOKE_ONLY`；
- `tests/outer_update_smoke.json` 为 `PASS_SIGN_TEST`；
- `workflow/run_summary.json` 仍为 `BLOCKED_AT_FORM_FINDING_AS_REQUIRED`。

## B. 第一次外部 CCX 缩减试算

1. 固定 CCX 版本、编译来源和可执行文件 SHA；
2. 建立新目录 `runs/CW-CCX-ZF-SMK-<date>-I00/`；
3. 复制 `SMK-Z0-01_zero_stress_formfind.inp`；
4. 记录完整命令、线程、CPU、内存和环境变量；
5. 运行后保留 `.dat`、`.frd`、`.sta`、stdout 和 stderr；
6. 提取 ZF_S2 末加载坐标、索力、反力和残差；
7. 提取 ZF_S3 保持步的坐标和能量变化；
8. 不满足任何门时立即停止，不进入动力。

命令模板：

```bash
ccx SMK-Z0-01_zero_stress_formfind  # 仅在固定 CCX 环境中执行，并将命令写入 run record。
```

该命令目前没有在本环境执行。

## C. 外层无应力几何迭代

外部后处理应生成：

`loaded_coordinates.csv`

字段：

`node_id,x_loaded_m,y_loaded_m,z_loaded_m`

然后执行：

```bash
python scripts/zeroform_controller.py --reference ir/target_reference_nodes.csv --loaded loaded_coordinates.csv --output next_reference.csv --report iteration_report.json  # 根据真实加载坐标生成下一轮无应力参考几何。
```

控制器只负责几何更新，不宣布收敛。下一轮必须由 `build_trial.py` 或生产 builder 把 `next_reference.csv` 写成新的 deck，并重新把初始应力设为零。

## D. G8B 的最低证据

- 目标几何最大误差；
- 全模型力残差/总重；
- 每根承重索最小轴力；
- 支反力和外载闭合；
- 临时控制已完全撤除；
- 同一恒载下保持步无漂移；
- 迭代历史没有覆盖；
- deck 和结果 SHA 闭合。

## E. 从缩减链升级到完整三维

通过缩减链后，按顺序加入：

1. 每幅 16 根承重索；
2. 门架承重索；
3. 门架横梁和立柱；
4. 21 道横向通道；
5. 扶手索和栏杆索；
6. 空间附属质量及其转动惯量；
7. 下拉与锚固体系；
8. 全四跨几何。

每次只加入一类物理对象并生成独立 run。禁止直接把当前 smoke deck 扩成全模型后一次性诊断。

## F. 动力解锁

- `DG0`：静力状态合同；
- `DG1`：质量、质心和转动惯量；
- `DG2`：切线模态；
- `DG3`：零荷载瞬态；
- `DG4`：微振幅自由衰减；
- `DG5`：振幅、时间步和阻尼敏感性；
- `DG6`：确定性动力荷载；
- `DG7`：随机抖振。

当前状态全部为 `NOT_ARMED`。
