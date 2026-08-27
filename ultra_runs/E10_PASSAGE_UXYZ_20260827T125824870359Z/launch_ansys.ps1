$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$solver = Join-Path $root "solver"
Set-Location $solver
$tmp = "D:\ANSYS_TMP"
if (-not (Test-Path $tmp)) { New-Item -ItemType Directory -Path $tmp | Out-Null }
$env:TEMP = $tmp
$env:TMP = $tmp
$lock = Join-Path $solver "cw_E10_0827t125824.lock"
if (Test-Path $lock) { Remove-Item $lock -Force }
$exe = "D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe"
$job = "cw_E10_0827t125824"
$inp = "e10_passage_uxyz_main.inp"
$out = "cw_e10_0827t125824.out"
Write-Host "cwd=$solver"
Write-Host "tmp=$tmp"
Write-Host "start $(Get-Date -Format o) job=$job E10"
& $exe -b -smp -np 4 -db 2048 -j $job -i $inp -o $out
$code = $LASTEXITCODE
Write-Host "exit=$code end $(Get-Date -Format o)"
exit $code
