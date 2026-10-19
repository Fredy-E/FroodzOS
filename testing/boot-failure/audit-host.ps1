$ErrorActionPreference = 'Stop'
'== Firmware and model (read-only) =='
Get-CimInstance Win32_ComputerSystem -OperationTimeoutSec 15 | Select-Object Manufacturer,Model,SystemSKUNumber | Format-List
Get-CimInstance Win32_BIOS -OperationTimeoutSec 15 | Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate | Format-List
'== USB media (read-only) =='
$usb = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object InterfaceType -eq 'USB')
$usb | Select-Object DeviceID,Model,Size,InterfaceType | Format-Table -AutoSize
foreach ($disk in $usb) {
    $parts = @(Get-CimAssociatedInstance -InputObject $disk -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)
    $parts | Select-Object DeviceID,Type,Size,BootPartition,StartingOffset | Format-Table -AutoSize
    foreach ($part in $parts) {
        $vols = @(Get-CimAssociatedInstance -InputObject $part -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15)
        foreach ($vol in $vols) {
            $vol | Select-Object DeviceID,VolumeName,FileSystem,Size,FreeSpace | Format-List
            if ($vol.VolumeName -eq 'KESTREL_A64') {
                foreach ($rel in @('EFI\BOOT\BOOTAA64.EFI','arch\aarch64\airootfs.sfs')) {
                    $file = Join-Path ($vol.DeviceID + '\') $rel
                    if (Test-Path -LiteralPath $file) {
                        Get-Item -LiteralPath $file | Select-Object FullName,Length
                        Get-FileHash -Algorithm SHA256 -LiteralPath $file | Select-Object Path,Hash
                    } else { 'MISSING ' + $file }
                }
            }
        }
    }
}
'== ISO tools =='
Get-Command 7z.exe,7za.exe -ErrorAction SilentlyContinue | Select-Object Name,Source
