param([switch]$Apply)
# File-only update. No formatting, raw-disk write, BCD or firmware changes.
$ErrorActionPreference = 'Stop'
$project = 'D:\CachyOS-ARM64'
$source = Join-Path $project 'live-staging-v2'
$manifestPath = Join-Path $project 'testing\boot-failure\staging-v2-manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Verified v2 manifest is not ready.' }
$m = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if (-not $m.qemu_shell_passed -or -not $m.qemu_systemd_passed) { throw 'Both v2 EFI tests must pass before any USB update.' }
$files = @($m.files)
if ($files.Count -ne $m.file_count) { throw 'Manifest count mismatch.' }
foreach ($f in $files) {
    $rel = [string]$f.path
    if ([IO.Path]::IsPathRooted($rel) -or $rel.Contains(':') -or @($rel.Split('/') | Where-Object { $_ -eq '..' -or $_ -eq '.' }).Count -gt 0) { throw "Unsafe manifest path: $rel" }
    if ($f.bytes -ge 4294967296) { throw "File exceeds FAT32 limit: $rel" }
    $p = Join-Path $source ($rel.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "Missing source file: $rel" }
    if ((Get-Item -LiteralPath $p).Length -ne $f.bytes) { throw "Source size changed: $rel" }
}
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.InterfaceType -eq 'USB' -and $_.Model -like '*Kingston*DataTraveler*' -and [uint64]$_.Size -ge 50000000000 -and [uint64]$_.Size -le 70000000000 })
if ($disks.Count -ne 1) { throw 'Need exactly one matching 50-70 GB Kingston DataTraveler USB disk.' }
$disk = $disks[0]
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disk -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1) { throw 'Matching USB must contain exactly one FAT32 KESTREL_A64 volume.' }
$vol = $volumes[0]
$target = $vol.DeviceID + '\'
# Conservative bound: full v2 source must fit in current free space even before replacing old files.
if ([uint64]$vol.FreeSpace -lt [uint64]$m.total_bytes) { throw 'Not enough free space for the full diagnostic/control tree.' }
Write-Host ("TARGET: {0}; {1}; volume {2}; source {3} files, {4} bytes" -f $disk.DeviceID,$disk.Model,$target,$files.Count,$m.total_bytes)
if (-not $Apply) { Write-Host 'DRY_RUN_OK - USB unchanged. Run with -Apply only after owner approval.'; exit 0 }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$log = Join-Path $project ("testing\boot-failure\usb-v2-$stamp.log")
Start-Transcript -Path $log | Out-Null
try {
    # Reject a different or previously altered medium before overwriting anything.
    $expected = @{
        'EFI\BOOT\BOOTAA64.EFI' = '61093676c2de8fd7282a87ba4fb2882e169f30f4d1ea4f62494c88f75c83176c'
        'arch\aarch64\airootfs.sfs' = '8ade18708a65fef9ca8221064f92a8d727a5487788d4f68e2b9737b8ee19ef81'
    }
    foreach ($rel in $expected.Keys) {
        $path = Join-Path $target $rel
        if (-not (Test-Path -LiteralPath $path)) { throw "Missing original USB artifact: $rel" }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected[$rel]) { throw "Original USB artifact changed: $rel" }
    }
    foreach ($f in $files) {
        $path = Join-Path $source ([string]$f.path).Replace('/', '\')
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw "Source hash changed: $($f.path)" }
    }
    $backup = Join-Path $project ("testing\boot-failure\usb-before-v2-$stamp")
    New-Item -ItemType Directory -Path $backup | Out-Null
    Copy-Item -LiteralPath (Join-Path $target 'EFI\BOOT\BOOTAA64.EFI') -Destination (Join-Path $backup 'BOOTAA64.EFI')
    Copy-Item -LiteralPath (Join-Path $target 'SHA256SUMS') -Destination (Join-Path $backup 'SHA256SUMS')
    # Original squashfs and UKI also remain in the untouched original local staging tree.
    & robocopy.exe $source $target /E /J /R:1 /W:1 /NFL /NDL /NP
    $rc = $LASTEXITCODE
    if ($rc -ge 8) { throw "Robocopy failed: $rc" }
    $bad = @()
    foreach ($f in $files) {
        $path = Join-Path $target ([string]$f.path).Replace('/', '\')
        if (-not (Test-Path -LiteralPath $path)) { $bad += "MISSING $($f.path)"; continue }
        if ((Get-Item -LiteralPath $path).Length -ne $f.bytes) { $bad += "SIZE $($f.path)"; continue }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { $bad += "HASH $($f.path)" }
    }
    if ($bad.Count -gt 0) { throw ($bad -join "`n") }
    Write-Host ("USB_V2_VERIFIED: {0}/{0} files read-back hash matched. Hardware boot remains untested." -f $files.Count)
    $result = [ordered]@{ time_utc=$stamp; disk=$disk.DeviceID; volume=$target; file_count=$files.Count; verified_count=$files.Count; log=$log; backup=$backup; hardware_boot_verified=$false }
    $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $project 'testing\boot-failure\usb-v2-result.json') -Encoding UTF8
} finally {
    Stop-Transcript | Out-Null
}
