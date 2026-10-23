#define MyAppName "FolderConformer"
#ifndef MyAppVersion
  #error MyAppVersion must be supplied by packaging/build.py
#endif

[Setup]
AppId=FolderConformer.Desktop
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename={#MyAppName}-{#MyAppVersion}-{#MyAppPlatform}-{#MyAppMachine}-Setup
SetupIconFile=..\folderconformer\FolderConformer.ico
UninstallDisplayIcon={app}\source\folderconformer\FolderConformer.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
CloseApplications=yes
SetupLogging=yes
ArchiveExtraction=full

[Files]
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}\source"; Flags: ignoreversion
Source: "https://github.com/astral-sh/uv/releases/download/0.11.11/uv-x86_64-pc-windows-msvc.zip"; DestDir: "{app}\tools"; DestName: "uv.zip"; ExternalSize: 68454400; Hash: "2f75a0db2c3530b6b3c24434dc38137f61ff1f4e5f2d7b4ddc5bcd142cf58b65"; Flags: external download extractarchive ignoreversion recursesubdirs createallsubdirs
Source: "..\folderconformer\*.py"; DestDir: "{app}\source\folderconformer"; Flags: ignoreversion
Source: "..\folderconformer\*.ico"; DestDir: "{app}\source\folderconformer"; Flags: ignoreversion
Source: "..\folderconformer\qml\*.qml"; DestDir: "{app}\source\folderconformer\qml"; Flags: ignoreversion
Source: "..\pyproject.toml"; DestDir: "{app}\source"; Flags: ignoreversion
Source: "..\uv.lock"; DestDir: "{app}\source"; Flags: ignoreversion
Source: "https://www.kaggle.com/api/v1/models/google/yamnet/tensorFlow2/yamnet/1/download"; DestDir: "{tmp}"; DestName: "yamnet.tar.gz"; ExternalSize: 14242921; Hash: "b80da2a1a56926fb0767205051a200dd7b3beaf3ea1ea126c42a53943996e5e0"; Flags: external download ignoreversion deleteafterinstall
Source: "https://download.visualstudio.microsoft.com/download/pr/ebdab8e5-1d7b-4d9f-a11b-cbb1720c3b12/843068991DAAA1F73AD9F6239BCE4D0F6A07A51F18C37EA2A867E9BECA71295C/VC_redist.x64.exe"; DestDir: "{tmp}"; DestName: "VC_redist.x64.exe"; ExternalSize: 18731856; Hash: "843068991daaa1f73ad9f6239bce4d0f6a07a51f18c37ea2a867e9beca71295c"; Flags: external download ignoreversion deleteafterinstall
Source: "install_runtime.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{localappdata}\FolderConformer\runtime\venv\Scripts\pythonw.exe"; Parameters: "-I -m folderconformer"; WorkingDir: "{app}"; IconFilename: "{app}\source\folderconformer\FolderConformer.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{localappdata}\FolderConformer\runtime\venv\Scripts\pythonw.exe"; Parameters: "-I -m folderconformer"; WorkingDir: "{app}"; IconFilename: "{app}\source\folderconformer\FolderConformer.ico"; Tasks: desktopicon

[Run]
Filename: "{tmp}\VC_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft Visual C++ runtime..."; Flags: shellexec waituntilterminated; AfterInstall: InstallRuntime
Filename: "{localappdata}\FolderConformer\runtime\venv\Scripts\pythonw.exe"; Parameters: "-I -m folderconformer"; WorkingDir: "{app}"; Description: "Launch {#MyAppName}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\source"
Type: filesandordirs; Name: "{localappdata}\FolderConformer\runtime"
Type: filesandordirs; Name: "{localappdata}\FolderConformer\Cache"

[Code]
var
  RuntimeExitCode: Integer;

procedure InstallRuntime;
begin
    WizardForm.StatusLabel.Caption := 'Downloading Python and installing FolderConformer dependencies...';
    ExecAndLogOutput(ExpandConstant('{app}\tools\uv.exe'),
      'run --isolated --no-project --python 3.12.10 --managed-python --with platformdirs==4.13.5 "' +
      ExpandConstant('{app}\install_runtime.py') + '" "' + ExpandConstant('{app}\source') +
      '" "' + ExpandConstant('{app}\tools\uv.exe') + '" "' + ExpandConstant('{tmp}\yamnet.tar.gz') + '"',
      ExpandConstant('{app}'), SW_SHOWNORMAL, ewWaitUntilTerminated, RuntimeExitCode, nil);
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := RuntimeExitCode;
end;
