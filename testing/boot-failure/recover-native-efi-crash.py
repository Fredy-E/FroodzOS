"""Recover Linux EFI pstore records without writing firmware or USB.
Enumerate names only, then read values ONLY in the Linux crash GUID namespace.
"""
import ctypes as c
from ctypes import wintypes as w
import datetime as dt
import hashlib
import json
from pathlib import Path
import struct
import uuid
import zlib

OUT = Path('D:/CachyOS-ARM64/testing/boot-failure')
CRASH_GUID = uuid.UUID('cfc8fc79-be2e-4ddc-97f0-9f98bfe298a0')

class LUID(c.Structure):
    _fields_ = [('LowPart', w.DWORD), ('HighPart', w.LONG)]
class LUID_AND_ATTRIBUTES(c.Structure):
    _fields_ = [('Luid', LUID), ('Attributes', w.DWORD)]
class TOKEN_PRIVILEGES(c.Structure):
    _fields_ = [('PrivilegeCount', w.DWORD), ('Privileges', LUID_AND_ATTRIBUTES * 1)]


def main():
    k = c.WinDLL('kernel32', use_last_error=True)
    a = c.WinDLL('advapi32', use_last_error=True)
    n = c.WinDLL('ntdll', use_last_error=True)
    k.GetCurrentProcess.argtypes = []
    k.GetCurrentProcess.restype = w.HANDLE
    k.CloseHandle.argtypes = [w.HANDLE]
    k.CloseHandle.restype = w.BOOL
    a.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)]
    a.OpenProcessToken.restype = w.BOOL
    a.LookupPrivilegeValueW.argtypes = [w.LPCWSTR, w.LPCWSTR, c.POINTER(LUID)]
    a.LookupPrivilegeValueW.restype = w.BOOL
    a.AdjustTokenPrivileges.argtypes = [w.HANDLE, w.BOOL, c.POINTER(TOKEN_PRIVILEGES), w.DWORD, c.POINTER(TOKEN_PRIVILEGES), c.POINTER(w.DWORD)]
    a.AdjustTokenPrivileges.restype = w.BOOL
    n.NtEnumerateSystemEnvironmentValuesEx.argtypes = [w.ULONG, c.c_void_p, c.POINTER(w.ULONG)]
    n.NtEnumerateSystemEnvironmentValuesEx.restype = w.LONG
    k.GetFirmwareEnvironmentVariableExW.argtypes = [w.LPCWSTR, w.LPCWSTR, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)]
    k.GetFirmwareEnvironmentVariableExW.restype = w.DWORD
    result = {'time_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'firmware_modified': False, 'usb_modified': False,
              'value_read_scope': 'Linux EFI crash namespace only; no boot/security/credential variable values read',
              'crash_guid': str(CRASH_GUID), 'records': []}
    token = w.HANDLE()
    previous = TOKEN_PRIVILEGES()
    previous_size = w.DWORD(c.sizeof(previous))
    adjusted = False
    try:
        if not a.OpenProcessToken(k.GetCurrentProcess(), 0x20 | 0x8, c.byref(token)):
            raise c.WinError(c.get_last_error())
        requested = TOKEN_PRIVILEGES()
        requested.PrivilegeCount = 1
        if not a.LookupPrivilegeValueW(None, 'SeSystemEnvironmentPrivilege', c.byref(requested.Privileges[0].Luid)):
            raise c.WinError(c.get_last_error())
        requested.Privileges[0].Attributes = 2
        c.set_last_error(0)
        ok = a.AdjustTokenPrivileges(token, False, c.byref(requested), c.sizeof(previous), c.byref(previous), c.byref(previous_size))
        err = c.get_last_error()
        if not ok or err == 1300:
            raise c.WinError(err)
        adjusted = True
        length = w.ULONG(0)
        status = n.NtEnumerateSystemEnvironmentValuesEx(1, None, c.byref(length)) & 0xffffffff
        if status != 0xC0000023 or not 0 < length.value <= 4 * 1024 * 1024:
            raise RuntimeError(f'Name enumeration sizing failed: NTSTATUS 0x{status:08x}; bytes {length.value}')
        buf = c.create_string_buffer(length.value)
        status = n.NtEnumerateSystemEnvironmentValuesEx(1, buf, c.byref(length)) & 0xffffffff
        if status != 0:
            raise RuntimeError(f'Name enumeration failed: NTSTATUS 0x{status:08x}')
        data = buf.raw[:length.value]
        off, count = 0, 0
        crash_names = []
        while off < len(data):
            if off + 22 > len(data):
                raise RuntimeError('Truncated VARIABLE_NAME record')
            step = struct.unpack_from('<I', data, off)[0]
            end = off + step if step else len(data)
            if end > len(data) or end < off + 22:
                raise RuntimeError('Invalid VARIABLE_NAME record boundary')
            guid = uuid.UUID(bytes_le=data[off+4:off+20])
            raw_name = data[off+20:end]
            name = raw_name[:len(raw_name)//2*2].decode('utf-16-le').split('\0', 1)[0]
            count += 1
            if guid == CRASH_GUID and name.startswith('dump-type'):
                crash_names.append(name)
            if not step:
                break
            off = end
        result['enumerated_name_count'] = count
        result['crash_variable_count'] = len(crash_names)
        for index, name in enumerate(crash_names):
            buffer = c.create_string_buffer(1024 * 1024)
            attributes = w.DWORD()
            size = k.GetFirmwareEnvironmentVariableExW(name, '{' + str(CRASH_GUID) + '}', buffer, len(buffer), c.byref(attributes))
            if size == 0:
                result['records'].append({'name': name, 'read_error': c.get_last_error()})
                continue
            payload = buffer.raw[:size]
            dest = OUT / f'native-efi-crash-{index:03d}.bin'
            dest.write_bytes(payload)
            entry = {'name': name, 'bytes': size, 'attributes': attributes.value,
                     'local_path': str(dest), 'sha256': hashlib.sha256(payload).hexdigest()}
            # Preserve exact payload; decode plain text or the kernel's zlib format.
            if name.endswith('-C'):
                try:
                    decoded = zlib.decompress(payload)
                except zlib.error as exc:
                    entry['decode_error'] = str(exc)
                    decoded = None
            else:
                decoded = payload
            if decoded is not None:
                text_path = dest.with_suffix('.txt')
                text_path.write_text(decoded.decode('utf-8', errors='replace'), encoding='utf-8')
                entry['text_path'] = str(text_path)
            result['records'].append(entry)
        result['status'] = 'records_found' if crash_names else 'no_linux_efi_crash_records'
    except (OSError, RuntimeError, ValueError) as exc:
        result['status'] = 'read_blocked_or_failed'
        result['error'] = str(exc)
    finally:
        if token:
            if adjusted:
                a.AdjustTokenPrivileges(token, False, c.byref(previous), 0, None, None)
            k.CloseHandle(token)
    (OUT / 'native-efi-crash-recovery.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return int(result['status'] == 'read_blocked_or_failed')

if __name__ == '__main__':
    raise SystemExit(main())
