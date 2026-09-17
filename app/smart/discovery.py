"""Local storage inventory. Discovery is never permission to mutate unknown data."""
import ctypes
import os
from pathlib import Path
import uuid
from app.safety.policy import linked, under

KNOWN = {'Desktop':'B4BFCC3A-DB2C-424C-B029-7FE99A87C641',
         'Downloads':'374DE290-123F-4565-9164-39C4925E467B',
         'Documents':'FDD39AD0-238F-46AF-ADB4-6C85480369C7',
         'Pictures':'33E28130-4E1E-4676-835A-98395C3BC3BB',
         'Videos':'18989B1D-99B5-455B-841C-AB7C74E4DDFC',
         'Music':'4BD8D571-6D19-48D3-BE97-422220080E43'}
PERSONAL = {'.pdf','.doc','.docx','.txt','.md','.rtf','.ppt','.pptx','.xls','.xlsx','.csv',
            '.png','.jpg','.jpeg','.heic','.webp','.gif','.mp4','.mov','.mkv','.avi',
            '.mp3','.wav','.flac','.m4a','.zip','.rar','.7z','.tar','.gz','.msi','.iso'}


def known_folders():
    result=[]
    for name,guid in KNOWN.items():
        p=Path.home()/name
        if os.name=='nt':
            raw=(ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID(guid).bytes_le)
            value=ctypes.c_void_p()
            shell=ctypes.WinDLL('shell32');fn=shell.SHGetKnownFolderPath
            fn.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
            fn.restype=ctypes.c_long
            if fn(ctypes.byref(raw),0,None,ctypes.byref(value))==0:
                try:p=Path(ctypes.wstring_at(value))
                finally:
                    free=ctypes.WinDLL('ole32').CoTaskMemFree;free.argtypes=[ctypes.c_void_p];free(value)
        if p.is_dir():result.append((name,p))
    for variable in ('OneDrive','OneDriveConsumer','OneDriveCommercial'):
        if os.environ.get(variable):
            p=Path(os.environ[variable])
            if p.is_dir():result.append(('OneDrive',p))
    return result


def drives():
    if os.name!='nt':return []
    kernel=ctypes.WinDLL('kernel32');mask=kernel.GetLogicalDrives()
    kind=kernel.GetDriveTypeW;kind.argtypes=[ctypes.c_wchar_p];kind.restype=ctypes.c_uint
    return [dict(path=f'{chr(65+n)}:\\',external=kind(f'{chr(65+n)}:\\')==2,type=kind(f'{chr(65+n)}:\\'))
            for n in range(26) if mask&(1<<n)]


def area_risk(path,policy):
    p=Path(path)
    if policy.directory_veto(p):return 'PROTECTED'
    if policy.project_root(p/'probe.pdf'):return 'PROJECT'
    if policy.veto(p/'probe.pdf'):return 'APPLICATION'
    return ''


def discover(policy,settings,profile=None,known=None,volumes=None):
    profile=Path(profile or Path.home());inventory=[];roots=[];seen=set()
    def add(name,path,kind,origin='additional'):
        p=Path(path);key=str(p.absolute()).casefold()
        if str(p).startswith('\\\\'):
            inventory.append(dict(name=name,path=str(p),kind='PROTECTED',eligible=False));return
        if key in seen or not p.is_dir():return
        seen.add(key)
        risk=area_risk(p,policy)
        if any(under(p,v) for v in settings['excluded_drives']):risk='PROTECTED'
        if under(p,settings['library']):risk='PROTECTED'
        inventory.append(dict(name=name,path=str(p),kind=risk or kind,origin=origin,eligible=not risk and kind in {'USER_DATA','DATA_DRIVE'}))
        if not risk and kind in {'USER_DATA','DATA_DRIVE'}:roots.append(str(p))
    for name,p in (known if known is not None else known_folders()):add(name,p,'USER_DATA','known')
    try:
        for p in profile.iterdir():
            if not p.is_dir() or p.name.startswith('.'):continue
            # Additional user folders need personal-file evidence, not just location.
            kind='UNKNOWN_RISK'
            try:
                sample=[c for c in p.iterdir() if c.is_file()][:200]
                if sample and all(c.suffix.lower() in PERSONAL for c in sample):kind='USER_DATA'
            except OSError:pass
            add(p.name,p,kind)
    except OSError:pass
    system=os.environ.get('SystemDrive','C:').casefold()
    for volume in (volumes if volumes is not None else drives()):
        root=Path(volume['path'])
        excluded=volume['path'].casefold() in {v.casefold() for v in settings['excluded_drives']}
        allowed=volume['type'] in {2,3} and not excluded and (not volume['external'] or settings['external_drives'])
        inventory.append(dict(name=volume['path'],path=volume['path'],kind='SYSTEM' if root.drive.casefold()==system else 'DATA_DRIVE' if allowed else 'PROTECTED',eligible=False,external=volume['external'],drive=True))
        if not allowed:continue
        if root.drive.casefold()!=system:
            add(volume['path'],root,'DATA_DRIVE','drive')
            continue
        try:
            for p in root.iterdir():
                if not p.is_dir() or p.name.startswith(('.', '$')) or p.name.lower()=='users':continue
                if root.drive.casefold()==system:
                    # Other system-drive roots are inventoried only; known folders cover user data.
                    add(p.name,p,'UNKNOWN_RISK')
                else:add(p.name,p,'DATA_DRIVE')
        except OSError:pass
    # Retain parents once; they include any known redirected child.
    roots=[p for p in roots if not any(p!=q and under(p,q) for q in roots)]
    return inventory,roots
