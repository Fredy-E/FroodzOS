param([switch]$Apply)
# File-only log-option delta. No formatting, raw-disk write, BCD or firmware changes.
$ErrorActionPreference = 'Stop'
$project = 'D:\CachyOS-ARM64'
$source = Join-Path $project 'testing\boot-failure\log-option'
$manifestPath = Join-Path $project 'testing\boot-failure\log-option-manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Log-option manifest is not ready.' }
$m = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if (-not $m.qemu_log_shell_passed -or -not $m.qemu_log_systemd_passed) { throw 'Both log-capture EFI tests must pass before any USB update.' }
$files = @($m.files)
foreach ($f in $files) {
    $rel = [string]$f.path
    if ([IO.Path]::IsPathRooted($rel) -or $rel.Contains(':') -or @($rel.Split('/') | Where-Object { $_ -eq '..' -or $_ -eq '.' }).Count -gt 0) { throw "Unsafe manifest path: $rel" }
    if ($f.bytes -ge 4294967296) { throw "File exceeds FAT32 limit: $rel" }
    $p = Join-Path $source ($rel.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "Missing source file: $rel" }
    if ((Get-Item -LiteralPath $p).Length -ne $f.bytes) { throw "Source size changed: $rel" }
    if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw "Source hash changed: $rel" }
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
if ([uint64]$vol.FreeSpace -lt 400000000) { throw 'Not enough free space for the log-option delta.' }
# Pre-state: refuse if the USB is not the verified v2 tree.
$pre = $m.expected_prestate
$oldGrub = Join-Path $target 'boot\grub\grub.cfg'
if ((Get-FileHash -LiteralPath $oldGrub -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pre.'boot/grub/grub.cfg'.sha256) { throw 'USB grub.cfg is not the verified v2 menu; refusing delta.' }
foreach ($key in @('efi/boot/bootaa64.efi', 'efi/linux/kestrel-live.efi')) {
    $p = Join-Path $target ($key.Replace('/', '\'))
    $e = $pre.$key
    if ((Get-Item -LiteralPath $p).Length -ne $e.bytes) { throw "USB prestate size changed: $key" }
    if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -ne $e.sha256) { throw "USB prestate hash changed: $key" }
}
$sfs = Join-Path $target 'arch\aarch64\airootfs.sfs'
if ((Get-Item -LiteralPath $sfs).Length -ne $pre.'arch/aarch64/airootfs.sfs'.bytes) { throw 'USB squashfs size changed.' }
Write-Host ("TARGET: {0}; {1}; volume {2}; delta {3} files" -f $disk.DeviceID,$disk.Model,$target,$files.Count)
if (-not $Apply) { Write-Host 'DRY_RUN_OK - USB unchanged. Run with -Apply only after owner approval.'; exit 0 }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$log = Join-Path $project ("testing\boot-failure\usb-log-option-$stamp.log")
Start-Transcript -Path $log | Out-Null
try {
    $backup = Join-Path $project ("testing\boot-failure\usb-before-log-option-$stamp")
    New-Item -ItemType Directory -Path $backup | Out-Null
    Copy-Item -LiteralPath $oldGrub -Destination (Join-Path $backup 'grub.cfg')
    & robocopy.exe $source $target /E /J /R:1 /W:1 /NFL /NDL /NP
    $rc = $LASTEXITCODE
    if ($rc -ge 8) { throw "Robocopy failed: $rc" }
    $logsDir = Join-Path $target 'Logs'
    if (-not (Test-Path -LiteralPath $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }
    $bad = @()
    foreach ($f in $files) {
        $path = Join-Path $target ([string]$f.path).Replace('/', '\')
        if (-not (Test-Path -LiteralPath $path)) { $bad += "MISSING $($f.path)"; continue }
        if ((Get-Item -LiteralPath $path).Length -ne $f.bytes) { $bad += "SIZE $($f.path)"; continue }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { $bad += "HASH $($f.path)" }
    }
    if (-not (Test-Path -LiteralPath $logsDir -PathType Container)) { $bad += 'MISSING Logs/' }
    if ($bad.Count -gt 0) { throw ($bad -join "`n") }
    Write-Host ("USB_LOG_OPTION_VERIFIED: {0}/{0} delta files read-back hash matched. Hardware boot remains untested." -f $files.Count)
    $result = [ordered]@{ time_utc=$stamp; disk=$disk.DeviceID; volume=$target; file_count=$files.Count; verified_count=$files.Count; log=$log; backup=$backup; hardware_boot_verified=$false }
    $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $project 'testing\boot-failure\usb-log-option-result.json') -Encoding UTF8
} finally {
    Stop-Transcript | Out-Null
}
