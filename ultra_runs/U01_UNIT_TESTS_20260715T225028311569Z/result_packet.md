# U01 Unit Tests Result Packet

- Suite: `U01_UNIT_TESTS_20260715T225028311569Z`
- Status: `PASSED`
- Passed tests: `8/8`
- MAPDL: `2026 R1 / v261`
- Executable SHA-256: `6c6327f6b906db8e6dd498bd38c97685d7e3e4acf52fccbf243b2dff7ed7af1b`
- B00 full-solve memory ready: `false`
- Next action: `PREPARE_B00_ISOLATED_INPUT_ONLY`

## Eight mandatory gates

| Test | Status |
|---|---|
| `U01_01_LINK180_FULL_CHAIN` | `PASS` |
| `U01_02_BEAM188_AXIS` | `PASS` |
| `U01_03_SECTIONS` | `PASS` |
| `U01_04_MPC184` | `PASS` |
| `U01_05_REVOLUTE_6DOF` | `PASS` |
| `U01_06_MASS21_INERTIA` | `PASS` |
| `U01_07_BLOCK_LANCZOS_CLOSURE` | `PASS` |
| `U01_08_DMP4_EXPORT` | `PASS` |

## Evidence boundary

本套件只证明本机 MAPDL 的小模型单元、截面、连接、质量、Block Lanczos 与 DMP 导出链；不证明全桥几何、静力平衡或报告目标频率已经正确。

原生截面仅作为剪切因子和积分属性参考；H175、RHS160 和 RHS50×30 的原生扭转常数与冻结目标可能不满足 0.1%，因此不得把原生截面未经等价处理直接并入生产模型。

U01_03 的十二对原生/ASEC 总挠度、剪切挠度、ROTX 和根部 MX 明细见 `U01_status.json` 的 `pair_results`，原始求解列见 `post/sections__u01_section_native_deflections.csv` 与 `post/sections__u01_section_torsion_audit.csv`。

完整数值指标见 `U01_status.json` 与 `qa/U01_gate_results.csv`；CSV/JSON 字段见 `qa/field_dictionary.md`。
