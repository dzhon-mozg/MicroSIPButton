#define MyAppName "MicroSIPButton"
#define MyAppExeName "MicroSIPButton.exe"
#ifndef AppVersion
  #define AppVersion "1.6.1"
#endif

[Setup]
AppId={{4E8D2A77-9B1C-4A3F-8E5D-2C6B9F1A7D30}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher={#MyAppName}
DefaultDirName={localappdata}\Programs\MicroSIPButton
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=MicroSIPButton-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#AppVersion}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "installmicrosip"; Description: "Установить MicroSIP (из комплекта)"; GroupDescription: "MicroSIP:"; Check: not MicroSIPInstalled
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "bundled\*"; DestDir: "{localappdata}\MicroSIP"; Tasks: installmicrosip; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\MicroSIPButton"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"

[Code]
var
  BundledMicroSIPFiles: array of String;

function MicroSIPInstalled(): Boolean;
var
  Value: String;
begin
  Result := FileExists(ExpandConstant('{localappdata}\MicroSIP\MicroSIP.exe'));
  if Result then
    Exit;
  Result := RegQueryStringValue(HKCU,
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\MicroSIP', 'UninstallString', Value);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if (not MicroSIPInstalled()) and (not WizardIsTaskSelected('installmicrosip')) then
    if MsgBox('MicroSIP не найден. Кнопка не заработает без MicroSIP.' + #13#10 +
              'Вернитесь назад и отметьте «Установить MicroSIP (из комплекта)».' + #13#10 + #13#10 +
              'Продолжить установку без MicroSIP?', mbConfirmation, MB_YESNO) = IDNO then
      Result := 'MicroSIP не установлен.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    if WizardIsTaskSelected('installmicrosip') then
      RegWriteStringValue(HKCU, 'Software\MicroSIPButton', 'MicroSIPBundled', '1');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Flag: String;
  Dir: String;
  I: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if RegQueryStringValue(HKCU, 'Software\MicroSIPButton', 'MicroSIPBundled', Flag) and (Flag = '1') then
    begin
      Dir := ExpandConstant('{localappdata}\MicroSIP');
      SetArrayLength(BundledMicroSIPFiles, 15);
      BundledMicroSIPFiles[0] := 'MicroSIP.exe';
      BundledMicroSIPFiles[1] := 'avcodec-60.dll';
      BundledMicroSIPFiles[2] := 'avformat-60.dll';
      BundledMicroSIPFiles[3] := 'avutil-58.dll';
      BundledMicroSIPFiles[4] := 'lame_enc.dll';
      BundledMicroSIPFiles[5] := 'SDL2.dll';
      BundledMicroSIPFiles[6] := 'swscale-7.dll';
      BundledMicroSIPFiles[7] := 'hangup.wav';
      BundledMicroSIPFiles[8] := 'msgin.wav';
      BundledMicroSIPFiles[9] := 'msgout.wav';
      BundledMicroSIPFiles[10] := 'ringing.wav';
      BundledMicroSIPFiles[11] := 'ringing2.wav';
      BundledMicroSIPFiles[12] := 'ringtone.wav';
      BundledMicroSIPFiles[13] := 'MicroSIP.url';
      BundledMicroSIPFiles[14] := 'License.txt';
      for I := 0 to GetArrayLength(BundledMicroSIPFiles) - 1 do
        DeleteFile(Dir + '\' + BundledMicroSIPFiles[I]);
    end;
    RegDeleteKeyIncludingSubkeys(HKCU, 'Software\MicroSIPButton');
  end;
end;
