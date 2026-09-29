import type { Application, WebGLRenderer } from 'pixi.js';

export interface BenchResult {
  frames: number;
  msPerFrame: number;
  /** Сколько кадров в секунду выдержала бы сцена без ограничения частоты экрана. */
  fpsCapacity: number;
}

/**
 * Замер без requestAnimationFrame (браузер может его притормаживать, если вкладка не на виду):
 * `frames` раз прогоняем тикер (анимации, движение) и рисуем кадр, в конце ждём GPU через
 * readPixels. Итог — время кадра CPU + GPU.
 */
export function benchRender(app: Application, frames = 120): BenchResult {
  const gl = (app.renderer as WebGLRenderer).gl;
  const pixel = new Uint8Array(4);
  const sync = () => gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
  app.ticker.stop();
  app.render();
  sync(); // прогрев: загрузка текстур, компиляция шейдеров
  const t0 = performance.now();
  for (let i = 1; i <= frames; i++) {
    app.ticker.update(t0 + (i * 1000) / 60);
    app.render();
  }
  sync();
  const ms = (performance.now() - t0) / frames;
  app.ticker.start();
  return { frames, msPerFrame: ms, fpsCapacity: 1000 / ms };
}
