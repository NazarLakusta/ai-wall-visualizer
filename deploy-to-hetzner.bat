@echo off
REM Run on Windows PC (double-click or: deploy-to-hetzner.bat)
set KEY=%USERPROFILE%\.ssh\id_ed25519_hetzner
set HOST=root@49.13.8.211
set PORT=443
set LOCAL=C:\Users\Nazar Lakusta\Projects\ai-wall-visualizer

echo Uploading nginx.conf and docker-compose.yml ...
scp -P %PORT% -i "%KEY%" "%LOCAL%\nginx\nginx.conf" %HOST%:/opt/ai-wall-visualizer/nginx/nginx.conf
scp -P %PORT% -i "%KEY%" "%LOCAL%\docker-compose.yml" %HOST%:/opt/ai-wall-visualizer/docker-compose.yml

echo Restarting nginx on server ...
ssh -p %PORT% -i "%KEY%" %HOST% "systemctl stop nginx apache2 2>/dev/null; systemctl disable nginx apache2 2>/dev/null; cd /opt/ai-wall-visualizer && docker compose up -d --force-recreate nginx && sleep 2 && curl -sI http://127.0.0.1/platform/ | head -1 && curl -sI http://49.13.8.211/platform/ | head -1"

echo.
echo Open in browser: http://49.13.8.211/platform/
pause
