$ErrorActionPreference = 'Stop'
# File-only: swap plain UKI to v2-dt10 (apps-usb via config_noc). No formatting or other changes.
$project = 'D:\CachyOS-ARM64'
$src = Join-Path $project 'live-staging-v2\EFI\Linux\kestrel-live.efi'
$oldUsb = '3004ed18d4afbdf5d34bb7006988d71b2961c2134e6ee9462bd7ce6aca8bfdac'
$newHash = 'e2e1fe9333e19759709900bf4320834bc20a450a289ca9a80f75eb7b1b6b9fd1'
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
$backup = Join-Path $project ("testing\boot-failure\usb-before-dt10-$stamp")
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $dst -Destination (Join-Path $backup 'kestrel-live.efi')
Copy-Item -LiteralPath $src -Destination $dst -Force
if ((Get-Item -LiteralPath $dst).Length -ne $newBytes) { throw 'USB UKI size mismatch after copy.' }
if ((Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newHash) { throw 'USB UKI hash mismatch after copy.' }
Write-Host 'USB_DT10_VERIFIED'
[ordered]@{ time_utc=$stamp; disk=$disk.DeviceID; volume=$usb; new_uki=$newHash; backup=$backup; hardware_boot_verified=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $project 'testing\boot-failure\usb-dt10-result.json') -Encoding UTF8
