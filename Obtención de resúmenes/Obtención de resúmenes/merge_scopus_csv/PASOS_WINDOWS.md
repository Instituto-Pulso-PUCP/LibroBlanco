# Pasos completos en Windows

## 1. Organizar los archivos

Cree una carpeta, por ejemplo:

```text
C:\proyecto-scopus
```

Dentro coloque:

```text
C:\proyecto-scopus\
├── integrar_scopus.py
├── requirements.txt
├── doi-resultados.csv
└── scopus_csv\
    ├── scopus_001.csv
    ├── scopus_002.csv
    ├── scopus_003.csv
    └── ...
```

No cambie ni combine manualmente los archivos exportados por Scopus.

## 2. Exportar desde Scopus

Para cada lote de DOI:

1. Entre a Scopus mediante el acceso institucional.
2. Abra **Advanced Search**.
3. Pegue una consulta generada previamente.
4. Ejecute la búsqueda.
5. Seleccione todos los resultados.
6. Pulse **Export**.
7. Elija **CSV**.
8. Marque:
   - Document title
   - EID
   - DOI
   - Abstract
   - Author keywords
   - Indexed keywords
   - PubMed ID, si está disponible
9. Descargue el archivo dentro de `scopus_csv`.
10. Use nombres ordenados: `scopus_001.csv`, `scopus_002.csv`, etc.

## 3. Abrir PowerShell

Abra PowerShell dentro de:

```text
C:\proyecto-scopus
```

## 4. Crear un entorno virtual

```powershell
python -m venv .venv
```

## 5. Activar el entorno

```powershell
.\.venv\Scripts\Activate.ps1
```

## 6. Instalar la dependencia

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 7. Ejecutar el programa

En una sola línea:

```powershell
python integrar_scopus.py doi-resultados.csv scopus_csv -o doi-resultados-final.csv
```

En varias líneas:

```powershell
python integrar_scopus.py doi-resultados.csv scopus_csv `
  -o doi-resultados-final.csv
```

## 8. Revisar los resultados

El archivo principal será:

```text
doi-resultados-final.csv
```

Revise también:

```text
doi-resultados-final_estadisticas.csv
doi-resultados-final_pendientes.csv
doi-resultados-final_log_archivos.csv
```

El archivo `pendientes` contiene únicamente los registros que todavía carecen
de resumen, palabras clave o ambos.

## 9. Comprobaciones mínimas

Abra `doi-resultados-final_estadisticas.csv` y revise:

- `filas_base`
- `doi_encontrados_scopus_web`
- `resumenes_completados`
- `palabras_clave_completadas`
- `sin_resumen_o_palabras_final`

Abra `doi-resultados-final_log_archivos.csv` y confirme que todos los archivos
tengan estado `OK`.

## 10. Repetir el proceso

Puede añadir nuevas exportaciones a `scopus_csv` y ejecutar nuevamente el
programa. El CSV base no se modifica; se crea un nuevo resultado final.
