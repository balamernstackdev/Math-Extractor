@echo off
echo ==========================================
echo      CLEANING PREVIOUS BUILDS
echo ==========================================
if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"
if exist "installer\Output" rd /s /q "installer\Output"

echo ==========================================
echo      BUILDING APP (PyInstaller)
echo ==========================================
:: Modify this path if your python environment is different
if exist ".venv\Scripts\pyinstaller.exe" (
    echo "Using venv PyInstaller..."
    .venv\Scripts\python.exe -c "import tokenizers; print(f'BUILD DEBUG: tokenizers version = {tokenizers.__version__}')"
    call .venv\Scripts\pyinstaller.exe MathpixClone.spec --clean --noconfirm
) else (
    echo "Could not find .venv PyInstaller, trying global..."
    pyinstaller MathpixClone.spec --clean --noconfirm
)

if %errorlevel% neq 0 (
    echo "ERROR: App build failed!"
    pause
    exit /b %errorlevel%
)

echo ==========================================
echo      PREPARING INSTALLER FILES
echo ==========================================
del /Q "installer\app\*.exe"
xcopy /E /I /Y "dist\Math Extractor" "installer\app"

echo ==========================================
echo      BUILDING INSTALLER (Inno Setup)
echo ==========================================
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "installer\installer.iss"
if %errorlevel% neq 0 (
    echo "ERROR: Installer build failed!"
    pause
    exit /b %errorlevel%
)

echo ==========================================
echo      SUCCESS!
echo ==========================================
echo Installer is ready at: installer\Output\MathExtractorInstaller.exe
pause
