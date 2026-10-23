# Packages src/ as a signed .wgt and installs it on the TV.
# Usage:  .\deploy.ps1                      (profile "kurumi", TV 192.168.1.50)
#         .\deploy.ps1 -Tv 192.168.18.50    (if the TV changes IP)
#         .\deploy.ps1 -NoRun               (install without opening it)
param(
    [string]$Profile = 'kurumi',
    [string]$Tv = '192.168.1.50',
    [switch]$NoRun
)
$ErrorActionPreference = 'Stop'

$tizen = 'C:\tizen-studio\tools\ide\bin\tizen.bat'
$sdb   = 'C:\tizen-studio\tools\sdb.exe'
$appId = 'KurumiTV01.Home'
$serial = "$($Tv):26101"

$root = $PSScriptRoot
$src  = Join-Path $root 'src'
$out  = Join-Path $root 'build'

# Fresh copy of src/ so packaging never writes signatures into the sources
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory $out | Out-Null
Copy-Item "$src\*" $out -Recurse
# The PC-preview stand-in for the Tizen APIs never runs on the TV; keep it out of the package
Remove-Item (Join-Path $out 'js\mock-tizen.js') -ErrorAction SilentlyContinue

# Small copies of the wallpapers for the picker, so the TV doesn't decode six full images at once
$py = Join-Path $root 'tools\venv\Scripts\python.exe'
if (Test-Path $py) {
    Write-Host "== Gerando miniaturas"
    & $py (Join-Path $root 'tools\thumbs.py') (Join-Path $out 'assets')
} else {
    Write-Host "== Sem tools\venv: o seletor vai usar as imagens inteiras"
}

Write-Host "== Assinando com o perfil '$Profile'"
& $tizen package -t wgt -s $Profile -- $out
if ($LASTEXITCODE -ne 0) { throw "tizen package falhou" }

# The TV refuses package file names with spaces, so rename whatever was produced
$wgt = Get-ChildItem $out -Filter *.wgt | Select-Object -First 1
if (-not $wgt) { throw "nenhum .wgt gerado" }
$final = Join-Path $out 'KurumiHome.wgt'
if ($wgt.FullName -ne $final) { Move-Item $wgt.FullName $final -Force }

Write-Host "== Conectando em $serial"
& $sdb connect $serial | Out-Host

Write-Host "== Instalando"
& $tizen install -n KurumiHome.wgt -s $serial -- $out
if ($LASTEXITCODE -ne 0) { throw "tizen install falhou" }

if (-not $NoRun) {
    Write-Host "== Abrindo $appId"
    & $tizen run -p $appId -s $serial
}
