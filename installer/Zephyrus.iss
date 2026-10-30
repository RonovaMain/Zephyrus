; ============================================================================
;  Zephyrus — скрипт установщика Inno Setup 6.3+
;  Перед компиляцией выполните сборку PyInstaller:  pyinstaller Zephyrus.spec
;  (или просто запустите build.bat — он сделает всё сам)
; ============================================================================

#define MyAppName      "Zephyrus"
; Версию можно передать из командной строки: ISCC /DMyAppVersion=1.2.3 Zephyrus.iss
#ifndef MyAppVersion
#define MyAppVersion   "1.0.0"
#endif
#define MyAppPublisher "RonovaDev"
#define MyAppExeName   "Zephyrus.exe"
; Впишите ссылку на свой GitHub (можно оставить пустой строкой)
#define MyAppURL       ""

[Setup]
; Уникальный GUID приложения. Не меняйте его между версиями — по нему работает обновление.
AppId={{B7E2A6D4-5C1F-4E8B-9A3D-2F6C7A1E9D40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
#if MyAppURL != ""
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
#endif
VersionInfoVersion={#MyAppVersion}

; Установка в Program Files; страница выбора папки включена, поэтому можно выбрать любой диск
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Не даём поставить поверх запущенной программы (имя мьютекса совпадает с main.py)
AppMutex=ZephyrusSingleInstance
CloseApplications=yes

SetupIconFile=..\assets\zephyrus.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=Output
OutputBaseFilename=Zephyrus_Setup_{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=auto

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon"; Description: "Создать ярлык в меню «Пуск»"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Вся папка, собранная PyInstaller (--onedir): exe, _internal, а в ней bin\ с yt-dlp и ffmpeg
Source: "..\dist\Zephyrus\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenuicon
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
{ ---------- Страница выбора диска установки (C:, D:, ...) ---------- }
var
  DrivePage: TInputOptionWizardPage;
  DriveLetters: array of String;

function DriveExists(const Letter: String): Boolean;
begin
  Result := DirExists(Letter + ':\');
end;

procedure InitializeWizard;
var
  i, idx: Integer;
  L: String;
  ProgramDrive: String;
begin
  DrivePage := CreateInputOptionPage(wpWelcome,
    'Диск установки',
    'На какой диск установить Zephyrus?',
    'Выберите диск. Данные программы (база, сессии, обновления движка) в любом случае хранятся в профиле пользователя: %LOCALAPPDATA%\Zephyrus.',
    True, False);

  ProgramDrive := Copy(ExpandConstant('{autopf}'), 1, 1);
  SetArrayLength(DriveLetters, 0);
  for i := 0 to 23 do
  begin
    L := Chr(Ord('C') + i);
    if DriveExists(L) then
    begin
      idx := GetArrayLength(DriveLetters);
      SetArrayLength(DriveLetters, idx + 1);
      DriveLetters[idx] := L;
      DrivePage.Add('Диск ' + L + ':');
      if CompareText(L, ProgramDrive) = 0 then
        DrivePage.Values[idx] := True;
    end;
  end;
  if (GetArrayLength(DriveLetters) > 0) and (DrivePage.SelectedValueIndex < 0) then
    DrivePage.Values[0] := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Letter, ProgramDrive: String;
begin
  Result := True;
  if CurPageID = DrivePage.ID then
  begin
    if DrivePage.SelectedValueIndex >= 0 then
    begin
      Letter := DriveLetters[DrivePage.SelectedValueIndex];
      ProgramDrive := Copy(ExpandConstant('{autopf}'), 1, 1);
      if CompareText(Letter, ProgramDrive) = 0 then
        WizardForm.DirEdit.Text := ExpandConstant('{autopf}\{#MyAppName}')
      else
        WizardForm.DirEdit.Text := Letter + ':\{#MyAppName}';
    end;
  end;
end;

{ ---------- Удаление: спросить про пользовательские данные ---------- }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\{#MyAppName}');
    if DirExists(DataDir) then
    begin
      if MsgBox('Удалить также данные программы (история, сессии, обновлённый движок)?' + #13#10 + DataDir,
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
