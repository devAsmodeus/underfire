import { Container, Graphics } from 'pixi.js';
import { addStats } from '../debug/stats';
import { Camera } from '../engine/camera';
import { FrameCache } from '../engine/frames';
import type { Demo } from '../main';
import { infernoBlur } from '../render/infernoBlur';
import { loadMapBackground, STAR_1_MAP_01 } from '../render/mapBackground';
import { buildLayout } from '../ui/ccb';
import { prepareLayout } from './ui';

/**
 * Размытие под окном: карта миссии размывается портом шейдера игры, поверх — окно из макета.
 * ?passes=N — число проходов (по умолчанию 3, 0 — без размытия), клавиша B — вкл/выкл.
 */
export const run: Demo = async (app, params) => {
  const camera = new Camera(app, { minScale: 0.5, maxScale: 2 });
  const map = await loadMapBackground(STAR_1_MAP_01);
  camera.world.addChild(map);
  camera.centerOn(map.width / 2, map.height / 2);

  const passes = Math.max(0, Number(params.get('passes') ?? 3)); // 0 — без размытия (для замера)
  const filters = Array.from({ length: passes }, () => infernoBlur(2));
  let blurred = passes > 0;
  const apply = () => (camera.world.filters = blurred ? filters : []);
  apply();
  window.addEventListener('keydown', (e) => {
    if (e.key.toLowerCase() === 'b' || e.key.toLowerCase() === 'и') {
      blurred = !blurred;
      apply();
    }
  });

  // Окно поверх размытого мира — в экранных координатах, как слой интерфейса.
  const frames = new FrameCache();
  await frames.init();
  const { doc, templates } = await prepareLayout('city/popups/yes_no_popup', frames);
  const winSize = { width: Math.max(1024, Math.round((768 * app.screen.width) / app.screen.height)), height: 768 };
  const ui = new Container({ label: 'ui' });
  ui.scale.set(app.screen.height / winSize.height);
  app.stage.addChild(ui);
  ui.addChild(new Graphics().rect(0, 0, winSize.width, winSize.height).fill({ color: 0x000000, alpha: 0.25 }));
  const layout = buildLayout(doc, { frames, winSize, templates });
  ui.addChild(layout.root);
  const b = layout.root.getBounds();
  layout.root.x += (app.screen.width / 2 - (b.x + b.width / 2)) / ui.scale.x;
  layout.root.y += (app.screen.height / 2 - (b.y + b.height / 2)) / ui.scale.y;

  addStats(app, () => `размытие: ${blurred ? `${passes} прох.` : 'выкл'} (клавиша B) · перетаскивайте карту`);
};
