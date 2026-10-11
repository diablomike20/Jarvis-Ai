; BRAHMA/JARVIS full Windows setup with reconstructed Claude Code runtime.
; Produced only after the PyInstaller onedir distribution and packaged MCP/
; Claude smoke tests pass. Keeps the existing HUD and all Brahma resources.
#define AppName "Brahma JARVIS"
#define AppVersion "0.1.0-preview"
#define AppPublisher "Brahma JARVIS Project"
#define AppExe "BrahmaEvo.exe"

[Setup]
AppId={{C26DE920-19AE-4DA4-9219-6C97BB69DB41}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\BrahmaJARVIS
DefaultGroupName=Brahma JARVIS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=build_setup
OutputBaseFilename=BRAHMA-JARVIS-Claude-Full-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=force
RestartApplications=no
SetupLogging=yes

[Files]
Source: "..\dist\BrahmaEvo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Brahma JARVIS"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\Brahma JARVIS"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start Brahma JARVIS"; Flags: nowait postinstall skipifsilent
