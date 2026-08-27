$ErrorActionPreference = "Continue"
$solver = "D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0\ultra_runs\C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z\solver"
$errf = Join-Path $solver "cw_C20x_0827t053427.err"
$stf = Join-Path $solver "c20_gate_status.txt"
$deadline = (Get-Date).AddHours(5)
while ((Get-Date) -lt $deadline) {
    $status = ""
    if (Test-Path $stf) { $status = Get-Content $stf -Raw -ErrorAction SilentlyContinue }
    if ($status -match "SOLVER_EXPORT_COMPLETED") {
        Write-Output "DONE"
        exit 0
    }
    if ($status -match "REJECTED") {
        Write-Output "FAILED"
        exit 1
    }
    $err = ""
    if (Test-Path $errf) { $err = Get-Content $errf -Raw -ErrorAction SilentlyContinue }
    if ($err -match "(?i)\*\*\* ERROR \*\*\*") {
        Write-Output "FAILED"
        exit 1
    }
    if ($err -match "(?i)negative pivot|ZERO PIVOT TERM") {
        Write-Output "FAILED"
        exit 1
    }
    $alive = Get-Process -Name ANSYS,ANSYS261 -ErrorAction SilentlyContinue
    if (-not $alive) {
        Start-Sleep -Seconds 8
        if (Test-Path $stf) { $status = Get-Content $stf -Raw -ErrorAction SilentlyContinue }
        if ($status -match "SOLVER_EXPORT_COMPLETED") {
            Write-Output "DONE"
            exit 0
        }
        Write-Output "FAILED"
        exit 1
    }
    Start-Sleep -Seconds 45
}
Write-Output "FAILED"
exit 1
