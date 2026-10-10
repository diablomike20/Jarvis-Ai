; JARVIS AI - complete Windows desktop installation from genuine PyInstaller output.
; Installer never copies private voice reference, account data or model weights.
#define AppName "JARVIS AI"
#define AppVersion "2026.10.10"
#define MainExe "BrahmaEvo.exe"

[Setup]
AppId={{79A94B3A-15A7-45EE-A648-7602715226D7}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} - {#AppVersion}
AppPublisher=JARVIS AI Project
DefaultDirName={localappdata}\Programs\JARVIS AI
DefaultGroupName=JARVIS AI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=JARVIS_AI_Setup_Windows_x64
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
UninstallDisplayIcon={app}\{#MainExe}
ChangesEnvironment=no
CloseApplications=yes
RestartApplications=no

[Files]
Source: "..\dist\BrahmaEvo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Asztali JARVIS AI parancsikon"; GroupDescription: "További lehetőségek"; Flags: checkedonce

[Icons]
Name: "{autoprograms}\JARVIS AI"; Filename: "{app}\{#MainExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\JARVIS AI"; Filename: "{app}\{#MainExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MainExe}"; Description: "JARVIS AI indítása"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := IsWin64;
  if not Result then
    MsgBox('A JARVIS AI Windows x64 rendszert igényel.', mbError, MB_OK);
end;
