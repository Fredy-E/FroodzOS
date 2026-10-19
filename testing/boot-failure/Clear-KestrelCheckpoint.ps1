[CmdletBinding()]
param(
    [switch]$Yes,
    [string]$ExpectedBootId
)
$ErrorActionPreference = 'Stop'
# Deletes ONLY the four project-owned checkpoint variables under the
# project GUID. Never touches legacy, boot, security, or vendor variables.
# Requires -Yes (explicit opt-in); always exports before deleting.
if (-not $Yes) { throw 'Refusing: pass -Yes to delete the project checkpoints.' }
$guid = '{674b8af1-da8e-4c2b-a84c-467e2d36c97c}'
$code = @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class KestrelCheckpointClear {
    [StructLayout(LayoutKind.Sequential)] public struct Luid { public UInt32 Low; public Int32 High; }
    [StructLayout(LayoutKind.Sequential)] public struct TokenPrivileges { public UInt32 Count; public Luid Id; public UInt32 Attributes; }
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool CloseHandle(IntPtr handle);
    [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr process,UInt32 access,out IntPtr token);
    [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool LookupPrivilegeValue(string system,string name,out Luid value);
    [DllImport("advapi32.dll",SetLastError=true)] static extern bool AdjustTokenPrivileges(IntPtr token,bool disable,ref TokenPrivileges value,UInt32 size,out TokenPrivileges previous,out UInt32 needed);
    [DllImport("kernel32.dll",EntryPoint="GetFirmwareEnvironmentVariableW",CharSet=CharSet.Unicode,SetLastError=true)]
    static extern UInt32 ReadVar(string name,string guid,byte[] data,UInt32 length);
    [DllImport("kernel32.dll",EntryPoint="SetFirmwareEnvironmentVariableW",CharSet=CharSet.Unicode,SetLastError=true)]
    static extern bool WriteVar(string name,string guid,byte[] data,UInt32 length);
    public sealed class PrivilegeScope : IDisposable {
        IntPtr token; TokenPrivileges old; bool active;
        public PrivilegeScope() {
            if(!OpenProcessToken(GetCurrentProcess(),0x28,out token)) throw new Win32Exception(Marshal.GetLastWin32Error());
            try {
                Luid id; if(!LookupPrivilegeValue(null,"SeSystemEnvironmentPrivilege",out id)) throw new Win32Exception(Marshal.GetLastWin32Error());
                var next=new TokenPrivileges{Count=1,Id=id,Attributes=2}; UInt32 need;
                bool ok=AdjustTokenPrivileges(token,false,ref next,(UInt32)Marshal.SizeOf(typeof(TokenPrivileges)),out old,out need);
                int error=Marshal.GetLastWin32Error();
                if(!ok || error!=0) throw new Win32Exception(error,"Firmware-write privilege unavailable; no firmware was changed.");
                active=true;
            } catch { CloseHandle(token);token=IntPtr.Zero;throw; }
        }
        public void Dispose() {
            if(token==IntPtr.Zero)return;
            if(active) {
                TokenPrivileges unused; UInt32 need;
                bool restored=AdjustTokenPrivileges(token,false,ref old,(UInt32)Marshal.SizeOf(typeof(TokenPrivileges)),out unused,out need);
                int error=Marshal.GetLastWin32Error(); CloseHandle(token); token=IntPtr.Zero;
                if(!restored || error!=0) throw new Win32Exception(error,"Privilege restore failed.");
            } else { CloseHandle(token);token=IntPtr.Zero; }
        }
    }
    public static byte[] Read(string name,string guid,out int error) {
        var data=new byte[65536]; UInt32 n=ReadVar(name,guid,data,(UInt32)data.Length);
        error=n==0?Marshal.GetLastWin32Error():0;
        if(n==0)return null;
        Array.Resize(ref data,(int)n);return data;
    }
    public static void Delete(string name,string guid) {
        if(!WriteVar(name,guid,null,0)) throw new Win32Exception(Marshal.GetLastWin32Error(),"Delete failed; variable retained.");
    }
}
'@
$parsed = [Guid]::Empty
if (-not [Guid]::TryParseExact($ExpectedBootId, 'D', [ref]$parsed)) { throw 'Pass the exact exported boot ID via -ExpectedBootId.' }
$reader = Join-Path $PSScriptRoot 'Read-KestrelCheckpoint.ps1'
$out = Join-Path $PSScriptRoot ('firmware-clear-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
# Separate process: the read-only script cannot clobber our scope or exit us.
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $reader -OutputDirectory $out
if ($LASTEXITCODE -ne 0) { throw 'Pre-delete export failed; refusing to delete.' }
$report = Get-Content -LiteralPath (Join-Path $out 'report.json') -Raw | ConvertFrom-Json
if (-not $report.valid -or $report.input_is_fixture) { throw 'Invalid or synthetic export; refusing.' }
$targets = @($report.records | Where-Object { $_.name -match '^KestrelBoot0[0-3]$' })
if ($targets.Count -ne 4) { throw 'Incomplete checkpoint export.' }
foreach ($record in $targets) {
    if ($record.status -eq 'Missing' -and $record.error -eq 203) { continue }
    if ($record.status -ne 'Saved' -or -not $record.text.StartsWith('boot=' + $ExpectedBootId + ' ')) { throw 'Record mismatch; nothing deleted.' }
    $raw = Join-Path $out ($record.name + '.bin')
    if ((Get-FileHash -LiteralPath $raw -Algorithm SHA256).Hash.ToLowerInvariant() -ne $record.sha256) { throw 'Backup mismatch; refusing.' }
}
Add-Type -TypeDefinition $code
$privilege = New-Object KestrelCheckpointClear+PrivilegeScope
$deleted = @()
try {
    # Verify ALL current bytes against backup before the first delete.
    foreach ($record in $targets) {
        $errorCode = 0
        $bytes = [KestrelCheckpointClear]::Read($record.name, $guid, [ref]$errorCode)
        if ($record.status -eq 'Missing') {
            if ($null -ne $bytes -or $errorCode -ne 203) { throw 'Firmware changed after export; refusing.' }
        } else {
            $backup = [IO.File]::ReadAllBytes((Join-Path $out ($record.name + '.bin')))
            if ($null -eq $bytes -or [Convert]::ToBase64String($backup) -cne [Convert]::ToBase64String($bytes)) { throw 'Firmware changed after export; refusing.' }
        }
    }
    foreach ($record in $targets) {
        if ($record.status -ne 'Saved') { continue }
        [KestrelCheckpointClear]::Delete($record.name, $guid)
        $deleted += $record.name
    }
    foreach ($record in $targets) {
        $errorCode = 0
        $bytes = [KestrelCheckpointClear]::Read($record.name, $guid, [ref]$errorCode)
        if ($null -ne $bytes -or $errorCode -ne 203) { throw 'Post-delete readback is not empty; stop and inspect.' }
    }
} finally { $privilege.Dispose() }
[ordered]@{ verified_empty=$true; expected_boot_id=$ExpectedBootId; deleted=$deleted; backup=$out; scope_guid=$guid } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $out 'clear-result.json') -Encoding UTF8
Write-Output ('CHECKPOINT_CLEAR_VERIFIED ' + $out)
exit 0
