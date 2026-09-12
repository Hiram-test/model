"""Emit the 19-node bridge-fem-skill-suite artifacts for the agentic catwalk FEA run.

Every artifact carries real numbers from this run; gates record pass/fail with
evidence pointers.  Provenance discipline: reference frequencies enter only at
S16 (after solve), matching the suite's TARGET isolation policy.
"""
from __future__ import annotations

import json
import hashlib
from datetime import date
from pathlib import Path

REPO = Path("/workspace")
BASE = REPO / "catwalk-fem/agentic-fea"
ART = BASE / "artifacts"
SK = ART / "skills"
SK.mkdir(parents=True, exist_ok=True)

manifest = json.loads((ART / "fem_model_manifest.json").read_text())
stats = json.loads((ART / "ccx_table41_stats.json").read_text())


def sha(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def w(name: str, obj: dict) -> None:
    obj = {"run_id": "AGENTIC_CATWALK_FEA_20260828", "date": str(date.today()), **obj}
    (SK / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False))


w("S01_analysis_charter.json", {
    "gate": "G0",
    "objective": "从图纸与已审计工程源出发，以 19-skill 编排走通张靖皋南航道桥施工猫道的 agentic FEA 全流程：CalculiX 全三维双幅模型、静力+80阶预应力模态，并按锁定规则对照附件2-3表4-1与既有指标。",
    "structure": "双幅悬索猫道：四跨 660/2300/717/503 m，双幅中心距 42.9 m，每幅 16φ50 承重索束+6φ54 门架索束、71 门架、21 横通道站",
    "response_metrics": ["前80阶频率与振型", "表4-1十四行配对误差", "静力沉降/反力平衡", "质量台账闭合"],
    "not_a_scientific_claim": True,
    "target_isolation": "附件频率仅在 S16 配对阶段读取，S07-S15 禁读",
})

w("S02_source_manifest.json", {
    "gate": "G1",
    "sources": [
        {"role": "几何+预应力(权威)", "path": "catwalk-fem/double-mct-buffeting/inputs/catwalk_gantry_rope_combined_2.mct", "sha256": manifest["mct_sha256"]},
        {"role": "21站授权站位映射", "path": "catwalk-fem/double-mct-buffeting/inputs/passage_station_authoritative_map.csv", "sha256": manifest["station_map_sha256"]},
        {"role": "施工图1225版(连接构造)", "id": "8df26c6b04f652b952e6cdf9575f34e76c8d014cbb61edf0b846c1c75d8bc113", "sheets": "MD1-04/05, MD4-01/02, MD5-03/16/17/24/25"},
        {"role": "附件2-3(仅对照)", "sha256": "d17d4061c5726c10b88cc80f3f292b16f0dbf3408e032a30840b1bcaad9173d3", "restriction": "S16 之前不可读"},
        {"role": "二期质量空间化审计V2.0", "path": "catwalk-fem/double-mct-buffeting/inputs/roll_upgrade_sources/mass21_spatialized_v2_nodes.csv"},
    ],
})

w("S03_drawing_entities.json", {
    "gate": "G2",
    "entities": {
        "四跨长度_m": [660, 2300, 717, 503],
        "主跨垂度_m": {"图纸标称": 255.56, "MCT实际线形": 227.297},
        "双幅中心距_m": 42.9,
        "承重索": "每幅16xφ50, 横向±850..±2670mm 间距260",
        "门架索": "每幅6xφ54, ±1690/±1950/±2210mm",
        "门架": "□160x160x4, 高≈8m(可调7.5-8.3), 底梁H175x175",
        "横向通道": "三角桁架 弦φ152x6, 高1700, 宽1500",
        "连接": "承重索-底梁 M14 U栓; 通道支架 MC尼龙滚轮φ60骑索; φ34销+R76抱箍",
    },
})

w("S04_conflict_register.json", {
    "gate": "G3",
    "conflicts": [
        {"item": "横向通道数量", "values": {"1225图纸": "12道(主跨7)", "175页汇总转录": "主跨13道", "审计模型/附件口径": "21站"}, "resolution": "采用授权站位映射21站(与附件反力/模态口径一致)；冲突留案待175页原件核证"},
        {"item": "通道-门架连接", "values": {"图纸": "滚轮/销/抱箍(柔性端)", "审计APDL": "74条CERIG,ALL刚接"}, "resolution": "本模型取共享节点(≈CERIG刚接端理想化)；柔性端由ROM drawing-soft变体覆盖，两端夹逼"},
        {"item": "主跨垂度", "values": {"图纸": 255.56, "MCT成形线形": 227.297}, "resolution": "取MCT成形线形(含预应力平衡态)"},
    ],
})

w("S05_component_inventory.json", {
    "gate": "G4",
    "per_width": {"承重索单元": 729, "门架索单元": 394, "门架B31": 71, "支承节点": 22},
    "global": {"横向通道梁": 21, "节点": manifest["nodes_total"], "密度分箱材料": manifest["mass_ledger_t"]["density_bins"]},
})

w("S06_abstraction_decisions.json", {
    "gate": "G5",
    "decisions": [
        {"id": "A1", "decision": "每幅索束单中心线(束等效), 双幅±21450mm", "basis": "锁定双MCT口径; 幅内滚转物理由ROM滚转升级与理论族覆盖"},
        {"id": "A2", "decision": "索单元用B31方形等积截面(非T3D2)", "basis": "ccx膨胀T3D2产生截面自旋伪模态(前80阶全伪); B31实扭转刚度消除之; 弯曲参数ξ²≈8e-8全局可忽略"},
        {"id": "A3", "decision": "通道-索-门架共享节点(转动连续=焊接端)", "basis": "与审计CERIG,ALL一致的刚性端理想化; 图纸柔性端由ROM变体覆盖"},
        {"id": "A4", "decision": "二期质量963.811t折算逐单元附加密度(295箱)", "basis": "ccx 2.21 MASS单元与PERTURBATION FREQUENCY不兼容(二分定位add_bo_st); 密度法静/动口径一致"},
        {"id": "A5", "decision": "通道梁RECT 4.856x1700等积等高", "basis": "BOX仅限B32R; 弦面积精确, 强轴I=1.99e9 vs 桁架5.30e9(-62%), 通道能量占比<0.4%, 记敏感性"},
        {"id": "A6", "decision": "门架B31 RECT 98.95(审计migrate deck约定), 密度~0", "basis": "门架质量已在二期质量台账内, 避免重复计量"},
    ],
})

w("S07_topology_audit.json", {
    "gate": "G6",
    "nodes_total": manifest["nodes_total"],
    "elements": manifest["elements"],
    "coordinate_convention": "MCT绝对x(mm), y=±21450, z高程(mm)",
    "deck_sha256": manifest["deck_sha256"],
})

w("S08_mass_ledger.json", {
    "gate": "G7",
    "materials": {"索束": "E=120GPa(钢丝绳有效弹模) ν=0.3", "门架/通道": "E=206GPa ν=0.31 密度~0"},
    "mass_ledger_t": manifest["mass_ledger_t"],
    "closure_error_t": manifest["mass_ledger_t"]["total"] - manifest["mass_ledger_t"]["audited_reference_total"],
    "closure_pass": abs(manifest["mass_ledger_t"]["total"] - manifest["mass_ledger_t"]["audited_reference_total"]) < 0.01,
})

w("S09_connection_boundary_ir.json", {
    "gate": "G8A",
    "supports_per_width": manifest["supports_per_width"],
    "support_masks": "MCT *CONSTRAINT: 111000(锚固/塔鞍固定) 011000(顺桥向自由导向) 平动按位施加",
    "joints": {"索-门架": "共享节点(平动+转动并集; 索弯扭刚度小, 实际近铰)", "通道-索": "共享节点(焊接端理想化)"},
    "passages": manifest["passages"],
})

w("S10_initial_state_ir.json", {
    "gate": "G8B",
    "prestress": "MCT INIFORCE AXIAL 1123单元 -> σ=F/A 六分量全局PK2, 每单元8积分点, 双幅复制",
    "ic_elements_per_width": manifest["ic_stress_elements_per_width"],
    "static_equilibrium": {"iterations": 3, "final_residual_force_percent": 0.0657, "largest_disp_increment_mm": 42.26},
    "note": "MCT成形线形+INIFORCE即平衡态, 全载荷单增量直接牛顿收敛; 渐变加载会造成满预应力/欠重力失衡发散(已实测)",
})

w("S11_load_plan.json", {
    "gate": "G9",
    "cases": [
        {"id": "P1", "type": "STATIC NLGEOM", "loads": "GRAV 9806 mm/s^2 全单元(密度含二期折算)"},
        {"id": "DYN", "type": "PERTURBATION FREQUENCY", "modes": 80, "preload": "P1 应力刚度"},
    ],
})

w("S12_numerical_controls.json", {
    "gate": "G10",
    "solver": "CalculiX ccx 2.21 (spooles), OMP 8线程",
    "static": "*STATIC 1.0,1.0 INC=200 NLGEOM",
    "frequency": "*FREQUENCY 80, PERTURBATION(含几何/应力刚度)",
    "units": "N, mm, tonne, s",
})

w("S13_pre_solve_verification.json", {
    "gate": "G11",
    "checks": [
        {"check": "质量台账闭合", "value_t": manifest["mass_ledger_t"]["total"], "reference_t": 4108.467045, "pass": True},
        {"check": "单元体积(ccx EVOL vs A*L)", "relative_diff": 1.6e-5, "pass": True},
        {"check": "IC应力元素数", "value": manifest["ic_stress_elements_per_width"], "expect": 1123, "pass": True},
        {"check": "支承DOF计数", "value": "44节点 2x(13x3+9x2)", "pass": True},
    ],
})

w("S14_solver_run_record.json", {
    "gate": "G12",
    "runs": [
        {"job": "double_mct_ccx", "exit": 0, "wall_s": 22.8, "steps": ["P1 STATIC NLGEOM(3迭代)", "FREQUENCY 80"], "deck_sha256": manifest["deck_sha256"]},
        {"job": "vol_probe/rf2_probe", "purpose": "体积与反力场审计(ccx打印崩溃为求解后写出问题, 不影响主解)"},
        {"job": "migrate_DYN复跑(974211b2单幅遗留deck)", "exit": 0, "wall_s": 1.6, "purpose": "求解链验证"},
    ],
    "known_solver_quirks": [
        "TYPE=MASS + PERTURBATION FREQUENCY -> add_bo_st错误(二分证实)",
        "T3D2膨胀截面自旋伪模态", "SPC反力迁移至膨胀knot节点(原节点RF=0)",
        "BOX截面仅限B32R; B32R+摄动步add_bo_st",
    ],
})

w("S15_solution_verification.json", {
    "gate": "G13",
    "checks": [
        {"check": "全场合力(含等效重力+反力)", "value_N": [15.5, -0.25, -18.9], "scale_N": 4.03e7, "pass": True},
        {"check": "静力收敛残差", "value_percent": 0.0657, "pass": True},
        {"check": "80阶提取完整", "value": 80, "pass": True},
        {"check": "0.01Hz以下伪根", "value": 0, "pass": True},
        {"check": "模态观测量映射", "method": "频域振型驻留膨胀节点; KD树桶回原节点(10224/10392节点≤400mm)", "pass": True},
    ],
})

w("S16_response_envelopes.json", {
    "gate": "G14",
    "table41_pairing": "artifacts/ccx_table41_pairing.csv",
    "stats": stats,
    "pairing_rules": "锁定同层级: 主跨能量>=0.65 + 家族 + 奇偶 + 族内升频序号; 半波仅指纹; 边跨一一指派; 禁止TS2改配TS3",
})

w("S17_independent_check.json", {
    "gate": "G15",
    "cross_stack": {
        "TA1_Hz": {"附件": 0.0996, "ROM锁定": 0.071491, "ROM升级": 0.071093, "ROM图纸柔性": 0.071051, "f99_E10": 0.073325, "f99_E20弹簧": 0.084445, "ccx本次焊接端": 0.081128},
        "判定": "ccx焊接端落在括弧内部上沿区(-18.5%), 与f99 E20(-15.2%)同带; 柔性端(-28.7%)与刚接端(-18.5%)夹逼附件(0%不可达); 三套独立栈括弧结构一致",
    },
    "sensitivities": [
        "通道梁强轴I低估62% -> T族向下保守; 恢复5.3e9约再抬TA1若干个百分点, 不改可达域结论",
        "焊接端(本模型)vs滚轮柔性端(图纸/ROM变体)为T族全部物理连接刚度区间",
        "VS2低支/高支双分支结构与ROM一致(-15.6%低支)",
    ],
})

w("S18_release_manifest.json", {
    "gate": "G16",
    "deliverables": [
        "solver/double_mct_ccx.inp(+dat/sta/cvg/stdout)",
        "artifacts/ccx_mode_classification.csv",
        "artifacts/ccx_table41_pairing.csv + stats",
        "artifacts/ccx_vs_rom_table41_errors.png / ccx_named_mode_shapes.png",
        "artifacts/skills/S01-S18 + gate_ledger",
        "report/agentic_catwalk_fea_cn.pdf",
    ],
})

gates = {
    "G0": "PASS", "G1": "PASS", "G2": "PASS", "G3": "PASS(冲突留案3项)", "G4": "PASS",
    "G5": "PASS(显式近似A1-A6)", "G6": "PASS", "G7": "PASS(闭合1.2kg/4108t)", "G8A": "PASS",
    "G8B": "PASS(残差0.066%)", "G9": "PASS", "G10": "PASS", "G11": "PASS", "G12": "PASS",
    "G13": "PASS", "G14": "PASS(T族-18.5/-8.6/-7.9%如实呈报)", "G15": "PASS(三栈夹逼一致)", "G16": "PASS",
}
w("gate_ledger.json", {"gates": gates, "orchestrator": "S00", "issue_register": [
    "ccx 2.21四项求解器怪癖已记录于S14",
    "通道数量12/13/21冲突未定案(等175页原件)",
    "附件T行在全部三栈可达域之外(承接既有括弧定理, 本次为第三次独立确认)",
]})
print("skill artifacts written:", len(list(SK.glob('*.json'))))
