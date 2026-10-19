# Complete the USB file copy and verify every file (2026-10-08, non-elevated).
$ErrorActionPreference = 'Stop'
$log = 'D:\CachyOS-ARM64\testing\control\copy-complete.log'
Start-Transcript -Path $log -Force | Out-Null

$isoPath = 'D:\CachyOS-ARM64\testing\control\stonking-desktop-arm64+x1e.iso'
Write-Host "Mounting ISO..."
$null = Mount-DiskImage -ImagePath $isoPath -PassThru -Access ReadOnly
Start-Sleep -Seconds 2
$isoVol = (Get-DiskImage -ImagePath $isoPath | Get-Volume | Select-Object -First 1)
$isoL = $isoVol.DriveLetter
Write-Host ("ISO at {0}:" -f $isoL)

Write-Host "Completing robocopy to G: ..."
& robocopy.exe ("{0}:\" -f $isoL) 'G:\' /E /J /R:2 /W:2 /NFL /NDL /NP /TBD
Write-Host ("robocopy exit: {0} (0-7 = success)" -f $LASTEXITCODE)

$isoFiles = Get-ChildItem -LiteralPath ("{0}:\" -f $isoL) -Recurse -File
$usbFiles = Get-ChildItem -LiteralPath 'G:\' -Recurse -File
$isoSum = ($isoFiles | Measure-Object Length -Sum).Sum
$usbSum = ($usbFiles | Measure-Object Length -Sum).Sum
Write-Host ("ISO: {0} files {1} bytes" -f $isoFiles.Count, $isoSum)
Write-Host ("USB: {0} files {1} bytes" -f $usbFiles.Count, $usbSum)

$bad = @()
foreach ($f in $isoFiles) {
    $rel = $f.FullName.Substring(3)
    $u = "G:\$rel"
    if (-not (Test-Path -LiteralPath $u)) { $bad += "MISSING $rel"; continue }
    $ul = (Get-Item -LiteralPath $u).Length
    if ($ul -ne $f.Length) { $bad += "SIZE $rel iso=$($f.Length) usb=$ul" }
}
if ($bad.Count -eq 0 -and $isoFiles.Count -eq $usbFiles.Count -and $isoSum -eq $usbSum) {
    Write-Host "ALL_FILES_MATCH"
} else {
    Write-Host ("FILE_MISMATCHES: {0}" -f $bad.Count)
    $bad | Select-Object -First 10 | ForEach-Object { Write-Host ("  " + $_) }
}

foreach ($c in @('casper\vmlinuz', 'casper\initrd', 'EFI\BOOT\BOOTAA64.EFI', 'boot\grub\grub.cfg', '.disk\casper-uuid-generic')) {
    $h1 = (Get-FileHash -Algorithm SHA256 -LiteralPath ("{0}:\{1}" -f $isoL, $c)).Hash
    $h2 = (Get-FileHash -Algorithm SHA256 -LiteralPath ("G:\{0}" -f $c)).Hash
    if ($h1 -eq $h2) { Write-Host ("HASH_OK   {0}" -f $c) } else { Write-Host ("HASH_BAD  {0}" -f $c) }
}

$null = Dismount-DiskImage -ImagePath $isoPath
if ($bad.Count -eq 0 -and $isoFiles.Count -eq $usbFiles.Count) { Write-Host "USB_READY" } else { Write-Host "USB_INCOMPLETE"; exit 1 }
Stop-Transcript | Out-Null
