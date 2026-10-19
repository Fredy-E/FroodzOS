$errs = $null
[System.Management.Automation.Language.Parser]::ParseFile('D:\CachyOS-ARM64\testing\control\write-live-stick.ps1', [ref]$null, [ref]$errs) | Out-Null
if ($errs.Count -eq 0) { 'PARSE_OK' } else { $errs | Select-Object -First 5 | ForEach-Object { 'line ' + $_.Extent.StartLineNumber + ': ' + $_.Message } }
