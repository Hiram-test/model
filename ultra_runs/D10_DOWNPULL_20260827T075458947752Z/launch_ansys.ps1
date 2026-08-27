$ErrorActionPreference = "Stop"
$solver = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "solver"
Set-Location $solver
$exe = "D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe"
$job = "cw_D10x_0827t075458"
$inp = "d10_downpull_main.inp"
$out = "cw_d10x_0827t075458.out"
Write-Host "cwd=$solver"
Write-Host "start $(Get-Date -Format o) job=$job"
& $exe -b -smp -np 4 -db 2048 -j $job -i $inp -o $out
$code = $LASTEXITCODE
Write-Host "exit=$code end $(Get-Date -Format o)"
exit $code
