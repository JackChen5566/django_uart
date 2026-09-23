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

$InstallerDir = ".\dist\windows-installer"
New-Item -ItemType Directory -Path $InstallerDir -Force | Out-Null
Copy-Item -LiteralPath ".\dist\$Name.exe" -Destination "$InstallerDir\console-agent.exe" -Force
Copy-Item -LiteralPath ".\scripts\install.ps1" -Destination "$InstallerDir\install.ps1" -Force
Copy-Item -LiteralPath ".\scripts\uninstall.ps1" -Destination "$InstallerDir\uninstall.ps1" -Force

$ZipPath = ".\dist\console-agent-windows-installer.zip"
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path "$InstallerDir\*" -DestinationPath $ZipPath

Write-Host ""
Write-Host "Built .\dist\$Name.exe"
Write-Host "Built $ZipPath"
Write-Host "Client PCs should extract the zip and run install.ps1 as Administrator."
