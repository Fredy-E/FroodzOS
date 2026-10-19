[CmdletBinding()]
param(
    [string]$InputFile,
    [string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
# Read-only: no SetFirmwareEnvironmentVariable declaration or deletion path.
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $PSScriptRoot ('firmware-recovery-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
}
$code = @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
public static class KestrelCheckpointReader {
    [StructLayout(LayoutKind.Sequential)] public struct Luid { public UInt32 Low; public Int32 High; }
    [StructLayout(LayoutKind.Sequential)] public struct TokenPrivileges { public UInt32 Count; public Luid Id; public UInt32 Attributes; }
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool CloseHandle(IntPtr handle);
    [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr process,UInt32 access,out IntPtr token);
    [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool LookupPrivilegeValue(string system,string name,out Luid value);
    [DllImport("advapi32.dll",SetLastError=true)] static extern bool AdjustTokenPrivileges(IntPtr token,bool disable,ref TokenPrivileges value,UInt32 size,out TokenPrivileges previous,out UInt32 needed);
    [DllImport("kernel32.dll",EntryPoint="GetFirmwareEnvironmentVariableW",CharSet=CharSet.Unicode,SetLastError=true)]
    static extern UInt32 ReadVar(string name,string guid,byte[] data,UInt32 length);
    public sealed class PrivilegeScope : IDisposable {
        IntPtr token; TokenPrivileges old; bool active;
        public PrivilegeScope() {
            if(!OpenProcessToken(GetCurrentProcess(),0x28,out token)) throw new Win32Exception(Marshal.GetLastWin32Error());
            try {
                Luid id; if(!LookupPrivilegeValue(null,"SeSystemEnvironmentPrivilege",out id)) throw new Win32Exception(Marshal.GetLastWin32Error());
                var next=new TokenPrivileges{Count=1,Id=id,Attributes=2}; UInt32 need;
                bool ok=AdjustTokenPrivileges(token,false,ref next,(UInt32)Marshal.SizeOf(typeof(TokenPrivileges)),out old,out need);
                int error=Marshal.GetLastWin32Error();
                if(!ok || error!=0) throw new Win32Exception(error,"Firmware-read privilege unavailable. Run elevated; no firmware was changed.");
                active=true;
            } catch { CloseHandle(token);token=IntPtr.Zero;throw; }
        }
        public void Dispose() {
            if(token==IntPtr.Zero)return;
            if(active) { TokenPrivileges unused; UInt32 need; AdjustTokenPrivileges(token,false,ref old,(UInt32)Marshal.SizeOf(typeof(TokenPrivileges)),out unused,out need); }
            CloseHandle(token);token=IntPtr.Zero;
        }
    }
    public static byte[] Read(string name,string guid,out int error) {
        var data=new byte[65536]; UInt32 n=ReadVar(name,guid,data,(UInt32)data.Length);
        error=n==0?Marshal.GetLastWin32Error():0;
        if(n==0)return null;
        Array.Resize(ref data,(int)n);return data;
    }
    static UInt32 Crc(byte[] b) {
        UInt32 crc=0xffffffffU;
        foreach(byte v in b) { crc^=v;for(int k=0;k<8;k++)crc=(crc>>1)^((crc&1)!=0?0xedb88320U:0U); }
        return ~crc;
    }
    public static string Decode(byte[] data) {
        if(data.Length<80 || data.Length>1024 || Encoding.ASCII.GetString(data,0,8)!="KSTRLOG1")throw new FormatException("Bad header/size");
        if(BitConverter.ToUInt32(data,8)!=1 || BitConverter.ToUInt32(data,12)>3 || BitConverter.ToUInt32(data,16)!=data.Length-80)throw new FormatException("Bad version/slot/length");
        UInt32 crc=BitConverter.ToUInt32(data,20);var copy=(byte[])data.Clone();Array.Clear(copy,20,4);
        if(Crc(copy)!=crc)throw new FormatException("CRC mismatch");
        string boot=Encoding.ASCII.GetString(data,32,36);Guid parsed;
        if(!Guid.TryParseExact(boot,"D",out parsed))throw new FormatException("Bad boot ID");
        return "boot="+boot+" slot="+BitConverter.ToUInt32(data,12)+" uptime_ms="+BitConverter.ToUInt64(data,24)+" reason="+Encoding.ASCII.GetString(data,68,12).TrimEnd('\0')+"\r\n"+Encoding.UTF8.GetString(data,80,data.Length-80);
    }
}
'@
Add-Type -TypeDefinition $code
New-Item -ItemType Directory -Path $OutputDirectory -ErrorAction Stop | Out-Null
$records = @()
$invalid = $false
function Save-Record([string]$Name, [byte[]]$Bytes, [bool]$Legacy) {
    $raw = Join-Path $OutputDirectory ($Name + '.bin')
    [IO.File]::WriteAllBytes($raw, $Bytes)
    $readback = [IO.File]::ReadAllBytes($raw)
    if ([Convert]::ToBase64String($readback) -cne [Convert]::ToBase64String($Bytes)) { throw 'Export read-back mismatch' }
    $valid = $true
    try {
        $text = if ($Legacy) { 'LEGACY UNCHECKSUMMED RECORD' + "`r`n" + [Text.Encoding]::UTF8.GetString($Bytes) } else { [KestrelCheckpointReader]::Decode($Bytes) }
    } catch { $valid = $false; $text = 'INVALID RECORD: ' + $_.Exception.Message }
    [IO.File]::WriteAllText((Join-Path $OutputDirectory ($Name + '.txt')), $text)
    return [ordered]@{ name=$Name; status=if($valid){'Saved'}else{'Invalid'}; bytes=$Bytes.Length; sha256=(Get-FileHash -LiteralPath $raw -Algorithm SHA256).Hash.ToLowerInvariant(); text=$text }
}
if ($InputFile) {
    $r = Save-Record 'fixture' ([IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $InputFile).Path)) $false
    $records += $r; $invalid = $r.status -eq 'Invalid'
} else {
    $privilege = New-Object KestrelCheckpointReader+PrivilegeScope
    try {
        $targets = @()
        0..3 | ForEach-Object { $targets += [pscustomobject]@{ Name=('KestrelBoot{0:D2}' -f $_); Guid='{674b8af1-da8e-4c2b-a84c-467e2d36c97c}'; Legacy=$false } }
        @('KestrelSeq','KestrelLog0','KestrelLog1','KestrelLog2','KestrelLog3') | ForEach-Object { $targets += [pscustomobject]@{ Name=$_; Guid='{8be4df61-93ca-11d2-aa0d-00e098032b2c}'; Legacy=$true } }
        foreach ($target in $targets) {
            $errorCode = 0
            $bytes = [KestrelCheckpointReader]::Read($target.Name, $target.Guid, [ref]$errorCode)
            if ($null -eq $bytes) {
                $status = if ($errorCode -eq 203) {'Missing'} elseif ($errorCode -eq 1314 -or $errorCode -eq 5) {'Denied'} elseif ($errorCode -eq 1) {'Unsupported'} else {'ReadError'}
                $records += [ordered]@{ name=$target.Name; status=$status; error=$errorCode }
                if ($status -ne 'Missing') { $invalid = $true }
            } else {
                $r = Save-Record $target.Name $bytes $target.Legacy
                $records += $r
                if ($r.status -eq 'Invalid') { $invalid = $true }
            }
        }
    } finally { $privilege.Dispose() }
}
$bootIds = @($records | Where-Object { $_.status -eq 'Saved' -and $_.name -match '^KestrelBoot0[0-3]$' } | ForEach-Object { if ($_.text -match '^boot=([0-9a-f-]{36}) ') { $Matches[1] } } | Select-Object -Unique)
$unchanged = $null
$previous = $null
if (-not $InputFile) {
    $previous = Get-ChildItem -LiteralPath $PSScriptRoot -Directory -Filter 'firmware-recovery-*' | Where-Object { $_.FullName -ne [IO.Path]::GetFullPath($OutputDirectory) -and (Test-Path -LiteralPath (Join-Path $_.FullName 'report.json')) } | Sort-Object Name -Descending | Select-Object -First 1
    if ($previous) {
        $prior = Get-Content -LiteralPath (Join-Path $previous.FullName 'report.json') -Raw | ConvertFrom-Json
        $unchanged = $true
        foreach ($r in $records) {
            $old = @($prior.records | Where-Object { $_.name -eq $r.name })
            if ($old.Count -ne 1 -or $old[0].status -ne $r.status -or $old[0].sha256 -ne $r.sha256) { $unchanged = $false }
        }
    }
}
$report = [ordered]@{ read_only=$true; firmware_writes=0; input_is_fixture=[bool]$InputFile; boot_ids=$bootIds; unchanged_from_previous_export=$unchanged; all_checkpoint_slots_present=(@($records | Where-Object { $_.name -match '^KestrelBoot0[0-3]$' -and $_.status -eq 'Saved' }).Count -eq 4); records=$records; valid=(-not $invalid) }
$json = $report | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText((Join-Path $OutputDirectory 'report.json'), $json)
Write-Output $json
Write-Output ('RECOVERY_SAVED ' + $OutputDirectory)
if ($invalid) { exit 2 } else { exit 0 }
