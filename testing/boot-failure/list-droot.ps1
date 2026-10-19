$ErrorActionPreference = 'SilentlyContinue'
Get-ChildItem 'D:\' -Force | Select-Object Name, @{n='GB';e={ if ($_.PSIsContainer) {'<dir>'} else {[math]::Round($_.Length / 1GB, 2)} }} | Format-Table -AutoSize | Out-String | Set-Content 'D:\CachyOS-ARM64\testing\boot-failure\droot.txt' -Encoding ASCII
