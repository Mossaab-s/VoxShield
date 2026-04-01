@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   VoxShield v1.0 - Installation Windows
echo   MSIA Systems - Mars 2026
echo ============================================================
echo.

:: -- Verification Python -------------------------------------------------------
echo [1/9] Verification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Python n'est pas installe ou introuvable dans PATH.
    echo Telechargez Python 3.11 depuis https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo Python %PYVER% trouve.

:: -- Environnement virtuel -----------------------------------------------------
echo.
echo [2/9] Creation de l'environnement virtuel...
if not exist "venv" (
    python -m venv venv
    if errorlevel 1 (
        echo ERREUR : Impossible de creer l'environnement virtuel.
        pause
        exit /b 1
    )
)
call venv\Scripts\activate.bat
echo Environnement virtuel active.

:: -- Installation des dependances ----------------------------------------------
echo.
echo [3/9] Installation des dependances Python...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERREUR lors de l'installation des dependances.
    pause
    exit /b 1
)

echo [4/9] Installation dependances Windows specifiques...
pip install -r requirements_windows.txt --quiet

:: -- Telechargement Piper TTS --------------------------------------------------
echo.
echo [5/9] Telechargement du binaire Piper TTS pour Windows...
set PIPER_DIR=venv\piper
if not exist "%PIPER_DIR%" mkdir "%PIPER_DIR%"

set PIPER_URL=https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip
set PIPER_ZIP=%PIPER_DIR%\piper.zip

if not exist "%PIPER_DIR%\piper.exe" (
    echo Telechargement Piper TTS...
    powershell -Command "Invoke-WebRequest -Uri '%PIPER_URL%' -OutFile '%PIPER_ZIP%' -UseBasicParsing"
    if exist "%PIPER_ZIP%" (
        powershell -Command "Expand-Archive -Path '%PIPER_ZIP%' -DestinationPath '%PIPER_DIR%' -Force"
        del "%PIPER_ZIP%"
        echo Piper TTS installe.
    ) else (
        echo AVERTISSEMENT : Telechargement Piper echoue.
        echo Telechargez manuellement : https://github.com/rhasspy/piper/releases
    )
) else (
    echo Piper TTS deja present.
)

:: -- Telechargement modele Whisper ---------------------------------------------
echo.
echo [6/9] Telechargement du modele Whisper 'base'...
python -c "from faster_whisper import WhisperModel; print('Telechargement...'); WhisperModel('base', device='cpu', compute_type='int8'); print('Modele Whisper base OK.')" 2>nul
if errorlevel 1 (
    echo AVERTISSEMENT : Le modele Whisper sera telecharge au premier demarrage.
)

:: -- Telechargement modeles Piper ----------------------------------------------
echo.
echo [7/9] Telechargement des modeles Piper (FR + EN)...
set MODELS_DIR=%APPDATA%\VoxShield\MSIASystems\models\piper
if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%"

set FR_MODEL=fr_FR-siwis-medium
set FR_URL=https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx
if not exist "%MODELS_DIR%\%FR_MODEL%.onnx" (
    echo Telechargement modele francais...
    powershell -Command "Invoke-WebRequest -Uri '%FR_URL%' -OutFile '%MODELS_DIR%\%FR_MODEL%.onnx' -UseBasicParsing" 2>nul
    powershell -Command "Invoke-WebRequest -Uri '%FR_URL%.json' -OutFile '%MODELS_DIR%\%FR_MODEL%.onnx.json' -UseBasicParsing" 2>nul
)

set EN_MODEL=en_US-lessac-medium
set EN_URL=https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
if not exist "%MODELS_DIR%\%EN_MODEL%.onnx" (
    echo Telechargement modele anglais...
    powershell -Command "Invoke-WebRequest -Uri '%EN_URL%' -OutFile '%MODELS_DIR%\%EN_MODEL%.onnx' -UseBasicParsing" 2>nul
    powershell -Command "Invoke-WebRequest -Uri '%EN_URL%.json' -OutFile '%MODELS_DIR%\%EN_MODEL%.onnx.json' -UseBasicParsing" 2>nul
)

:: -- ArgosTranslate fr<->en ----------------------------------------------------
echo.
echo [8/9] Installation ArgosTranslate (fr-en et en-fr)...
python -c "import argostranslate.package, argostranslate.translate; argostranslate.package.update_package_index(); available = argostranslate.package.get_available_packages(); [argostranslate.package.install_from_path(p.download()) for pair in [('fr','en'),('en','fr')] for p in available if p.from_code==pair[0] and p.to_code==pair[1]]; print('ArgosTranslate OK.')" 2>nul

:: -- Raccourci Bureau ----------------------------------------------------------
echo.
echo [9/9] Creation du raccourci bureau...
set SCRIPT_DIR=%~dp0
set VENV_PYTHON=%SCRIPT_DIR%venv\Scripts\pythonw.exe
set MAIN_SCRIPT=%SCRIPT_DIR%main.py
set SHORTCUT=%USERPROFILE%\Desktop\VoxShield.lnk

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%SHORTCUT%'); $sc.TargetPath = '%VENV_PYTHON%'; $sc.Arguments = '%MAIN_SCRIPT%'; $sc.WorkingDirectory = '%SCRIPT_DIR%'; $sc.Description = 'VoxShield'; $sc.Save()" 2>nul

:: -- Resume --------------------------------------------------------------------
echo.
echo ============================================================
echo   Installation terminee !
echo ============================================================
echo.
echo IMPORTANT - Virtual Cable audio requis :
echo   Telechargez VB-Audio Virtual Cable : https://vb-audio.com/Cable/
echo   Installez en tant qu'administrateur puis redemarrez Windows.
echo.
echo Pour lancer : venv\Scripts\python.exe main.py
echo.
pause
