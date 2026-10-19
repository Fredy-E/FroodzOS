$ErrorActionPreference = 'Stop'
# File-only: dt16 UKI (bounded checkpoint, handover + atomic-write fixes) + 11-entry menu.
# No formatting, no partition/BCD/BIOS changes. Refuses on any prestate mismatch.
$project = 'D:\CachyOS-ARM64\'
$srcUki = Join-Path $project 'live-staging-v2\EFI\Linux\kestrel-live.efi'
$srcMenu = Join-Path $project 'testing\boot-failure\log-option\boot\grub\grub.cfg'
$oldUki = '0f319c9847b3dcbb31701b707c557d78fab62fd7bbaf9823174ac63c2e4410a2'
$newUki = 'd85658ae24762ef9ee0d71c4df2b3b208dbabbe8096dd7124805037fc8055cab'
$newUkiBytes = 244407296
$oldMenu = '9bbf0d682159a9ac5d5856b8c58efa20ec0d6bec0a3f721a50593f7f912e5200'
$newMenu = 'c79c5bc52f3f44c7acc2fcf362704cacc3d121932361861703506681614bd0f5'
$newMenuBytes = 5586
if ((Get-Item -LiteralPath $srcUki).Length -ne $newUkiBytes) { throw 'Source UKI size changed.' }
if ((Get-FileHash -LiteralPath $srcUki -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newUki) { throw 'Source UKI hash changed.' }
if ((Get-Item -LiteralPath $srcMenu).Length -ne $newMenuBytes) { throw 'Source menu size changed.' }
if ((Get-FileHash -LiteralPath $srcMenu -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newMenu) { throw 'Source menu hash changed.' }
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.InterfaceType -eq 'USB' -and $_.Model -like '*Kingston*DataTraveler*' -and [uint64]$_.Size -ge 50000000000 -and [uint64]$_.Size -le 70000000000 })
if ($disks.Count -ne 1) { throw 'Need exactly one matching Kingston DataTraveler USB disk.' }
$disk = $disks[0]
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disk -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1) { throw 'Matching USB must contain exactly one FAT32 KESTREL_A64 volume.' }
$usb = $volumes[0].DeviceID + '\'
$dstUki = Join-Path $usb 'EFI\Linux\kestrel-live.efi'
$dstMenu = Join-Path $usb 'boot\grub\grub.cfg'
if ((Get-FileHash -LiteralPath $dstUki -Algorithm SHA256).Hash.ToLowerInvariant() -ne $oldUki) { throw 'USB UKI prestate mismatch; refusing.' }
if ((Get-FileHash -LiteralPath $dstMenu -Algorithm SHA256).Hash.ToLowerInvariant() -ne $oldMenu) { throw 'USB menu prestate mismatch; refusing.' }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$backup = Join-Path $project ("testing\boot-failure\usb-before-dt16-$stamp")
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $dstUki -Destination (Join-Path $backup 'kestrel-live-dt13.efi')
Copy-Item -LiteralPath $dstMenu -Destination (Join-Path $backup 'grub.cfg')
Copy-Item -LiteralPath $srcUki -Destination $dstUki -Force
Copy-Item -LiteralPath $srcMenu -Destination $dstMenu -Force
if ((Get-FileHash -LiteralPath $dstUki -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newUki) { throw 'USB UKI hash mismatch after copy.' }
if ((Get-FileHash -LiteralPath $dstMenu -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newMenu) { throw 'USB menu hash mismatch after copy.' }
Write-Host 'USB_DT16_VERIFIED'
[ordered]@{ time_utc=$stamp; disk=$disk.DeviceID; volume=$usb; new_uki=$newUki; new_menu=$newMenu; backup=$backup; hardware_boot_verified=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $project 'testing\boot-failure\usb-dt16-result.json') -Encoding UTF8
