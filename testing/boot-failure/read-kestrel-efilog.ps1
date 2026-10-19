[CmdletBinding()]
param([switch]$Delete)
$ErrorActionPreference = 'Stop'
if ($Delete) { throw 'Deletion is disabled. Export with Read-KestrelCheckpoint.ps1 first; clearing requires separate approval.' }
$reader = Join-Path $PSScriptRoot 'Read-KestrelCheckpoint.ps1'
& $reader
exit $LASTEXITCODE
