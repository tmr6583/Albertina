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
set "DEFAULT_ALBERTINA_DATABASE_URL=postgresql://postgres:Esquilo08!!!@db.zbdgxbktblttarkradmk.supabase.co:6543/postgres?sslmode=require"
set "DEFAULT_OLIST_CLIENT_ID=tiny-api-5a6c6021a81d09b280ca8f1f4e685b6107fc4d3e-1776458496"
set "DEFAULT_OLIST_REDIRECT_URI=http://localhost:3500/olist/callback"

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
call :cleanup_stale_pid "%BACKEND_PID_FILE%" "%BACKEND_PORT%"
call :cleanup_stale_pid "%FRONTEND_PID_FILE%" "%FRONTEND_PORT%"
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

call :start_backend
call :start_frontend
call :show_status
exit /b 0

:start_backend
call :is_port_listening "%BACKEND_PORT%"
if "%ERRORLEVEL%"=="0" (
  echo Backend ja esta em execucao.
  call :log "Backend ja estava em execucao."
  exit /b 0
)

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
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -WindowStyle Hidden -FilePath 'python' -WorkingDirectory '%APP_ROOT%' -ArgumentList '-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8000' -RedirectStandardOutput '%BACKEND_RUNTIME_LOG%' -RedirectStandardError '%BACKEND_RUNTIME_ERR_LOG%'" >nul 2>&1
call :wait_for_port "%BACKEND_PORT%" 12
call :get_pid_from_port "%BACKEND_PORT%" BACKEND_PID

if "%BACKEND_PID%"=="" (
  echo Falha ao iniciar o backend.
  call :log "Falha ao iniciar o backend."
  exit /b 1
)

>%BACKEND_PID_FILE% echo %BACKEND_PID%
call :log "Backend iniciado com PID %BACKEND_PID%."
timeout /t 2 /nobreak >nul
exit /b 0

:start_frontend
call :is_port_listening "%FRONTEND_PORT%"
if "%ERRORLEVEL%"=="0" (
  echo Frontend ja esta em execucao.
  call :log "Frontend ja estava em execucao."
  exit /b 0
)

echo Iniciando frontend...
call :log "Iniciando frontend."

set "FRONTEND_PID="
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -WindowStyle Hidden -FilePath 'npm.cmd' -WorkingDirectory '%APP_ROOT%\frontend' -ArgumentList 'run','dev' -RedirectStandardOutput '%FRONTEND_RUNTIME_LOG%' -RedirectStandardError '%FRONTEND_RUNTIME_ERR_LOG%'" >nul 2>&1
call :wait_for_port "%FRONTEND_PORT%" 12
call :get_pid_from_port "%FRONTEND_PORT%" FRONTEND_PID

if "%FRONTEND_PID%"=="" (
  echo Falha ao iniciar o frontend.
  call :log "Falha ao iniciar o frontend."
  exit /b 1
)

>%FRONTEND_PID_FILE% echo %FRONTEND_PID%
call :log "Frontend iniciado com PID %FRONTEND_PID%."
exit /b 0

:stop_application
call :stop_component "Backend" "%BACKEND_PID_FILE%" "%BACKEND_PORT%"
call :stop_component "Frontend" "%FRONTEND_PID_FILE%" "%FRONTEND_PORT%"
call :show_status
exit /b 0

:stop_component
set "LABEL=%~1"
set "PID_FILE=%~2"
set "PORT=%~3"
set "PID="

if exist "%PID_FILE%" set /p PID=<"%PID_FILE%"

if not "%PID%"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Stop-Process -Id %PID% -Force -ErrorAction Stop } catch {}" >nul 2>&1
  call :log "%LABEL%: tentativa de encerramento do PID %PID%."
)

call :get_pid_from_port "%PORT%" PORT_PID
if not "%PORT_PID%"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Stop-Process -Id %PORT_PID% -Force -ErrorAction Stop } catch {}" >nul 2>&1
  call :log "%LABEL%: processo da porta %PORT% encerrado via PID %PORT_PID%."
)

if exist "%PID_FILE%" del /f /q "%PID_FILE%" >nul 2>&1

call :is_port_listening "%PORT%"
if "%ERRORLEVEL%"=="0" (
  echo %LABEL% ainda responde na porta %PORT%.
  call :log "%LABEL% permaneceu ativo na porta %PORT% apos a tentativa de encerramento."
  exit /b 1
)

echo %LABEL% encerrado.
call :log "%LABEL% encerrado."
exit /b 0

:cleanup_stale_pid
set "PID_FILE=%~1"
set "PORT=%~2"
if not exist "%PID_FILE%" exit /b 0

call :is_port_listening "%PORT%"
if "%ERRORLEVEL%"=="0" exit /b 0

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

:wait_for_port
set /a WAIT_RETRIES=%~2
:wait_for_port_loop
call :is_port_listening "%~1"
if "%ERRORLEVEL%"=="0" exit /b 0
if %WAIT_RETRIES% LEQ 0 exit /b 1
set /a WAIT_RETRIES-=1
timeout /t 1 /nobreak >nul
goto wait_for_port_loop

:log
echo [%date% %time%] %~1>>"%LOG_FILE%"
exit /b 0
