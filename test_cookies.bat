@echo off
chcp 65001 > nul
echo ============================================
echo  PRUEBA COMPLETA - YouTube Descargador
echo ============================================
echo.

echo Verificando dependencias...
echo.

REM Verificar Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Node.js NO encontrado - Instalar desde: https://nodejs.org
    pause
    exit /b 1
) else (
    for /f "tokens=*" %%i in ('node --version') do echo [OK] Node.js %%i
)

REM Verificar yt-dlp-ejs
python -c "import yt_dlp_ejs" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] yt-dlp-ejs NO encontrado - Instalando...
    pip install yt-dlp-ejs --quiet
) else (
    echo [OK] yt-dlp-ejs instalado
)

echo.
echo Verificando cookies.txt...
if exist "cookies.txt" (
    echo [OK] Archivo cookies.txt encontrado
) else (
    echo [!] No se encontro cookies.txt
    echo     Exporta desde tu navegador con la extension "Get cookies.txt LOCALLY"
    pause
    exit /b 1
)

echo.
echo Probando descarga...
echo.
python -c "import yt_dlp; ydl_opts = {'cookiefile': 'cookies.txt', 'quiet': False, 'js_runtimes': {'node': {}}}; ydl = yt_dlp.YoutubeDL(ydl_opts); info = ydl.extract_info('https://www.youtube.com/watch?v=dQw4w9WgXcQ', download=False); print('EXITO! Titulo:', info.get('title', '?'))"
echo.
pause
