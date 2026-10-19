$ErrorActionPreference = 'SilentlyContinue'
wsl.exe --list --verbose
Write-Host '--- builder files ---'
Get-ChildItem "$env:LOCALAPPDATA\Packages" -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*CachyOS*' } | Select-Object Name
Get-ChildItem 'D:\CachyOS-ARM64' -Directory | Select-Object Name
Write-Host '--- disk free ---'
Get-PSDrive C | Select-Object Name, @{n='FreeGB';e={[math]::Round($_.Free / 1GB, 1)}}
Get-PSDrive D | Select-Object Name, @{n='FreeGB';e={[math]::Round($_.Free / 1GB, 1)}}
