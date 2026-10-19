$ErrorActionPreference = 'Stop'
$kali = 'D:\Kali_WSL2_Backup_7-4-26'
$codex = 'D:\Codex-archive'
foreach ($p in @($kali, $codex)) {
  if (-not (Test-Path -LiteralPath $p)) { throw "NOT FOUND: $p (refusing to guess)" }
}
$kaliItem = Get-Item -LiteralPath $kali -Force
$codexItem = Get-Item -LiteralPath $codex -Force
Write-Host "kali: $($kaliItem.GetType().Name) linktype=$($kaliItem.LinkType)"
Write-Host "codex: $($codexItem.GetType().Name) linktype=$($codexItem.LinkType)"
if ($kaliItem.LinkType -or $codexItem.LinkType) { throw 'Link detected; refusing' }
Remove-Item -LiteralPath $kali -Recurse -Force
Remove-Item -LiteralPath $codex -Recurse -Force
Write-Host 'DELETED_BOTH'
Write-Host "D free now: $([math]::Round((Get-PSDrive D).Free / 1GB, 1)) GB"
