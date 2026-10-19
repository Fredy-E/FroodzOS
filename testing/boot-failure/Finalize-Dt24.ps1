$ErrorActionPreference = 'Stop'
$test = 'D:\CachyOS-ARM64\testing\boot-failure'
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
Start-Transcript -LiteralPath (Join-Path $test ('dt24-finalize-' + $stamp + '.log')) | Out-Null
try {
# All guest builds and tests must already have finished successfully.
& python (Join-Path $test 'prepare-dt24-update.py')
if ($LASTEXITCODE -ne 0) { throw 'Manifest/test gate preparation failed.' }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $test 'Update-Dt24Usb.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Physical USB dry-run failed; nothing written.' }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $test 'Update-Dt24Usb.ps1') -Apply
if ($LASTEXITCODE -ne 0) { throw 'USB writer failed; inspect retained backup and temporary files.' }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $test 'Verify-Dt24Usb.ps1') -RequireRearmed
if ($LASTEXITCODE -ne 0) { throw 'Independent media/firmware readback failed; not ready for boot.' }
Write-Output 'DT24_USB_READY_FOR_OWNER_NATIVE_BOOT'
} finally {
    Stop-Transcript | Out-Null
}
exit 0
