$ErrorActionPreference = 'SilentlyContinue'
$vbox = Get-Command VBoxManage.exe -ErrorAction SilentlyContinue
Write-Host "VBoxManage: $($vbox.Source)"
$hv = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All -ErrorAction SilentlyContinue
Write-Host "Hyper-V: $($hv.State)"
$vmms = Get-Service vmms -ErrorAction SilentlyContinue
Write-Host "VMMS: $($vmms.Status)"
$qemu = Get-Command qemu-system-aarch64.exe -ErrorAction SilentlyContinue
Write-Host "QEMU-win: $($qemu.Source)"
