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
Source: "install_runtime.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{localappdata}\FolderConformer\runtime\venv\Scripts\pythonw.exe"; Parameters: "-I -m folderconformer"; WorkingDir: "{app}"; IconFilename: "{app}\source\folderconformer\FolderConformer.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{localappdata}\FolderConformer\runtime\venv\Scripts\pythonw.exe"; Parameters: "-I -m folderconformer"; WorkingDir: "{app}"; IconFilename: "{app}\source\folderconformer\FolderConformer.ico"; Tasks: desktopicon

[UninstallDelete]
Type: filesandordirs; Name: "{app}\source"
Type: filesandordirs; Name: "{localappdata}\FolderConformer\runtime"
Type: filesandordirs; Name: "{localappdata}\FolderConformer\Cache"

[Code]
var
  RuntimeExitCode: Integer;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    WizardForm.StatusLabel.Caption := 'Downloading Python and installing FolderConformer dependencies...';
    ExecAndLogOutput(ExpandConstant('{app}\tools\uv.exe'),
      'run --isolated --no-project --python 3.12.10 --managed-python --with platformdirs==4.13.5 "' +
      ExpandConstant('{app}\install_runtime.py') + '" "' + ExpandConstant('{app}\source') +
      '" "' + ExpandConstant('{app}\tools\uv.exe') + '"',
      ExpandConstant('{app}'), SW_SHOWNORMAL, ewWaitUntilTerminated, RuntimeExitCode, nil);
  end;
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := RuntimeExitCode;
end;
