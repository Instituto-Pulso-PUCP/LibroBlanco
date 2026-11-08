# Atlas Temático en el servidor

Desde el 2026-11-08 el atlas se sirve desde el EC2 del proyecto (`pulso-vri`,
Ubuntu 26.04, t4g.small) con nginx, en vez de como artifact de Claude.

- **Dirección:** http://44.195.204.129/ (`?ds=pucp` o `?ds=ecotec` abre un dataset)
- **Acceso:** usuario `pulso` y una clave compartida (HTTP basic auth). La clave
  no está en el repositorio; pedirla al responsable del proyecto.
- **Sin HTTPS todavía:** no hay dominio. Por HTTP la clave viaja sin cifrar.

## Publicar una versión nueva

En el servidor, después de cualquier cambio en las corridas, los perfiles
(`atlas_profiles.py`) o la página (`scripts/analysis/templates/atlas/`: `index.html`,
`atlas.css`, `atlas.js`; `build_atlas.py` los junta en un solo HTML):

```bash
cd ~/LibroBlanco && git pull && source config/env.sh
python3 scripts/analysis/build_atlas.py --run projects=<run> --run publications_linked=<run>
python3 scripts/analysis/build_atlas.py --run ecotec_projects=<run> --run ecotec_publications=<run>
./scripts/analysis/deploy_atlas.sh
```

`deploy_atlas.sh` copia `salidas/topics/atlas/` a una carpeta nueva en
`/var/www/atlas-releases/<fecha>` y cambia el enlace `/var/www/atlas` de un
golpe, así que nadie ve una versión a medias. Guarda las 3 últimas. Volver a
la anterior:

```bash
ls /var/www/atlas-releases/
sudo ln -sfn /var/www/atlas-releases/<anterior> /var/www/atlas.tmp && sudo mv -T /var/www/atlas.tmp /var/www/atlas
```

nginx no cachea en el navegador (`Cache-Control: no-cache`, con ETag): tras
publicar basta con recargar.

## Configuración

| Qué | Dónde |
|---|---|
| Sitio | `/etc/nginx/sites-available/atlas` (enlazado en `sites-enabled/`; el sitio `default` de Ubuntu está desactivado) |
| Usuario y clave | `/etc/nginx/atlas.htpasswd` (root:www-data, 640) |
| Versión de nginx oculta | `server_tokens off;` en `/etc/nginx/nginx.conf` |
| Puertos | 80 y 443 abiertos en el security group `pulso-vri`; `ufw` inactivo |

El sitio además manda `X-Robots-Tag: noindex`, comprime los JSON (los datos
de PUCP viajan en ~0,6 MB en vez de 2,5) y responde 204 a `/favicon.ico`.

Cambiar la clave (o agregar otro usuario con `tee -a`):

```bash
printf "pulso:%s\n" "$(openssl passwd -apr1)" | sudo tee /etc/nginx/atlas.htpasswd >/dev/null
sudo systemctl reload nginx
```

## Pendiente: dominio y HTTPS

Cuando haya un dominio (p. ej. un subdominio de PUCP) con un registro A a
`44.195.204.129`:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo sed -i 's/server_name _;/server_name <dominio>;/' /etc/nginx/sites-available/atlas
sudo certbot --nginx -d <dominio> --redirect
```

certbot agrega el bloque de 443, la redirección desde HTTP y la renovación
automática.
