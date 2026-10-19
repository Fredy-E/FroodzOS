$ErrorActionPreference = 'SilentlyContinue'
$out = @()
$out += '--- D: top level ---'
$out += Get-ChildItem 'D:\' -Directory -ErrorAction SilentlyContinue | ForEach-Object {
  $s = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
  "$($_.Name): $([math]::Round($s / 1GB, 1)) GB"
}
$out += '--- project big ---'
$out += Get-ChildItem 'D:\CachyOS-ARM64' -Directory -ErrorAction SilentlyContinue | ForEach-Object {
  $s = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
  "$($_.Name): $([math]::Round($s / 1GB, 1)) GB"
}
$out | Set-Content -LiteralPath 'D:\CachyOS-ARM64\testing\boot-failure\disk-usage.txt' -Encoding ASCII
