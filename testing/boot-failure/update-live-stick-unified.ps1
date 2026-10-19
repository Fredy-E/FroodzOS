$ErrorActionPreference = 'Stop'
# File-only: unified UKI (dt11, hook-in) + repointed menu; retire stale log UKI.
$project = 'D:\CachyOS-ARM64'
$srcUki = Join-Path $project 'live-staging-v2\EFI\Linux\kestrel-live.efi'
$srcMenu = Join-Path $project 'testing\boot-failure\log-option\boot\grub\grub.cfg'
$oldUki = 'e2e1fe9333e19759709900bf4320834bc20a450a289ca9a80f75eb7b1b6b9fd1'
$newUki = '765ddb44c25f923f32dcfef274c4cc1d50df7874c3713c89e6a396b9ba1f1eb9'
$newUkiBytes = 244916736
$oldMenu = '0ca570671e06858dd07479806beae7a6399db538dbc5a1305ac1cd00dfdc5f3f'
$newMenu = 'ce2580fa6e81343fdb11efaa3ccd4128711a8b0767224595756f5ad5c64b083a'
$newMenuBytes = 4621
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
$dstLogUki = Join-Path $usb 'EFI\Linux\kestrel-live-log.efi'
if ((Get-FileHash -LiteralPath $dstUki -Algorithm SHA256).Hash.ToLowerInvariant() -ne $oldUki) { throw 'USB UKI prestate mismatch; refusing.' }
if ((Get-FileHash -LiteralPath $dstMenu -Algorithm SHA256).Hash.ToLowerInvariant() -ne $oldMenu) { throw 'USB menu prestate mismatch; refusing.' }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$backup = Join-Path $project ("testing\boot-failure\usb-before-unified-$stamp")
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $dstUki -Destination (Join-Path $backup 'kestrel-live.efi')
Copy-Item -LiteralPath $dstMenu -Destination (Join-Path $backup 'grub.cfg')
if (Test-Path -LiteralPath $dstLogUki) {
    Move-Item -LiteralPath $dstLogUki -Destination (Join-Path $backup 'kestrel-live-log.efi')
}
Copy-Item -LiteralPath $srcUki -Destination $dstUki -Force
Copy-Item -LiteralPath $srcMenu -Destination $dstMenu -Force
if ((Get-FileHash -LiteralPath $dstUki -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newUki) { throw 'USB UKI hash mismatch after copy.' }
if ((Get-FileHash -LiteralPath $dstMenu -Algorithm SHA256).Hash.ToLowerInvariant() -ne $newMenu) { throw 'USB menu hash mismatch after copy.' }
if (Test-Path -LiteralPath $dstLogUki) { throw 'Stale log UKI still present.' }
Write-Host 'USB_UNIFIED_VERIFIED'
[ordered]@{ time_utc=$stamp; disk=$disk.DeviceID; volume=$usb; new_uki=$newUki; new_menu=$newMenu; backup=$backup; hardware_boot_verified=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $project 'testing\boot-failure\usb-unified-result.json') -Encoding UTF8
