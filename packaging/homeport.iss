; Inno Setup script: Homeport-Setup.exe (per-user install, no admin rights).
;   iscc /DAppVersion=1.3.0 packaging\homeport.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6C1C9F1E-5A43-4C8E-9B1B-48F2D6A1B7E3}
AppName=Homeport
AppVersion={#AppVersion}
AppPublisher=The Homeport contributors
AppPublisherURL=https://github.com/ferdousmikdad/Homeport
DefaultDirName={localappdata}\Programs\Homeport
DefaultGroupName=Homeport
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Homeport-Setup-x64
SetupIconFile=homeport.ico
UninstallDisplayIcon={app}\Homeport.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\Homeport\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Homeport"; Filename: "{app}\Homeport.exe"
Name: "{autodesktop}\Homeport"; Filename: "{app}\Homeport.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Homeport.exe"; Description: "Launch Homeport"; Flags: nowait postinstall skipifsilent
