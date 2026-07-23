#!/usr/bin/env bash
# 扎青吊桥 CAD-003 虚拟机建模总 Hook。
#
# 该 Hook 采用 fail-closed：任一参数句柄、FreeCAD 建模、STEP 回读或渲染失败，
# 最终退出码均非零；但上层 GitHub Actions 会先上传已有日志和中间文件再执行失败判定。
set -euo pipefail

ROOT_DIR="${GITHUB_WORKSPACE:-$(pwd)}"
MODEL_DIR="$ROOT_DIR/automation/zhaqing_cad003/freecad_model"
SCAN_DIR="${ZHAQING_SCAN_DIR:-$ROOT_DIR/build/zhaqing-cad003/scan}"
OUT_DIR="${ZHAQING_OUT:-$ROOT_DIR/build/zhaqing-cad003/freecad}"
FREECAD_CMD="${FREECAD_CMD:?FREECAD_CMD environment variable is required}"
FREECAD_GUI="${FREECAD_GUI:?FREECAD_GUI environment variable is required}"

mkdir -p "$OUT_DIR/logs" "$OUT_DIR/process_sources"
export ZHAQING_OUT="$OUT_DIR"
export ZHAQING_PARAMS="$OUT_DIR/frozen_model_contract.json"

# Step 0: 在任何可失败动作前记录运行入口和工具位置。
{
  printf 'pipeline_started_utc=%s\n' "$(date -u +%FT%TZ)"
  printf 'root=%s\nscan=%s\nout=%s\n' "$ROOT_DIR" "$SCAN_DIR" "$OUT_DIR"
  printf 'freecad_cmd=%s\nfreecad_gui=%s\n' "$FREECAD_CMD" "$FREECAD_GUI"
  "$FREECAD_CMD" --version || true
  "$FREECAD_GUI" --version || true
} 2>&1 | tee "$OUT_DIR/logs/00-environment.log"

# Step 1: 从 N03 CSV 按 source+handle 冻结合同；禁止建模脚本自行解释 CSV。
python3 "$MODEL_DIR/freeze_model_contract.py" \
  --scan-dir "$SCAN_DIR" \
  --facts "$MODEL_DIR/source_facts.json" \
  --output "$ZHAQING_PARAMS" \
  2>&1 | tee "$OUT_DIR/logs/01-freeze-model-contract.log"

# Step 2: FreeCADCmd 逐阶段生成 FCStd 快照、最终 FCStd 和 STEP。
"$FREECAD_CMD" "$MODEL_DIR/build_freecad_model.py" \
  2>&1 | tee "$OUT_DIR/logs/02-freecad-build.log"

# Step 3: 使用独立脚本重新打开 FCStd 和 STEP，不复用建模器内存状态。
"$FREECAD_CMD" "$MODEL_DIR/validate_freecad_model.py" \
  2>&1 | tee "$OUT_DIR/logs/03-independent-validation.log"

# Step 4: 在 Xvfb 虚拟显示中使用 FreeCAD GUI 保存四个视图。
# timeout 防止 GUI 插件异常时无限挂起。
timeout 180s xvfb-run -a "$FREECAD_GUI" "$MODEL_DIR/render_freecad_model.py" \
  2>&1 | tee "$OUT_DIR/logs/04-freecad-render.log"

# Step 5: 把本次实际使用的脚本和事实清单复制到交付物，便于逐行复核。
cp "$MODEL_DIR/source_facts.json" "$OUT_DIR/process_sources/"
cp "$MODEL_DIR/freeze_model_contract.py" "$OUT_DIR/process_sources/"
cp "$MODEL_DIR/build_freecad_model.py" "$OUT_DIR/process_sources/"
cp "$MODEL_DIR/validate_freecad_model.py" "$OUT_DIR/process_sources/"
cp "$MODEL_DIR/render_freecad_model.py" "$OUT_DIR/process_sources/"
cp "$MODEL_DIR/run_freecad_pipeline.sh" "$OUT_DIR/process_sources/"

# Step 6: 文件级终检。工程 Gate 可以是 BLOCKED，但技术文件不得缺失或为空。
test -s "$OUT_DIR/Zhaqing_CAD-003.FCStd"
test -s "$OUT_DIR/Zhaqing_CAD-003-display.step"
test -s "$OUT_DIR/Zhaqing_CAD-003-STEP-roundtrip.FCStd"
test -s "$OUT_DIR/validation_report.json"
test -s "$OUT_DIR/gate_receipt.json"
test -s "$OUT_DIR/renders/01-axonometric.png"
test -s "$OUT_DIR/renders/02-elevation.png"
test -s "$OUT_DIR/renders/03-plan.png"
test -s "$OUT_DIR/renders/04-cross-section.png"

find "$OUT_DIR" -type f ! -name 'SHA256SUMS.txt' ! -name 'Zhaqing_CAD-003-delivery.zip' -print0 \
  | sort -z \
  | xargs -0 sha256sum > "$OUT_DIR/SHA256SUMS.txt"
find "$OUT_DIR" -type f -printf '%P\t%s bytes\n' | sort > "$OUT_DIR/FILE_INVENTORY.txt"

# Step 7: 生成单一下载包，排除自身，保留目录结构、脚本、日志和所有阶段快照。
(
  cd "$OUT_DIR"
  zip -q -r "Zhaqing_CAD-003-delivery.zip" . -x "Zhaqing_CAD-003-delivery.zip"
)
test -s "$OUT_DIR/Zhaqing_CAD-003-delivery.zip"
printf 'pipeline_completed_utc=%s\n' "$(date -u +%FT%TZ)" | tee "$OUT_DIR/logs/99-complete.log"
