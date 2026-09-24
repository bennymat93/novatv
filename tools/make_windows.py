"""Windows installer: Kodi (portable) + the BN build pre-installed -> dist/BN-Stream-Setup-<ver>.exe
Needs Inno Setup 6 (ISCC.exe). Usage: python tools/make_windows.py --version X
"""
import argparse
import os
import re
import shutil
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KODI = os.path.join(ROOT, 'testkodi')
STAGE = os.path.join(ROOT, 'work', 'winstage')
ISCC = [os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Inno Setup 6', 'ISCC.exe'),
        r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe']
SKIP = {'portable_data', 'kodi.log', 'kodi.old.log'}

ISS = r'''
#define Ver "{ver}"
[Setup]
AppId={{{{B7E5C1A2-6F3D-4B8E-9C11-BN5TREAM0001}}
AppName=BN Stream
AppVersion={{#Ver}}
AppPublisher=BN
DefaultDirName={{localappdata}}\BN Stream
DefaultGroupName=BN Stream
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir={dist}
OutputBaseFilename=BN-Stream-Setup-{{#Ver}}
SetupIconFile={icon}
UninstallDisplayIcon={{app}}\bn.ico
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
ShowLanguageDialog=auto

[Languages]
Name: "he"; MessagesFile: "compiler:Languages\Hebrew.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"

[InstallDelete]
; program files are replaced on upgrade; personal data (portable_data\userdata) is kept
Type: filesandordirs; Name: "{{app}}\addons"
Type: filesandordirs; Name: "{{app}}\portable_data\addons"

[Files]
Source: "{stage}\kodi\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{stage}\data\addons\*"; DestDir: "{{app}}\portable_data\addons"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{stage}\data\*"; Excludes: "\addons\*"; DestDir: "{{app}}\portable_data"; Flags: onlyifdoesntexist recursesubdirs createallsubdirs
Source: "{icon}"; DestDir: "{{app}}"; DestName: "bn.ico"

[Icons]
Name: "{{group}}\BN Stream"; Filename: "{{app}}\kodi.exe"; Parameters: "-p"; WorkingDir: "{{app}}"; IconFilename: "{{app}}\bn.ico"
Name: "{{group}}\{{cm:UninstallProgram,BN Stream}}"; Filename: "{{uninstallexe}}"
Name: "{{userdesktop}}\BN Stream"; Filename: "{{app}}\kodi.exe"; Parameters: "-p"; WorkingDir: "{{app}}"; IconFilename: "{{app}}\bn.ico"; Tasks: desktopicon

[Run]
Filename: "{{app}}\kodi.exe"; Parameters: "-p"; WorkingDir: "{{app}}"; Description: "{{cm:LaunchProgram,BN Stream}}"; Flags: nowait postinstall skipifsilent
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', required=True)
    v = ap.parse_args().version
    build = os.path.join(ROOT, 'dist', 'NovaTV-%s.zip' % v)
    shutil.rmtree(STAGE, ignore_errors=True)
    shutil.copytree(KODI, os.path.join(STAGE, 'kodi'), ignore=lambda d, names: [n for n in names if n in SKIP] if d == KODI else [])
    with zipfile.ZipFile(build) as z:
        z.extractall(os.path.join(STAGE, 'data'))
    iss = os.path.join(STAGE, 'bn.iss')
    open(iss, 'w', encoding='utf-8-sig').write(ISS.format(ver=v, dist=os.path.join(ROOT, 'dist'), stage=STAGE,
                                                          icon=os.path.join(ROOT, 'brand', 'bn.ico')))
    iscc = next(p for p in ISCC if os.path.exists(p))
    subprocess.check_call([iscc, '/Q', iss])
    out = os.path.join(ROOT, 'dist', 'BN-Stream-Setup-%s.exe' % v)
    print('->', out, '%.1f MB' % (os.path.getsize(out) / 1e6))


if __name__ == '__main__':
    main()
