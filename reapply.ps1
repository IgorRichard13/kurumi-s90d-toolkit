# Reaplica o Kurumi Home, o screensaver, o auto-update e o debloat.
# Use depois de uma atualização de firmware ou se algo voltar ao padrao.
# Uso:  .\reapply.ps1
#       .\reapply.ps1 -Tv 192.168.18.50
#       .\reapply.ps1 -SkipDeploy   (se os apps ja estao instalados)
#       .\reapply.ps1 -SkipSaver    (sem o screensaver)
param(
    [string]$Tv = '192.168.1.50',
    [switch]$SkipDeploy,
    [switch]$SkipSaver
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Push-Location $root
try {
    if (-not $SkipDeploy) {
        Write-Host "== Deploy do Kurumi Home"
        & (Join-Path $root 'deploy.ps1') -Tv $Tv
        if ($LASTEXITCODE -ne 0) { throw "deploy.ps1 falhou" }
    }

    if (-not $SkipSaver -and -not $SkipDeploy) {
        Write-Host "== Deploy do Kurumi Saver"
        & (Join-Path $root 'deploy-saver.ps1') -Tv $Tv
        if ($LASTEXITCODE -ne 0) { throw "deploy-saver.ps1 falhou" }
    }

    Write-Host "== Home no Kurumi"
    & py -3 (Join-Path $root 'tools\home.py') --tv $Tv set --yes
    if ($LASTEXITCODE -ne 0) { throw "home.py set falhou" }

    # O sdbd desta TV fica ocupado por alguns minutos depois de cada appinstall.
    Write-Host "== Aguardando o sdbd liberar (3 min)"
    Start-Sleep -Seconds 180

    Write-Host "== Auto-update desligado"
    & py -3 (Join-Path $root 'tools\updates.py') --tv $Tv off --yes
    if ($LASTEXITCODE -ne 0) { throw "updates.py off falhou" }

    Write-Host "== Aguardando o sdbd liberar (3 min)"
    Start-Sleep -Seconds 180

    Write-Host "== Debloat"
    & py -3 (Join-Path $root 'tools\debloat.py') --tv $Tv apply --yes
    if ($LASTEXITCODE -ne 0) { throw "debloat.py apply falhou" }

    if (-not $SkipSaver) {
        Write-Host "== Aguardando o sdbd liberar (3 min)"
        Start-Sleep -Seconds 180
        Write-Host "== Screensaver Kurumi"
        & py -3 (Join-Path $root 'tools\saver.py') --tv $Tv apply --yes
        if ($LASTEXITCODE -ne 0) { throw "saver.py apply falhou" }
    }

    Write-Host "== Pronto"
    Write-Host "Se algum passo falhar com 'sdbd preso', espere ~3 minutos e rode de novo."
}
finally {
    Pop-Location
}
