$ErrorActionPreference = 'Stop'
# File-only: swap plain UKI to v2-dt3 (minimal-boot round). No formatting or other changes.
$project = 'D:\CachyOS-ARM64'
$src = Join-Path $project 'live-staging-v2\EFI\Linux\kestrel-live.efi'
$oldUsb = 'b1adc18b7e0b550b73a1f42dc8573c1b8efc2a1a975f9b0d0b305eca892cf136'
$newHash = 'a3d1f6c2aa3d6c71cbb5c23f983d7eefe6b516a3d6243c2d355f836888e975d6'
$newBytes = 244386304
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.InterfaceType -eq 'USB' -and $_.Model -like '*Kingston*DataTraveler*' -and [uint64]$_.Size -ge 50000000000 -and [uint64]$_.Size -le 70000000000 })
if ($disks.Count -ne 1) { throw 'Need exactly one matching Kingston DataTraveler USB disk.' }
$disk = $disks[0]
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disk -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1) { throw 'Matching USB must contain exactly one FAT32 KESTREL_A64 volume.' }
$usb = $volumes[0].DeviceID + '\'
$dst = Join-Path $usb 'EFI\Linux\kestrel-live.efi'
if ((Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant() -ne $oldUsb) { throw 'USB UKI prestate mismatch; refusing.' }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$backup = Join-Path $project ("testing\boot-failure\usb-before-dt3-$stamp")
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $dst -Destination (Join-Path $backup 'kestrel-live.efi')
Copy-Item -LiteralPath $src -Destination $dst -Force
if ((Get-Item -LiteralPath $dst).Length -ne $newBytes) { throw 'USB UKI size mismatch after copy.' }
if ((Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newHash) { throw 'USB UKI hash mismatch after copy.' }
Write-Host 'USB_DT3_VERIFIED'
[ordered]@{ time_utc=$stamp; disk=$disk.DeviceID; volume=$usb; new_uki=$newHash; backup=$backup; hardware_boot_verified=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $project 'testing\boot-failure\usb-dt3-result.json') -Encoding UTF8
