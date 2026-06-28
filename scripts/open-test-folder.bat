@echo off
REM Скопіюйте свої файли в storage\test з правильними іменами
set DEST=%~dp0..\storage\test
if not exist "%DEST%" mkdir "%DEST%"

echo.
echo  Покладіть у цю папку файли:
echo  %DEST%
echo.
echo  original.jpg  - фото кімнати
echo  mask.png      - маска
echo  specular.png  - specular
echo.
echo  Потім у боті натисніть Тестове фото (нова кнопка).
echo.
pause
