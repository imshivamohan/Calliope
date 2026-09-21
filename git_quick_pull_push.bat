@echo off
REM ============================================
REM Quick Git Pull and Push for Current Repo
REM Run this script INSIDE your repository folder
REM ============================================

echo.
echo ========================================
echo Quick Git Pull and Push
echo ========================================
echo.

REM Check if we're in a git repository
if not exist ".git" (
    echo ERROR: This is not a git repository!
    echo Please run this script inside a repository folder.
    pause
    exit /b 1
)

echo Current directory: %cd%
echo.

REM Pull latest changes
echo [1/4] Pulling latest changes from origin main...
git pull origin main
if errorlevel 1 (
    echo ERROR: Pull failed!
    goto :check_status
)
echo SUCCESS: Pull completed
echo.

REM Check status
echo [2/4] Checking git status...
git status
echo.

REM Stage all changes
echo [3/4] Staging all changes...
git add .
echo Staged changes.
echo.

REM Commit if there are changes
git status --porcelain | findstr /V "^$" >nul 2>&1
if errorlevel 1 (
    echo [4/4] No changes to commit, pushing...
    goto :push
)

echo [4/4] Committing changes...
set /p message="Enter commit message (or press Enter for auto-message): "
if "!message!"=="" (
    git commit -m "Auto-commit at %date% %time%"
) else (
    git commit -m "!message!"
)

:push
echo.
echo Pushing to origin main...
git push origin main
if errorlevel 1 (
    echo ERROR: Push failed!
    echo.
    echo Common issues:
    echo - SSH authentication: Run git_ssh_setup.bat first
    echo - Permission denied: Check your GitHub SSH keys
    pause
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS: Pull and Push completed!
echo ========================================
echo.
pause
