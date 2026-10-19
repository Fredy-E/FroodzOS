# Launch the USB writer elevated (UAC prompt appears - approve it). 2026-10-08
$argList = @(
  '-NoProfile',
  '-ExecutionPolicy', 'Bypass',
  '-File', 'D:\CachyOS-ARM64\testing\control\write-usb2.ps1',
  '-DiskNumber', '2',
  '-IsoPath', 'D:\CachyOS-ARM64\testing\control\stonking-desktop-arm64+x1e.iso'
)
Write-Host 'Launching elevated USB writer. APPROVE THE UAC PROMPT on your screen.'
try {
    $p = Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $argList -Wait -PassThru
    Write-Host ("Elevated writer exit code: {0}" -f $p.ExitCode)
} catch {
    Write-Host ("Elevation failed or cancelled: {0}" -f $_.Exception.Message)
    exit 1
}
Write-Host 'LAUNCHER_DONE'
