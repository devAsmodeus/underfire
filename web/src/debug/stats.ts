import { type Application, Container, Text, type TextureSource } from 'pixi.js';

/** Текстуры в видеопамяти (у экспериментального Canvas-рендерера такого списка нет). */
const managed = (app: Application): readonly TextureSource[] =>
  (app.renderer.texture as { managedTextures?: readonly TextureSource[] }).managedTextures ?? [];

/** Сколько байт занимают текстуры в видеопамяти (оценка: RGBA8, с мипмапами — ×4/3). */
export function textureBytes(app: Application): number {
  let bytes = 0;
  for (const s of managed(app)) {
    const base = s.pixelWidth * s.pixelHeight * 4;
    bytes += s.mipLevelCount > 1 ? (base * 4) / 3 : base;
  }
  return bytes;
}

export const mib = (bytes: number) => bytes / (1024 * 1024);

/** Панель замеров поверх сцены: FPS, время кадра, число текстур и оценка видеопамяти. */
export function addStats(app: Application, extra: () => string = () => ''): Container {
  const panel = new Container({ label: 'stats' });
  const text = new Text({
    text: '',
    style: { fill: '#ffffff', fontFamily: 'monospace', fontSize: 13, stroke: { color: '#000000', width: 3 } },
  });
  panel.addChild(text);
  panel.position.set(8, 8);
  app.stage.addChild(panel);

  let acc = 0;
  app.ticker.add((t) => {
    acc += t.deltaMS;
    if (acc < 250) return; // обновляем 4 раза в секунду
    acc = 0;
    const textures = managed(app).length;
    text.text = [
      `${t.FPS.toFixed(0)} FPS · ${(1000 / Math.max(t.FPS, 1)).toFixed(1)} мс`,
      `текстур ${textures} · ~${mib(textureBytes(app)).toFixed(0)} МиБ видеопамяти`,
      extra(),
    ]
      .filter(Boolean)
      .join('\n');
    app.stage.addChild(panel); // всегда сверху
  });
  return panel;
}
