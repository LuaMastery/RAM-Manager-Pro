@echo off
REM ========================================
REM     RAM Manager Pro - Inicializador
REM ========================================

REM Mudar para o diretório onde o batch está localizado
cd /d "%~dp0"

echo.
echo ========================================
echo     RAM Manager Pro - Inicializador
echo ========================================
echo.

REM Verificar se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo Por favor, instale o Python 3.8 ou superior.
    pause
    exit /b 1
)

echo [OK] Python encontrado
echo.

REM Verificar dependencias
echo Verificando dependencias...
python -c "import customtkinter, psutil, wmi" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Instalando dependencias...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar dependencias!
        pause
        exit /b 1
    )
)

echo [OK] Dependencias OK
echo.

REM Iniciar programa (sem console - usar pythonw)
echo Iniciando RAM Manager Pro...
echo ========================================
start "" pythonw "%~dp0ram_manager.py"

if errorlevel 1 (
    echo.
    echo [ERRO] O programa encerrou com erro.
    pause
)
