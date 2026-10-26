@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === EncoLibMG - instalacao / install ===

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [ERRO] ffmpeg nao encontrado no PATH. Instale com: winget install Gyan.FFmpeg
    echo [ERROR] ffmpeg not found on PATH. Install it with: winget install Gyan.FFmpeg
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente Python 3.12... / Creating the Python 3.12 environment...
    py -3.12 -m venv .venv || (echo [ERRO/ERROR] Python 3.12 nao encontrado / not found. & pause & exit /b 1)
)

set PY=.venv\Scripts\python.exe
%PY% -m pip install --upgrade pip

nvidia-smi >nul 2>nul
if errorlevel 1 (
    echo Sem placa NVIDIA: PyTorch para CPU. / No NVIDIA card: installing PyTorch for CPU.
    %PY% -m pip install torch==2.8.* torchaudio==2.8.* --index-url https://download.pytorch.org/whl/cpu || goto :erro
) else (
    echo Placa NVIDIA encontrada: PyTorch com CUDA 12.8. / NVIDIA card found: installing PyTorch with CUDA 12.8.
    %PY% -m pip install torch==2.8.* torchaudio==2.8.* --index-url https://download.pytorch.org/whl/cu128 || goto :erro
)

%PY% -m pip install -r requirements.txt || goto :erro

echo.
echo Pronto! Abra o programa com "Abrir EncoLibMG.bat".
echo Done! Start the app with "Abrir EncoLibMG.bat".
pause
exit /b 0

:erro
echo [ERRO] A instalacao falhou. Veja as mensagens acima.
echo [ERROR] The installation failed. See the messages above.
pause
exit /b 1
