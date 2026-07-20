# Guía para Linux

Estas instrucciones se aplican a Ubuntu y distribuciones derivadas.

## 1. Instalar Python

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

## 2. Preparar la carpeta

Descomprima el paquete:

```bash
unzip guia_resumenes_doi.zip -d guia_resumenes_doi
cd guia_resumenes_doi
```

## 3. Crear el entorno virtual

```bash
python3 -m venv .venv
```

## 4. Activar el entorno virtual

```bash
source .venv/bin/activate
```

El indicador debería comenzar con:

```text
(.venv)
```

## 5. Instalar dependencias

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 6. Preparar el archivo de entrada

CSV con una columna denominada `doi`:

```csv
doi
10.1001/jama.2017.14585
10.1038/s41586-020-2649-2
```

También se acepta un TXT con un DOI por línea.

## 7. Configurar la API Key

```bash
export ELSEVIER_API_KEY='SU_API_KEY'
```

Configure un correo de contacto:

```bash
export API_CONTACT_EMAIL='nombre@institucion.edu'
```

### Verificar sin mostrar la clave completa

```bash
echo "${ELSEVIER_API_KEY:0:6}..."
```

No escriba:

```bash
$SU_API_KEY
```

Bash interpretaría el texto posterior a `$` como el nombre de una variable.

## 8. Ejecutar el script

En una sola línea:

```bash
python resumenes_por_doi.py doi_ejemplo.csv -o resultados.csv
```

En varias líneas, Linux utiliza la barra invertida:

```bash
python resumenes_por_doi.py doi_ejemplo.csv \
  -o resultados.csv \
  --timeout 30 \
  --reintentos 2
```

No utilice el acento grave de PowerShell.

## 9. Revisar la salida

```bash
head -n 5 resultados.csv
```

Para contar filas:

```bash
wc -l resultados.csv
```

Para ver el tamaño:

```bash
ls -lh resultados.csv
```

## 10. Interpretar estados

### `OK`

Scopus encontró el registro.

### `API_KEY_INVALIDA`

La API Key no fue reconocida.

### `SIN_AUTORIZACION`

La clave es válida, pero el recurso o algunos campos están restringidos.

### `NO_ENCONTRADO`

Scopus no encontró el DOI. El script continúa con las fuentes abiertas.

### `CUOTA_EXCEDIDA`

Se alcanzó el límite de solicitudes.

### `ERROR_RED`

Hubo un timeout, problema DNS, proxy o interrupción de red.

## 11. Ejecución en segundo plano

Para listas grandes:

```bash
nohup python resumenes_por_doi.py lista_dois.csv \
  -o resultados.csv \
  > ejecucion.log 2>&1 &
```

Ver avance:

```bash
tail -f ejecucion.log
```

Ver el proceso:

```bash
ps aux | grep resumenes_por_doi.py
```

## 12. Desactivar el entorno virtual

```bash
deactivate
```
