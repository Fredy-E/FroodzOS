# Read-only independent verification after the authorized file-only updater.
$ErrorActionPreference = 'Stop'
$project = 'D:\CachyOS-ARM64'
$state = Join-Path $project 'testing\boot-failure'
$manifestPath = Join-Path $state 'staging-v2-manifest.json'
$m = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$r = Get-Content -LiteralPath (Join-Path $state 'usb-v2-result.json') -Raw | ConvertFrom-Json
$files = @($m.files)
if ($files.Count -ne $m.file_count -or $r.file_count -ne $m.file_count -or $r.verified_count -ne $m.file_count) { throw 'Manifest/update result counts disagree.' }
if (-not $m.qemu_shell_passed -or -not $m.qemu_systemd_passed) { throw 'Missing prior EFI validation.' }
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.InterfaceType -eq 'USB' -and $_.Model -like '*Kingston*DataTraveler*' -and [uint64]$_.Size -ge 50000000000 -and [uint64]$_.Size -le 70000000000 })
if ($disks.Count -ne 1 -or $disks[0].DeviceID -ne $r.disk) { throw 'USB identity no longer matches the write result.' }
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disks[0] -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1) { throw 'Expected one KESTREL_A64 FAT32 USB volume.' }
$target = $volumes[0].DeviceID + '\'
if ($target -ne $r.volume) { throw 'USB volume differs from the write result.' }
$expectedBytes = [uint64]0
$paths = @{}
foreach ($f in $files) {
    $rel = [string]$f.path
    if ([IO.Path]::IsPathRooted($rel) -or $rel.Contains(':') -or @($rel.Split('/') | Where-Object { $_ -eq '..' -or $_ -eq '.' }).Count -gt 0) { throw "Unsafe path: $rel" }
    $key = $rel.ToLowerInvariant()
    if ($paths.ContainsKey($key)) { throw "Duplicate manifest path: $rel" }
    $paths[$key] = $true
    $p = Join-Path $target ($rel.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "Missing file: $rel" }
    if ((Get-Item -LiteralPath $p).Length -ne $f.bytes) { throw "Size mismatch: $rel" }
    $expectedBytes += [uint64]$f.bytes
}
if ($expectedBytes -ne [uint64]$m.total_bytes) { throw 'Manifest byte total mismatch.' }
$critical = @('efi/boot/bootaa64.efi','efi/linux/kestrel-live.efi','arch/aarch64/airootfs.sfs','boot/grub/grub.cfg')
$checks = @()
foreach ($key in $critical) {
    $entry = @($files | Where-Object { ([string]$_.path).ToLowerInvariant() -eq $key })
    if ($entry.Count -ne 1) { throw "Missing critical manifest entry: $key" }
    $f = $entry[0]
    $p = Join-Path $target ([string]$f.path).Replace('/', '\')
    $hash = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $f.sha256) { throw "Critical read-back hash mismatch: $key" }
    $checks += [ordered]@{path=$f.path; bytes=$f.bytes; sha256=$hash; matched=$true}
    Write-Host "CRITICAL_READBACK_OK $($f.path) $hash"
}
$extra = @()
foreach ($f in @(Get-ChildItem -LiteralPath $target -Recurse -File -Force)) {
    $rel = $f.FullName.Substring($target.Length).Replace('\', '/')
    if (-not $paths.ContainsKey($rel.ToLowerInvariant())) { $extra += $rel }
}
$out = [ordered]@{
    verification_time_utc=[DateTime]::UtcNow.ToString('o')
    update_time_utc=$r.time_utc
    disk=$r.disk
    model=$disks[0].Model
    volume=$target
    manifest_file_count=$files.Count
    size_matched_count=$files.Count
    updater_hash_matched_count=$r.verified_count
    manifest_bytes=$expectedBytes
    manifest_sha256=(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    independent_critical_hashes=$checks
    extra_file_paths=$extra
    updater_log=$r.log
    backup=$r.backup
    hardware_boot_verified=$false
    verified=$true
}
$out | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $state 'usb-v2-independent-verification.json') -Encoding UTF8
$out | ConvertTo-Json -Depth 6
Write-Host 'INDEPENDENT_USB_V2_VERIFIED - native boot remains untested.'
