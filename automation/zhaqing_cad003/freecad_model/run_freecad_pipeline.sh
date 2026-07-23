#!/usr/bin/env bash
# 扎青吊桥 CAD-003 虚拟机建模总 Hook。
#
# 该 Hook 采用 fail-closed：任一图纸句柄、合同协调、FreeCAD 建模、装配接口修正、
# 锚碇/风缆复核、吊杆索夹间隙、Compound STEP 封装、STEP 回读、禁止穿透审计、
# 专项几何审计或渲染失败，最终退出码均非零；上层 Actions 会先上传已有日志和
# 中间文件，再执行最终失败判定。
set -euo pipefail

ROOT_DIR="${GITHUB_WORKSPACE:-$(pwd)}"
MODEL_DIR="$ROOT_DIR/automation/zhaqing_cad003/freecad_model"
SCAN_DIR="${ZHAQING_SCAN_DIR:-$ROOT_DIR/build/zhaqing-cad003/scan}"
OUT_DIR="${ZHAQING_OUT:-$ROOT_DIR/build/zhaqing-cad003/freecad}"
FREECAD_CMD="${FREECAD_CMD:?FREECAD_CMD environment variable is required}"
FREECAD_GUI="${FREECAD_GUI:?FREECAD_GUI environment variable is required}"

mkdir -p "$OUT_DIR/logs" "$OUT_DIR/process_sources"
export ZHAQING_SCAN_DIR="$SCAN_DIR"
export ZHAQING_OUT="$OUT_DIR"
export ZHAQING_PARAMS="$OUT_DIR/frozen_model_contract.json"

# FreeCAD 0.19 may print a Python exception but still return process exit code 0.
# Therefore every stage must also create a JSON receipt with an expected field.
assert_json_equals() {
  local json_path="$1"
  local dotted_field="$2"
  local expected="$3"
  test -s "$json_path"
  python3 - "$json_path" "$dotted_field" "$expected" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
field = sys.argv[2]
expected = sys.argv[3]
value = json.loads(path.read_text(encoding="utf-8"))
for key in field.split("."):
    if not isinstance(value, dict) or key not in value:
        raise SystemExit(f"missing JSON field {field!r} in {path}")
    value = value[key]
if str(value) != expected:
    raise SystemExit(f"{path}:{field}={value!r}, expected {expected!r}")
print(json.dumps({"path": str(path), "field": field, "value": value}, ensure_ascii=False))
PY
}

# Step 0: 在任何可失败动作前记录运行入口、工具版本并编译所有实际适配器。
{
  printf 'pipeline_started_utc=%s\n' "$(date -u +%FT%TZ)"
  printf 'root=%s\nscan=%s\nout=%s\n' "$ROOT_DIR" "$SCAN_DIR" "$OUT_DIR"
  printf 'freecad_cmd=%s\nfreecad_gui=%s\n' "$FREECAD_CMD" "$FREECAD_GUI"
  "$FREECAD_CMD" --version || true
  "$FREECAD_GUI" --version || true
  python3 -m py_compile \
    "$MODEL_DIR/freeze_model_contract.py" \
    "$MODEL_DIR/reconcile_anchor_wind_contract.py" \
    "$MODEL_DIR/add_contract_compatibility_aliases.py" \
    "$MODEL_DIR/build_freecad_model.py" \
    "$MODEL_DIR/repair_assembly_interfaces.py" \
    "$MODEL_DIR/adjust_hanger_clamp_gaps.py" \
    "$MODEL_DIR/correct_anchor_wind_geometry.py" \
    "$MODEL_DIR/export_compound_step.py" \
    "$MODEL_DIR/validate_freecad_model.py" \
    "$MODEL_DIR/validate_freecad_model_contract.py" \
    "$MODEL_DIR/validate_freecad_model_contract_direct_step.py" \
    "$MODEL_DIR/audit_forbidden_penetrations.py" \
    "$MODEL_DIR/audit_anchor_wind_geometry.py" \
    "$MODEL_DIR/render_freecad_model.py"
} 2>&1 | tee "$OUT_DIR/logs/00-environment.log"

# Step 1: 从 N03 CSV 按 source+handle 冻结第一版合同；建模脚本不得自行解释 CSV。
python3 "$MODEL_DIR/freeze_model_contract.py" \
  --scan-dir "$SCAN_DIR" \
  --facts "$MODEL_DIR/source_facts.json" \
  --output "$ZHAQING_PARAMS" \
  2>&1 | tee "$OUT_DIR/logs/01-freeze-model-contract.log"
test -s "$ZHAQING_PARAMS"
assert_json_equals "$ZHAQING_PARAMS" "engineeringReleaseStatus" "BLOCKED"

# Step 2: 专项复核 SGT-26/32/33，纠正被误分类的尺寸并登记真实冲突。
# 这里明确保留平面图 8/18 号与说明 13/27 号的冲突，不用平均或静默覆盖。
python3 "$MODEL_DIR/reconcile_anchor_wind_contract.py" \
  2>&1 | tee "$OUT_DIR/logs/02-anchor-wind-contract-reconciliation.log"
assert_json_equals "$OUT_DIR/anchor_wind_contract_reconciliation.json" "status" "PASS_WITH_BLOCKED_CONFLICTS"
assert_json_equals "$ZHAQING_PARAMS" "engineeringReleaseStatus" "BLOCKED"

# Step 3: 原候选建模器仍读取几个旧字段名来写 sourceRef。只建立正确值的兼容别名，
# 不恢复已否决的 310 cm 高度、13/27 号或单块风缆锚座解释。
python3 "$MODEL_DIR/add_contract_compatibility_aliases.py" \
  2>&1 | tee "$OUT_DIR/logs/03-contract-compatibility-aliases.log"
assert_json_equals "$OUT_DIR/contract_compatibility_alias_report.json" "status" "PASS"

# Step 4: FreeCADCmd 逐阶段生成初次 FCStd 快照和候选 STEP。
# 初次阶段仍被保留，用于展示候选外包络如何在后续专项步骤中被纠正。
"$FREECAD_CMD" "$MODEL_DIR/build_freecad_model.py" \
  2>&1 | tee "$OUT_DIR/logs/04-freecad-build.log"
test -s "$OUT_DIR/Zhaqing_CAD-003.FCStd"
test -s "$OUT_DIR/Zhaqing_CAD-003-display.step"
test -s "$OUT_DIR/artifact_manifest.json"

# Step 5: 修正横梁、纵梁、塔柱、索鞍等已知装配穿透。
"$FREECAD_CMD" "$MODEL_DIR/repair_assembly_interfaces.py" \
  2>&1 | tee "$OUT_DIR/logs/05-assembly-interface-repair.log"
assert_json_equals "$OUT_DIR/assembly_interface_repair_report.json" "status" "PASS"

# Step 6: 吊杆不靠实体互穿连接主缆；保留未建索夹的 20 mm 显示间隙。
"$FREECAD_CMD" "$MODEL_DIR/adjust_hanger_clamp_gaps.py" \
  2>&1 | tee "$OUT_DIR/logs/06-hanger-clamp-display-gap.log"
assert_json_equals "$OUT_DIR/hanger_clamp_gap_report.json" "status" "PASS"

# Step 7: 按专项协调合同重建锚碇轮廓、主缆锚端横向散开、风缆 B 点及风缆锚座。
# 原 01–08B 快照不删除；新增 stage 10 记录复核前后差异。
"$FREECAD_CMD" "$MODEL_DIR/correct_anchor_wind_geometry.py" \
  2>&1 | tee "$OUT_DIR/logs/07-anchor-wind-geometry-correction.log"
assert_json_equals "$OUT_DIR/anchor_wind_geometry_correction_report.json" "status" "PASS_WITH_ENGINEERING_BLOCKERS"
test -s "$OUT_DIR/stages/10_anchor_wind_geometry_reconciliation.FCStd"

# Step 8: 将最终全部 DISPLAY 对象封装为一个顶层 Compound STEP。
# FreeCAD 0.19 回读数百个顶层 free shapes 时可能段错误；对象身份由 FCStd 和 sidecar manifest 保留。
"$FREECAD_CMD" "$MODEL_DIR/export_compound_step.py" \
  2>&1 | tee "$OUT_DIR/logs/08-compound-step-export.log"
assert_json_equals "$OUT_DIR/compound_step_export_report.json" "status" "PASS"

# Step 9: 新进程重开 FCStd，并把 STEP 直接读成一个 TopoShape，而不是让 FreeCAD 0.19
# 展开 675 个 solids 为数百个文档对象；随后仍执行有效性、体积和包围盒回读检查。
PYTHONPATH="$MODEL_DIR${PYTHONPATH:+:$PYTHONPATH}" \
  "$FREECAD_CMD" "$MODEL_DIR/validate_freecad_model_contract_direct_step.py" \
  2>&1 | tee "$OUT_DIR/logs/09-independent-validation.log"
assert_json_equals "$OUT_DIR/validation_report.json" "technicalStatus" "PASS"
assert_json_equals "$OUT_DIR/validation_report.json" "directStepReaderApplied" "True"
assert_json_equals "$OUT_DIR/gate_receipt.json" "technicalGeometryValidation" "PASS"

# Step 10: 独立执行 OpenCASCADE 公共体积审计；未闭合的局部硬件接口不伪装成已通过。
"$FREECAD_CMD" "$MODEL_DIR/audit_forbidden_penetrations.py" \
  2>&1 | tee "$OUT_DIR/logs/10-forbidden-penetration-audit.log"
assert_json_equals "$OUT_DIR/forbidden_penetration_audit.json" "status" "PASS"

# Step 11: 新进程专项验证锚碇台阶、横向槽、索面散开以及四条风缆/锚座控制坐标。
"$FREECAD_CMD" "$MODEL_DIR/audit_anchor_wind_geometry.py" \
  2>&1 | tee "$OUT_DIR/logs/11-anchor-wind-geometry-audit.log"
assert_json_equals "$OUT_DIR/anchor_wind_geometry_audit.json" "status" "PASS"
assert_json_equals "$OUT_DIR/anchor_wind_geometry_audit.json" "engineeringReleaseStatus" "BLOCKED"

# Step 12: 在 Xvfb 虚拟显示中保存四个最终视图，并逐图执行非白像素门禁。
QT_QPA_PLATFORM=xcb timeout 180s xvfb-run -a "$FREECAD_GUI" "$MODEL_DIR/render_freecad_model.py" \
  2>&1 | tee "$OUT_DIR/logs/12-freecad-render.log"
assert_json_equals "$OUT_DIR/renders/render_report.json" "status" "PASS"

# Step 13: 把本次实际使用的脚本和事实清单复制到交付物，便于逐行复核。
for file in \
  source_facts.json \
  freeze_model_contract.py \
  reconcile_anchor_wind_contract.py \
  add_contract_compatibility_aliases.py \
  build_freecad_model.py \
  repair_assembly_interfaces.py \
  adjust_hanger_clamp_gaps.py \
  correct_anchor_wind_geometry.py \
  export_compound_step.py \
  validate_freecad_model.py \
  validate_freecad_model_contract.py \
  validate_freecad_model_contract_direct_step.py \
  audit_forbidden_penetrations.py \
  audit_anchor_wind_geometry.py \
  render_freecad_model.py \
  run_freecad_pipeline.sh \
  README.md; do
  cp "$MODEL_DIR/$file" "$OUT_DIR/process_sources/$file"
done

# Step 14: 文件级终检。工程 Gate 可以是 BLOCKED，但技术文件不得缺失或为空。
for required in \
  Zhaqing_CAD-003.FCStd \
  Zhaqing_CAD-003-display.step \
  Zhaqing_CAD-003-STEP-roundtrip.FCStd \
  frozen_model_contract.json \
  anchor_wind_contract_reconciliation.json \
  contract_compatibility_alias_report.json \
  assembly_interface_repair_report.json \
  hanger_clamp_gap_report.json \
  anchor_wind_geometry_correction_report.json \
  compound_step_export_report.json \
  validation_report.json \
  forbidden_penetration_audit.json \
  anchor_wind_geometry_audit.json \
  gate_receipt.json \
  renders/01-axonometric.png \
  renders/02-elevation.png \
  renders/03-plan.png \
  renders/04-cross-section.png \
  renders/render_report.json; do
  test -s "$OUT_DIR/$required"
done

find "$OUT_DIR" -type f ! -name 'SHA256SUMS.txt' ! -name 'Zhaqing_CAD-003-delivery.zip' -print0 \
  | sort -z \
  | xargs -0 sha256sum > "$OUT_DIR/SHA256SUMS.txt"
find "$OUT_DIR" -type f -printf '%P\t%s bytes\n' | sort > "$OUT_DIR/FILE_INVENTORY.txt"

# Step 15: 生成单一下载包，排除自身，保留目录结构、脚本、日志和全部阶段快照。
(
  cd "$OUT_DIR"
  zip -q -r "Zhaqing_CAD-003-delivery.zip" . -x "Zhaqing_CAD-003-delivery.zip"
)
test -s "$OUT_DIR/Zhaqing_CAD-003-delivery.zip"
printf 'pipeline_completed_utc=%s\n' "$(date -u +%FT%TZ)" | tee "$OUT_DIR/logs/99-complete.log"
