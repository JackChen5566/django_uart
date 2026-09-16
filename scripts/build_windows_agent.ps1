param(
    [string]$Python = "python",
    [string]$Name = "console-agent"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".\.venv")) {
    & $Python -m venv .venv
}

$VenvPython = ".\.venv\Scripts\python.exe"
$PyInstaller = ".\.venv\Scripts\pyinstaller.exe"

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r .\console_agent\requirements-build.txt

& $PyInstaller `
    --onefile `
    --clean `
    --name $Name `
    --add-data "console_agent\browser_client.js;console_agent" `
    .\run_console_agent.py

Write-Host ""
Write-Host "Built .\dist\$Name.exe"
Write-Host "Client PCs can run:"
Write-Host ".\dist\$Name.exe --host 127.0.0.1 --port 9001"
