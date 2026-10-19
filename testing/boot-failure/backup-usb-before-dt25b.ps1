$ErrorActionPreference = 'Stop'
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$d = Join-Path 'D:/CachyOS-ARM64/testing/boot-failure' ('usb-before-dt25b-' + $stamp)
New-Item -ItemType Directory -Path $d | Out-Null
Copy-Item -LiteralPath 'E:/EFI/Linux/kestrel-live.efi' -Destination (Join-Path $d 'kestrel-live-dt24.efi')
Copy-Item -LiteralPath 'E:/boot/grub/grub.cfg' -Destination (Join-Path $d 'grub.cfg')
$uki = Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $d 'kestrel-live-dt24.efi')
$cfg = Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $d 'grub.cfg')
Write-Output ('BACKUP_UKI_SHA256 ' + $uki.Hash)
Write-Output ('BACKUP_CFG_SHA256 ' + $cfg.Hash)
if ($uki.Hash -ne '4FCA331543A347DA2D431631AE002F90046507E485765EF24F383257902EDC02') { throw 'backup UKI hash mismatch' }
if ($cfg.Hash -ne '261CA61194B356DC33307CA5F76EC982B6324C561DA775D0C1614E8E6E09D4BA') { throw 'backup cfg hash mismatch' }
Write-Output ('BACKUP_DIR ' + $d)
Write-Output 'BACKUP_VERIFIED'
