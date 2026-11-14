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
set "VECTOR_DIR=vectors"
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
    set "MODEL_!COUNT!=%%f"
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
echo Selected main model: %SELECTED_MODEL%
echo.

:: ========== ВЫБОР ВЕКТОРА ==========
set "USE_VECTOR=N"
set "SELECTED_VECTOR="
set "VECTOR_STRENGTH=0.7"

if exist "%VECTOR_DIR%" (
    echo Available vectors:
    echo -----------------
    set "VEC_COUNT=0"
    for %%v in ("%VECTOR_DIR%\*.gguf") do (
        set /a VEC_COUNT+=1
        set "VECTOR_!VEC_COUNT!=%%v"
        echo [!VEC_COUNT!] %%~nxv
    )
    
    if !VEC_COUNT! gtr 0 (
        echo.
        set /p USE_VECTOR="Apply control vector? (Y/N): "
        if /i "!USE_VECTOR!"=="Y" (
            set /p VEC_CHOICE="Select vector number (1-!VEC_COUNT!): "
            if defined VECTOR_!VEC_CHOICE! (
                set "SELECTED_VECTOR=!VECTOR_!VEC_CHOICE!!"
                echo.
                echo Vector strength options:
                echo [1] Standard (0.7)
                echo [2] Manual input
                echo.
                set /p STRENGTH_MODE="Choose (1/2): "
                
                if "!STRENGTH_MODE!"=="2" (
                    set /p VECTOR_STRENGTH="Enter strength (0.3-1.5): "
                    if "!VECTOR_STRENGTH!"=="" set "VECTOR_STRENGTH=0.7"
                ) else (
                    set "VECTOR_STRENGTH=0.7"
                    echo Using standard strength: 0.7
                )
                echo Selected vector: !SELECTED_VECTOR! with strength !VECTOR_STRENGTH!
            )
        )
    )
)

:: ========== ПАРАМЕТРЫ СЕРВЕРА ==========
set "GPU_LAYERS=99"
set "CTX_SIZE=8192"
set "THREADS=12"

:: Для больших моделей уменьшаем контекст
echo !SELECTED_MODEL! | findstr /i "24B 34B 70B" >nul
if !errorlevel! equ 0 (
    echo [INFO] Large model detected. Adjusting context to 4096 to save VRAM.
    set "CTX_SIZE=4096"
)

:: ========== ЗАПУСК ВАЛИДАТОРА (БЫСТРАЯ МОДЕЛЬ) ==========
set "VALIDATOR_MODEL=models\draft\qwen2.5-0.5b-instruct-q4_k_s.gguf"
if exist "%VALIDATOR_MODEL%" (
    echo Starting validator server on port 8001...
    start "LLAMA VALIDATOR (8001)" cmd /k ""%LLAMA_SERVER%" --model "%VALIDATOR_MODEL%" --n-gpu-layers 99 --ctx-size 2048 --threads 4 --host 127.0.0.1 --port 8001"
) else (
    echo [WARNING] Validator model not found at %VALIDATOR_MODEL%
    echo          Continuing without validator.
)

:: ========== ФОРМИРОВАНИЕ КОМАНДЫ ЗАПУСКА ОСНОВНОГО СЕРВЕРА ==========
set "SERVER_CMD="%LLAMA_SERVER%" --model "%SELECTED_MODEL%" --n-gpu-layers %GPU_LAYERS% --ctx-size %CTX_SIZE% --threads %THREADS% --host 127.0.0.1 --port 8000"

:: Добавляем вектор если выбран (формат filename:scale)
if /i "!USE_VECTOR!"=="Y" if defined SELECTED_VECTOR (
    set "SERVER_CMD=!SERVER_CMD! --control-vector-scaled "%SELECTED_VECTOR%:!VECTOR_STRENGTH!""
)

:: ========== ЗАПУСК ОСНОВНОГО СЕРВЕРА ==========
echo.
echo Starting main server on port 8000...
echo   Model: %SELECTED_MODEL%
echo   GPU Layers: %GPU_LAYERS%
echo   Context: %CTX_SIZE%
echo   Threads: %THREADS%
if /i "!USE_VECTOR!"=="Y" if defined SELECTED_VECTOR (
    echo   Control Vector: %SELECTED_VECTOR%
    echo   Vector Strength: !VECTOR_STRENGTH!
)
echo.

start "LLAMA MAIN (8000)" cmd /k "!SERVER_CMD!"

echo.
echo Server launched in separate window.
echo You can close this launcher window.
pause