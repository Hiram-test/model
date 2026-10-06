# 猫道二维 CFD 试算工作包

按用户要求，**采用图纸原型尺寸，先跑通二维，三维暂停，代码与记录全部保存。** 网格使用 Gmsh 4.8.4，流场和三分力使用 OpenFOAM 1912。脚本只处理几何、字典、调度和输出，没有自写网格或流体求解器。

已完成两组主要尺寸核查和真实软件计算流程。当前是二维试算，**尚未验证为成功复现风洞三分力曲线**；短时间积分及稳态迭代波动均不作为充分统计的均值。两组几何、表格和结果独立保存。

|项目|模型与来源|结果入口|
|---|---|---|
|张靖皋原图 / 表3-1|净宽5.6m，16根承重索；图纸与INP交叉核查|[阶段报告](results/zhangjinggao/stage_report.md)、[对比图](results/zhangjinggao/comparison.png)|
|新提供A-A/B-B/C-C图 / 表5.8|推定1:8还原；净宽4m、外宽4.17m、中跨高1.5m、8根承重索|[阶段报告](results/user_drawing/stage_report.md)、[对比图](results/user_drawing/comparison.png)|

第二组五个攻角为−12、−6、0、6、12°，另有0°的C-C木踏板截面对照。尚未确认的索径、网孔、扶手细节和原表系数参考轴均列在[第二组建模说明](report/user_drawing_assumptions.md)，未冒充图纸实测值。第一组说明见[建模依据](report/model_assumptions.md)。

## 模型选择

- 原型净宽 **5.6 m**，参考高度 **1.477 m**；16 根 φ50 mm 承重索的位置经三维 INP 与图纸交叉核对。保留6根扶手索、双层底网和两侧网。
- **主二维模型：等开孔率圆杆。** 保留网片双向绕流阻力，参考猫道 CFD 文献中的二维简化。圆杆直径是等效尺寸，不是实际网丝直径；见 `scripts/mesh_2d.py`。
- **对照模型：纯多孔薄面。** `porousBafflePressure` 的压降、受力和力矩通过了解析直管测试，但该模型只提供法向阻力，遗漏底网沿网面方向的网丝阻力。因此保留作简化模型对照，不作为主复现模型。
- 沿桥长离散的横梁、立柱和木条本阶段二维省略；其影响需在后续模型中评估。三维代码、已建 CAD 和几何核查保留，本阶段不启动三维流场。
- 来流暂取原型工况13.8 m/s、SST湍流模型；不是宣称报告的测力风速已经确认。未知风洞细节不阻碍按图纸原型计算。

## 环境

```bash
docker build --secret id=ca_bundle,src=/etc/ssl/certs/ca-certificates.crt \
  -t catwalk-cfd:bookworm .
docker run -d --name catwalk-cfd-run --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" catwalk-cfd:bookworm sleep infinity
docker exec -it catwalk-cfd-run bash
source /usr/share/openfoam/etc/bashrc
```

以下计算命令在容器 `/work` 中执行。主机绘图依赖见 `requirements-postprocess.txt`，软件版本见 `sources/software_versions.txt`。

## 二维主流程

```bash
python3 scripts/mesh_2d.py --out geometry/my_2d --factor 1.7
python3 scripts/prepare_case.py --mesh geometry/my_2d --out geometry/my_2d --speed 13.8
bash scripts/convert_mesh.sh geometry/my_2d
python3 scripts/run_campaign.py --mesh geometry/my_2d \
  --angles=-12,0,12 --speed 13.8 --iterations 600 --workers 3 --prefix my_steady
```

网格必须通过 `checkMesh -allTopology -allGeometry` 并出现 `Mesh OK.`；数值不收敛的稳态结果不能作为气动力系数。`--factor`越小网格越细。当前等效圆杆模型的稳态试算波动明显，因此主试算采用非定常 `pimpleFoam`。

圆杆二维网格还可用`python3 scripts/check_saved_mesh.py --mesh geometry/my_2d`反查实际MSH单元连接中的承重索数量、位置、直径、部件数量及米制范围。两组正式网格与C-C对照均通过该检查；它确认模型文件身份，不替代网格独立性验证。

```bash
python3 scripts/run_transient_campaign.py \
  --sources cases/my_steady_m012_0 cases/my_steady_p000_0 cases/my_steady_p012_0 \
  --prefix my_urans --cold-start --end 2 --average-start 1 \
  --max-dt 0.002 --max-co 10 --outer 2 --workers 3
```

`--cold-start`读取初始场，避免把发散的稳态场带入非定常计算。上述2 s是**流程试算长度**，1–2 s采样窗口仅约2.46个B/U，不满足充分统计要求。要验证系数，须延长积分、检查分块均值，并完成网格和时间步敏感性；当前设置不能直接作为已验证的生产参数。

每例保存输入哈希、原生命令、开始/结束时间、退出码和收敛判定。批次名须唯一，程序拒绝覆盖已有算例。

## 多孔薄面对照与解析核验

```bash
python3 scripts/verify_porous_duct.py --out geometry/my_duct_check
python3 scripts/mesh_porous2d.py --out geometry/my_porous --factor 1.6
python3 scripts/prepare_case.py --mesh geometry/my_porous --out geometry/my_porous
bash scripts/convert_mesh.sh geometry/my_porous
python3 scripts/prepare_porous_mesh.py --mesh geometry/my_porous
```

内部面由原生 `topoSet/createBaffles` 创建；力由原生 `forceCoeffs` 积分。直管测试验证实现，不证明薄面简化足以复现猫道。相关假设和已发现的切向阻力遗漏见模型说明。

## 复跑第二组图纸

配置已保存在`geometry/user_drawing_model.json`及`user_drawing_timber_model.json`，不用重新获取图片。`setup_user_drawing.py`可重新生成这两个默认配置并执行10项尺寸链核验；如果已手工调整配置，不要再调用它覆盖调整。

在OpenFOAM容器内执行，批次名称须新建：

```bash
python3 scripts/mesh_2d.py --model geometry/user_drawing_model.json \
  --out geometry/new_user_mesh --factor 1.7
python3 scripts/prepare_case.py --mesh geometry/new_user_mesh \
  --out geometry/new_user_mesh --speed 15
bash scripts/convert_mesh.sh geometry/new_user_mesh
```

网格转换脚本同时检查日志必须包含`Mesh OK.`，不能只看进程返回0。然后生成五个独立初始场：

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, 'scripts')
from prepare_case import create_case
for angle in [-12, -6, 0, 6, 12]:
    create_case('cases/repeat_user_initial_' + str(angle), 'geometry/new_user_mesh', angle, 15)
PY
python3 scripts/run_transient_campaign.py \
  --sources cases/repeat_user_initial_-12 cases/repeat_user_initial_-6 \
    cases/repeat_user_initial_0 cases/repeat_user_initial_6 cases/repeat_user_initial_12 \
  --prefix repeat_user --cold-start --end 1.5 --average-start 0.75 \
  --max-dt 0.002 --max-co 5 --outer 2 --workers 4
```

C-C对照将模型参数改为`geometry/user_drawing_timber_model.json`、网格目录另起名字，生成0°初始场并以新的批次名前缀运行同样的非定常流程。它是局部截面，不能与普通截面的系数任意加权冒充三维平均。

主机后处理使用第二组原表：

```bash
python3 scripts/plot_results.py --prefix repeat_user \
  --geometry geometry/new_user_mesh/geometry.json \
  --reference sources/table_5_8_user.csv --reference-label 'User Table 5.8' \
  --output results/repeat_user
```

本次已保存批次的综合报告由`python3 scripts/summarize_user_trial.py`生成，包含有量纲的每延米力与力矩、风轴/体轴系数、采样长度和未通过的判据。对比图的虚线只是连接已计算点，25点黑线来自原表，不是25个CFD工况。

## 输出和保存

以下后处理命令在安装了 `requirements-postprocess.txt` 依赖的主机运行：

```bash
python3 scripts/assess_results.py
python3 scripts/plot_results.py --prefix rod_urans --geometry geometry/proto2d_f170/geometry.json
```

- `sources/table_3_1.csv`：报告25个攻角原值，未经拟合。
- `geometry/model.json`：原型基本参数；`verified_dimensions.json`及`audit_status.json`：尺寸与来源核查。
- `cases/*/postProcessing/coeffsH/*/coefficient.dat`：CD，分母qHL。
- `cases/*/postProcessing/coeffsB/*/coefficient.dat`：CL、CmPitch，分母qBL和qB²L。
- 力矩顺时针为正，参考轴取名义包络中心 `(0,0.7135)` m；不从目标曲线反求轴高。
- `results/`：对比图、原始时间历史CSV、有效性判定和阶段报告。`WORK_STATE.json`记录当前状态。
- Git保留源代码与文档版本；`scripts/package_work.py`生成源码/历史包、原生结果包、历史诊断包及来源证据包。按用户要求提前停止的算例，仅在有`user_stop.json`且原生求解器正常退出时，允许用`--allow-user-stopped`打包；记录实际末时刻与原目标，不视为完成验证。

旧1:10计算和不同建模方案均有记录，但不混入原型主结果。只有计算与对比验证通过后，才按原请求制作“复现成功”的详细skill。

## 原生并行续算

先通过OpenFOAM的 `stopAt writeNow` 保存并正常停止当前算例，日志出现结束标记后，再运行：

```bash
python3 scripts/resume_parallel.py --case cases/my_urans_p012_0 --ranks 3
```

脚本使用原生 `decomposePar`、`mpirun pimpleFoam -parallel` 和 `reconstructPar`，从保存时间继续，保留每段记录。Debian安装包中的Scotch分解库是占位实现，因此使用内置hierarchical分解；容器中关闭不支持的CMA单次复制机制。两项都只涉及运行配置，不替换网格或流体求解方法。

并行续算时，`execution.json`保留首段执行记录，`parallel_resume*.json`保留各续算段；最终状态由`assess_results.py`重新读取全部原生时间目录生成。时间历史图省去最初启动尖峰以便读图，CSV保留全部原始样本。

源码包中的`catwalk-cfd-history.bundle`保存Git历史；需要恢复完整版本库时，可用`git clone catwalk-cfd-history.bundle restored-repository`。

## GitHub发布与完整恢复

本工作包在仓库内位于`projects/catwalk/cfd`，试算分支为`exp/catwalk-openfoam-2d-pilot-20261006`。大型原生文件使用[Release下载](https://github.com/Hiram-test/model/releases/tag/catwalk-openfoam-2d-pilot-v0.1.0-20261006)：

- `code`包：代码、模型配置、图表、报告、Git历史。
- `results`包：本轮原生算例的网格、初始场、求解字典、末时刻场、力系数、日志、逐文件校验和，以及暂停的9m三维CAD。
- `diagnostics`包：此前失败、停止、旧比例或其他简化的试算；不属于已验证结果。
- `source-evidence`包：用户提供的报告、原仓库图纸/INP及转录表，用于独立追溯；第三方论文仅提供链接。

将需要的zip解压到同一父目录，公共前缀均为`catwalk-cfd/`；包内MANIFEST给出SHA-256。源码包不依赖原始大文件也可运行，重新核查原始资料时再解压`source-evidence`。所有正式算例都有`RUN_MANIFEST.md`、`INPUT_SHA256SUMS.txt`和`STATUS.txt`，规范编号及原生路径映射见`report/catwalk_openfoam_run_register_20261006.csv`。为保持续算路径可用，既有原生目录名不迁移。

CFD网格/场采用米制；暂停的`geometry/prototype_9m/prototype_9m.step`采用毫米制，附有`step_unit_check.json`。有三维CAD不代表做过三维CFD。
