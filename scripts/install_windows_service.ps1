param(
    [string]$ExePath = ".\console-agent.exe",
    [string]$InstallDir = "$env:ProgramFiles\ConsoleAgent",
    [string]$ServiceName = "ConsoleAgent",
    [string]$DisplayName = "Console Agent",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 9001
)

$ErrorActionPreference = "Stop"

$principal = [Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated PowerShell window."
}

$ResolvedExe = Resolve-Path -LiteralPath $ExePath
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

$TargetExe = Join-Path $InstallDir "console-agent.exe"
Copy-Item -LiteralPath $ResolvedExe -Destination $TargetExe -Force

$LogDir = Join-Path $InstallDir "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$Existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($Existing) {
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
}

$BinPath = "`"$TargetExe`" --host $HostAddress --port $Port"
sc.exe create $ServiceName binPath= $BinPath start= auto DisplayName= $DisplayName | Out-Null
sc.exe description $ServiceName "Local serial console agent for browser access." | Out-Null
sc.exe failure $ServiceName reset= 60 actions= restart/5000/restart/5000/restart/5000 | Out-Null

Start-Service -Name $ServiceName

Write-Host "Installed and started $ServiceName."
Write-Host "Status:"
Get-Service -Name $ServiceName
Write-Host ""
Write-Host "Test on this PC:"
Write-Host "http://127.0.0.1:$Port/api/status"
