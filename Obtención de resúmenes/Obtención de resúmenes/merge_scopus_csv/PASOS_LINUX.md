# Pasos completos en Linux

## 1. Organizar los archivos

Ejemplo:

```text
/home/ubuntu/proyecto-scopus/
├── integrar_scopus.py
├── requirements.txt
├── doi-resultados.csv
└── scopus_csv/
    ├── scopus_001.csv
    ├── scopus_002.csv
    ├── scopus_003.csv
    └── ...
```

Crear la estructura:

```bash
mkdir -p /home/ubuntu/proyecto-scopus/scopus_csv
cd /home/ubuntu/proyecto-scopus
```

Coloque `doi-resultados.csv` en la carpeta principal y copie todas las
exportaciones de Scopus a `scopus_csv`.

## 2. Exportar desde Scopus

Para cada lote:

1. Abra Advanced Search.
2. Pegue la consulta.
3. Seleccione todos los resultados.
4. Exporte en CSV.
5. Marque:
   - Document title
   - EID
   - DOI
   - Abstract
   - Author keywords
   - Indexed keywords
   - PubMed ID, opcional
6. Guarde como `scopus_001.csv`, `scopus_002.csv`, etc.

## 3. Crear el entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 4. Instalar la dependencia

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Ejecutar

```bash
python integrar_scopus.py doi-resultados.csv scopus_csv \
  -o doi-resultados-final.csv
```

## 6. Revisar los archivos

```bash
ls -lh doi-resultados-final*.csv
```

Ver estadísticas:

```bash
column -s, -t < doi-resultados-final_estadisticas.csv
```

Ver errores de lectura:

```bash
cat doi-resultados-final_log_archivos.csv
```

Contar pendientes:

```bash
wc -l doi-resultados-final_pendientes.csv
```

## 7. Ejecución en segundo plano

Para una carpeta muy grande:

```bash
nohup python integrar_scopus.py doi-resultados.csv scopus_csv \
  -o doi-resultados-final.csv \
  > integracion.log 2>&1 &
```

Ver el registro:

```bash
tail -f integracion.log
```

## 8. Resultado final

El archivo que debe conservarse para la siguiente etapa es:

```text
doi-resultados-final.csv
```

Los demás CSV son reportes de auditoría y control de calidad.
