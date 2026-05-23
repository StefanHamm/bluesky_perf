@echo off
setlocal enabledelayedexpansion

REM Benchmark settings
set "PYTHON=python"
set "SCRIPT=compare_compiled.py"
set "CONFIG=./test.cfg"
set "OUTPUT_DIR=output\scaling"
set "LOCAL_BLUESKY=bluesky"
set "BACKUP_BLUESKY=bluesky_local_backup"
set "SEED=42"
set "STEPS=200000"

REM Aircraft counts to test. Edit this list for your scaling sweep.
set "AIRCRAFT_LIST=50 100 200 500 1000"

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

if exist "%OUTPUT_DIR%\numba.csv" del /q "%OUTPUT_DIR%\numba.csv"
if exist "%OUTPUT_DIR%\cpp.csv" del /q "%OUTPUT_DIR%\cpp.csv"
if exist "%OUTPUT_DIR%\python.csv" del /q "%OUTPUT_DIR%\python.csv"

REM Make sure the local bluesky folder exists before the first run.
if not exist "%LOCAL_BLUESKY%" (
    if exist "%BACKUP_BLUESKY%" (
        ren "%BACKUP_BLUESKY%" "%LOCAL_BLUESKY%"
    )
)

for %%A in (%AIRCRAFT_LIST%) do (
    echo ==================================================
    echo Aircraft count: %%A
    echo Steps: %STEPS%
    echo ==================================================

    REM 1) Local checkout: numba implementation
    if not exist "%LOCAL_BLUESKY%" (
        if exist "%BACKUP_BLUESKY%" ren "%BACKUP_BLUESKY%" "%LOCAL_BLUESKY%"
    )
    echo Running local numba version...
    %PYTHON% %SCRIPT% --aircraft %%A --steps %STEPS% --seed %SEED% --output "%OUTPUT_DIR%\numba.csv"
    if errorlevel 1 goto :fail

    REM 2) Rename local folder so pip-installed BlueSky is imported
    if exist "%LOCAL_BLUESKY%" (
        if exist "%BACKUP_BLUESKY%" rmdir /s /q "%BACKUP_BLUESKY%"
        ren "%LOCAL_BLUESKY%" "%BACKUP_BLUESKY%"
    )

    echo Running upstream compiled C++ version...
    %PYTHON% %SCRIPT% --aircraft %%A --steps %STEPS% --seed %SEED% --output "%OUTPUT_DIR%\cpp.csv"
    if errorlevel 1 goto :restore_and_fail

    echo Running upstream Python geo version...
    %PYTHON% %SCRIPT% --aircraft %%A --steps %STEPS% --seed %SEED% --config %CONFIG% --output "%OUTPUT_DIR%\python.csv"
    if errorlevel 1 goto :restore_and_fail

    REM Restore local checkout for the next loop iteration
    if exist "%BACKUP_BLUESKY%" (
        if exist "%LOCAL_BLUESKY%" rmdir /s /q "%LOCAL_BLUESKY%"
        ren "%BACKUP_BLUESKY%" "%LOCAL_BLUESKY%"
    )
)

echo.
echo Scaling sweep complete. CSV files are in %q%.
echo You can now run: python visualize_scaling.py --input-dir %OUTPUT_DIR%
exit /b 0

:restore_and_fail
if exist "%BACKUP_BLUESKY%" (
    if exist "%LOCAL_BLUESKY%" rmdir /s /q "%LOCAL_BLUESKY%"
    ren "%BACKUP_BLUESKY%" "%LOCAL_BLUESKY%"
)
:fail
echo Benchmark run failed.
exit /b 1
