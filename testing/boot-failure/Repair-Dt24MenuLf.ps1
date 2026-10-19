$ErrorActionPreference = 'Stop'
$project = 'D:\CachyOS-ARM64'
$test = Join-Path $project 'testing\boot-failure'
$mPath = Join-Path $test 'dt24-update-manifest.json'
$rPath = Join-Path $test 'usb-dt24-result.json'
$m = Get-Content -LiteralPath $mPath -Raw | ConvertFrom-Json
$r = Get-Content -LiteralPath $rPath -Raw | ConvertFrom-Json
$a = Get-Content -LiteralPath (Join-Path $test 'dt24-menu-newline-audit.json') -Raw | ConvertFrom-Json
if (-not $a.passed -or -not $a.only_crlf_to_lf -or -not $a.qemu_tested_source_equivalence_verified) { throw 'Menu normalization not audited.' }
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.DeviceID -eq $r.disk -and $_.InterfaceType -eq 'USB' -and $_.Model -like '*Kingston*DataTraveler*' -and [uint64]$_.Size -ge 50000000000 -and [uint64]$_.Size -le 70000000000 })
if ($disks.Count -ne 1) { throw 'Original physical target missing/changed.' }
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disks[0] -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1) { throw 'USB volume association mismatch.' }
$usb = $volumes[0].DeviceID + '\'
if ((Get-Content -LiteralPath (Join-Path $usb 'KESTREL-LOG-TARGET') -Raw).Trim() -ne 'KESTREL_A64_USB_CAPTURE_V1') { throw 'USB marker mismatch.' }
foreach ($f in @($m.files) + @($m.unchanged_files)) {
    $path = Join-Path $usb $f.path
    if ((Get-Item -LiteralPath $path).Length -ne $f.bytes -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw 'Interrupted update state differs; refuse normalization.' }
}
$menuEntry = @($m.files | Where-Object { $_.path -eq 'boot/grub/grub.cfg' })
if ($menuEntry.Count -ne 1 -or $menuEntry[0].sha256 -ne $a.old_menu_sha256) { throw 'Unexpected menu prestate.' }
$source = Join-Path $test 'dt24-grub.cfg'
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $a.old_menu_sha256) { throw 'Source menu changed.' }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$backup = Join-Path $test ('dt24-menu-format-backup-' + $stamp)
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $mPath -Destination (Join-Path $backup 'manifest.json')
Copy-Item -LiteralPath $rPath -Destination (Join-Path $backup 'usb-result.json')
$dest = Join-Path $usb 'boot/grub/grub.cfg'
Copy-Item -LiteralPath $dest -Destination (Join-Path $backup 'grub-crlf.cfg')
if ((Get-FileHash -LiteralPath (Join-Path $backup 'grub-crlf.cfg') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $a.old_menu_sha256) { throw 'Menu backup mismatch.' }
$text = [IO.File]::ReadAllText($source).Replace("`r`n", "`n")
if ($text.Contains("`r")) { throw 'Unexpected non-CRLF carriage return.' }
$bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($text)
$candidate = Join-Path $backup 'grub-lf.cfg'
[IO.File]::WriteAllBytes($candidate, $bytes)
if ($bytes.Length -ne $a.lf_menu_bytes -or (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant() -ne $a.lf_menu_sha256) { throw 'Normalized bytes do not match audited/tested source.' }
$temp = $dest + '.dt24-lf-new'
if (Test-Path -LiteralPath $temp) { throw 'Existing normalization temp retained.' }
Copy-Item -LiteralPath $candidate -Destination $temp
$stream = [IO.File]::Open($temp,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
try { $stream.Flush($true) } finally { $stream.Dispose() }
if ((Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant() -ne $a.lf_menu_sha256) { throw 'USB temp menu mismatch.' }
Move-Item -LiteralPath $temp -Destination $dest -Force
if ((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $a.lf_menu_sha256) { throw 'USB normalized menu readback failed.' }
foreach ($path in @($source,(Join-Path $test 'log-option-grub.cfg'),(Join-Path $test 'log-option\boot\grub\grub.cfg'),(Join-Path $project 'live-staging-v2\boot\grub\grub.cfg'))) {
    [IO.File]::WriteAllBytes($path, $bytes)
}
$menuEntry[0].bytes = $a.lf_menu_bytes
$menuEntry[0].sha256 = $a.lf_menu_sha256
[IO.File]::WriteAllText($mPath, ($m | ConvertTo-Json -Depth 10))
$r.files = $m.files
$r | Add-Member -NotePropertyName menu_lf_normalization_backup -NotePropertyValue $backup -Force
[IO.File]::WriteAllText($rPath, ($r | ConvertTo-Json -Depth 10))
Write-Output ('DT24_MENU_ONLY_LF_REPAIR_READBACK_VERIFIED backup=' + $backup)
exit 0
