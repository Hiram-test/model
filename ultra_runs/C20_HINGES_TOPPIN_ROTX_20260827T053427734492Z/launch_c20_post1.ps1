$ErrorActionPreference = "Stop"
$solver = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "solver"
Set-Location $solver
$lock = Join-Path $solver "cw_C20x_0827t053427.lock"
if (Test-Path $lock) { Remove-Item $lock -Force }
$exe = "D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe"
$job = "cw_C20x_0827t053427"
$inp = "c20_post1_continue.inp"
$out = "c20_post1_continue.out"
Write-Host "cwd=$solver"
Write-Host "start $(Get-Date -Format o) job=$job POST1"
& $exe -b -smp -np 4 -db 2048 -j $job -i $inp -o $out
$code = $LASTEXITCODE
Write-Host "exit=$code end $(Get-Date -Format o)"
exit $code
