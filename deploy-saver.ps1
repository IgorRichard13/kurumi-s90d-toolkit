# Empacota e instala o app de screensaver (KurumiSvr1.Saver).
# Uso:  .\deploy-saver.ps1
#       .\deploy-saver.ps1 -NoRun
param(
    [string]$Profile = 'kurumi',
    [string]$Tv = '192.168.1.50',
    [switch]$NoRun
)
$ErrorActionPreference = 'Stop'

$tizen = 'C:\tizen-studio\tools\ide\bin\tizen.bat'
$sdb   = 'C:\tizen-studio\tools\sdb.exe'
$appId = 'KurumiSvr1.Saver'
$serial = "$($Tv):26101"

$root = $PSScriptRoot
$src  = Join-Path $root 'saver'
$out  = Join-Path $root 'build-saver'

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory $out | Out-Null
Copy-Item "$src\*" $out -Recurse

Write-Host "== Assinando com o perfil '$Profile'"
& $tizen package -t wgt -s $Profile -- $out
if ($LASTEXITCODE -ne 0) { throw "tizen package falhou" }

$wgt = Get-ChildItem $out -Filter *.wgt | Select-Object -First 1
if (-not $wgt) { throw "nenhum .wgt gerado" }
$final = Join-Path $out 'KurumiSaver.wgt'
if ($wgt.FullName -ne $final) { Move-Item $wgt.FullName $final -Force }

Write-Host "== Conectando em $serial"
& $sdb connect $serial | Out-Host

Write-Host "== Instalando"
& $tizen install -n KurumiSaver.wgt -s $serial -- $out
if ($LASTEXITCODE -ne 0) { throw "tizen install falhou" }

if (-not $NoRun) {
    Write-Host "== Abrindo $appId"
    & $tizen run -p $appId -s $serial
}
