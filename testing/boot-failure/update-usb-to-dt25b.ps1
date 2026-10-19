$ErrorActionPreference = 'Stop'
# File-only dt25b USB update. SFS is byte-identical, skipped by design.
$ukiSrc = 'D:/CachyOS-ARM64/testing/boot-failure/dt25b-candidate.efi'
$cfgSrc = 'D:/CachyOS-ARM64/testing/boot-failure/dt25b-grub.cfg'
$expUki = 'B535444F8A3560B602D2A8549A35389D3914A8B8B4294C7408CA8E1840A11753'
$expCfg = 'A4BEC7016A798E82F7D6F2C546B8829D072075D36E8B61F61ED88E48035740DE'
$expSfs = '5041E7D0E9C6AF0A5C754F083CA9D77197BF226854F4DB3A781B544725D94D4C'
Copy-Item -LiteralPath $ukiSrc -Destination 'E:/EFI/Linux/kestrel-live.efi' -Force
Copy-Item -LiteralPath $cfgSrc -Destination 'E:/boot/grub/grub.cfg' -Force
$uki = Get-FileHash -Algorithm SHA256 -LiteralPath 'E:/EFI/Linux/kestrel-live.efi'
$cfg = Get-FileHash -Algorithm SHA256 -LiteralPath 'E:/boot/grub/grub.cfg'
$sfs = Get-FileHash -Algorithm SHA256 -LiteralPath 'E:/arch/aarch64/airootfs.sfs'
Write-Output ('STICK_UKI_SHA256 ' + $uki.Hash)
Write-Output ('STICK_CFG_SHA256 ' + $cfg.Hash)
Write-Output ('STICK_SFS_SHA256 ' + $sfs.Hash)
if ($uki.Hash -ne $expUki) { throw 'stick UKI hash mismatch' }
if ($cfg.Hash -ne $expCfg) { throw 'stick cfg hash mismatch' }
if ($sfs.Hash -ne $expSfs) { throw 'stick SFS changed unexpectedly' }
if ((Get-Item -LiteralPath 'E:/EFI/Linux/kestrel-live.efi').Length -ne 244424704) { throw 'stick UKI size mismatch' }
Write-Output 'USB_DT25B_UPDATE_VERIFIED'
