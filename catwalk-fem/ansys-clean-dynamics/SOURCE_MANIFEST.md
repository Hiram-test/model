# 冻结源清单与拆分决策

基准仓库：`Hiram-test/model`  
基准分支：`f99-chain-closure`  
基准提交：`2c7e7cd64467a0e61801c0091c407a9b0edbdef2`  
源目录：`ultra_runs/S10_SECTION_SHEAR_20260716T050342389124Z/solver`

| 顺序 | 冻结源文件 | Git blob SHA | 本包处理 |
|---:|---|---|---|
| 1 | `full_line_beam4_crossbeam_mesh_xlong.inp` | `92cca4e36f49d3367d533bcf5f947d55478a6fdc` | 物理装配必选 |
| 2 | `convert_crossbeams_beam4_to_beam188.inp` | `68d4babef5b1383800c7b73e09d5f0590966c6ba` | 统一求解器单元兼容层；保持拓扑、面积和双向惯性矩 |
| 3 | `apply_mct_downpull_equivalent_xlong.inp` | `7263cd540558763f73f5c8cf0302e280e9978b54` | 物理装配必选 |
| 4 | `apply_mct_constraints_xlong.inp` | `8edacfecbcbf7b4b5e364137205f74ed9089217b` | 物理装配必选 |
| 5 | `apply_mct_authoritative_initial_state_link180.inp` | `cdfb657a6f14bb78562ab3917840fc013078b680` | 物理装配必选 |
| 6 | `apply_finite_gates_and_passages_v2.inp` | `fa1c8f6874d82c62ba64c98d6ba721d62aaf2ffb` | 物理装配必选 |
| 7 | `apply_modal_roty_stabilization_xlong.inp` | `7442ce73b1f4fe8f7bb4d592c240b85028c8063d` | 默认不读；仅 `CW_USE_ROTY_GAUGE=1` 时显式读取 |
| 8 | `define_representative_rope_component.inp` | `27a46f8a73e910884d4b650f59883830f70ee6ce` | 后处理组件，不进入物理装配 |
| 9 | `apply_authoritative_mct_deadload_v1.inp` | `d1d186838c57b77aa9dff546afabe3e2944b8424` | 物理装配必选 |
| 10 | `apply_dynamic_mass21_spatialized_v2.inp` | `4772d7f3fd7161fc2cb59500dd2e6d956896a1d5` | 物理装配必选 |
| 11 | `apply_authoritative_mct_gravity_v1.inp` | `58e1fe30f6ad046fab405c4aced761dbfdef193b` | 不进入装配；各求解入口直接施加同一 `ACEL` |

原 S10 顶层输入 `s10_section_shear_main.inp` 的 Git blob 为 `fe9a3410d0bff5f0f58930cb7188bf59e4c15c3c`。本包不调用该顶层输入，因为它将物理装配、模态专用 ROTY 约束、静力基态、线性摄动模态和大规模后处理写在同一个作业中。

## 关键拆分原则

1. `apply_modal_roty_stabilization_xlong.inp` 不再隐式进入所有静力和动力状态。它被视为待验证的数值零空间处理，而不是既定物理连接。
2. `apply_authoritative_mct_gravity_v1.inp` 只包含求解级重力命令，因此不属于物理模型母文件。
3. `define_representative_rope_component.inp` 只为后处理选择代表索，不应改变模型物理状态。
4. `convert_crossbeams_beam4_to_beam188.inp` 虽在旧说明中标为线性摄动专用，但本包将其固定为所有入口共用的单元兼容层，避免静力、模态和瞬态使用不同梁拓扑。其单元公式差异仍需通过微算例和结果敏感性检查。
5. 本包不调用任何 C20、D10、E10 或 E20 修改文件；这些分支只作为既有消融证据，不进入新的基准模型。
