#!/usr/bin/env bash
# 扎青吊桥 CAD-003 的虚拟机建模总入口。
#
# 设计原则：
# 1. 每个阶段都写独立日志；任何失败都保留现有输出，不覆盖历史证据。
# 2. FreeCAD 建模与独立校验必须在两个不同的 FreeCADCmd 进程中执行。
# 3. 脚本退出码、起止时间、命令行和日志路径写入 stage_ledger.jsonl。
# 4. 数值只来自 compile_model_contract.py 生成的模型契约；FreeCAD 脚本不能自行猜尺寸。
# 5. 流程成功仅表示“生成并通过确定性几何回读检查”，不表示工程放行。
set -Eeuo pipefail

usage() {
  cat <<'EOF'
用法：
  run_vm_freecad_pipeline.sh <scan-dir> <run-root>

示例：
  automation/zhaqing_cad003/run_vm_freecad_pipeline.sh \
    build/zhaqing-cad003/scan build/zhaqing-cad003/run
EOF
}

if [[ $# -ne 2 ]]; then
  usage >&2
  exit 64
fi

SCAN_DIR="$(realpath "$1")"
RUN_ROOT="$(realpath -m "$2")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTRACT_DIR="$RUN_ROOT/contract"
MODEL_DIR="$RUN_ROOT/model"
VALIDATION_DIR="$RUN_ROOT/validation"
PROCESS_DIR="$RUN_ROOT/process"
LOG_DIR="$PROCESS_DIR/logs"
LEDGER="$PROCESS_DIR/stage_ledger.jsonl"

mkdir -p "$CONTRACT_DIR" "$MODEL_DIR" "$VALIDATION_DIR" "$LOG_DIR" "$PROCESS_DIR/scripts_snapshot"
: > "$LEDGER"

# 将实际执行脚本复制到工件包，避免后续仓库修改后无法还原本次过程。
for script in \
  compile_model_contract.py \
  build_freecad_model.py \
  validate_freecad_model.py \
  generate_run_report.py \
  run_vm_freecad_pipeline.sh; do
  cp "$SCRIPT_DIR/$script" "$PROCESS_DIR/scripts_snapshot/$script"
done

# Ubuntu/FreeCAD 发行版使用过 FreeCADCmd 与 freecadcmd 两种名称，因此只做显式探测，
# 找不到时立即失败，不用语言模型猜测路径。
FREECAD_CMD="${FREECAD_CMD:-}"
if [[ -z "$FREECAD_CMD" ]]; then
  FREECAD_CMD="$(command -v FreeCADCmd || command -v freecadcmd || true)"
fi
if [[ -z "$FREECAD_CMD" ]]; then
  echo "ERROR: 未找到 FreeCADCmd/freecadcmd" >&2
  exit 69
fi

record_stage() {
  local stage_id="$1" description="$2" start="$3" end="$4" duration="$5" exit_code="$6" command_text="$7" log_relpath="$8"
  STAGE_ID="$stage_id" DESCRIPTION="$description" START_UTC="$start" END_UTC="$end" \
  DURATION_SECONDS="$duration" EXIT_CODE="$exit_code" COMMAND_TEXT="$command_text" \
  LOG_RELPATH="$log_relpath" LEDGER="$LEDGER" python - <<'PY'
import json, os
from pathlib import Path
record = {
    "stageId": os.environ["STAGE_ID"],
    "description": os.environ["DESCRIPTION"],
    "startedAtUtc": os.environ["START_UTC"],
    "finishedAtUtc": os.environ["END_UTC"],
    "durationSeconds": float(os.environ["DURATION_SECONDS"]),
    "exitCode": int(os.environ["EXIT_CODE"]),
    "command": os.environ["COMMAND_TEXT"],
    "logRelpath": os.environ["LOG_RELPATH"],
}
with Path(os.environ["LEDGER"]).open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
PY
}

run_stage() {
  local stage_id="$1" description="$2"
  shift 2
  local log="$LOG_DIR/${stage_id}.log"
  local start_epoch end_epoch start_utc end_utc status command_text
  start_epoch="$(date +%s.%N)"
  start_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf -v command_text '%q ' "$@"
  echo "===== [$stage_id] $description =====" | tee "$log"
  echo "开始：$start_utc" | tee -a "$log"
  echo "命令：$command_text" | tee -a "$log"

  set +e
  "$@" 2>&1 | tee -a "$log"
  status=${PIPESTATUS[0]}
  set -e

  end_epoch="$(date +%s.%N)"
  end_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local duration
  duration="$(python - <<PY
print(round(float('$end_epoch') - float('$start_epoch'), 6))
PY
)"
  echo "结束：$end_utc；退出码：$status；用时：${duration}s" | tee -a "$log"
  record_stage "$stage_id" "$description" "$start_utc" "$end_utc" "$duration" "$status" "$command_text" "process/logs/${stage_id}.log"
  return "$status"
}

PIPELINE_STATUS="FAILED"
finalize() {
  local original_status=$?
  if [[ $original_status -eq 0 ]]; then
    PIPELINE_STATUS="COMPLETED"
  fi
  python "$SCRIPT_DIR/generate_run_report.py" \
    --run-root "$RUN_ROOT" \
    --ledger "$LEDGER" \
    --status "$PIPELINE_STATUS" \
    > "$LOG_DIR/99-final-report.log" 2>&1 || true
  exit "$original_status"
}
trap finalize EXIT

run_stage "04-contract" "从冻结 DWG 证据编译 N04–N06 数值/装配/抽象契约" \
  python "$SCRIPT_DIR/compile_model_contract.py" \
    --scan-dir "$SCAN_DIR" \
    --geometry-dir "$SCAN_DIR/n03_geometry" \
    --output-dir "$CONTRACT_DIR"

run_stage "05-freecad-environment" "记录 FreeCAD 与 Ubuntu 虚拟机环境" \
  bash -lc "set -euo pipefail; uname -a; cat /etc/os-release; '$FREECAD_CMD' --version || true; dpkg-query -W freecad freecad-python3 2>/dev/null || true; python --version"

# 不给 FreeCADCmd 传自定义参数，避免不同版本对未知命令行参数处理不一致。
# 路径通过显式环境变量传入；建模脚本若缺任一变量会立即报错。
run_stage "06-freecad-build" "在 FreeCADCmd 中创建 FCStd 并导出 STEP" \
  env \
    CAD003_CONTRACT="$CONTRACT_DIR/model_contract.json" \
    CAD003_ASSEMBLY_GRAPH="$CONTRACT_DIR/assembly_graph.json" \
    CAD003_OUTPUT_DIR="$MODEL_DIR" \
    QT_QPA_PLATFORM=offscreen \
    "$FREECAD_CMD" "$SCRIPT_DIR/build_freecad_model.py"

# 这是新的 FreeCADCmd 进程；它不能复用 builder 的内存对象。
run_stage "07-independent-validation" "独立重新打开 FCStd、重新导入 STEP 并检查拓扑/哈希/包围盒" \
  env \
    CAD003_CONTRACT="$CONTRACT_DIR/model_contract.json" \
    CAD003_ASSEMBLY_GRAPH="$CONTRACT_DIR/assembly_graph.json" \
    CAD003_BUILD_DIR="$MODEL_DIR" \
    CAD003_VALIDATION_DIR="$VALIDATION_DIR" \
    QT_QPA_PLATFORM=offscreen \
    "$FREECAD_CMD" "$SCRIPT_DIR/validate_freecad_model.py"

run_stage "08-artifact-smoke-test" "检查最终关键文件非空并输出尺寸" \
  bash -lc "set -euo pipefail; test -s '$MODEL_DIR/Zhaqing_CAD-003.FCStd'; test -s '$MODEL_DIR/Zhaqing_CAD-003-display.step'; test -s '$VALIDATION_DIR/n07_geometry_validation.json'; find '$RUN_ROOT' -maxdepth 3 -type f -printf '%P %s bytes\\n' | sort"
