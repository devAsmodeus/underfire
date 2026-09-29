import { Container } from 'pixi.js';
import { addStats } from '../debug/stats';
import { Camera } from '../engine/camera';
import type { Demo } from '../main';
import { loadMapBackground, STAR_1_MAP_01 } from '../render/mapBackground';
import { Animated, directionOf, Visual } from '../render/visual';

interface Walker {
  body: Animated;
  tx: number;
  ty: number;
}

/**
 * Изометрия: карта миссии и толпа юнитов, бегущих в 8 направлениях, с сортировкой по глубине.
 * ?count=200 — число юнитов; ?units=units/a,mobs/b — визуалы; ?bench=1 — замер без rAF.
 */
export const run: Demo = async (app, params) => {
  const camera = new Camera(app, { minScale: 0.4, maxScale: 2 });
  const map = await loadMapBackground(STAR_1_MAP_01);
  camera.world.addChild(map);
  camera.centerOn(map.width / 2, map.height / 2);

  const count = Number(params.get('count') ?? 200);
  const paths = (params.get('units') ?? 'units/praetorians_peacekeeper_enemy,mobs/bug,units/bomb_pig').split(',');
  const visuals = await Promise.all(paths.map((p) => Visual.load(p)));

  // Бегают в середине карты: мир — ромб, у фона за его краями тёмные углы.
  const area = { x0: map.width * 0.3, x1: map.width * 0.7, y0: map.height * 0.3, y1: map.height * 0.7 };
  const rand = (a: number, b: number) => a + Math.random() * (b - a);
  const units = new Container({ label: 'units', sortableChildren: true });
  camera.world.addChild(units);
  const walkers: Walker[] = [];
  for (let i = 0; i < count; i++) {
    const body = new Animated(visuals[i % visuals.length], 'run', 'sw');
    body.position.set(rand(area.x0, area.x1), rand(area.y0, area.y1));
    units.addChild(body);
    walkers.push({ body, tx: rand(area.x0, area.x1), ty: rand(area.y0, area.y1) });
  }

  const speed = 45; // точек в секунду (прототип; настоящая скорость — из конфига юнита)
  app.ticker.add((t) => {
    const step = (speed * t.deltaMS) / 1000;
    for (const w of walkers) {
      const dx = w.tx - w.body.x;
      const dy = w.ty - w.body.y;
      const dist = Math.hypot(dx, dy);
      if (dist <= step) {
        w.tx = rand(area.x0, area.x1);
        w.ty = rand(area.y0, area.y1);
        continue;
      }
      w.body.face(directionOf(dx, dy));
      w.body.x += (dx / dist) * step;
      w.body.y += (dy / dist) * step;
      w.body.zIndex = w.body.y; // ниже на экране — ближе к камере
      w.body.update(t);
    }
  });

  addStats(app, () => `юнитов ${count} · ${paths.join(', ')} · колесо — зум, перетаскивание — камера`);
};
