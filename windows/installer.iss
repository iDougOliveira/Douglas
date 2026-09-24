#ifndef MyAppVersion
#define MyAppVersion "3.18.0"
#endif

[Setup]
AppId={{D1F0F4AC-79E9-4C98-BB95-0DD86F2B9B59}
AppName=PokerCoach
AppVersion={#MyAppVersion}
AppPublisher=PokerCoach Local
DefaultDirName={localappdata}\Programs\PokerCoach
DefaultGroupName=PokerCoach
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=PokerCoach-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayName=PokerCoach {#MyAppVersion}

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked
Name: "tesseract"; Description: "Tentar instalar Tesseract OCR para leitura de stack/pote (requer Winget e pode pedir confirmação)"; GroupDescription: "OCR numérico:"; Flags: unchecked

[Files]
Source: "..\dist\PokerCoach.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\PokerCoachServer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\PokerVision.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\PokerCoach"; Filename: "{app}\PokerCoach.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\PokerCoach"; Filename: "{app}\PokerCoach.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command ""if (Get-Command winget -ErrorAction SilentlyContinue) {{ winget install -e --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements --silent | Out-Null }}; exit 0"""; Flags: runhidden waituntilterminated; Tasks: tesseract
Filename: "{app}\PokerCoach.exe"; Description: "Abrir PokerCoach agora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
