[CmdletBinding()]
param([switch]$RequireRearmed)
$ErrorActionPreference = 'Stop'
$project = 'D:\CachyOS-ARM64'
$test = Join-Path $project 'testing\boot-failure'
$run = Get-Content -LiteralPath (Join-Path $test 'usb-dt22-result.json') -Raw | ConvertFrom-Json
$m = Get-Content -LiteralPath (Join-Path $test 'dt22-update-manifest.json') -Raw | ConvertFrom-Json
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.DeviceID -eq $run.disk })
if ($disks.Count -ne 1) { throw 'Physical target missing/ambiguous.' }
$disk = $disks[0]
if ($disk.InterfaceType -ne 'USB' -or $disk.Model -notlike '*Kingston*DataTraveler*' -or [uint64]$disk.Size -lt 50000000000 -or [uint64]$disk.Size -gt 70000000000) { throw 'Physical target changed.' }
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disk -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1 -or $volumes[0].DeviceID + '\' -ne $run.volume) { throw 'USB association changed.' }
$usb = $run.volume
if ((Get-Content -LiteralPath (Join-Path $usb 'KESTREL-LOG-TARGET') -Raw).Trim() -ne 'KESTREL_A64_USB_CAPTURE_V1') { throw 'USB marker mismatch.' }
$verified = @()
foreach ($f in @($m.files) + @($m.unchanged_files)) {
    $path = Join-Path $usb $f.path
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Get-Item -LiteralPath $path).Length -ne $f.bytes -or $hash -ne $f.sha256) { throw ('USB payload mismatch: ' + $f.path) }
    $staging = Join-Path $project ('live-staging-v2\' + $f.path)
    if ((Get-FileHash -LiteralPath $staging -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash) { throw 'Staging is stale.' }
    $verified += [ordered]@{ path=$f.path; bytes=$f.bytes; sha256=$hash }
}
$menu = Get-Content -LiteralPath (Join-Path $usb 'boot\grub\grub.cfg') -Raw
$entries = [regex]::Matches($menu,'(?ms)^menuentry .*?(?=^menuentry |\z)')
if ($entries.Count -ne $m.menu_entries -or $menu -notmatch '(?m)^set default=7$') { throw 'Menu shape mismatch.' }
foreach ($i in @(7,8)) {
    foreach ($option in @('kestrel_log=1','kestrel_efilog=1','rd.log=console rd.log=file','module_blacklist=dispcc_x1e80100','init=/usr/local/sbin/kestrel-pid1')) {
        if (-not $entries[$i].Value.Contains($option)) { throw ('Missing shell/logger option: ' + $option) }
    }
}
$fw = Join-Path $test ('dt22-preboot-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $test 'Read-KestrelCheckpoint.ps1') -OutputDirectory $fw | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Firmware readback failed.' }
$fr = Get-Content -LiteralPath (Join-Path $fw 'report.json') -Raw | ConvertFrom-Json
$slots = @($fr.records | Where-Object { $_.name -match '^KestrelBoot0[0-3]$' })
if ($slots.Count -ne 4) { throw 'Firmware export shape mismatch.' }
$rearmed = @($slots | Where-Object { $_.status -ne 'Missing' -or $_.error -ne 203 }).Count -eq 0
$r = [ordered]@{ verified=$true; revision='v2-dt22'; disk=$disk.DeviceID; model=$disk.Model; volume=$usb; critical_files=$verified; menu_entries=$entries.Count; entry8=$entries[7].Value.Split("`n")[0]; entry9=$entries[8].Value.Split("`n")[0]; firmware_slots_verified_empty=$rearmed; firmware_readback=$fw; firmware_boot_ids=$fr.boot_ids; usb_log_files=@(Get-ChildItem -LiteralPath (Join-Path $usb 'Logs') -File -Recurse).Count; hardware_boot_verified=$false }
$json = $r | ConvertTo-Json -Depth 7
[IO.File]::WriteAllText((Join-Path $test 'usb-dt22-independent.json'), $json)
Write-Output $json
if ($RequireRearmed -and -not $rearmed) { throw 'File update verified, but firmware capture still disarmed; no variables changed.' }
exit 0
