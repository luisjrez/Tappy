# Landing Tappy

Base estática Astro, independiente del backend. L02 implementa HTML semántico mínimo; la composición visual de Pencil corresponde a L04–L09.

## Entorno reproducible

Node 22.23.4 (`.node-version`) y npm 10.9.2. Desde esta carpeta:

```sh
npm ci
npx playwright install chromium
npm run check
npm run format:check
npm test
npm run build
```

`npm run dev` inicia desarrollo. `npm run preview -- --ignore-lock` sirve el build en primer plano. Playwright ejecuta build y preview propios en 127.0.0.1:4394 y detiene el servidor al terminar. No requiere variables de entorno, secretos ni conexión bancaria.

La salida es `dist/`, con `index.html` y `404.html`. La prueba 404 comprueba el status en Astro preview; el contrato equivalente en Cloudflare Pages se verifica en L12.

La versión de TypeScript se fija en 6 porque `@astrojs/check` 0.9.12 declara compatibilidad con 5 y 6. El lockfile fija todas las dependencias. No hay scripts cliente ni solicitudes externas desde las páginas.
