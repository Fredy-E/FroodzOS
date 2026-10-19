$ErrorActionPreference = 'SilentlyContinue'
$out = @()
$out += '--- vhdx hunt ---'
$out += Get-ChildItem 'D:\CachyOS-ARM64\builder' -Recurse -Filter '*.vhdx' -ErrorAction SilentlyContinue | ForEach-Object { "$($_.FullName) $([math]::Round($_.Length / 1GB, 1))GB" }
$out += Get-ChildItem "$env:LOCALAPPDATA\Hermes" -Recurse -Filter '*.vhdx' -ErrorAction SilentlyContinue | ForEach-Object { "$($_.FullName) $([math]::Round($_.Length / 1GB, 1))GB" }
$out += '--- free ---'
$out += "C free: $([math]::Round((Get-PSDrive C).Free / 1GB, 1)) GB"
$out += "D free: $([math]::Round((Get-PSDrive D).Free / 1GB, 1)) GB"
$out += '--- wsl registration ---'
$out += (wsl.exe --list --verbose 2>&1 | Out-String)
$out | Set-Content -LiteralPath 'D:\CachyOS-ARM64\testing\boot-failure\builder-disk-report.txt' -Encoding ASCII
