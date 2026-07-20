@echo off
setlocal

if "%ELSEVIER_API_KEY%"=="" (
    echo ERROR: defina ELSEVIER_API_KEY antes de ejecutar.
    exit /b 2
)

python resumenes_por_doi.py doi_ejemplo.csv -o resultados.csv --timeout 30 --reintentos 2

endlocal
pause
