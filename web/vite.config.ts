import { fileURLToPath } from 'node:url';
import sirv from 'sirv';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

// Ассеты (assets/ в корне репозитория) собирают инструменты из tools/, в git их нет.
// В dev их отдаёт этот плагин по адресу /assets/; в сборке адрес задаёт VITE_ASSETS_URL.
// Путь — от import.meta.url: Vite подставляет исходный адрес конфига (import.meta.dirname
// указывал бы во временную папку, куда Vite собирает конфиг).
const ASSETS_DIR = fileURLToPath(new URL('../assets', import.meta.url));

function serveAssets(): Plugin {
  const serve = sirv(ASSETS_DIR, { dev: true });
  return {
    name: 'underfire-assets',
    configureServer(server) {
      // Нет файла — честный 404, а не index.html от SPA-фолбэка Vite.
      server.middlewares.use('/assets', (req, res) =>
        serve(req, res, () => {
          res.statusCode = 404;
          res.end('not found');
        }),
      );
    },
  };
}

export default defineConfig({
  base: './',
  plugins: [serveAssets()],
  build: { assetsDir: 'static' }, // адрес /assets/ оставляем игровым ассетам
  test: { environment: 'node' },
});
