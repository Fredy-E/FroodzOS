$ErrorActionPreference = 'Stop'
wsl.exe --shutdown
Start-Sleep -Seconds 15
Optimize-VHD -Path 'D:\CachyOS-ARM64\builder\ext4.vhdx' -Mode Full
$v = Get-Item 'D:\CachyOS-ARM64\builder\ext4.vhdx'
Write-Host "COMPACTED_GB $([math]::Round($v.Length / 1GB, 1))"
Write-Host "D free now: $([math]::Round((Get-PSDrive D).Free / 1GB, 1)) GB"
