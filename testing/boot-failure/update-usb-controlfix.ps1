$ErrorActionPreference = 'Stop'
# File-only: fixed Ubuntu control entry (menu) + Slim 3 DTB for GRUB devicetree.
$project = 'D:\CachyOS-ARM64'
$srcMenu = Join-Path $project 'testing\boot-failure\log-option\boot\grub\grub.cfg'
$srcDtb = Join-Path $project 'testing\boot-failure\log-option\boot\slim3-x126100.dtb'
$oldMenu = 'a94ab610832d75d82dc2b72efcad54474b0dda3949062485cf6e5df02c63e7b1'
$newMenu = 'f80192128b852283d6461302b5f3aa7308af4e1f57a615ea809d5b05519f2411'
$newMenuBytes = 5591
$dtbHash = '986d7d837a5c4f00c220b02b9ba294b705887b74aa39a72331357e0da0aea111'
$dtbBytes = 207656
if ((Get-Item -LiteralPath $srcMenu).Length -ne $newMenuBytes) { throw 'Source menu size changed.' }
if ((Get-FileHash -LiteralPath $srcMenu -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newMenu) { throw 'Source menu hash changed.' }
if ((Get-Item -LiteralPath $srcDtb).Length -ne $dtbBytes) { throw 'Source DTB size changed.' }
if ((Get-FileHash -LiteralPath $srcDtb -Algorithm SHA256).Hash.ToLowerInvariant() -ne $dtbHash) { throw 'Source DTB hash changed.' }
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.InterfaceType -eq 'USB' -and $_.Model -like '*Kingston*DataTraveler*' -and [uint64]$_.Size -ge 50000000000 -and [uint64]$_.Size -le 70000000000 })
if ($disks.Count -ne 1) { throw 'Need exactly one matching Kingston DataTraveler USB disk.' }
$disk = $disks[0]
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disk -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1) { throw 'Matching USB must contain exactly one FAT32 KESTREL_A64 volume.' }
$usb = $volumes[0].DeviceID + '\'
$dstMenu = Join-Path $usb 'boot\grub\grub.cfg'
if ((Get-FileHash -LiteralPath $dstMenu -Algorithm SHA256).Hash.ToLowerInvariant() -ne $oldMenu) { throw 'USB menu prestate mismatch; refusing.' }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$backup = Join-Path $project ("testing\boot-failure\usb-before-controlfix-$stamp")
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $dstMenu -Destination (Join-Path $backup 'grub.cfg')
Copy-Item -LiteralPath $srcMenu -Destination $dstMenu -Force
$dstDtb = Join-Path $usb 'boot\slim3-x126100.dtb'
Copy-Item -LiteralPath $srcDtb -Destination $dstDtb -Force
if ((Get-FileHash -LiteralPath $dstMenu -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newMenu) { throw 'USB menu hash mismatch after copy.' }
if ((Get-Item -LiteralPath $dstDtb).Length -ne $dtbBytes) { throw 'USB DTB size mismatch after copy.' }
if ((Get-FileHash -LiteralPath $dstDtb -Algorithm SHA256).Hash.ToLowerInvariant() -ne $dtbHash) { throw 'USB DTB hash mismatch after copy.' }
Write-Host 'USB_CONTROLFIX_VERIFIED'
[ordered]@{ time_utc=$stamp; disk=$disk.DeviceID; volume=$usb; new_menu=$newMenu; dtb=$dtbHash; backup=$backup; hardware_boot_verified=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $project 'testing\boot-failure\usb-controlfix-result.json') -Encoding UTF8
