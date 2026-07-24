@echo off
setlocal enabledelayedexpansion

set PGPASSWORD=Password09!
set PGBIN="C:\Program Files\PostgreSQL\18\bin"

echo Checking database...
%PGBIN%\psql.exe -U postgres -p 5008 -tc "SELECT 1 FROM pg_database WHERE datname = 'network';" | findstr /C:"1" >nul
if errorlevel 1 (
    echo Database 'network' not found, creating...
    %PGBIN%\createdb.exe -U postgres -p 5008 network
) else (
    echo Database 'network' already exists.
)

echo Running migrations...
python manage.py migrate

echo Seeding data...
python manage.py seed

echo Starting Django server...
python manage.py runserver 8080

endlocal
