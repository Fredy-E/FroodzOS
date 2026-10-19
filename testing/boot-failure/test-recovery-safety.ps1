[CmdletBinding()]
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
# Parsing/compilation/refusal-path tests only. This script NEVER passes -Yes.
$root = 'D:\CachyOS-ARM64\testing\boot-failure'
foreach ($name in @('Read-KestrelCheckpoint.ps1','Clear-KestrelCheckpoint.ps1')) {
    $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $root $name), [ref]$null, [ref]$errors)
    if ($errors.Count) { throw ($errors | Out-String) }
    $assignment = $ast.FindAll({param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and $n.Left.Extent.Text -eq '$code'},$true)[0]
    $code = $assignment.Right.FindAll({param($n) $n -is [System.Management.Automation.Language.StringConstantExpressionAst]},$true)[0].Value
    Add-Type -TypeDefinition $code
    Write-Output ('PARSE_AND_CSHARP_OK ' + $name)
}
$ErrorActionPreference = 'Continue'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Clear-KestrelCheckpoint.ps1') 2>&1 | Out-String | Write-Output
if ($LASTEXITCODE -eq 0) { throw 'Clear must refuse without -Yes' }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Clear-KestrelCheckpoint.ps1') -Yes -ExpectedBootId 'not-a-guid' 2>&1 | Out-String | Write-Output
if ($LASTEXITCODE -eq 0) { throw 'Clear must refuse malformed boot ID before firmware calls' }
Write-Output 'HOST_RECOVERY_SAFETY_TESTS_PASS (no firmware calls)'
