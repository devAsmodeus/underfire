import { resolve } from 'node:path';
import sirv from 'sirv';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

// Ассеты (assets/ в корне репозитория) собирают инструменты из tools/, в git их нет.
// В dev их отдаёт этот плагин по адресу /assets/; в сборке адрес задаёт VITE_ASSETS_URL.
const ASSETS_DIR = resolve(import.meta.dirname, '../assets');

function serveAssets(): Plugin {
  return {
    name: 'underfire-assets',
    configureServer(server) {
      server.middlewares.use('/assets', sirv(ASSETS_DIR, { dev: true }));
    },
  };
}

export default defineConfig({
  base: './',
  plugins: [serveAssets()],
  build: { assetsDir: 'static' }, // адрес /assets/ оставляем игровым ассетам
  test: { environment: 'node' },
});
