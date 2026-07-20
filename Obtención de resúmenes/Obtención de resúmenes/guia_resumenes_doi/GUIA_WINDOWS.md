# Guía para Windows

## 1. Requisitos

Instale:

- Python 3.10 o superior.
- Un editor de texto, como Visual Studio Code.
- Una API Key válida del portal de desarrolladores de Elsevier.

Durante la instalación de Python, marque:

```text
Add Python to PATH
```

## 2. Preparar la carpeta

Descomprima el paquete, por ejemplo, en:

```text
C:\curso-resumenes-doi
```

Abra PowerShell dentro de esa carpeta.

Puede hacerlo desde el Explorador de archivos:

1. Abra la carpeta.
2. Haga clic en la barra de direcciones.
3. Escriba `powershell`.
4. Presione Enter.

## 3. Crear el entorno virtual

```powershell
python -m venv .venv
```

## 4. Activar el entorno virtual

```powershell
.\.venv\Scripts\Activate.ps1
```

El indicador debería comenzar con:

```text
(.venv)
```

### Si PowerShell bloquea la activación

Ejecute una vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Cierre PowerShell, ábralo de nuevo y active el entorno.

## 5. Instalar dependencias

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 6. Preparar el archivo de entrada

El archivo CSV debe tener una columna denominada `doi`:

```csv
doi
10.1001/jama.2017.14585
10.1038/s41586-020-2649-2
```

También se acepta un archivo TXT con un DOI por línea.

## 7. Configurar la API Key

En la sesión actual de PowerShell:

```powershell
$env:ELSEVIER_API_KEY="SU_API_KEY"
```

Configure también un correo de contacto:

```powershell
$env:API_CONTACT_EMAIL="nombre@institucion.edu"
```

No incluya el símbolo `$` antes de la API Key literal.

### Verificar sin mostrar la clave completa

```powershell
$env:ELSEVIER_API_KEY.Substring(0,6) + "..."
```

## 8. Ejecutar el script

En una sola línea:

```powershell
python resumenes_por_doi.py doi_ejemplo.csv -o resultados.csv
```

En varias líneas, PowerShell utiliza el acento grave:

```powershell
python resumenes_por_doi.py doi_ejemplo.csv `
  -o resultados.csv `
  --timeout 30 `
  --reintentos 2
```

## 9. Interpretar la consola

Ejemplo:

```text
[1/2] 10.1001/jama.2017.14585
    Scopus=OK | resumen=PubMed | palabras clave=PubMed
```

Significa que:

- Scopus encontró el registro;
- el resumen se completó con PubMed;
- las palabras clave se completaron con PubMed.

## 10. Abrir el resultado

El archivo generado será:

```text
resultados.csv
```

Puede abrirse con Excel. La codificación UTF-8 con BOM ayuda a conservar
acentos y caracteres especiales.

## 11. Errores frecuentes

### `API_KEY_INVALIDA`

La clave no existe, está mal copiada o fue revocada.

### `SIN_AUTORIZACION`

La clave es válida, pero Scopus restringe algunos campos o recursos.

### `NO_ENCONTRADO`

Scopus no encontró el DOI. El script todavía intentará PubMed, OpenAlex y
Crossref.

### `CUOTA_EXCEDIDA`

Se alcanzó el límite temporal de solicitudes de la API.

### El archivo aparece vacío durante mucho tiempo

Revise la consola. Cada DOI puede requerir varias consultas y reintentos. El
CSV se actualiza después de terminar cada DOI.

## 12. Desactivar el entorno virtual

```powershell
deactivate
```
