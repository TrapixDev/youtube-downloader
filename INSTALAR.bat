@echo off
chcp 65001 > nul
echo ============================================
echo  INSTALANDO DEPENDENCIAS
echo ============================================
echo.
pip install yt-dlp rich yt-dlp-ejs
echo.
echo Listo! Ya podes ejecutar "Descargar YouTube.bat"
echo.
pause
