; EncoLibMG installer (Inno Setup 6). Built by .github/workflows/release.yml:
;   ISCC /DAppVersion=1.0.0 installer\EncoLibMG.iss   →   installer\Output\EncoLibMG-1.0.0-Setup.exe
;
; The setup file only carries the app's code. While installing it downloads, with a progress bar:
;   - Python 3.12 (the official "embeddable" build) into {app}\python, plus pip;
;   - ffmpeg into {app}\ffmpeg\bin (the app puts it first on its PATH);
;   - PyTorch: the CUDA build when an NVIDIA card PyTorch supports is found (GTX 10 series or newer), otherwise
;     the processor build; then the other Python packages from requirements.txt.
; Per-user install, no administrator needed. Uninstalling removes the program; libraries and settings stay.
; Command line: /CPU forces the processor build (smaller download; used by the install test).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "EncoLibMG"
#define PythonUrl "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
#define GetPipUrl "https://bootstrap.pypa.io/get-pip.py"
#define FfmpegUrl "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
#define TorchCuda "https://download.pytorch.org/whl/cu128"
#define TorchCpu "https://download.pytorch.org/whl/cpu"

[Setup]
AppId={{3E3B3636-5691-4C6B-A831-DF72283FFCCC}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=pdromguel
AppPublisherURL=https://github.com/pdromguel/encolibmg
AppSupportURL=https://github.com/pdromguel/encolibmg/issues
AppUpdatesURL=https://github.com/pdromguel/encolibmg/releases
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\LICENSE
SetupIconFile=..\encolibmg\webui\static\brand\icon.ico
UninstallDisplayIcon={app}\app\encolibmg\webui\static\brand\icon.ico
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
OutputDir=Output
OutputBaseFilename={#AppName}-{#AppVersion}-Setup
ShowLanguageDialog=auto

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[CustomMessages]
en.Downloading=Downloading Python and ffmpeg…
ptbr.Downloading=Baixando o Python e o ffmpeg…
en.Setting=Setting up EncoLibMG
ptbr.Setting=Preparando o EncoLibMG
en.SettingNote=This takes a few minutes: PyTorch and the AI libraries are large (about 3 GB with an NVIDIA card).
ptbr.SettingNote=Isso leva alguns minutos: o PyTorch e as bibliotecas de IA são grandes (cerca de 3 GB com placa NVIDIA).
en.StepPython=Unpacking Python…
ptbr.StepPython=Descompactando o Python…
en.StepPip=Installing pip…
ptbr.StepPip=Instalando o pip…
en.StepFfmpeg=Unpacking ffmpeg…
ptbr.StepFfmpeg=Descompactando o ffmpeg…
en.StepTorchGpu=Installing PyTorch for your NVIDIA card (the longest step)…
ptbr.StepTorchGpu=Instalando o PyTorch para a sua placa NVIDIA (a etapa mais demorada)…
en.StepTorchCpu=Installing PyTorch for the processor…
ptbr.StepTorchCpu=Instalando o PyTorch para o processador…
en.StepPackages=Installing the other packages…
ptbr.StepPackages=Instalando os outros pacotes…
en.Failed=Setup couldn't finish this step:%n%n%1%n%nCheck your internet connection and run the installer again. Details are in:%n%2
ptbr.Failed=A instalação não conseguiu terminar esta etapa:%n%n%1%n%nConfira a sua internet e rode o instalador de novo. Os detalhes estão em:%n%2
en.Launch=Open EncoLibMG
ptbr.Launch=Abrir o EncoLibMG

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\encolibmg\*"; DestDir: "{app}\app\encolibmg"; Excludes: "__pycache__\*,*.pyc"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\requirements.txt"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m encolibmg"; WorkingDir: "{app}\app"; IconFilename: "{app}\app\encolibmg\webui\static\brand\icon.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m encolibmg"; WorkingDir: "{app}\app"; IconFilename: "{app}\app\encolibmg\webui\static\brand\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-m encolibmg"; WorkingDir: "{app}\app"; Description: "{cm:Launch}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\ffmpeg"
Type: filesandordirs; Name: "{app}\app"
Type: files; Name: "{app}\install-log.txt"

[Code]
var
  DownloadPage: TDownloadWizardPage;
  NeedPython, NeedFfmpeg: Boolean;

function LogFile(): String;
begin
  Result := ExpandConstant('{app}\install-log.txt');
end;

{ Runs a command hidden, appending its output to install-log.txt; True when it exits with 0. }
function RunLogged(const Exe, Params: String): Boolean;
var
  Code: Integer;
begin
  SaveStringToFile(LogFile(), #13#10 + '> ' + Exe + ' ' + Params + #13#10, True);
  Result := Exec(ExpandConstant('{cmd}'), '/S /C ""' + Exe + '" ' + Params + ' >> "' + LogFile() + '" 2>&1"',
                 '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
end;

function PowerShell(const Script: String): Boolean;
begin
  Result := RunLogged('powershell.exe', '-NoProfile -ExecutionPolicy Bypass -Command "' + Script + '"');
end;

{ The same rule as encolibmg/core/gpu.py: an NVIDIA card with compute capability 6.1 or newer. }
function UsableNvidia(): Boolean;
var
  Code, Major, Minor, Dot: Integer;
  Cap: AnsiString;
  Line: String;
begin
  Result := False;
  if Pos('/CPU', Uppercase(GetCmdTail())) > 0 then Exit;  { forced: smaller download, and the install test }
  if not Exec(ExpandConstant('{cmd}'), '/S /C "nvidia-smi --query-gpu=compute_cap --format=csv,noheader > "' +
              ExpandConstant('{tmp}\cap.txt') + '" 2>nul"', '', SW_HIDE, ewWaitUntilTerminated, Code) then Exit;
  if (Code <> 0) or not LoadStringFromFile(ExpandConstant('{tmp}\cap.txt'), Cap) then Exit;
  Line := Trim(String(Cap));
  if Pos(#13, Line) > 0 then Line := Copy(Line, 1, Pos(#13, Line) - 1);
  if Pos(#10, Line) > 0 then Line := Copy(Line, 1, Pos(#10, Line) - 1);
  Dot := Pos('.', Line);
  if Dot = 0 then Exit;
  Major := StrToIntDef(Copy(Line, 1, Dot - 1), 0);
  Minor := StrToIntDef(Copy(Line, Dot + 1, 3), 0);
  Result := (Major > 6) or ((Major = 6) and (Minor >= 1));
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), CustomMessage('Downloading'), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID <> wpReady then Exit;
  NeedPython := not FileExists(ExpandConstant('{app}\python\python.exe'));
  NeedFfmpeg := not FileExists(ExpandConstant('{app}\ffmpeg\bin\ffmpeg.exe'));
  if not (NeedPython or NeedFfmpeg) then Exit;  { an update over an existing install }
  DownloadPage.Clear;
  if NeedPython then begin
    DownloadPage.Add('{#PythonUrl}', 'python.zip', '');
    DownloadPage.Add('{#GetPipUrl}', 'get-pip.py', '');
  end;
  if NeedFfmpeg then DownloadPage.Add('{#FfmpegUrl}', 'ffmpeg.zip', '');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
    except
      if DownloadPage.AbortedByUser then Log('Download aborted by the user.')
      else SuppressibleMsgBox(AddPeriod(GetExceptionMessage), mbCriticalError, MB_OK, IDOK);
      Result := False;
    end;
  finally
    DownloadPage.Hide;
  end;
end;

procedure Fail(const What: String);
begin
  SuppressibleMsgBox(FmtMessage(CustomMessage('Failed'), [What, LogFile()]), mbCriticalError, MB_OK, IDOK);
end;

procedure SetUp();
var
  Page: TOutputProgressWizardPage;
  App, Py, Pth: String;
  Gpu: Boolean;
begin
  App := ExpandConstant('{app}');
  Py := App + '\python\python.exe';
  Page := CreateOutputProgressPage(CustomMessage('Setting'), CustomMessage('SettingNote'));
  Page.Show;
  try
    if NeedPython then begin
      Page.SetText(CustomMessage('StepPython'), ''); Page.SetProgress(0, 6);
      if not PowerShell('Expand-Archive -Force -LiteralPath ''' + ExpandConstant('{tmp}\python.zip') + ''' -DestinationPath ''' + App + '\python''') then begin
        Fail(CustomMessage('StepPython')); Exit;
      end;
      { let the embeddable Python see the app and site-packages }
      Pth := 'python312.zip' + #13#10 + '.' + #13#10 + '..\app' + #13#10 + 'import site' + #13#10;
      SaveStringToFile(App + '\python\python312._pth', Pth, False);
      Page.SetText(CustomMessage('StepPip'), ''); Page.SetProgress(1, 6);
      if not RunLogged(Py, '"' + ExpandConstant('{tmp}\get-pip.py') + '" --no-warn-script-location') then begin
        Fail(CustomMessage('StepPip')); Exit;
      end;
    end;
    if NeedFfmpeg then begin
      Page.SetText(CustomMessage('StepFfmpeg'), ''); Page.SetProgress(2, 6);
      if not PowerShell('$z = ''' + ExpandConstant('{tmp}\ffmpeg.zip') + '''; $d = ''' + ExpandConstant('{tmp}\ff') + ''';' +
                        ' Expand-Archive -Force -LiteralPath $z -DestinationPath $d;' +
                        ' $b = Get-ChildItem $d -Recurse -Filter ffmpeg.exe | Select-Object -First 1;' +
                        ' New-Item -ItemType Directory -Force ''' + App + '\ffmpeg\bin'' | Out-Null;' +
                        ' Copy-Item (Join-Path $b.DirectoryName ''*'') ''' + App + '\ffmpeg\bin'' -Force') then begin
        Fail(CustomMessage('StepFfmpeg')); Exit;
      end;
    end;
    Gpu := UsableNvidia();
    if Gpu then Page.SetText(CustomMessage('StepTorchGpu'), '') else Page.SetText(CustomMessage('StepTorchCpu'), '');
    Page.SetProgress(3, 6);
    if Gpu then begin
      if not RunLogged(Py, '-m pip install --no-warn-script-location --disable-pip-version-check "torch==2.8.*" "torchaudio==2.8.*" --index-url {#TorchCuda}') then begin
        Fail(CustomMessage('StepTorchGpu')); Exit;
      end;
    end else begin
      if not RunLogged(Py, '-m pip install --no-warn-script-location --disable-pip-version-check "torch==2.8.*" "torchaudio==2.8.*" --index-url {#TorchCpu}') then begin
        Fail(CustomMessage('StepTorchCpu')); Exit;
      end;
    end;
    Page.SetText(CustomMessage('StepPackages'), ''); Page.SetProgress(5, 6);
    if not RunLogged(Py, '-m pip install --no-warn-script-location --disable-pip-version-check -r "' + App + '\app\requirements.txt"') then begin
      Fail(CustomMessage('StepPackages')); Exit;
    end;
    Page.SetProgress(6, 6);
  finally
    Page.Hide;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then SetUp();
end;

{ PyTorch has very deep folders: in a deep install folder some paths pass Windows' 260-character limit and the
  normal uninstall can't delete them. rd with the \\?\ prefix can. Only the program's own folders are touched. }
procedure RemoveLongPathDir(const Dir: String);
var
  Code: Integer;
begin
  if DirExists(Dir) then
    Exec(ExpandConstant('{cmd}'), '/S /C "rd /s /q "\\?\' + Dir + '""', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then begin
    RemoveLongPathDir(ExpandConstant('{app}\python'));
    RemoveLongPathDir(ExpandConstant('{app}\ffmpeg'));
    RemoveLongPathDir(ExpandConstant('{app}\app'));
    RemoveDir(ExpandConstant('{app}'));  { only if nothing else is left in it }
  end;
end;
