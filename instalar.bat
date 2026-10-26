@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === EncoLibMG - instalacao ===

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [ERRO] ffmpeg nao encontrado no PATH. Instale com: winget install Gyan.FFmpeg
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente Python 3.12...
    py -3.12 -m venv .venv || (echo [ERRO] Python 3.12 nao encontrado. & pause & exit /b 1)
)

set PY=.venv\Scripts\python.exe
%PY% -m pip install --upgrade pip

nvidia-smi >nul 2>nul
if errorlevel 1 (
    echo Sem placa NVIDIA: instalando PyTorch para CPU.
    %PY% -m pip install torch==2.8.* torchaudio==2.8.* --index-url https://download.pytorch.org/whl/cpu || goto :erro
) else (
    echo Placa NVIDIA encontrada: instalando PyTorch com CUDA 12.8.
    %PY% -m pip install torch==2.8.* torchaudio==2.8.* --index-url https://download.pytorch.org/whl/cu128 || goto :erro
)

%PY% -m pip install -r requirements.txt || goto :erro

echo.
echo Pronto! Abra o programa com "Abrir EncoLibMG.bat".
pause
exit /b 0

:erro
echo [ERRO] A instalacao falhou. Veja as mensagens acima.
pause
exit /b 1
