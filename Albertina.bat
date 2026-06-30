@echo off
setlocal EnableExtensions DisableDelayedExpansion

REM ============================================================
REM Albertina - Controle de Aplicacao Windows
REM Metodo: .BAT robusto para start/stop/status local no Windows
REM
REM AVISO:
REM - As acoes start, stop, restart, status e install-deps normalmente
REM   NAO exigem Administrator.
REM - As acoes install-nssm e remove-nssm exigem prompt elevado
REM   como Administrator.
REM - Para PM2 e NSSM, instale previamente a ferramenta se ela nao existir.
REM ============================================================

REM ============================================================
REM [1] Caminhos absolutos e nomes de recursos
REM ============================================================

set "SCRIPT_FULL_PATH=%~f0"
for %%I in ("%SCRIPT_FULL_PATH%") do set "APP_ROOT=%%~dpI"
if "%APP_ROOT:~-1%"=="\" set "APP_ROOT=%APP_ROOT:~0,-1%"

set "BACKEND_DIR=%APP_ROOT%\backend"
set "FRONTEND_DIR=%APP_ROOT%\frontend"

set "BACKEND_HOST=127.0.0.1"
set "BACKEND_PORT=8000"
set "FRONTEND_HOST=127.0.0.1"
set "FRONTEND_PORT=3500"

set "BACKEND_URL=http://%BACKEND_HOST%:%BACKEND_PORT%/api/health"
set "FRONTEND_URL=http://%FRONTEND_HOST%:%FRONTEND_PORT%"

set "START_WAIT_SECONDS=45"
set "STOP_WAIT_SECONDS=20"

set "LOG_FILE=%APP_ROOT%\Albertina.log"
set "BACKEND_RUNTIME_LOG=%APP_ROOT%\Albertina.backend.log"
set "BACKEND_RUNTIME_ERR_LOG=%APP_ROOT%\Albertina.backend.err.log"
set "FRONTEND_RUNTIME_LOG=%APP_ROOT%\Albertina.frontend.log"
set "FRONTEND_RUNTIME_ERR_LOG=%APP_ROOT%\Albertina.frontend.err.log"
set "BACKEND_PID_FILE=%APP_ROOT%\Albertina.backend.pid"
set "FRONTEND_PID_FILE=%APP_ROOT%\Albertina.frontend.pid"
set "FRONTEND_BUILD_DIR=%FRONTEND_DIR%\dist"

set "NSSM_BACKEND_SERVICE=AlbertinaBackend"
set "NSSM_FRONTEND_SERVICE=AlbertinaFrontend"
set "PM2_BACKEND_APP=AlbertinaBackend"
set "PM2_FRONTEND_APP=AlbertinaFrontend"

REM ============================================================
REM [2] Executaveis padrao e autodeteccao de runtime
REM ============================================================

set "DEFAULT_NODE_EXE=C:\Program Files\nodejs\node.exe"
set "DEFAULT_NPM_CMD=C:\Program Files\nodejs\npm.cmd"
set "DEFAULT_PYTHON_EXE=C:\Program Files\Python312\python.exe"

call :resolve_runtime_paths || exit /b 1

REM ============================================================
REM [3] Variaveis de ambiente da aplicacao
REM ============================================================

set "DEFAULT_ALBERTINA_DATABASE_URL=postgresql://postgres:Esquilo08!!!@db.zbdgxbktblttarkradmk.supabase.co:6543/postgres?sslmode=require"
set "DEFAULT_OLIST_CLIENT_ID=tiny-api-5a6c6021a81d09b280ca8f1f4e685b6107fc4d3e-1776458496"
set "DEFAULT_OLIST_REDIRECT_URI=http://localhost:3500/olist/callback"
set "DEFAULT_VITE_API_BASE_URL=http://localhost:8000/api"

if "%ALBERTINA_DATABASE_URL%"=="" set "ALBERTINA_DATABASE_URL=%DEFAULT_ALBERTINA_DATABASE_URL%"
if "%OLIST_CLIENT_ID%"=="" set "OLIST_CLIENT_ID=%DEFAULT_OLIST_CLIENT_ID%"
if "%OLIST_REDIRECT_URI%"=="" set "OLIST_REDIRECT_URI=%DEFAULT_OLIST_REDIRECT_URI%"
if "%VITE_API_BASE_URL%"=="" set "VITE_API_BASE_URL=%DEFAULT_VITE_API_BASE_URL%"

for %%I in ("%NODE_EXE%") do set "NODE_DIR=%%~dpI"
if "%NODE_DIR:~-1%"=="\" set "NODE_DIR=%NODE_DIR:~0,-1%"
set "PATH=%NODE_DIR%;%PATH%"

if not exist "%LOG_FILE%" type nul > "%LOG_FILE%" || exit /b 1
call :log "Script iniciado. Acao=%~1"

REM ============================================================
REM [4] Rotas CLI
REM ============================================================

if /I "%~1"=="status" goto cli_status
if /I "%~1"=="iniciar" goto cli_start
if /I "%~1"=="start" goto cli_start
if /I "%~1"=="reiniciar" goto cli_restart
if /I "%~1"=="restart" goto cli_restart
if /I "%~1"=="encerrar" goto cli_stop
if /I "%~1"=="stop" goto cli_stop
if /I "%~1"=="install-deps" goto cli_install_deps
if /I "%~1"=="install-pm2" goto cli_install_pm2
if /I "%~1"=="remove-pm2" goto cli_remove_pm2
if /I "%~1"=="install-nssm" goto cli_install_nssm
if /I "%~1"=="remove-nssm" goto cli_remove_nssm

goto menu

REM ============================================================
REM [5] Menu interativo
REM ============================================================

:menu
cls
echo ============================================================
echo Albertina - Controle da Aplicacao
echo ============================================================
echo.
call :show_runtime_summary || exit /b 1
echo.
call :show_status || exit /b 1
echo.
echo Ver status volta ao menu; acoes operacionais liberam o prompt.
echo.
echo [1] Ver status
echo [2] Iniciar aplicacao
echo [3] Encerrar aplicacao
echo [4] Reiniciar aplicacao
echo [5] Instalar dependencias
echo [0] Sair
echo.
set "choice="
set /p "choice=Selecione uma opcao: "

if "%choice%"=="1" goto option_status
if "%choice%"=="2" goto option_start
if "%choice%"=="3" goto option_stop
if "%choice%"=="4" goto option_restart
if "%choice%"=="5" goto option_install_deps
if "%choice%"=="0" goto option_exit

echo.
echo Opcao invalida.
call :log "Opcao invalida: %choice%"
pause
goto menu

:option_status
call :show_status || exit /b 1
echo.
echo Pressione qualquer tecla para voltar ao menu.
pause >nul
goto menu

:option_start
call :start_application || (
  echo.
  echo Falha ao iniciar a aplicacao. Consulte os logs em "%APP_ROOT%".
  echo Pressione qualquer tecla para voltar ao menu.
  pause >nul
  goto menu
)
exit /b 0

:option_stop
call :stop_application || (
  echo.
  echo Falha ao encerrar completamente. Consulte os logs em "%APP_ROOT%".
  echo Pressione qualquer tecla para voltar ao menu.
  pause >nul
  goto menu
)
exit /b 0

:option_restart
call :restart_application || (
  echo.
  echo Falha ao reiniciar a aplicacao. Consulte os logs em "%APP_ROOT%".
  echo Pressione qualquer tecla para voltar ao menu.
  pause >nul
  goto menu
)
exit /b 0

:option_install_deps
call :install_dependencies || (
  echo.
  echo Falha ao instalar dependencias.
  echo Pressione qualquer tecla para voltar ao menu.
  pause >nul
  goto menu
)
exit /b 0

:option_exit
call :log "Menu fechado pelo usuario."
echo.
echo Menu fechado. Processos ja iniciados permanecem em execucao.
exit /b 0

REM ============================================================
REM [6] Entrada CLI
REM ============================================================

:cli_status
call :show_status || exit /b 1
exit /b 0

:cli_start
call :start_application || exit /b 1
exit /b 0

:cli_restart
call :restart_application || exit /b 1
exit /b 0

:cli_stop
call :stop_application || exit /b 1
exit /b 0

:cli_install_deps
call :install_dependencies || exit /b 1
exit /b 0

:cli_install_pm2
call :install_pm2 || exit /b 1
exit /b 0

:cli_remove_pm2
call :remove_pm2 || exit /b 1
exit /b 0

:cli_install_nssm
call :install_nssm || exit /b 1
exit /b 0

:cli_remove_nssm
call :remove_nssm || exit /b 1
exit /b 0

REM ============================================================
REM [7] Status e resumo
REM ============================================================

:show_runtime_summary
echo Runtime detectado:
echo - Node   : %NODE_EXE%
echo - NPM    : %NPM_CMD%
echo - Python : %PYTHON_EXE%
exit /b 0

:show_status
call :cleanup_stale_pid "%BACKEND_PID_FILE%" "%BACKEND_PORT%" "Backend" || exit /b 1
call :cleanup_stale_pid "%FRONTEND_PID_FILE%" "%FRONTEND_PORT%" "Frontend" || exit /b 1
echo Status da aplicacao:
call :print_component_status "Backend" "%BACKEND_PID_FILE%" "%BACKEND_PORT%" "%BACKEND_URL%" || exit /b 1
call :print_component_status "Frontend" "%FRONTEND_PID_FILE%" "%FRONTEND_PORT%" "%FRONTEND_URL%" || exit /b 1
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
    echo - %LABEL%: Em execucao na porta %PORT% ^(PID monitorado: %PID%^)
  ) else (
    echo - %LABEL%: Em execucao na porta %PORT%
  )
  echo   URL: %URL%
  exit /b 0
)

if not "%PID%"=="" (
  echo - %LABEL%: PID registrado, mas porta %PORT% nao esta ativa ^(PID: %PID%^)
  exit /b 0
)

echo - %LABEL%: Parado
exit /b 0

REM ============================================================
REM [8] Inicializacao, reinicio e encerramento
REM ============================================================

:start_application
echo.
echo Iniciando Albertina...
call :log "Inicio solicitado."
call :ensure_prerequisites || exit /b 1
call :stop_application_silent || exit /b 1
call :start_backend || exit /b 1
call :start_frontend || (
  call :log "Falha ao iniciar frontend; encerrando backend para evitar estado parcial."
  call :stop_component "Backend" "%BACKEND_PID_FILE%" "%BACKEND_PORT%" "backend" >nul 2>&1
  exit /b 1
)
echo.
call :show_status || exit /b 1
exit /b 0

:restart_application
echo.
echo Reiniciando Albertina...
call :log "Reinicio solicitado."
call :start_application || exit /b 1
exit /b 0

:stop_application
echo.
echo Encerrando Albertina...
call :log "Encerramento solicitado."
call :stop_component "Frontend" "%FRONTEND_PID_FILE%" "%FRONTEND_PORT%" "frontend" || exit /b 1
call :stop_component "Backend" "%BACKEND_PID_FILE%" "%BACKEND_PORT%" "backend" || exit /b 1
echo.
call :show_status || exit /b 1
exit /b 0

:stop_application_silent
call :stop_component "Frontend" "%FRONTEND_PID_FILE%" "%FRONTEND_PORT%" "frontend" >nul 2>&1
call :stop_component "Backend" "%BACKEND_PID_FILE%" "%BACKEND_PORT%" "backend" >nul 2>&1
exit /b 0

:start_backend
echo.
echo Iniciando backend...
call :log "Iniciando backend."

set "BACKEND_START_PID="
set "BACKEND_PID="

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Start-Process -WindowStyle Hidden -FilePath '%PYTHON_EXE%' -WorkingDirectory '%BACKEND_DIR%' -ArgumentList '-m','uvicorn','app:app','--host','%BACKEND_HOST%','--port','%BACKEND_PORT%' -RedirectStandardOutput '%BACKEND_RUNTIME_LOG%' -RedirectStandardError '%BACKEND_RUNTIME_ERR_LOG%' -PassThru; $p.Id" > "%BACKEND_PID_FILE%.tmp" 2>nul || exit /b 1

set /p BACKEND_START_PID=<"%BACKEND_PID_FILE%.tmp"
del /f /q "%BACKEND_PID_FILE%.tmp" >nul 2>&1

call :wait_for_http "%BACKEND_URL%" "%START_WAIT_SECONDS%"
if not "%ERRORLEVEL%"=="0" (
  if not "%BACKEND_START_PID%"=="" call :terminate_pid_tree "%BACKEND_START_PID%" "Backend"
  echo Falha ao iniciar o backend em %BACKEND_URL%.
  echo Verifique: "%BACKEND_RUNTIME_ERR_LOG%"
  call :log "Falha ao iniciar backend."
  exit /b 1
)

call :get_pid_from_port "%BACKEND_PORT%" BACKEND_PID || exit /b 1
if "%BACKEND_PID%"=="" set "BACKEND_PID=%BACKEND_START_PID%"
if "%BACKEND_PID%"=="" (
  echo Backend subiu, mas nao foi possivel identificar o PID.
  call :log "Backend sem PID identificado."
  exit /b 1
)

>"%BACKEND_PID_FILE%" echo %BACKEND_PID% || exit /b 1
call :log "Backend iniciado com PID %BACKEND_PID%."
exit /b 0

:start_frontend
echo.
echo Iniciando frontend...
call :log "Iniciando frontend."
call :prepare_frontend_runtime || exit /b 1

set "FRONTEND_START_PID="
set "FRONTEND_PID="

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Start-Process -WindowStyle Hidden -FilePath '%NPM_CMD%' -WorkingDirectory '%FRONTEND_DIR%' -ArgumentList 'run','preview','--','--host','%FRONTEND_HOST%','--port','%FRONTEND_PORT%','--strictPort' -RedirectStandardOutput '%FRONTEND_RUNTIME_LOG%' -RedirectStandardError '%FRONTEND_RUNTIME_ERR_LOG%' -PassThru; $p.Id" > "%FRONTEND_PID_FILE%.tmp" 2>nul || exit /b 1

set /p FRONTEND_START_PID=<"%FRONTEND_PID_FILE%.tmp"
del /f /q "%FRONTEND_PID_FILE%.tmp" >nul 2>&1

call :wait_for_http "%FRONTEND_URL%" "%START_WAIT_SECONDS%"
if not "%ERRORLEVEL%"=="0" (
  if not "%FRONTEND_START_PID%"=="" call :terminate_pid_tree "%FRONTEND_START_PID%" "Frontend"
  echo Falha ao iniciar o frontend em %FRONTEND_URL%.
  echo Verifique: "%FRONTEND_RUNTIME_ERR_LOG%"
  call :log "Falha ao iniciar frontend."
  exit /b 1
)

call :get_pid_from_port "%FRONTEND_PORT%" FRONTEND_PID || exit /b 1
if "%FRONTEND_PID%"=="" set "FRONTEND_PID=%FRONTEND_START_PID%"
if "%FRONTEND_PID%"=="" (
  echo Frontend subiu, mas nao foi possivel identificar o PID.
  call :log "Frontend sem PID identificado."
  exit /b 1
)

>"%FRONTEND_PID_FILE%" echo %FRONTEND_PID% || exit /b 1
call :log "Frontend iniciado com PID %FRONTEND_PID%."
exit /b 0

:stop_component
set "LABEL=%~1"
set "PID_FILE=%~2"
set "PORT=%~3"
set "KIND=%~4"
set "PID="
set "PORT_PID="

if exist "%PID_FILE%" set /p PID=<"%PID_FILE%"
call :get_pid_from_port "%PORT%" PORT_PID || exit /b 1

if "%PID%"=="" if "%PORT_PID%"=="" (
  if exist "%PID_FILE%" del /f /q "%PID_FILE%" >nul 2>&1
  echo %LABEL% ja esta parado.
  call :log "%LABEL% ja estava parado."
  exit /b 0
)

if not "%PID%"=="" call :terminate_pid_tree "%PID%" "%LABEL%" || exit /b 1
if not "%PORT_PID%"=="" if not "%PORT_PID%"=="%PID%" call :terminate_pid_tree "%PORT_PID%" "%LABEL% porta %PORT%" || exit /b 1

call :stop_related_processes "%KIND%" || exit /b 1
if exist "%PID_FILE%" del /f /q "%PID_FILE%" >nul 2>&1

call :wait_for_port_down "%PORT%" "%STOP_WAIT_SECONDS%"
if "%ERRORLEVEL%"=="0" (
  echo %LABEL% encerrado.
  call :log "%LABEL% encerrado."
  exit /b 0
)

echo %LABEL% ainda responde na porta %PORT%.
call :log "%LABEL% ainda ativo na porta %PORT%."
exit /b 1

REM ============================================================
REM [9] Validacoes e instalacao de dependencias
REM ============================================================

:ensure_prerequisites
call :ensure_paths || exit /b 1
call :ensure_runtime_binaries || exit /b 1
call :ensure_backend_dependencies || exit /b 1
call :ensure_frontend_dependencies || exit /b 1
exit /b 0

:ensure_paths
if not exist "%BACKEND_DIR%" (
  echo Diretorio backend nao encontrado: "%BACKEND_DIR%"
  call :log "Diretorio backend nao encontrado."
  exit /b 1
)
if not exist "%FRONTEND_DIR%" (
  echo Diretorio frontend nao encontrado: "%FRONTEND_DIR%"
  call :log "Diretorio frontend nao encontrado."
  exit /b 1
)
if not exist "%BACKEND_DIR%\requirements.txt" (
  echo Arquivo requirements.txt nao encontrado em "%BACKEND_DIR%".
  call :log "requirements.txt ausente."
  exit /b 1
)
if not exist "%FRONTEND_DIR%\package.json" (
  echo Arquivo package.json nao encontrado em "%FRONTEND_DIR%".
  call :log "package.json ausente."
  exit /b 1
)
exit /b 0

:ensure_runtime_binaries
"%NODE_EXE%" --version >nul 2>&1 || (
  echo Node.js foi localizado, mas nao executou corretamente: "%NODE_EXE%"
  call :log "Falha ao executar node --version."
  exit /b 1
)
"%NPM_CMD%" --version >nul 2>&1 || (
  echo NPM foi localizado, mas nao executou corretamente: "%NPM_CMD%"
  call :log "Falha ao executar npm --version."
  exit /b 1
)
"%PYTHON_EXE%" --version >nul 2>&1 || (
  echo Python foi localizado, mas nao executou corretamente: "%PYTHON_EXE%"
  call :log "Falha ao executar python --version."
  exit /b 1
)
exit /b 0

:ensure_backend_dependencies
"%PYTHON_EXE%" -c "import fastapi,uvicorn,psycopg,requests,sqlalchemy,pandas" >nul 2>&1 && exit /b 0
call :log "Dependencias Python ausentes; instalacao automatica iniciada."
echo Instalando dependencias do backend...
"%PYTHON_EXE%" -m pip install -r "%BACKEND_DIR%\requirements.txt" || (
  echo Falha ao instalar dependencias Python.
  call :log "Falha ao instalar dependencias Python."
  exit /b 1
)
"%PYTHON_EXE%" -c "import fastapi,uvicorn,psycopg,requests,sqlalchemy,pandas" >nul 2>&1 || (
  echo Dependencias Python continuam indisponiveis apos a instalacao.
  call :log "Dependencias Python continuam indisponiveis."
  exit /b 1
)
exit /b 0

:ensure_frontend_dependencies
call "%NPM_CMD%" --prefix "%FRONTEND_DIR%" exec vite -- --version >nul 2>&1 && exit /b 0
call :log "Dependencias Node.js ausentes; instalacao automatica iniciada."
echo Instalando dependencias do frontend...
call "%NPM_CMD%" --prefix "%FRONTEND_DIR%" install || (
  echo Falha ao instalar dependencias do frontend.
  call :log "Falha ao instalar dependencias do frontend."
  exit /b 1
)
call "%NPM_CMD%" --prefix "%FRONTEND_DIR%" exec vite -- --version >nul 2>&1 || (
  echo Dependencias do frontend continuam indisponiveis apos a instalacao.
  call :log "Dependencias do frontend continuam indisponiveis."
  exit /b 1
)
exit /b 0

:prepare_frontend_runtime
echo Compilando frontend para runtime estavel...
call :log "Gerando build do frontend para runtime estavel."
call "%NPM_CMD%" --prefix "%FRONTEND_DIR%" run build || (
  echo Falha ao gerar o build do frontend.
  call :log "Falha ao gerar build do frontend."
  exit /b 1
)
if not exist "%FRONTEND_BUILD_DIR%\index.html" (
  echo Build do frontend concluido sem gerar "%FRONTEND_BUILD_DIR%\index.html".
  call :log "Build do frontend sem artefato principal."
  exit /b 1
)
call :log "Build do frontend concluido."
exit /b 0

:install_dependencies
echo.
echo Instalando dependencias...
call :ensure_paths || exit /b 1
call :ensure_runtime_binaries || exit /b 1
echo - Backend
"%PYTHON_EXE%" -m pip install -r "%BACKEND_DIR%\requirements.txt" || exit /b 1
echo - Frontend
call "%NPM_CMD%" --prefix "%FRONTEND_DIR%" install || exit /b 1
echo - Build frontend estavel
call :prepare_frontend_runtime || exit /b 1
call :log "Dependencias instaladas manualmente."
echo Dependencias instaladas com sucesso.
exit /b 0

REM ============================================================
REM [10] PM2 e NSSM
REM ============================================================

:install_pm2
call :ensure_prerequisites || exit /b 1
call :prepare_frontend_runtime || exit /b 1
call :resolve_pm2_cmd || exit /b 1
echo.
echo Instalando processos no PM2...
call "%PM2_CMD%" delete "%PM2_BACKEND_APP%" >nul 2>&1
call "%PM2_CMD%" delete "%PM2_FRONTEND_APP%" >nul 2>&1
call "%PM2_CMD%" start "%PYTHON_EXE%" --name "%PM2_BACKEND_APP%" --cwd "%BACKEND_DIR%" --interpreter none -- -m uvicorn app:app --host %BACKEND_HOST% --port %BACKEND_PORT% || exit /b 1
call "%PM2_CMD%" start "%NPM_CMD%" --name "%PM2_FRONTEND_APP%" --cwd "%FRONTEND_DIR%" --interpreter none -- run preview -- --host %FRONTEND_HOST% --port %FRONTEND_PORT% --strictPort || exit /b 1
call "%PM2_CMD%" save || exit /b 1
call :log "Processos PM2 instalados."
echo Processos registrados no PM2 com sucesso.
echo Se quiser boot automatico com PM2 no Windows, instale e configure o suporte de startup apropriado.
exit /b 0

:remove_pm2
call :resolve_pm2_cmd || exit /b 1
echo.
echo Removendo processos do PM2...
call "%PM2_CMD%" delete "%PM2_BACKEND_APP%" >nul 2>&1
call "%PM2_CMD%" delete "%PM2_FRONTEND_APP%" >nul 2>&1
call "%PM2_CMD%" save >nul 2>&1
call :log "Processos PM2 removidos."
echo Processos removidos do PM2.
exit /b 0

:install_nssm
call :require_admin || exit /b 1
call :ensure_prerequisites || exit /b 1
call :prepare_frontend_runtime || exit /b 1
call :resolve_nssm_exe || exit /b 1
echo.
echo Instalando servicos no NSSM...

"%NSSM_EXE%" remove "%NSSM_BACKEND_SERVICE%" confirm >nul 2>&1
"%NSSM_EXE%" remove "%NSSM_FRONTEND_SERVICE%" confirm >nul 2>&1

"%NSSM_EXE%" install "%NSSM_BACKEND_SERVICE%" "%PYTHON_EXE%" >nul || exit /b 1
"%NSSM_EXE%" set "%NSSM_BACKEND_SERVICE%" AppDirectory "%BACKEND_DIR%" >nul || exit /b 1
"%NSSM_EXE%" set "%NSSM_BACKEND_SERVICE%" AppParameters "-m uvicorn app:app --host %BACKEND_HOST% --port %BACKEND_PORT%" >nul || exit /b 1
"%NSSM_EXE%" set "%NSSM_BACKEND_SERVICE%" AppStdout "%BACKEND_RUNTIME_LOG%" >nul || exit /b 1
"%NSSM_EXE%" set "%NSSM_BACKEND_SERVICE%" AppStderr "%BACKEND_RUNTIME_ERR_LOG%" >nul || exit /b 1
"%NSSM_EXE%" set "%NSSM_BACKEND_SERVICE%" AppEnvironmentExtra "ALBERTINA_DATABASE_URL=%ALBERTINA_DATABASE_URL%" "OLIST_CLIENT_ID=%OLIST_CLIENT_ID%" "OLIST_REDIRECT_URI=%OLIST_REDIRECT_URI%" "VITE_API_BASE_URL=%VITE_API_BASE_URL%" >nul || exit /b 1

"%NSSM_EXE%" install "%NSSM_FRONTEND_SERVICE%" "%NPM_CMD%" >nul || exit /b 1
"%NSSM_EXE%" set "%NSSM_FRONTEND_SERVICE%" AppDirectory "%FRONTEND_DIR%" >nul || exit /b 1
"%NSSM_EXE%" set "%NSSM_FRONTEND_SERVICE%" AppParameters "run preview -- --host %FRONTEND_HOST% --port %FRONTEND_PORT% --strictPort" >nul || exit /b 1
"%NSSM_EXE%" set "%NSSM_FRONTEND_SERVICE%" AppStdout "%FRONTEND_RUNTIME_LOG%" >nul || exit /b 1
"%NSSM_EXE%" set "%NSSM_FRONTEND_SERVICE%" AppStderr "%FRONTEND_RUNTIME_ERR_LOG%" >nul || exit /b 1
"%NSSM_EXE%" set "%NSSM_FRONTEND_SERVICE%" AppEnvironmentExtra "ALBERTINA_DATABASE_URL=%ALBERTINA_DATABASE_URL%" "OLIST_CLIENT_ID=%OLIST_CLIENT_ID%" "OLIST_REDIRECT_URI=%OLIST_REDIRECT_URI%" "VITE_API_BASE_URL=%VITE_API_BASE_URL%" >nul || exit /b 1

"%NSSM_EXE%" start "%NSSM_BACKEND_SERVICE%" >nul 2>&1
"%NSSM_EXE%" start "%NSSM_FRONTEND_SERVICE%" >nul 2>&1

call :log "Servicos NSSM instalados."
echo Servicos NSSM instalados com sucesso.
exit /b 0

:remove_nssm
call :require_admin || exit /b 1
call :resolve_nssm_exe || exit /b 1
echo.
echo Removendo servicos do NSSM...
"%NSSM_EXE%" stop "%NSSM_FRONTEND_SERVICE%" >nul 2>&1
"%NSSM_EXE%" stop "%NSSM_BACKEND_SERVICE%" >nul 2>&1
"%NSSM_EXE%" remove "%NSSM_FRONTEND_SERVICE%" confirm >nul 2>&1 || (
  echo Falha ao remover o servico "%NSSM_FRONTEND_SERVICE%".
  call :log "Falha ao remover servico frontend do NSSM."
  exit /b 1
)
"%NSSM_EXE%" remove "%NSSM_BACKEND_SERVICE%" confirm >nul 2>&1 || (
  echo Falha ao remover o servico "%NSSM_BACKEND_SERVICE%".
  call :log "Falha ao remover servico backend do NSSM."
  exit /b 1
)
call :log "Servicos NSSM removidos."
echo Servicos NSSM removidos com sucesso.
exit /b 0

REM ============================================================
REM [11] Utilitarios de processo, porta e runtime
REM ============================================================

:resolve_runtime_paths
call :resolve_node_exe || exit /b 1
call :resolve_npm_cmd || exit /b 1
call :resolve_python_exe || exit /b 1
exit /b 0

:resolve_node_exe
if not "%NODE_EXE%"=="" if exist "%NODE_EXE%" exit /b 0
if exist "%DEFAULT_NODE_EXE%" (
  set "NODE_EXE=%DEFAULT_NODE_EXE%"
  exit /b 0
)
for /f "delims=" %%I in ('where.exe node.exe 2^>nul') do (
  if exist "%%~fI" (
    set "NODE_EXE=%%~fI"
    exit /b 0
  )
)
echo Node.js nao encontrado.
echo Instale o Node.js para continuar.
exit /b 1

:resolve_npm_cmd
if not "%NPM_CMD%"=="" if exist "%NPM_CMD%" exit /b 0
if exist "%DEFAULT_NPM_CMD%" (
  set "NPM_CMD=%DEFAULT_NPM_CMD%"
  exit /b 0
)
for /f "delims=" %%I in ('where.exe npm.cmd 2^>nul') do (
  if exist "%%~fI" (
    set "NPM_CMD=%%~fI"
    exit /b 0
  )
)
echo npm.cmd nao encontrado.
echo Instale o Node.js e o NPM para continuar.
exit /b 1

:resolve_python_exe
if not "%PYTHON_EXE%"=="" if exist "%PYTHON_EXE%" exit /b 0
if exist "%DEFAULT_PYTHON_EXE%" (
  set "PYTHON_EXE=%DEFAULT_PYTHON_EXE%"
  exit /b 0
)
for /f "delims=" %%I in ('py -c "import sys; print(sys.executable)" 2^>nul') do (
  if exist "%%~fI" (
    set "PYTHON_EXE=%%~fI"
    exit /b 0
  )
)
for /f "delims=" %%I in ('where.exe python.exe 2^>nul') do (
  if exist "%%~fI" (
    set "PYTHON_EXE=%%~fI"
    exit /b 0
  )
)
echo Python nao encontrado.
echo Instale o Python 3 para continuar.
exit /b 1

:resolve_pm2_cmd
if not "%PM2_CMD%"=="" if exist "%PM2_CMD%" exit /b 0
for /f "delims=" %%I in ('where.exe pm2.cmd 2^>nul') do (
  if exist "%%~fI" (
    set "PM2_CMD=%%~fI"
    exit /b 0
  )
)
echo PM2 nao encontrado.
echo Instale com: npm install -g pm2
exit /b 1

:resolve_nssm_exe
if not "%NSSM_EXE%"=="" if exist "%NSSM_EXE%" exit /b 0
for /f "delims=" %%I in ('where.exe nssm.exe 2^>nul') do (
  if exist "%%~fI" (
    set "NSSM_EXE=%%~fI"
    exit /b 0
  )
)
echo NSSM nao encontrado.
echo Instale o NSSM para usar os comandos install-nssm e remove-nssm.
exit /b 1

:require_admin
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$current = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent()); if ($current.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { exit 0 } else { exit 1 }" >nul 2>&1
if "%ERRORLEVEL%"=="0" exit /b 0
echo Esta acao requer Administrator.
call :log "Acao bloqueada por falta de Administrator."
exit /b 1

:is_port_listening
for /f "tokens=5" %%P in ('netstat -ano -p TCP ^| findstr /R /C:":%~1 .*LISTENING"') do exit /b 0
exit /b 1

:get_pid_from_port
set "%~2="
for /f "tokens=5" %%P in ('netstat -ano -p TCP ^| findstr /R /C:":%~1 .*LISTENING"') do (
  set "%~2=%%P"
  exit /b 0
)
exit /b 0

:is_pid_running
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-Process -Id %~1 -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
exit /b %ERRORLEVEL%

:wait_for_http
set /a WAIT_RETRIES=%~2
:wait_for_http_loop
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; try { $response = Invoke-WebRequest -UseBasicParsing -Uri '%~1' -TimeoutSec 5; if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if "%ERRORLEVEL%"=="0" exit /b 0
if %WAIT_RETRIES% LEQ 0 exit /b 1
timeout /t 1 /nobreak >nul
set /a WAIT_RETRIES-=1
goto wait_for_http_loop

:wait_for_port_down
set /a WAIT_RETRIES=%~2
:wait_for_port_down_loop
call :is_port_listening "%~1"
if not "%ERRORLEVEL%"=="0" exit /b 0
if %WAIT_RETRIES% LEQ 0 exit /b 1
timeout /t 1 /nobreak >nul
set /a WAIT_RETRIES-=1
goto wait_for_port_down_loop

:terminate_pid_tree
set "TARGET_PID=%~1"
set "TARGET_LABEL=%~2"
if "%TARGET_PID%"=="" exit /b 0

taskkill /PID %TARGET_PID% /T >nul 2>&1
timeout /t 2 /nobreak >nul

call :is_pid_running "%TARGET_PID%"
if "%ERRORLEVEL%"=="0" (
  taskkill /PID %TARGET_PID% /T /F >nul 2>&1
  timeout /t 1 /nobreak >nul
)

call :is_pid_running "%TARGET_PID%"
if "%ERRORLEVEL%"=="0" (
  call :log "%TARGET_LABEL%: falha ao encerrar PID %TARGET_PID%."
  exit /b 1
)

call :log "%TARGET_LABEL%: PID %TARGET_PID% encerrado."
exit /b 0

:stop_related_processes
if /I "%~1"=="backend" goto stop_related_backend
if /I "%~1"=="frontend" goto stop_related_frontend
exit /b 0

:stop_related_backend
REM O PID da porta e o PID registrado ja sao suficientes para o encerramento seguro.
exit /b 0

:stop_related_frontend
REM O PID da porta e o PID registrado ja sao suficientes para o encerramento seguro.
exit /b 0

:cleanup_stale_pid
set "PID_FILE=%~1"
set "PORT=%~2"
set "LABEL=%~3"
set "PID="
set "PORT_PID="

if not exist "%PID_FILE%" exit /b 0
set /p PID=<"%PID_FILE%"
for /f "tokens=* delims= " %%I in ("%PID%") do set "PID=%%~I"

call :get_pid_from_port "%PORT%" PORT_PID || exit /b 1
if not "%PORT_PID%"=="" (
  >"%PID_FILE%" echo %PORT_PID% || exit /b 1
  exit /b 0
)

del /f /q "%PID_FILE%" >nul 2>&1
call :log "%LABEL%: PID file obsoleto removido."
exit /b 0

REM ============================================================
REM [12] Log
REM ============================================================

:log
set "LOG_MESSAGE=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ts = Get-Date -Format 'dd/MM/yyyy HH:mm:ss'; Add-Content -LiteralPath '%LOG_FILE%' -Value ('[' + $ts + '] ' + $env:LOG_MESSAGE)" >nul 2>&1
set "LOG_MESSAGE="
exit /b 0
