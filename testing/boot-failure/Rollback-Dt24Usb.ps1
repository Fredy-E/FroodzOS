[CmdletBinding()]
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$project = 'D:\CachyOS-ARM64'
$test = Join-Path $project 'testing\boot-failure'
$run = Get-Content -LiteralPath (Join-Path $test 'usb-dt24-result.json') -Raw | ConvertFrom-Json
$new = Get-Content -LiteralPath (Join-Path $test 'dt24-update-manifest.json') -Raw | ConvertFrom-Json
$old = Get-Content -LiteralPath (Join-Path $test 'dt23-update-manifest.json') -Raw | ConvertFrom-Json
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.DeviceID -eq $run.disk -and $_.InterfaceType -eq 'USB' -and $_.Model -like '*Kingston*DataTraveler*' -and [uint64]$_.Size -ge 50000000000 -and [uint64]$_.Size -le 70000000000 })
if ($disks.Count -ne 1) { throw 'Original USB physical target missing/changed.' }
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disks[0] -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1) { throw 'USB volume ambiguous.' }
$usb = $volumes[0].DeviceID + '\'
if ((Get-Content -LiteralPath (Join-Path $usb 'KESTREL-LOG-TARGET') -Raw).Trim() -ne 'KESTREL_A64_USB_CAPTURE_V1') { throw 'USB marker mismatch.' }
foreach ($f in $new.files) {
    if ((Get-FileHash -LiteralPath (Join-Path $usb $f.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw 'USB no longer matches dt24; reconcile before rollback.' }
}
$payloads = @()
foreach ($f in $old.files) {
    if ($f.path -notin @('EFI/Linux/kestrel-live.efi','boot/grub/grub.cfg')) { throw 'Rollback path outside scope.' }
    $leaf = if ($f.path -like '*.efi') { 'dt23.efi' } else { 'grub.cfg' }
    $source = Join-Path $run.backup $leaf
    if ((Get-Item -LiteralPath $source).Length -ne $f.bytes -or (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw 'Rollback backup mismatch.' }
    $payloads += @{ entry=$f; source=$source }
}
if (-not $Apply) { Write-Output ('DT24_ROLLBACK_DRY_RUN_OK ' + $usb); exit 0 }
foreach ($p in $payloads) {
    $f = $p.entry
    $dest = Join-Path $usb $f.path
    $temp = $dest + '.dt23-rollback'
    if (Test-Path -LiteralPath $temp) { throw 'Existing rollback temp retained for inspection.' }
    Copy-Item -LiteralPath $p.source -Destination $temp
    $stream = [IO.File]::Open($temp,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
    try { $stream.Flush($true) } finally { $stream.Dispose() }
    if ((Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw 'Rollback temporary-copy mismatch.' }
    Move-Item -LiteralPath $temp -Destination $dest -Force
    if ((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw 'Rollback readback mismatch.' }
    Copy-Item -LiteralPath $p.source -Destination (Join-Path $project ('live-staging-v2\' + $f.path)) -Force
}
foreach ($dest in @((Join-Path $test 'log-option-grub.cfg'),(Join-Path $test 'log-option\boot\grub\grub.cfg'))) {
    Copy-Item -LiteralPath (Join-Path $run.backup 'grub.cfg') -Destination $dest -Force
}
Write-Output 'DT23_TWO_FILE_ROLLBACK_READBACK_VERIFIED_NO_FIRMWARE_CHANGES'
exit 0
