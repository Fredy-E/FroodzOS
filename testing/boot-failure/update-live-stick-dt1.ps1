$ErrorActionPreference = 'Stop'
# File-only DT-test UKI refresh (16c0000 disabled). No formatting or other changes.
$project = 'D:\CachyOS-ARM64'
$src = Join-Path $project 'testing\boot-failure\log-option\EFI\Linux\kestrel-live.efi'
$oldHash = 'b9730ea275848fcea2cd3e73e2806dc3682c9256a88b8820b9b9a94ee31b8550'
$newHash = 'ed8b5c93642f3931af62c13916e7cebb0991b0a577b9470ab59be90646d9f696'
$newBytes = 244385792
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
$target = Join-Path ($volumes[0].DeviceID + '\') 'EFI\Linux\kestrel-live.efi'
if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $oldHash) { throw 'USB prestate mismatch; refusing.' }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$backup = Join-Path $project ("testing\boot-failure\usb-before-dt1-$stamp")
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $target -Destination (Join-Path $backup 'kestrel-live.efi')
Copy-Item -LiteralPath $src -Destination $target -Force
if ((Get-Item -LiteralPath $target).Length -ne $newBytes) { throw 'USB size mismatch after copy.' }
if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newHash) { throw 'USB hash mismatch after copy.' }
Write-Host 'USB_DT1_VERIFIED'
[ordered]@{ time_utc=$stamp; disk=$disk.DeviceID; new_sha256=$newHash; backup=$backup; hardware_boot_verified=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $project 'testing\boot-failure\usb-dt1-result.json') -Encoding UTF8
