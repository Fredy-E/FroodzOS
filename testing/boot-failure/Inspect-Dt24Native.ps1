$ErrorActionPreference = 'Stop'
$test = 'D:\CachyOS-ARM64\testing\boot-failure'
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object { $_.InterfaceType -eq 'USB' -and $_.Model -like '*Kingston*DataTraveler*' -and [uint64]$_.Size -ge 50000000000 -and [uint64]$_.Size -le 70000000000 })
if ($disks.Count -ne 1) { throw 'Need exactly one matching Kingston USB.' }
$volumes = @()
foreach ($part in @(Get-CimAssociatedInstance -InputObject $disks[0] -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) {
    $volumes += @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15 | Where-Object { $_.VolumeName -eq 'KESTREL_A64' -and $_.FileSystem -eq 'FAT32' })
}
if ($volumes.Count -ne 1) { throw 'USB volume association mismatch.' }
$usb = $volumes[0].DeviceID + '\'
if ((Get-Content -LiteralPath (Join-Path $usb 'KESTREL-LOG-TARGET') -Raw).Trim() -ne 'KESTREL_A64_USB_CAPTURE_V1') { throw 'USB marker mismatch.' }
$rows = @()
foreach ($dir in @(Get-ChildItem -LiteralPath (Join-Path $usb 'Logs') -Directory)) {
    if ($dir.Name -notmatch '^boot-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$') { continue }
    $files = @(Get-ChildItem -LiteralPath $dir.FullName -File | ForEach-Object {
        [ordered]@{name=$_.Name; bytes=$_.Length; modified_utc=$_.LastWriteTimeUtc.ToString('o')}
    })
    $rows += [ordered]@{boot_dir=$dir.Name; path=$dir.FullName; files=$files}
}
$out = Join-Path $test ('native-dt24-discovery-' + $stamp + '.json')
$r = [ordered]@{read_only=$true; time_utc=$stamp; disk=$disks[0].DeviceID; model=$disks[0].Model; volume=$usb; boots=$rows}
$json = $r | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText($out,$json)
Write-Output $json
$fw = Join-Path $test ('firmware-recovery-' + $stamp)
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $test 'Read-KestrelCheckpoint.ps1') -OutputDirectory $fw
if ($LASTEXITCODE -ne 0) { throw 'Read-only firmware export failed.' }
Write-Output ('DISCOVERY=' + $out)
Write-Output ('FIRMWARE=' + $fw)
exit 0
