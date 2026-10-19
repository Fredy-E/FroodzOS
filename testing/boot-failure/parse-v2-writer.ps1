$ErrorActionPreference = 'Stop'
$paths = @(
    'D:\CachyOS-ARM64\testing\boot-failure\update-live-stick-v2.ps1'
)
foreach ($path in $paths) {
    $errs = $null
    $tokens = $null
    [System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errs) | Out-Null
    if ($errs.Count -gt 0) {
        foreach ($err in $errs) { Write-Host ("{0}:{1}: {2}" -f $path,$err.Extent.StartLineNumber,$err.Message) }
        throw 'PowerShell parse failed.'
    }
    Write-Host ("PARSE_OK {0}" -f $path)
}
