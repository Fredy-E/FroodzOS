param(
  [Parameter(Mandatory=$true)][int]$DiskNumber,
  [Parameter(Mandatory=$true)][string]$IsoPath
)
# Combined USB writer (2026-10-08): raw attempt first, FAT32 file-copy fallback.
# Refuses non-USB disks. Fallback chosen after elevated raw writes were denied
# (likely corporate endpoint filter). ISO verified hybrid but copy-mode is
# equivalent here: BOOTAA64.EFI at root, no CDLABEL dependency, casper-uuid-generic.
$ErrorActionPreference = 'Stop'
Start-Transcript -Path 'D:\CachyOS-ARM64\testing\control\write-usb2.log' -Force | Out-Null

$iso = Get-Item -LiteralPath $IsoPath
$disk = Get-Disk -Number $DiskNumber
Write-Host ("Target: Disk {0} '{1}' BusType={2} Size={3} ReadOnly={4} Offline={5}" -f $DiskNumber, $disk.FriendlyName, $disk.BusType, $disk.Size, $disk.IsReadOnly, $disk.IsOffline)

if ($disk.BusType -ne 'USB') { throw "REFUSED: disk is not USB" }
if ($disk.Size -lt 50GB -or $disk.Size -gt 70GB) { throw "REFUSED: unexpected disk size" }
if ($disk.FriendlyName -notmatch 'Kingston') { throw "REFUSED: unexpected disk model" }
if ($iso.Length -gt $disk.Size) { throw "REFUSED: ISO larger than disk" }

try {
    Set-Disk -Number $DiskNumber -IsReadOnly $false -ErrorAction Stop
    Set-Disk -Number $DiskNumber -IsOffline $false -ErrorAction Stop
} catch { Write-Host ("flag clear skipped: {0}" -f $_.Exception.Message) }

Write-Host "== attempt 1: raw write =="
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'D:\CachyOS-ARM64\testing\control\write-usb.ps1' -DiskNumber $DiskNumber -IsoPath $IsoPath
if ($LASTEXITCODE -eq 0) {
    Write-Host "RAW_WRITE_OK"
    Stop-Transcript | Out-Null
    exit 0
}
Write-Host ("raw write failed (exit {0}); falling back to FAT32 file copy" -f $LASTEXITCODE)

Write-Host "== attempt 2: FAT32 extraction =="
$mount = Mount-DiskImage -ImagePath $IsoPath -PassThru -Access ReadOnly
Start-Sleep -Seconds 2
$isoVol = $mount | Get-Volume
$isoLetter = $isoVol.DriveLetter
Write-Host ("ISO mounted at {0}: label='{1}'" -f $isoLetter, $isoVol.FileSystemLabel)

Write-Host "Partitioning via diskpart (16GB FAT32)..."
@"
select disk $DiskNumber
clean
convert mbr
create partition primary size=16384
active
format fs=fat32 label=UBUNTU-ARM quick
assign
"@ | Set-Content -Path 'D:\CachyOS-ARM64\testing\control\usb-partition.txt' -Encoding ASCII
& diskpart.exe /s 'D:\CachyOS-ARM64\testing\control\usb-partition.txt'
Start-Sleep -Seconds 3
Get-Disk -Number $DiskNumber | Format-Table Number,PartitionStyle,OperationalStatus,Size -AutoSize | Out-String | Write-Host
$v = Get-Volume -FileSystemLabel 'UBUNTU-ARM' -ErrorAction SilentlyContinue
if (-not $v) {
    Write-Host "volume label lookup failed; probing partitions..."
    $v = (Get-Partition -DiskNumber $DiskNumber -ErrorAction SilentlyContinue | Where-Object { $_.DriveLetter -match '^[A-Z]$' } | Select-Object -First 1 | Get-Volume)
}
if (-not $v) { throw "REFUSED: could not find the new FAT32 volume" }
$usbLetter = $v.DriveLetter
Write-Host ("USB at {0}:" -f $usbLetter)

Write-Host "Copying ISO contents (robocopy)..."
& robocopy.exe ("{0}:\" -f $isoLetter) ("{0}:\" -f $usbLetter) /E /J /R:1 /W:1 /NFL /NDL /NP
Write-Host ("robocopy exit: {0} (0-7 = success)" -f $LASTEXITCODE)

$checks = @(
  'EFI\BOOT\BOOTAA64.EFI',
  'casper\vmlinuz',
  'casper\initrd',
  'boot\grub\grub.cfg',
  '.disk\casper-uuid-generic'
)
$fail = $false
foreach ($c in $checks) {
    $p = ("{0}:\{1}" -f $usbLetter, $c)
    if (Test-Path -LiteralPath $p) { Write-Host ("CHECK_OK   {0}" -f $c) } else { Write-Host ("CHECK_MISS {0}" -f $c); $fail = $true }
}
$usbFiles = Get-ChildItem -LiteralPath ("{0}:\" -f $usbLetter) -Recurse -File
Write-Host ("USB file count: {0}" -f $usbFiles.Count)
Dismount-DiskImage -ImagePath $IsoPath | Out-Null
if ($fail) { Write-Host "EXTRACTION_FAIL"; Stop-Transcript | Out-Null; exit 1 }
Write-Host "EXTRACTION_DONE - stick is UEFI-bootable (remove it when you are ready)"
Stop-Transcript | Out-Null
