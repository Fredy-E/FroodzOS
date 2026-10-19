# Launch the USB formatter elevated (UAC prompt appears - approve it). 2026-10-08
$argList = @(
  '-NoProfile',
  '-ExecutionPolicy', 'Bypass',
  '-File', 'D:\CachyOS-ARM64\testing\control\format-usb.ps1',
  '-DiskNumber', '2'
)
Write-Host 'Launching elevated USB formatter. APPROVE THE UAC PROMPT on your screen.'
try {
    $p = Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $argList -Wait -PassThru
    Write-Host ("Elevated formatter exit code: {0}" -f $p.ExitCode)
} catch {
    Write-Host ("Elevation failed or cancelled: {0}" -f $_.Exception.Message)
    exit 1
}
Write-Host 'LAUNCHER_DONE'
