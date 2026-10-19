$ErrorActionPreference = 'Stop'
$expected = @{
    'EFI/Linux/kestrel-live-log.efi' = '4fd7ae12d70b1b2c8e38b4b33cec1e0d21bc34ec8239d7364547f5cf37517a9f'
    'boot/grub/grub.cfg' = 'f58a763aed178e59aa203aafc083cda5000bdb0e2dbd4c2e40e4d8d6b1a93831'
    'KESTREL-LOG-TARGET' = 'cb46268b17146213a1cf517322f02c5d5b2c2e3491daea692c4fc4a18a353913'
    'EFI/Linux/kestrel-live.efi' = '948589b827ac23f64551ace06b877853f92a536a845fc04b63baa16b77d4625e'
    'EFI/boot/bootaa64.efi' = 'cfc15dd8e3794369215790c3e8438a0a5fc16d9aa7c7dcba8cccafd6dac054ab'
}
foreach ($k in $expected.Keys) {
    $p = Join-Path 'E:\' ($k.Replace('/', '\'))
    $h = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($h -ne $expected[$k]) { throw "MISMATCH $k" }
    Write-Host "OK $k"
}
if (-not (Test-Path -LiteralPath 'E:\Logs' -PathType Container)) { throw 'Logs dir missing' }
Write-Host 'OK Logs/'
Write-Host 'INDEPENDENT_DELTA_VERIFIED'
