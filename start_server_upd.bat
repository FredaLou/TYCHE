@echo off
setlocal enabledelayedexpansion

echo =============================================
echo         LLAMA.CPP SERVER SELECTOR
echo =============================================
echo.

set "LLAMA_SERVER=llama_cpp_bin\llama-server.exe"

if not exist "%LLAMA_SERVER%" (
    echo [ERROR] llama-server.exe not found at %LLAMA_SERVER%
    echo Please download from https://github.com/ggerganov/llama.cpp/releases
    pause
    exit /b
)

set "MODEL_DIR=models"
set "COUNT=0"

if not exist "%MODEL_DIR%" (
    echo [ERROR] Folder '%MODEL_DIR%' not found.
    pause
    exit /b
)

echo Available models:
echo -----------------
for %%f in ("%MODEL_DIR%\*.gguf") do (
    set /a COUNT+=1
    set "MODEL_!COUNT!=%%~f"
    echo [!COUNT!] %%~nxf
)

if %COUNT%==0 (
    echo [ERROR] No .gguf files found in '%MODEL_DIR%'.
    pause
    exit /b
)

echo.
set /p CHOICE="Select model number (1-%COUNT%): "

if not defined MODEL_%CHOICE% (
    echo [ERROR] Invalid choice.
    pause
    exit /b
)

set "SELECTED_MODEL=!MODEL_%CHOICE%!"
echo.
echo Selected: %SELECTED_MODEL%
echo.

:: --- Speculative Decoding Option ---
set "USE_DRAFT=0"
set "DRAFT_MODEL="
set /p USE_DRAFT_INPUT="Enable Speculative Decoding (draft model)? [y/N]: "
if /i "!USE_DRAFT_INPUT!"=="y" set "USE_DRAFT=1"

if !USE_DRAFT! equ 1 (
    set "DRAFT_DIR=models\draft"
    if not exist "!DRAFT_DIR!" (
        echo [WARN] Draft folder '!DRAFT_DIR!' not found. Creating it...
        mkdir "!DRAFT_DIR!"
    )
    set "DRAFT_COUNT=0"
    echo.
    echo Available draft models:
    echo ------------------------
    for %%f in ("!DRAFT_DIR!\*.gguf") do (
        set /a DRAFT_COUNT+=1
        set "DRAFT_MODEL_!DRAFT_COUNT!=%%~f"
        echo [!DRAFT_COUNT!] %%~nxf
    )
    if !DRAFT_COUNT! equ 0 (
        echo [WARN] No .gguf draft models found in '!DRAFT_DIR!'.
        echo Please place a small model there ^(e.g., Qwen2.5-0.5B-Instruct Q4_K_S^).
        echo Disabling speculative decoding.
        set "USE_DRAFT=0"
    ) else (
        echo.
        set /p DRAFT_CHOICE="Select draft model number (1-!DRAFT_COUNT!): "
        :: Надёжный способ получить значение переменной с динамическим именем
        set "DRAFT_MODEL="
        for /L %%i in (1,1,!DRAFT_COUNT!) do (
            if "!DRAFT_CHOICE!"=="%%i" set "DRAFT_MODEL=!DRAFT_MODEL_%%i!"
        )
        if not defined DRAFT_MODEL (
            echo [ERROR] Invalid draft choice. Disabling speculative decoding.
            set "USE_DRAFT=0"
        ) else (
            echo Selected draft: !DRAFT_MODEL!
        )
    )
)

:: --- Параметры сервера ---
set "GPU_LAYERS=99"
set "CTX_SIZE=8192"
set "THREADS=16"

echo !SELECTED_MODEL! | findstr /i "24B 34B 70B" >nul
if !errorlevel! equ 0 (
    echo [INFO] Large model detected. Adjusting context to 4096 to save VRAM.
    set "CTX_SIZE=4096"
)

echo.
echo =============================================
echo Starting server with:
echo   Model      : %SELECTED_MODEL%
echo   GPU Layers : %GPU_LAYERS%
echo   Context    : %CTX_SIZE%
echo   Threads    : %THREADS%
if !USE_DRAFT! equ 1 (
    echo   Draft Model: !DRAFT_MODEL!
    echo   Draft Settings: p-min=0.9, max-tokens=16
)
echo =============================================
echo.

:: Запуск сервера напрямую (без промежуточной переменной CMD)
if !USE_DRAFT! equ 1 (
    "%LLAMA_SERVER%" ^
        --model "%SELECTED_MODEL%" ^
        --n-gpu-layers %GPU_LAYERS% ^
        --ctx-size %CTX_SIZE% ^
        --threads %THREADS% ^
        --host 127.0.0.1 ^
        --port 8000 ^
        --model-draft "!DRAFT_MODEL!" ^
        --draft-max 16 ^
        --draft-p-min 0.9
) else (
    "%LLAMA_SERVER%" ^
        --model "%SELECTED_MODEL%" ^
        --n-gpu-layers %GPU_LAYERS% ^
        --ctx-size %CTX_SIZE% ^
        --threads %THREADS% ^
        --host 127.0.0.1 ^
        --port 8000
)

echo.
echo Server stopped.
pause