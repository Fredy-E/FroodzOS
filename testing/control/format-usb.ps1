param(
  [Parameter(Mandatory=$true)][int]$DiskNumber
)
# Clean format of the USB stick back to a single full-size exFAT volume (2026-10-08).
# Refuses non-USB disks. The control-test media remains reproducible from the ISO on D:.
$ErrorActionPreference = 'Stop'
Start-Transcript -Path 'D:\CachyOS-ARM64\testing\control\format-usb.log' -Force | Out-Null

$disk = Get-Disk -Number $DiskNumber
Write-Host ("Target: Disk {0} '{1}' BusType={2} Size={3}" -f $DiskNumber, $disk.FriendlyName, $disk.BusType, $disk.Size)
if ($disk.BusType -ne 'USB') { throw "REFUSED: disk is not USB" }
if ($disk.Size -lt 50GB -or $disk.Size -gt 70GB) { throw "REFUSED: unexpected disk size" }
if ($disk.FriendlyName -notmatch 'Kingston') { throw "REFUSED: unexpected disk model" }

@"
select disk $DiskNumber
clean
convert mbr
create partition primary
format fs=exfat label=KINGSTON quick
assign
"@ | Set-Content -Path 'D:\CachyOS-ARM64\testing\control\usb-format.txt' -Encoding ASCII
& diskpart.exe /s 'D:\CachyOS-ARM64\testing\control\usb-format.txt'
Start-Sleep -Seconds 3
Get-Disk -Number $DiskNumber | Format-Table Number,PartitionStyle,OperationalStatus,Size -AutoSize | Out-String | Write-Host
Get-Volume -FileSystemLabel 'KINGSTON' -ErrorAction SilentlyContinue | Format-Table DriveLetter,FileSystem,Size -AutoSize | Out-String | Write-Host
Write-Host "FORMAT_DONE"
Stop-Transcript | Out-Null
