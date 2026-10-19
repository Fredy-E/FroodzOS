param(
  [Parameter(Mandatory=$true)][int]$DiskNumber,
  [Parameter(Mandatory=$true)][string]$IsoPath
)
# Safety-checked raw ISO write to a USB disk (2026-10-08). Refuses non-USB disks.
$ErrorActionPreference = 'Stop'
Start-Transcript -Path 'D:\CachyOS-ARM64\testing\control\write-usb.log' -Force | Out-Null

$iso = Get-Item -LiteralPath $IsoPath
$disk = Get-Disk -Number $DiskNumber
Write-Host ("Target: Disk {0} '{1}' BusType={2} Size={3}" -f $DiskNumber, $disk.FriendlyName, $disk.BusType, $disk.Size)

if ($disk.BusType -ne 'USB') { throw "REFUSED: disk is not USB" }
if ($disk.Size -lt 50GB -or $disk.Size -gt 70GB) { throw "REFUSED: unexpected disk size" }
if ($disk.FriendlyName -notmatch 'Kingston') { throw "REFUSED: unexpected disk model" }
if ($iso.Length -gt $disk.Size) { throw "REFUSED: ISO larger than disk" }

Write-Host "Safety checks passed. Dismounting volumes..."
$parts = Get-Partition -DiskNumber $DiskNumber -ErrorAction SilentlyContinue
foreach ($p in $parts) {
    if ($p.DriveLetter -and ($p.DriveLetter -match '^[A-Z]$')) {
        Write-Host ("  mountvol {0}: /D" -f $p.DriveLetter)
        & mountvol.exe ("{0}:" -f $p.DriveLetter) /D 2>$null
    }
}
Start-Sleep -Seconds 2

Write-Host ("Writing {0} bytes to \\.\PhysicalDrive{1} ..." -f $iso.Length, $DiskNumber)
$src = [System.IO.File]::Open($iso.FullName, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
$dst = $null
for ($try = 1; $try -le 3 -and -not $dst; $try++) {
    try {
        $dst = [System.IO.File]::Open(("\\.\PhysicalDrive{0}" -f $DiskNumber), [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    } catch {
        Write-Host ("  open attempt {0} failed: {1}" -f $try, $_.Exception.Message)
        Start-Sleep -Seconds 3
    }
}
if (-not $dst) { throw "REFUSED: cannot open physical drive for writing" }
$buf = New-Object byte[] (8 * 1024 * 1024)
$total = 0L
$nextReport = 256MB
while ($true) {
    $n = $src.Read($buf, 0, $buf.Length)
    if ($n -le 0) { break }
    $dst.Write($buf, 0, $n)
    $total += $n
    if ($total -ge $nextReport) {
        Write-Host ("  {0:N0} MB written..." -f ($total / 1MB))
        $nextReport += 512MB
    }
}
$dst.Flush()
$src.Close(); $dst.Close()
Write-Host ("Wrote {0} bytes." -f $total)

Write-Host "Verifying first 4KB and last 4KB against the ISO..."
$src = [System.IO.File]::Open($iso.FullName, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
$dst = [System.IO.File]::Open(("\\.\PhysicalDrive{0}" -f $DiskNumber), [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::None)
function Compare-Block($s, $d, $offset, $count) {
    $s.Seek($offset, [System.IO.SeekOrigin]::Begin) | Out-Null
    $d.Seek($offset, [System.IO.SeekOrigin]::Begin) | Out-Null
    $a = New-Object byte[] $count; $b = New-Object byte[] $count
    $s.Read($a, 0, $count) | Out-Null
    $d.Read($b, 0, $count) | Out-Null
    for ($i = 0; $i -lt $count; $i++) { if ($a[$i] -ne $b[$i]) { return $false } }
    return $true
}
$okHead = Compare-Block $src $dst 0 4096
$okTail = Compare-Block $src $dst ($iso.Length - 4096) 4096
$src.Close(); $dst.Close()
if ($okHead -and $okTail) { Write-Host "VERIFY_OK" } else { Write-Host ("VERIFY_FAIL head={0} tail={1}" -f $okHead, $okTail); exit 1 }
Write-Host "WRITE_DONE - remove and reinsert the stick so Windows re-reads the new partition table."
