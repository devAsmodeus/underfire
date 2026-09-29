import { Application, Text } from 'pixi.js';

/** Точка входа клиента. Пока — заглушка каркаса: сцена PixiJS и счётчик FPS. */
async function main() {
  const app = new Application();
  await app.init({
    background: '#000000',
    resizeTo: window,
    antialias: false,
    autoDensity: true,
    resolution: window.devicePixelRatio,
  });
  document.body.appendChild(app.canvas);

  const title = new Text({
    text: 'Under Fire: Invasion — PixiJS 8',
    style: { fill: '#fff66f', fontFamily: 'sans-serif', fontSize: 28 },
  });
  title.position.set(24, 24);
  app.stage.addChild(title);

  const fps = new Text({ text: '', style: { fill: '#ffffff', fontFamily: 'monospace', fontSize: 14 } });
  fps.position.set(24, 64);
  app.stage.addChild(fps);
  app.ticker.add(() => {
    fps.text = `${app.ticker.FPS.toFixed(0)} FPS`;
  });
}

void main();
