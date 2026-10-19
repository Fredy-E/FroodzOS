$ErrorActionPreference = 'Stop'
# File-only alignment-fix UKI refresh. No formatting, raw-disk, BCD or firmware changes.
$project = 'D:\CachyOS-ARM64'
$source = Join-Path $project 'testing\boot-failure\log-option\EFI\Linux'
$oldPlain = '948589b827ac23f64551ace06b877853f92a536a845fc04b63baa16b77d4625e'
$oldLog = '4fd7ae12d70b1b2c8e38b4b33cec1e0d21bc34ec8239d7364547f5cf37517a9f'
$newPlain = 'b9730ea275848fcea2cd3e73e2806dc3682c9256a88b8820b9b9a94ee31b8550'
$newLog = 'b92eeb3d49ca7a0fbc3f95c4ba774155a5ee2e69e861834ecbcaca69932566d2'
$files = @(
    [ordered]@{ name='kestrel-live.efi'; bytes=244385792; old=$oldPlain; new=$newPlain },
    [ordered]@{ name='kestrel-live-log.efi'; bytes=244916224; old=$oldLog; new=$newLog }
)
foreach ($f in $files) {
    $p = Join-Path $source $f.name
    if ((Get-Item -LiteralPath $p).Length -ne $f.bytes) { throw "Source size changed: $($f.name)" }
    if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.new) { throw "Source hash changed: $($f.name)" }
}
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.InterfaceType -eq 'USB' -and $_.Model -like '*Kingston*DataTraveler*' -and [uint64]$_.Size -ge 50000000000 -and [uint64]$_.Size -le 70000000000 })
if ($disks.Count -ne 1) { throw 'Need exactly one matching Kingston DataTraveler USB disk.' }
$disk = $disks[0]
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disk -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1) { throw 'Matching USB must contain exactly one FAT32 KESTREL_A64 volume.' }
$target = Join-Path ($volumes[0].DeviceID + '\') 'EFI\Linux'
foreach ($f in $files) {
    $p = Join-Path $target $f.name
    if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.old) { throw "USB prestate mismatch: $($f.name); refusing." }
}
Write-Host ("TARGET: {0}; {1}; {2}; both UKIs prestate-verified" -f $disk.DeviceID,$disk.Model,$target)
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$backup = Join-Path $project ("testing\boot-failure\usb-before-align-$stamp")
New-Item -ItemType Directory -Path $backup | Out-Null
foreach ($f in $files) {
    Copy-Item -LiteralPath (Join-Path $target $f.name) -Destination (Join-Path $backup $f.name)
    Copy-Item -LiteralPath (Join-Path $source $f.name) -Destination (Join-Path $target $f.name) -Force
    $p = Join-Path $target $f.name
    if ((Get-Item -LiteralPath $p).Length -ne $f.bytes) { throw "USB size mismatch: $($f.name)" }
    if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.new) { throw "USB hash mismatch: $($f.name)" }
    Write-Host "OK $($f.name)"
}
Write-Host 'USB_ALIGN_FIX_VERIFIED: both UKIs read-back hash matched. Hardware boot remains untested.'
[ordered]@{ time_utc=$stamp; disk=$disk.DeviceID; volume=$target; new_plain=$newPlain; new_log=$newLog; backup=$backup; hardware_boot_verified=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $project 'testing\boot-failure\usb-align-result.json') -Encoding UTF8
