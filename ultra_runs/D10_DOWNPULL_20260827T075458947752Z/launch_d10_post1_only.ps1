$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$solver = Join-Path $root "solver"
Set-Location $solver
$tmp = "D:\ANSYS_TMP"
if (-not (Test-Path $tmp)) { New-Item -ItemType Directory -Path $tmp | Out-Null }
$env:TEMP = $tmp
$env:TMP = $tmp
$lock = Join-Path $solver "cw_D10x_0827t075458.lock"
if (Test-Path $lock) { Remove-Item $lock -Force }
foreach ($stale in @(
    "d10_section_modal_sene.csv",
    "d10_modal_sene_groups.csv",
    "d10_mode_probes.csv",
    "d10_modal_properties.csv"
)) {
    $p = Join-Path $solver $stale
    if (Test-Path $p) { Remove-Item $p -Force }
}
$exe = "D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe"
$job = "cw_D10x_0827t075458"
$inp = "d10_post1_continue.inp"
$out = "d10_post1_continue.out"
Write-Host "cwd=$solver"
Write-Host "start $(Get-Date -Format o) job=$job POST1-only"
& $exe -b -smp -np 4 -db 2048 -j $job -i $inp -o $out
$code = $LASTEXITCODE
Write-Host "exit=$code end $(Get-Date -Format o)"
exit $code
