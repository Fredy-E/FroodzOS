$ErrorActionPreference = 'Stop'
# File-only: swap plain UKI to v2-dt8 (mdss off). No formatting or other changes.
$project = 'D:\CachyOS-ARM64'
$src = Join-Path $project 'live-staging-v2\EFI\Linux\kestrel-live.efi'
$oldUsb = 'ce4281605837637dd2d07f0d0a27fd5bf5a751d2a81c49fca3b66156c0da92ea'
$newHash = '00b5ffe6efc167fd49c3abd4cdb7690f985ba80f60545c05b075a9a332bf562c'
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
$backup = Join-Path $project ("testing\boot-failure\usb-before-dt8-$stamp")
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $dst -Destination (Join-Path $backup 'kestrel-live.efi')
Copy-Item -LiteralPath $src -Destination $dst -Force
if ((Get-Item -LiteralPath $dst).Length -ne $newBytes) { throw 'USB UKI size mismatch after copy.' }
if ((Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newHash) { throw 'USB UKI hash mismatch after copy.' }
Write-Host 'USB_DT8_VERIFIED'
[ordered]@{ time_utc=$stamp; disk=$disk.DeviceID; volume=$usb; new_uki=$newHash; backup=$backup; hardware_boot_verified=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $project 'testing\boot-failure\usb-dt8-result.json') -Encoding UTF8
