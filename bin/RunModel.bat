@echo off
setlocal

set "CONTROL_CENTER_PATH=%~1"
set "SCENARIO_FOLDER=%~2"

if "%CONTROL_CENTER_PATH%"=="" goto :usage
if "%SCENARIO_FOLDER%"=="" goto :usage
if not exist "%SCENARIO_FOLDER%\" (
    echo RunModel.bat: scenario folder not found: "%SCENARIO_FOLDER%"
    exit /b 1
)
if "%VOYAGER_EXE%"=="" (
    echo RunModel.bat: VOYAGER_EXE is not set. Set Voyager_EXE in config/local.yaml.
    exit /b 1
)
if not exist "%VOYAGER_EXE%" (
    echo RunModel.bat: VOYAGER_EXE does not exist: "%VOYAGER_EXE%"
    exit /b 1
)

set "DRIVER_SCRIPT="
set "DRIVER_SCRIPT_COUNT=0"
for %%F in ("%SCENARIO_FOLDER%\*.s") do (
    set "DRIVER_SCRIPT=%%~nxF"
    set /a DRIVER_SCRIPT_COUNT+=1
)

if "%DRIVER_SCRIPT_COUNT%"=="0" (
    echo RunModel.bat: no driver script ^(*.s^) found in "%SCENARIO_FOLDER%"
    exit /b 1
)
if not "%DRIVER_SCRIPT_COUNT%"=="1" (
    echo RunModel.bat: found %DRIVER_SCRIPT_COUNT% driver scripts ^(*.s^) in "%SCENARIO_FOLDER%" -- expected exactly 1
    exit /b 1
)

echo RunModel.bat: control center  = "%CONTROL_CENTER_PATH%"
echo RunModel.bat: scenario folder = "%SCENARIO_FOLDER%"
echo RunModel.bat: driver script   = "%DRIVER_SCRIPT%"
echo RunModel.bat: voyager exe     = "%VOYAGER_EXE%"

pushd "%SCENARIO_FOLDER%"
start /w "" "%VOYAGER_EXE%" "%DRIVER_SCRIPT%" /Start -Report
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%

:usage
echo Usage: RunModel.bat "<control_center_path>" "<scenario_folder>"
exit /b 1
