$ErrorActionPreference = 'Stop'
$project = 'D:\CachyOS-ARM64'; $test = Join-Path $project 'testing\boot-failure'
$run = Get-Content -LiteralPath (Join-Path $test 'usb-dt19-result.json') -Raw | ConvertFrom-Json
$m = Get-Content -LiteralPath (Join-Path $test 'dt19-update-manifest.json') -Raw | ConvertFrom-Json
$disk = Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.DeviceID -eq $run.disk }
if (-not $disk -or $disk.InterfaceType -ne 'USB' -or $disk.Model -notlike '*Kingston*DataTraveler*' -or [uint64]$disk.Size -lt 50000000000 -or [uint64]$disk.Size -gt 70000000000) { throw 'Physical target changed.' }
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disk -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1 -or $volumes[0].DeviceID + '\' -ne $run.volume) { throw 'Volume changed.' }
$usb = $run.volume; $verified = @()
foreach ($f in $m.files) {
    $target = Join-Path $usb $f.path
    $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Get-Item -LiteralPath $target).Length -ne $f.bytes -or $hash -ne $f.sha256) { throw 'Changed file readback failed.' }
    if ((Get-FileHash -LiteralPath (Join-Path $project ('live-staging-v2\' + $f.path)) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash) { throw 'Local staging is stale.' }
    $verified += [ordered]@{ path=$f.path; bytes=$f.bytes; sha256=$hash }
}
foreach ($relative in @('EFI\BOOT\BOOTAA64.EFI','arch\aarch64\airootfs.sfs')) {
    $target = Join-Path $usb $relative
    $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    $source = Join-Path $project ('live-staging-v2\' + $relative)
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash) { throw 'Unchanged loader/root payload mismatch.' }
    $verified += [ordered]@{ path=$relative; bytes=(Get-Item -LiteralPath $target).Length; sha256=$hash }
}
$menu = Get-Content -LiteralPath (Join-Path $usb 'boot\grub\grub.cfg') -Raw
$entries = [regex]::Matches($menu,'(?ms)^menuentry .*?(?=^menuentry |\z)')
if ($entries.Count -ne 11 -or $menu -notmatch '(?m)^set default=7$') { throw 'Menu shape mismatch.' }
foreach ($i in @(7,8)) {
    if ($entries[$i].Value -notmatch 'kestrel_efilog=1' -or $entries[$i].Value -notmatch 'rd.log=console rd.log=file') { throw 'Logger flag missing.' }
}
$fw = Join-Path $test ('dt19-preboot-empty-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $test 'Read-KestrelCheckpoint.ps1') -OutputDirectory $fw | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Firmware readback failed.' }
$fr = Get-Content -LiteralPath (Join-Path $fw 'report.json') -Raw | ConvertFrom-Json
$slots = @($fr.records | Where-Object { $_.name -match '^KestrelBoot0[0-3]$' })
if ($slots.Count -ne 4 -or @($slots | Where-Object { $_.status -ne 'Missing' -or $_.error -ne 203 }).Count -ne 0) { throw 'Logger is not rearmed; prior records remain.' }
$r = [ordered]@{ verified=$true; revision='v2-dt19'; disk=$disk.DeviceID; model=$disk.Model; volume=$usb; critical_files=$verified; menu_entries=$entries.Count; entry8=$entries[7].Value.Split("`n")[0]; entry9=$entries[8].Value.Split("`n")[0]; firmware_slots_verified_empty=$true; firmware_readback=$fw; usb_log_files=@(Get-ChildItem -LiteralPath (Join-Path $usb 'Logs') -File -Recurse).Count; hardware_boot_verified=$false }
$json = $r | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText((Join-Path $test 'usb-dt19-independent.json'),$json)
Write-Output $json
