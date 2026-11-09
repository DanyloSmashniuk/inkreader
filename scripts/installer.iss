; Інсталятор InkReader для Windows (Inno Setup 6). Збирається скриптом build_windows.ps1.
; Без прав адміністратора ставиться в профіль користувача; з правами адміністратора можна обрати встановлення для всіх.
#ifndef AppVersion
  #define AppVersion "0.1"
#endif

[Setup]
AppId={{6F3B2A7C-9D41-4E58-8B1A-2C7E5D90A4F3}
AppName=InkReader
AppVersion={#AppVersion}
AppVerName=InkReader {#AppVersion}
AppPublisher=Danylo Smashniuk
AppPublisherURL=https://github.com/DanyloSmashniuk/inkreader
AppSupportURL=https://github.com/DanyloSmashniuk/inkreader/issues
DefaultDirName={autopf}\InkReader
DefaultGroupName=InkReader
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=InkReader-setup
SetupIconFile=..\dist\icon.ico
UninstallDisplayIcon={app}\InkReader.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "assoc"; Description: "Відкривати книги .epub і .fb2 через InkReader (пункт «Відкрити за допомогою»)"; GroupDescription: "Файли книг:"

[Files]
Source: "..\dist\InkReader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\InkReader"; Filename: "{app}\InkReader.exe"
Name: "{autodesktop}\InkReader"; Filename: "{app}\InkReader.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\InkReader.Book"; ValueType: string; ValueName: ""; ValueData: "Книга (InkReader)"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\InkReader.Book\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\InkReader.exe,0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\InkReader.Book\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\InkReader.exe"" ""%1"""; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.epub\OpenWithProgids"; ValueType: string; ValueName: "InkReader.Book"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.fb2\OpenWithProgids"; ValueType: string; ValueName: "InkReader.Book"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc

[Run]
Filename: "{app}\InkReader.exe"; Description: "{cm:LaunchProgram,InkReader}"; Flags: nowait postinstall skipifsilent
