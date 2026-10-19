param(
  [Parameter(Mandatory=$true)][string]$IsoPath
)
# Read-only ISO inspection: hybrid-GPT check + largest-file check (2026-10-08)
$ErrorActionPreference = 'Stop'
Write-Host "== ISO file =="
$f = Get-Item -LiteralPath $IsoPath
Write-Host ("Path: {0}" -f $f.FullName)
Write-Host ("Size: {0} bytes" -f $f.Length)

Write-Host "== hybrid check (GPT signature at LBA1) =="
$fs = [System.IO.File]::Open($IsoPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
$fs.Seek(512, [System.IO.SeekOrigin]::Begin) | Out-Null
$buf = New-Object byte[] 8
$fs.Read($buf, 0, 8) | Out-Null
$fs.Close()
$sig = [System.Text.Encoding]::ASCII.GetString($buf)
if ($sig -eq 'EFI PART') { Write-Host "HYBRID_GPT=yes (dd raw-write to USB will be UEFI-bootable)" }
else { Write-Host ("HYBRID_GPT=no (bytes at 512: {0})" -f $sig) }

Write-Host "== mount and list contents =="
$mount = Mount-DiskImage -ImagePath $IsoPath -PassThru -Access ReadOnly
Start-Sleep -Seconds 2
$letter = ($mount | Get-Volume).DriveLetter
Write-Host ("Mounted at {0}:" -f $letter)
Get-ChildItem -LiteralPath ("{0}:\" -f $letter) -Recurse -File |
  Sort-Object Length -Descending |
  Select-Object -First 8 |
  ForEach-Object { Write-Host ("{0,14}  {1}" -f $_.Length, $_.FullName) }
$tooBig = Get-ChildItem -LiteralPath ("{0}:\" -f $letter) -Recurse -File | Where-Object { $_.Length -gt 4294967296 }
if ($tooBig) { Write-Host "FILES_OVER_4GIB=yes (FAT32 extraction NOT possible)" } else { Write-Host "FILES_OVER_4GIB=no (FAT32 extraction possible)" }
$bootEfi = Test-Path -LiteralPath ("{0}:\EFI\BOOT\BOOTAA64.EFI" -f $letter)
Write-Host ("BOOTAA64_EFI={0}" -f $bootEfi)
Dismount-DiskImage -ImagePath $IsoPath | Out-Null
Write-Host "INSPECT_DONE"
