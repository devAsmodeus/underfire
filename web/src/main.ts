import { Application, Text } from 'pixi.js';
import { benchRender } from './debug/bench';

/** Демо прототипа (issue #33): ?demo=<имя>. */
const DEMOS: Record<string, { title: string; load: () => Promise<{ run: Demo }> }> = {
  ui: { title: 'Интерфейс из макетов ccbi', load: () => import('./demos/ui') },
  iso: { title: 'Изометрия: юниты в 8 направлениях', load: () => import('./demos/iso') },
  blur: { title: 'Размытие под окном', load: () => import('./demos/blur') },
};

export type Demo = (app: Application, params: URLSearchParams) => Promise<void>;

async function main() {
  const app = new Application();
  await app.init({
    preference: 'webgl', // WebGL2; WebGPU в PixiJS 8 для продакшена пока не рекомендуют
    background: '#000000',
    resizeTo: window,
    antialias: false,
    autoDensity: true,
    resolution: window.devicePixelRatio,
  });
  document.body.appendChild(app.canvas);

  const params = new URLSearchParams(location.search);
  const demo = DEMOS[params.get('demo') ?? ''];
  if (demo) {
    document.title = `${demo.title} — Under Fire: Invasion`;
    const { run } = await demo.load();
    await run(app, params);
    if (params.has('bench')) {
      // ?bench=1: замер без requestAnimationFrame — результат в консоли и заголовке вкладки
      const r = benchRender(app, Number(params.get('frames') ?? 240));
      const line = `bench ${location.search}: ${r.msPerFrame.toFixed(2)} мс/кадр (~${r.fpsCapacity.toFixed(0)} FPS)`;
      console.log(line);
      document.title = line;
    }
    return;
  }

  // Стартовая страница: список демо.
  const lines = Object.entries(DEMOS).map(([key, d]) => `?demo=${key} — ${d.title}`);
  const menu = new Text({
    text: ['Under Fire: Invasion — прототип на PixiJS 8', '', ...lines].join('\n'),
    style: { fill: '#fff66f', fontFamily: 'sans-serif', fontSize: 20, lineHeight: 30 },
  });
  menu.position.set(24, 24);
  app.stage.addChild(menu);
}

void main();
