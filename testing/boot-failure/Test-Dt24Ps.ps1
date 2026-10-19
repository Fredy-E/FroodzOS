$ErrorActionPreference = 'Stop'
$root = 'D:\CachyOS-ARM64\testing\boot-failure'
foreach ($name in @('Update-Dt24Usb.ps1','Verify-Dt24Usb.ps1','Finalize-Dt24.ps1','Rollback-Dt24Usb.ps1')) {
    $errors = $null
    $tokens = $null
    [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $root $name), [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors.Count -ne 0) { throw ($errors | Out-String) }
    Write-Output ('PARSE_OK ' + $name)
}
exit 0
