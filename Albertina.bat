@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "APP_ROOT=%~dp0"
if "%APP_ROOT:~-1%"=="\" set "APP_ROOT=%APP_ROOT:~0,-1%"

set "LOG_FILE=%APP_ROOT%\Albertina.log"
set "BACKEND_RUNTIME_LOG=%APP_ROOT%\Albertina.backend.log"
set "BACKEND_RUNTIME_ERR_LOG=%APP_ROOT%\Albertina.backend.err.log"
set "FRONTEND_RUNTIME_LOG=%APP_ROOT%\Albertina.frontend.log"
set "FRONTEND_RUNTIME_ERR_LOG=%APP_ROOT%\Albertina.frontend.err.log"
set "BACKEND_PID_FILE=%APP_ROOT%\Albertina.backend.pid"
set "FRONTEND_PID_FILE=%APP_ROOT%\Albertina.frontend.pid"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=3500"
set "START_WAIT_SECONDS=20"
set "DEFAULT_ALBERTINA_DATABASE_URL=postgresql://postgres:Esquilo08!!!@db.zbdgxbktblttarkradmk.supabase.co:6543/postgres?sslmode=require"
set "DEFAULT_OLIST_CLIENT_ID=tiny-api-5a6c6021a81d09b280ca8f1f4e685b6107fc4d3e-1776458496"
set "DEFAULT_OLIST_REDIRECT_URI=http://localhost:3500/olist/callback"
set "DEFAULT_VITE_API_BASE_URL=http://localhost:8000/api"

if not exist "%LOG_FILE%" type nul > "%LOG_FILE%"
call :log "Script aberto."

if /I "%~1"=="status" goto cli_status
if /I "%~1"=="iniciar" goto cli_start
if /I "%~1"=="encerrar" goto cli_stop

:menu
cls
echo ================================================
echo Albertina - Controle da Aplicacao
echo ================================================
echo.
call :show_status
echo.
echo [1] Ver status do processo
echo [2] Iniciar a aplicacao
echo [3] Encerrar a aplicacao
echo [0] Sair
echo.
set "choice="
set /p "choice=Selecione uma opcao: "

if "%choice%"=="1" goto option_status
if "%choice%"=="2" goto option_start
if "%choice%"=="3" goto option_stop
if "%choice%"=="0" goto option_exit

echo.
echo Opcao invalida.
call :log "Opcao invalida informada: %choice%"
pause
goto menu

:option_status
call :log "Usuario consultou status."
echo.
call :show_status
echo.
pause
goto menu

:option_start
call :log "Usuario solicitou inicio da aplicacao."
call :start_application
echo.
pause
goto menu

:option_stop
call :log "Usuario solicitou encerramento da aplicacao."
call :stop_application
echo.
pause
goto menu

:option_exit
call :log "Script encerrado pelo usuario."
echo.
echo O menu sera fechado. Os processos iniciados permanecem em execucao.
exit /b 0

:cli_status
call :log "Consulta de status via linha de comando."
call :show_status
exit /b 0

:cli_start
call :log "Inicializacao via linha de comando."
call :start_application
exit /b %ERRORLEVEL%

:cli_stop
call :log "Encerramento via linha de comando."
call :stop_application
exit /b %ERRORLEVEL%

:show_status
call :cleanup_stale_pid "%BACKEND_PID_FILE%" "%BACKEND_PORT%" "backend"
call :cleanup_stale_pid "%FRONTEND_PID_FILE%" "%FRONTEND_PORT%" "frontend"
call :print_component_status "Backend" "%BACKEND_PID_FILE%" "%BACKEND_PORT%" "http://localhost:8000/api/health"
call :print_component_status "Frontend" "%FRONTEND_PID_FILE%" "%FRONTEND_PORT%" "http://localhost:3500"
exit /b 0

:print_component_status
set "LABEL=%~1"
set "PID_FILE=%~2"
set "PORT=%~3"
set "URL=%~4"
set "PID="
if exist "%PID_FILE%" set /p PID=<"%PID_FILE%"

call :is_port_listening "%PORT%"
if "%ERRORLEVEL%"=="0" (
  if not "%PID%"=="" (
    echo %LABEL% : Em execucao na porta %PORT% ^(PID monitorado: %PID%^)
  ) else (
    echo %LABEL% : Em execucao na porta %PORT%
  )
  echo           URL: %URL%
  exit /b 0
)

if not "%PID%"=="" (
  echo %LABEL% : PID registrado, mas porta %PORT% nao esta ativa ^(PID: %PID%^)
  exit /b 0
)

echo %LABEL% : Parado
exit /b 0

:start_application
call :ensure_dependencies
if not "%ERRORLEVEL%"=="0" exit /b 1

echo Reiniciando a aplicacao...
call :log "Reinicio completo solicitado."
call :stop_application >nul

call :start_backend
if not "%ERRORLEVEL%"=="0" exit /b 1
call :start_frontend
if not "%ERRORLEVEL%"=="0" (
  call :log "Falha ao iniciar o frontend. Encerrando backend para evitar estado parcial."
  call :stop_component "Backend" "%BACKEND_PID_FILE%" "%BACKEND_PORT%" "backend" >nul
  exit /b 1
)
call :show_status
exit /b 0

:start_backend
echo Iniciando backend...
call :log "Iniciando backend."

set "BACKEND_DATABASE_URL=%ALBERTINA_DATABASE_URL%"
if "%BACKEND_DATABASE_URL%"=="" set "BACKEND_DATABASE_URL=%DEFAULT_ALBERTINA_DATABASE_URL%"
set "BACKEND_OLIST_CLIENT_ID=%OLIST_CLIENT_ID%"
if "%BACKEND_OLIST_CLIENT_ID%"=="" set "BACKEND_OLIST_CLIENT_ID=%DEFAULT_OLIST_CLIENT_ID%"
set "BACKEND_OLIST_REDIRECT_URI=%OLIST_REDIRECT_URI%"
if "%BACKEND_OLIST_REDIRECT_URI%"=="" set "BACKEND_OLIST_REDIRECT_URI=%DEFAULT_OLIST_REDIRECT_URI%"
set "ALBERTINA_DATABASE_URL=%BACKEND_DATABASE_URL%"
set "OLIST_CLIENT_ID=%BACKEND_OLIST_CLIENT_ID%"
set "OLIST_REDIRECT_URI=%BACKEND_OLIST_REDIRECT_URI%"

set "BACKEND_PID="
set "BACKEND_WAIT_RESULT="
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -WindowStyle Hidden -FilePath 'python' -WorkingDirectory '%APP_ROOT%' -ArgumentList '-m','uvicorn','app:app','--app-dir','%APP_ROOT%\backend','--host','127.0.0.1','--port','8000' -RedirectStandardOutput '%BACKEND_RUNTIME_LOG%' -RedirectStandardError '%BACKEND_RUNTIME_ERR_LOG%'" >nul 2>&1
call :wait_for_port "%BACKEND_PORT%" %START_WAIT_SECONDS%
set "BACKEND_WAIT_RESULT=%ERRORLEVEL%"
call :get_pid_from_port "%BACKEND_PORT%" BACKEND_PID

if not "%BACKEND_WAIT_RESULT%"=="0" (
  if not "%BACKEND_PID%"=="" call :kill_pid_tree "%BACKEND_PID%" "Backend"
  echo Falha ao iniciar o backend na porta %BACKEND_PORT%.
  call :log "Falha ao iniciar o backend na porta %BACKEND_PORT%."
  exit /b 1
)

if "%BACKEND_PID%"=="" (
  echo Falha ao iniciar o backend.
  call :log "Falha ao iniciar o backend."
  exit /b 1
)

>%BACKEND_PID_FILE% echo %BACKEND_PID%
call :log "Backend iniciado com PID %BACKEND_PID%."
exit /b 0

:start_frontend
echo Iniciando frontend...
call :log "Iniciando frontend."

set "FRONTEND_API_BASE_URL=%VITE_API_BASE_URL%"
if "%FRONTEND_API_BASE_URL%"=="" set "FRONTEND_API_BASE_URL=%DEFAULT_VITE_API_BASE_URL%"
set "VITE_API_BASE_URL=%FRONTEND_API_BASE_URL%"
set "FRONTEND_PID="
set "FRONTEND_WAIT_RESULT="
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -WindowStyle Hidden -FilePath 'npm.cmd' -WorkingDirectory '%APP_ROOT%\frontend' -ArgumentList 'run','dev','--','--host','127.0.0.1','--port','3500','--strictPort' -RedirectStandardOutput '%FRONTEND_RUNTIME_LOG%' -RedirectStandardError '%FRONTEND_RUNTIME_ERR_LOG%'" >nul 2>&1
call :wait_for_port "%FRONTEND_PORT%" %START_WAIT_SECONDS%
set "FRONTEND_WAIT_RESULT=%ERRORLEVEL%"
call :get_pid_from_port "%FRONTEND_PORT%" FRONTEND_PID

if not "%FRONTEND_WAIT_RESULT%"=="0" (
  if not "%FRONTEND_PID%"=="" call :kill_pid_tree "%FRONTEND_PID%" "Frontend"
  echo Falha ao iniciar o frontend na porta %FRONTEND_PORT%.
  call :log "Falha ao iniciar o frontend na porta %FRONTEND_PORT%."
  exit /b 1
)

if "%FRONTEND_PID%"=="" (
  echo Falha ao iniciar o frontend.
  call :log "Falha ao iniciar o frontend."
  exit /b 1
)

>%FRONTEND_PID_FILE% echo %FRONTEND_PID%
call :log "Frontend iniciado com PID %FRONTEND_PID%."
exit /b 0

:stop_application
call :stop_component "Frontend" "%FRONTEND_PID_FILE%" "%FRONTEND_PORT%" "frontend"
call :stop_component "Backend" "%BACKEND_PID_FILE%" "%BACKEND_PORT%" "backend"
call :show_status
exit /b 0

:stop_component
set "LABEL=%~1"
set "PID_FILE=%~2"
set "PORT=%~3"
set "KIND=%~4"
set "PID="

if exist "%PID_FILE%" set /p PID=<"%PID_FILE%"

if not "%PID%"=="" (
  call :kill_pid_tree "%PID%" "%LABEL%"
  call :log "%LABEL%: tentativa de encerramento da arvore do PID %PID%."
)

call :get_pid_from_port "%PORT%" PORT_PID
if not "%PORT_PID%"=="" (
  call :kill_pid_tree "%PORT_PID%" "%LABEL%"
  call :log "%LABEL%: processo da porta %PORT% encerrado via PID %PORT_PID%."
)

call :stop_related_processes "%KIND%"

if exist "%PID_FILE%" del /f /q "%PID_FILE%" >nul 2>&1

call :wait_for_port_down "%PORT%" 8
if "%ERRORLEVEL%"=="0" (
  echo %LABEL% encerrado.
  call :log "%LABEL% encerrado."
  exit /b 0
)

echo %LABEL% ainda responde na porta %PORT%.
call :log "%LABEL% permaneceu ativo na porta %PORT% apos a tentativa de encerramento."
exit /b 1

:cleanup_stale_pid
set "PID_FILE=%~1"
set "PORT=%~2"
set "KIND=%~3"
if not exist "%PID_FILE%" exit /b 0

set "PID="
set /p PID=<"%PID_FILE%"

if not "%PID%"=="" (
  call :is_pid_running "%PID%"
  if not "%ERRORLEVEL%"=="0" (
    del /f /q "%PID_FILE%" >nul 2>&1
    exit /b 0
  )
)

call :is_port_listening "%PORT%"
if "%ERRORLEVEL%"=="0" exit /b 0

if not "%PID%"=="" call :kill_pid_tree "%PID%" "%KIND%"
call :stop_related_processes "%KIND%"
del /f /q "%PID_FILE%" >nul 2>&1
exit /b 0

:ensure_dependencies
where python >nul 2>&1
if not "%ERRORLEVEL%"=="0" (
  echo Python nao foi encontrado no PATH. Instale o Python para iniciar o backend.
  call :log "Python nao encontrado no PATH."
  exit /b 1
)

where npm >nul 2>&1
if not "%ERRORLEVEL%"=="0" (
  echo NPM nao foi encontrado no PATH. Instale Node.js com NPM para iniciar o frontend.
  call :log "NPM nao encontrado no PATH."
  exit /b 1
)

exit /b 0

:is_port_listening
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -LocalPort %~1 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
exit /b %ERRORLEVEL%

:get_pid_from_port
set "%~2="
for /f %%P in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$conn = Get-NetTCPConnection -LocalPort %~1 -State Listen -ErrorAction SilentlyContinue; if ($conn) { $conn | Select-Object -ExpandProperty OwningProcess -Unique | Select-Object -First 1 }"') do set "%~2=%%P"
exit /b 0

:is_pid_running
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-Process -Id %~1 -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
exit /b %ERRORLEVEL%

:kill_pid_tree
set "TARGET_PID=%~1"
set "TARGET_LABEL=%~2"
if "%TARGET_PID%"=="" exit /b 0
taskkill /PID %TARGET_PID% /T /F >nul 2>&1
call :log "%TARGET_LABEL%: taskkill /T executado para o PID %TARGET_PID%."
exit /b 0

:stop_related_processes
set "KIND=%~1"
if /I "%KIND%"=="backend" goto stop_related_backend
if /I "%KIND%"=="frontend" goto stop_related_frontend
exit /b 0

:stop_related_backend
for /f %%P in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$backendRoot = [regex]::Escape('%APP_ROOT%\backend'); $procIds = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -and $_.CommandLine -match 'uvicorn' -and (($_.CommandLine -match 'backend\.app:app') -or ($_.CommandLine -match 'app:app' -and $_.CommandLine -match $backendRoot)) } | Select-Object -ExpandProperty ProcessId -Unique; foreach ($procId in $procIds) { Write-Output $procId }"') do call :kill_pid_tree "%%P" "Backend relacionado"
exit /b 0

:stop_related_frontend
for /f %%P in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$frontRoot = [regex]::Escape('%APP_ROOT%\frontend'); $procIds = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -and $_.CommandLine -match $frontRoot -and $_.CommandLine -match 'vite|npm(\.cmd)?\s+run\s+dev' } | Select-Object -ExpandProperty ProcessId -Unique; foreach ($procId in $procIds) { Write-Output $procId }"') do call :kill_pid_tree "%%P" "Frontend relacionado"
exit /b 0

:wait_for_port
set /a WAIT_RETRIES=%~2
:wait_for_port_loop
call :is_port_listening "%~1"
if "%ERRORLEVEL%"=="0" exit /b 0
if %WAIT_RETRIES% LEQ 0 exit /b 1
set /a WAIT_RETRIES-=1
timeout /t 1 /nobreak >nul
goto wait_for_port_loop

:wait_for_port_down
set /a WAIT_RETRIES=%~2
:wait_for_port_down_loop
call :is_port_listening "%~1"
if not "%ERRORLEVEL%"=="0" exit /b 0
if %WAIT_RETRIES% LEQ 0 exit /b 1
set /a WAIT_RETRIES-=1
timeout /t 1 /nobreak >nul
goto wait_for_port_down_loop

:log
echo [%date% %time%] %~1>>"%LOG_FILE%"
exit /b 0
