# 扎青桥断面气动力与整桥荷载接口

本目录已经实现并测试了气动力表读取、运动相对风速、有限转角攻角、三分力转换、沿桥空间风场插值和全节点一致荷载积分。**没有内置或冒充扎青整桥的三分力系数。** 默认拒绝未经验证的系数、缺少来源散列的表、攻角外推和风场时空外推。

## 真实图纸的核查结果

`桥跨横断面图.dwg` 的 TEXT `C2A` 是“杂多县尕沙河电站至昂塞乡政府支线”，而扎青 SGT-4/5/12 的项目名是“玉树州杂多县城至扎青乡公路改建工程”。旧模型契约中的 `U-XS-001` 已经记录这个项目名冲突；5500 mm 宽度有其他图纸佐证，不能因此把整张断面都当成已核实的扎青气动轮廓。

重新读取了真正的 `04-05-桥面板构造.dwg` 和 `12-纵梁构造.dwg`。桥面板材料表包含 10×1560×2690 mm 钢板、6 根长2666 mm的16号槽钢及160 mm高的加劲板，不是一个均质50 mm厚实心板。槽钢细部160×65 mm、腹板8.5 mm、翼缘10 mm与表中的19.752 kg/m对应。面板拼接位置、横梁所在截面与跨中截面、栏杆和间隙仍必须按对应图纸装配核对。

SGT-12的单根纵梁 **HW400×400×13×21** 可以独立、明确地提取。`extract_girder_profile.py` 使用16个原始LINE/ARC句柄，保留24 mm根部圆角；原始DWG、DXF、句柄和坐标原点记录在 `sgt12_girder_geometry.json`。这个模型用于实际桥梁构件的CFD计算与流程验证，**不是完整桥面断面，其气动力系数禁止代入整桥模型**。

## 已实现的物理接口

采用SI单位，桥梁x轴沿桥向、y横桥向、z竖向。CFD局部x/y/z分别对应桥梁y/z/x。所有系数统一采用桥面参考宽度B：

\[
F_D'=\tfrac12\rho |U_{rel}|^2 B C_D(\alpha),\quad
F_L'=\tfrac12\rho |U_{rel}|^2 B C_L(\alpha),\quad
M'=\tfrac12\rho |U_{rel}|^2 B^2 C_M(\alpha).
\]

`quasi_steady_loads`扣除平动速度和气动中心处的转动速度，使用当前相对来流方向减去有限转角求攻角，把风轴阻力/升力转为桥轴分力，再把气动力矩移到结构参考轴。沿桥一致积分保持合力、力的一阶矩及扭矩，不删除实际结构节点。风输入保留`time × station × 2`的完整时空数据。

这是**运动相关的非线性准定常接口**；静态三分力表不能单独提供颤振导数、非定常记忆或保证准确的气动弹性失稳预测。斜风沿桥分量、气动导纳及非定常自激力需要相应的额外数据/模型。

## 原生CFD流程

`build_openfoam_case.py`从有来源的闭合轮廓或原生圆弧生成Gmsh网格及OpenFOAM1912 `pimpleFoam`/`kOmegaSST`输入。模型含真正的黏性壁面、压力—速度耦合、湍流方程、`forceCoeffs`积分和`yPlus`输出。先通过`checkMesh -allGeometry -allTopology`才启动求解。

单根SGT-12纵梁的实际运行目录是：

`results/zhaqing_global_local_20261026/aero/girder_cfd_native_arcs/`

该构件案例使用42820个棱柱有限体积单元，原生圆弧几何，10 m/s来流，参考宽度0.4 m、Re≈266667、明确给定的1%入口湍流和0.07B长度尺度。40B/U的计算时长为1.6 s。这些是构件流程验证的情景参数，不是实测桥址风参数。`result_summary.json`根据原生日志和实际末时刻判断完成状态，不能把启动或提前停止当作完成。

本次已实际跑完5222步、1.6 s，用时1317 s。后半段0.8–1.6 s的构件系数时间均值为Cd=2.05220、Cl=-0.02132、Cm=-0.00880；四个等时长窗口的Cd均值跨度占总均值6.42%，升力和力矩仍明显振荡，**统计稳定性测试没有通过**。这些数值仅用于核对原生求解与后处理，不能作为桥梁设计系数。实际启动阶段maxCo=0.5，在日志物理时刻0.02867415862 s之后改为2；完整控制历史记在案例契约中。下方整程`--max-co 2`命令可复建同一几何与物理情景，但不与此次启动时序逐步相同；此次原始网格、字段和日志已完整保存。

安装包OpenFOAM1912存在已知的旧SHA1stream与现代C++库的兼容问题。`sha1_stream_compat.cpp`只对运行时类型完全匹配的旧SHA1缓冲区补齐`overflow`，继续调用原来的`xsputn`散列写入；不改变流体方程或容差。独立C++回归验证逐字符/整段写入均保留原字节，其他标准流不变。上游修复说明见下列链接。

`forceCoeffs`的实际输出头中pitchAxis为负CFD-z。后处理按原生输出的三个力矩轴投影到正桥梁x轴，**不会直接把CmPitch当成正桥梁扭矩**。所有均值按实际自适应时间间隔积分，且预先丢弃前半段启动过程。完整时程、四个时间块均值及统计漂移一起保存；网格、时间步、计算域、雷诺数适用性、完整断面和三维效应未验证时，系数仍不可发布为整桥验证数据。

## 复现

```bash
# 读取原始SGT12轮廓；DXF由LibreDWG从原始DWG转换。
python automation/zhaqing_global_local/aero/extract_girder_profile.py SOURCE_GIRDER.dxf source-inputs/zhaqing-suspension-bridge/drawings/12-纵梁构造.dwg results/zhaqing_global_local_20261026/aero
# 生成明确标为构件案例的原生CFD输入；Co=2的探索计算还需要时间步收敛研究。
python automation/zhaqing_global_local/aero/build_openfoam_case.py results/zhaqing_global_local_20261026/aero/sgt12_girder_geometry.json NEW_CASE --allow-partial --mesh-size 0.008 --convective-times 40 --max-co 2
# 运行时前缀包含下载并解包的OpenFOAM1912/Gmsh及依赖。
CFD_RUNTIME=/absolute/path/to/cfd-runtime bash automation/zhaqing_global_local/aero/run_native_case.sh NEW_CASE
# 解析实际运行状态和系数；不会把部分运行标为完成。
python automation/zhaqing_global_local/aero/summarize_cfd.py NEW_CASE
# 运行16项解析验证。
python automation/zhaqing_global_local/aero/test_aero_loads.py
```

Python只承担CAD/数据解析、物理计算和测试；**没有调用Python绘图库**。图纸线条图和时程图由Gnuplot渲染，CFD压力云图由Gmsh原生OpenGL渲染。`vtk_to_gmsh_view.js`只转换`foamToVTK`导出的真实单元场，不插值伪造云图，也不将汇总数值画成场。

## 一手依据

- [OpenFOAM forceCoeffs 文档](https://doc.openfoam.com/2312/tools/post-processing/function-objects/forces/forceCoeffs/)：积分方向、参考面积和长度必须显式规定；本项目进一步检查实际输出头。
- [OpenFOAM pimpleFoam 源码说明](https://cpp.openfoam.org/v10/pimpleFoam_8C.html)：不可压缩瞬态求解器。
- [OpenFOAM freestreamPressure](https://doc.openfoam.com/2312/tools/processing/boundary-conditions/rtm/derived/inletOutlet/freestreamPressure/)：外边界的压力条件。
- [Gmsh 手册](https://gmsh.info/doc/texinfo/)：源曲线、带孔平面域、单层挤出与原生结果视图。
- [OpenFOAM 官方SHA1stream兼容修复](https://github.com/OpenFOAM/OpenFOAM-9/commit/b0c15bebd37142f3902901ed5e9a60e33ed456eb)：解释旧缓冲区缺少C++11所需overflow方法的错误。
- [Carassale、Wu、Kareem，2012](https://iawe.org/wp-content/uploads/2025/07/L.Carassale.pdf)：准定常非线性与具有记忆的抖振/自激气动力模型的适用区别。
