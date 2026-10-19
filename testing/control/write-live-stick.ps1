param(
  [string]$StagingDir = 'D:\CachyOS-ARM64\live-staging'
)
# Write the Kestrel live image to the USB stick (2026-10-08).
# Auto-detects the Kingston USB disk (refuses if not exactly one). FAT32 16GB,
# label KESTREL_A64 (matches archisolabel in the UKI cmdline), then copies +
# verifies every file by SHA256. Refuses to run if the staging manifest is absent.
$ErrorActionPreference = 'Stop'
Start-Transcript -Path 'D:\CachyOS-ARM64\testing\control\write-live-stick.log' -Force | Out-Null

$manifest = Join-Path $StagingDir 'SHA256SUMS'
if (-not (Test-Path -LiteralPath $manifest)) { throw "REFUSED: staging manifest missing: $manifest" }

$usbDrives = @(Get-CimInstance Win32_DiskDrive | Where-Object { $_.InterfaceType -eq 'USB' -and $_.Model -match 'Kingston' })
if ($usbDrives.Count -ne 1) { throw ("REFUSED: expected exactly one Kingston USB disk, found {0}" -f $usbDrives.Count) }
$dev = $usbDrives[0]
if ($dev.Size -lt 50GB -or $dev.Size -gt 70GB) { throw "REFUSED: unexpected disk size" }
$DiskNumber = [int]($dev.DeviceID -replace '.*PHYSICALDRIVE', '')
Write-Host ("Target: {0} = \\.\PHYSICALDRIVE{1} Size={2}" -f $dev.Model, $DiskNumber, $dev.Size)

@"
select disk $DiskNumber
clean
convert mbr
create partition primary size=16384
active
format fs=fat32 label=KESTREL_A64 quick
assign
"@ | Set-Content -Path 'D:\CachyOS-ARM64\testing\control\usb-live-partition.txt' -Encoding ASCII
& diskpart.exe /s 'D:\CachyOS-ARM64\testing\control\usb-live-partition.txt'
if ($LASTEXITCODE -ne 0) { throw ("diskpart failed exit {0}" -f $LASTEXITCODE) }
Start-Sleep -Seconds 3

$vol = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.VolumeName -eq 'KESTREL_A64' } | Select-Object -First 1
if (-not $vol) { throw "REFUSED: KESTREL_A64 volume not found after format" }
$usbLetter = $vol.DeviceID.Substring(0, 1)
Write-Host ("USB at {0}:" -f $usbLetter)

& robocopy.exe $StagingDir ("{0}:\" -f $usbLetter) /E /J /R:2 /W:2 /NFL /NDL /NP
Write-Host ("robocopy exit: {0} (0-7 = success)" -f $LASTEXITCODE)

$fail = $false
Get-Content -LiteralPath $manifest | ForEach-Object {
    if ($_ -match '^([0-9a-f]{64})\s+\*?(.+)$') {
        $want = $Matches[1]; $rel = $Matches[2]
        $p = Join-Path ("{0}:\" -f $usbLetter) $rel
        if (-not (Test-Path -LiteralPath $p)) { Write-Host ("MISS {0}" -f $rel); $fail = $true; return }
        $got = (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash
        if ($got -eq $want) { Write-Host ("HASH_OK {0}" -f $rel) } else { Write-Host ("HASH_BAD {0}" -f $rel); $fail = $true }
    }
}
if ($fail) { Write-Host "STICK_VERIFY_FAIL"; Stop-Transcript | Out-Null; exit 1 }
Write-Host "STICK_READY - boot the 83N3 with F12 -> UEFI: Kingston DataTraveler"
Stop-Transcript | Out-Null
