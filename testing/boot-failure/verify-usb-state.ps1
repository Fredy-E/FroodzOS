$ErrorActionPreference = 'Stop'
$expected = @{
    'EFI/Linux/kestrel-live.efi' = 'ed8b5c93642f3931af62c13916e7cebb0991b0a577b9470ab59be90646d9f696'
    'EFI/Linux/kestrel-live-log.efi' = 'b92eeb3d49ca7a0fbc3f95c4ba774155a5ee2e69e861834ecbcaca69932566d2'
    'boot/grub/grub.cfg' = 'f80192128b852283d6461302b5f3aa7308af4e1f57a615ea809d5b05519f2411'
    'boot/slim3-x126100.dtb' = '986d7d837a5c4f00c220b02b9ba294b705887b74aa39a72331357e0da0aea111'
    'EFI/boot/bootaa64.efi' = 'cfc15dd8e3794369215790c3e8438a0a5fc16d9aa7c7dcba8cccafd6dac054ab'
}
foreach ($k in $expected.Keys) {
    $p = Join-Path 'E:\' ($k.Replace('/', '\'))
    $h = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($h -ne $expected[$k]) { throw "MISMATCH $k" }
    Write-Host "OK $k"
}
Write-Host 'USB_STATE_VERIFIED'
