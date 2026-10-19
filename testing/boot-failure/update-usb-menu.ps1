$ErrorActionPreference = 'Stop'
# File-only GRUB menu refresh (adds 2 initcall-debug entries). No formatting or other changes.
$project = 'D:\CachyOS-ARM64'
$src = Join-Path $project 'testing\boot-failure\log-option\boot\grub\grub.cfg'
$oldHash = 'ce2580fa6e81343fdb11efaa3ccd4128711a8b0767224595756f5ad5c64b083a'
$newHash = '477247a0384db6e65ac99c2fc6556cbbb53951e0d9980259a4a4e8a7498b8dbf'
$newBytes = 4705
if ((Get-Item -LiteralPath $src).Length -ne $newBytes) { throw 'Source menu size changed.' }
if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newHash) { throw 'Source menu hash changed.' }
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.InterfaceType -eq 'USB' -and $_.Model -like '*Kingston*DataTraveler*' -and [uint64]$_.Size -ge 50000000000 -and [uint64]$_.Size -le 70000000000 })
if ($disks.Count -ne 1) { throw 'Need exactly one matching Kingston DataTraveler USB disk.' }
$disk = $disks[0]
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disk -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1) { throw 'Matching USB must contain exactly one FAT32 KESTREL_A64 volume.' }
$target = $volumes[0].DeviceID + '\'
$dst = Join-Path $target 'boot\grub\grub.cfg'
if ((Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant() -ne $oldHash) { throw 'USB menu is not the expected log-option menu; refusing.' }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$backup = Join-Path $project ("testing\boot-failure\usb-before-menu-update-$stamp")
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $dst -Destination (Join-Path $backup 'grub.cfg')
Copy-Item -LiteralPath $src -Destination $dst -Force
if ((Get-Item -LiteralPath $dst).Length -ne $newBytes) { throw 'USB menu size mismatch after copy.' }
if ((Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newHash) { throw 'USB menu hash mismatch after copy.' }
Write-Host 'USB_MENU_UPDATED_VERIFIED'
[ordered]@{ time_utc=$stamp; disk=$disk.DeviceID; volume=$target; old_sha256=$oldHash; new_sha256=$newHash; hardware_boot_verified=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $project 'testing\boot-failure\usb-menu-update-result.json') -Encoding UTF8
