import { Container, Graphics } from 'pixi.js';
import { addStats } from '../debug/stats';
import { loadFonts } from '../engine/fonts';
import { ASSETS_URL, FrameCache } from '../engine/frames';
import type { Demo } from '../main';
import { buildLayout, type CcbDoc, collectRefs } from '../ui/ccb';

/** Макеты прототипа (issue #33); ?layout=<путь внутри ui/1024x768 без .json>. */
export const LAYOUTS = ['city/popups/yes_no_popup', 'city/construction_menu', 'city/CityScene'];

export async function loadDoc(path: string): Promise<CcbDoc> {
  const res = await fetch(`${ASSETS_URL}ui/1024x768/${path}.json`);
  if (!res.ok) throw new Error(`нет макета ${path}: соберите assets/ui (tools/ccbi_to_json.py)`);
  return res.json();
}

/** Макет со всем, что ему нужно: кадры, шрифты, шаблоны строк списков. */
export async function prepareLayout(path: string, frames: FrameCache) {
  const doc = await loadDoc(path);
  const refs = collectRefs(doc);
  const dir = path.includes('/') ? path.slice(0, path.lastIndexOf('/') + 1) : '';
  const templates = new Map<string, CcbDoc>();
  for (const name of refs.templates) {
    const t = await loadDoc(dir + name);
    templates.set(name, t);
    const r = collectRefs(t);
    r.frames.forEach((f) => refs.frames.add(f));
    r.fonts.forEach((f) => refs.fonts.add(f));
  }
  await Promise.all([frames.preload(refs.frames), loadFonts(refs.fonts)]);
  return { doc, templates };
}

export const run: Demo = async (app, params) => {
  const path = params.get('layout') ?? LAYOUTS[0];
  const frames = new FrameCache();
  await frames.init();
  const { doc, templates } = await prepareLayout(path, frames);

  // Экран оригинала: высота 768 точек, ширина по соотношению сторон окна (не меньше 1024).
  const winSize = { width: Math.max(1024, Math.round((768 * app.screen.width) / app.screen.height)), height: 768 };
  const screen = new Container({ label: 'screen' });
  screen.scale.set(app.screen.height / winSize.height);
  app.stage.addChild(screen);
  screen.addChild(new Graphics().rect(0, 0, winSize.width, winSize.height).fill(0x1b2433));

  const clicks: string[] = [];
  const layout = buildLayout(doc, {
    frames,
    winSize,
    templates,
    onCallback: (selector) => clicks.unshift(selector),
  });
  screen.addChild(layout.root);

  // Всплывающие окна меньше экрана ставит в центр код игры — здесь делаем то же.
  if (layout.size.width < winSize.width || layout.size.height < winSize.height) {
    const b = layout.root.getBounds();
    const k = screen.scale.x;
    layout.root.x += (app.screen.width / 2 - (b.x + b.width / 2)) / k;
    layout.root.y += (app.screen.height / 2 - (b.y + b.height / 2)) / k;
  }

  if (layout.missingFrames.size) console.warn('нет кадров:', [...layout.missingFrames]);
  addStats(app, () =>
    [
      `${path}: узлов ${layout.nodes}, outlets ${layout.outlets.size}, нет кадров ${layout.missingFrames.size}`,
      `?layout=${LAYOUTS.join(' | ')}`,
      clicks.length ? `нажато: ${clicks.slice(0, 3).join(', ')}` : '',
    ].join('\n'),
  );
};
