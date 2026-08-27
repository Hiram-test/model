$ErrorActionPreference = "Stop"
$solver = Split-Path -Parent $MyInvocation.MyCommand.Path
$solver = Join-Path $solver "solver"
Set-Location $solver
$exe = "D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe"
$job = "cw_C20x_0827t053427"
$inp = "c20_gate_post_hinges_main.inp"
$out = "cw_c20x_0827t053427.out"
Write-Host "cwd=$solver"
Write-Host "start $(Get-Date -Format o) job=$job"
& $exe -b -smp -np 4 -db 2048 -j $job -i $inp -o $out
$code = $LASTEXITCODE
Write-Host "exit=$code end $(Get-Date -Format o)"
exit $code
