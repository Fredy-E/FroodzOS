$ErrorActionPreference = 'Stop'
# File-only: swap plain UKI to v2-dt12 (0016 apps-usb optional). No formatting or other changes.
$project = 'D:\CachyOS-ARM64'
$src = Join-Path $project 'live-staging-v2\EFI\Linux\kestrel-live.efi'
$oldUsb = '765ddb44c25f923f32dcfef274c4cc1d50df7874c3713c89e6a396b9ba1f1eb9'
$newHash = 'afb0aa04424b9832bc7803e31cb7ba285e1d42a3f76b8b24a72c7fc2838335e4'
$newBytes = 244916736
if ((Get-Item -LiteralPath $src).Length -ne $newBytes) { throw 'Source UKI size changed.' }
if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newHash) { throw 'Source UKI hash changed.' }
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
$backup = Join-Path $project ("testing\boot-failure\usb-before-dt12-$stamp")
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $dst -Destination (Join-Path $backup 'kestrel-live-dt11.efi')
Copy-Item -LiteralPath $src -Destination $dst -Force
if ((Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newHash) { throw 'USB UKI hash mismatch after copy.' }
Write-Host 'USB_DT12_VERIFIED'
[ordered]@{ time_utc=$stamp; disk=$disk.DeviceID; volume=$usb; new_uki=$newHash; backup=$backup; hardware_boot_verified=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $project 'testing\boot-failure\usb-dt12-result.json') -Encoding UTF8
