[CmdletBinding()]
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$project = 'D:\CachyOS-ARM64'
$test = Join-Path $project 'testing\boot-failure'
$manifest = Get-Content -LiteralPath (Join-Path $test 'dt24-update-manifest.json') -Raw | ConvertFrom-Json
if ($manifest.revision -ne 'v2-dt24' -or $manifest.files.Count -ne 2 -or $manifest.firmware_clear_included) { throw 'Unexpected update scope.' }
foreach ($gate in $manifest.gates) {
    $r = Get-Content -LiteralPath (Join-Path $test $gate) -Raw | ConvertFrom-Json
    if (-not $r.passed -or $r.uki_sha256 -ne $manifest.uki_sha256) { throw ('Gate mismatch: ' + $gate) }
}
foreach ($f in $manifest.files) {
    if ($f.path -notin @('EFI/Linux/kestrel-live.efi','boot/grub/grub.cfg')) { throw 'Unapproved file path.' }
    $source = Join-Path $project $f.source
    if ((Get-Item -LiteralPath $source).Length -ne $f.bytes -or (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw 'Source size/hash mismatch.' }
}
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.InterfaceType -eq 'USB' -and $_.Model -like '*Kingston*DataTraveler*' -and [uint64]$_.Size -ge 50000000000 -and [uint64]$_.Size -le 70000000000 })
if ($disks.Count -ne 1) { throw 'Need exactly one matching Kingston USB disk.' }
$disk = $disks[0]
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disk -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1 -or $volumes[0].FreeSpace -lt 300000000) { throw 'USB volume/space mismatch.' }
$usb = $volumes[0].DeviceID + '\'
if ((Get-Content -LiteralPath (Join-Path $usb 'KESTREL-LOG-TARGET') -Raw).Trim() -ne 'KESTREL_A64_USB_CAPTURE_V1') { throw 'USB marker mismatch.' }
foreach ($f in $manifest.files) {
    if ((Get-FileHash -LiteralPath (Join-Path $usb $f.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.old_sha256) { throw 'USB prestate changed; refusing.' }
}
foreach ($f in $manifest.unchanged_files) {
    $path = Join-Path $usb $f.path
    if ((Get-Item -LiteralPath $path).Length -ne $f.bytes -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw 'Unchanged boot payload mismatch.' }
}
if (-not $Apply) { Write-Output ('DT24_DRY_RUN_OK target=' + $disk.DeviceID + ' volume=' + $usb); exit 0 }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$backup = Join-Path $test ('usb-before-dt24-' + $stamp)
New-Item -ItemType Directory -Path $backup | Out-Null
foreach ($f in $manifest.files) {
    $leaf = if ($f.path -like '*.efi') {'dt23.efi'} else {'grub.cfg'}
    Copy-Item -LiteralPath (Join-Path $usb $f.path) -Destination (Join-Path $backup $leaf)
    if ((Get-FileHash -LiteralPath (Join-Path $backup $leaf) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.old_sha256) { throw 'Rollback backup mismatch.' }
}
foreach ($f in $manifest.files) {
    $dest = Join-Path $usb $f.path
    $temp = $dest + '.dt24-new'
    if (Test-Path -LiteralPath $temp) { throw 'Unexpected existing candidate temp file; retained for inspection.' }
    Copy-Item -LiteralPath (Join-Path $project $f.source) -Destination $temp
    $stream = [IO.File]::Open($temp, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::Read)
    try { $stream.Flush($true) } finally { $stream.Dispose() }
    if ((Get-Item -LiteralPath $temp).Length -ne $f.bytes -or (Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw 'Temp copy mismatch; original retained.' }
    Move-Item -LiteralPath $temp -Destination $dest -Force
    if ((Get-Item -LiteralPath $dest).Length -ne $f.bytes -or (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw 'USB readback mismatch.' }
}
Copy-Item -LiteralPath (Join-Path $test 'dt24-candidate.efi') -Destination (Join-Path $project 'live-staging-v2\EFI\Linux\kestrel-live.efi') -Force
foreach ($dest in @((Join-Path $test 'log-option-grub.cfg'), (Join-Path $test 'log-option\boot\grub\grub.cfg'), (Join-Path $project 'live-staging-v2\boot\grub\grub.cfg'))) {
    Copy-Item -LiteralPath (Join-Path $test 'dt24-grub.cfg') -Destination $dest -Force
}
$result = [ordered]@{ verified=$true; revision='v2-dt24'; time_utc=$stamp; disk=$disk.DeviceID; model=$disk.Model; volume=$usb; backup=$backup; files=$manifest.files; hardware_boot_verified=$false; firmware_variables_changed=$false }
$result | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $test 'usb-dt24-result.json') -Encoding UTF8
Write-Output 'USB_DT24_FILE_UPDATE_VERIFIED'
exit 0
