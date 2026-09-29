import { type Application, Container, type FederatedPointerEvent, Rectangle } from 'pixi.js';

export interface CameraOptions {
  minScale?: number;
  maxScale?: number;
}

/**
 * Камера над миром, как CCLayerPanZoom в оригинале (упрощённо): перетаскивание мышью
 * и зум колесом вокруг курсора в пределах [minScale, maxScale]. Мир — дочерний Container.
 */
export class Camera {
  readonly world = new Container({ label: 'world' });
  private readonly minScale: number;
  private readonly maxScale: number;

  constructor(
    private readonly app: Application,
    opts: CameraOptions = {},
  ) {
    this.minScale = opts.minScale ?? 0.5;
    this.maxScale = opts.maxScale ?? 2;
    const stage = app.stage;
    stage.addChild(this.world);
    stage.eventMode = 'static';
    stage.hitArea = new Rectangle(-1e6, -1e6, 2e6, 2e6);

    let drag: { x: number; y: number } | null = null;
    stage.on('pointerdown', (e: FederatedPointerEvent) => {
      drag = { x: e.global.x - this.world.x, y: e.global.y - this.world.y };
    });
    stage.on('pointerup', () => (drag = null));
    stage.on('pointerupoutside', () => (drag = null));
    stage.on('pointermove', (e: FederatedPointerEvent) => {
      if (drag) this.world.position.set(e.global.x - drag.x, e.global.y - drag.y);
    });
    app.canvas.addEventListener(
      'wheel',
      (e) => {
        e.preventDefault();
        this.zoomAt(e.offsetX, e.offsetY, Math.exp(-e.deltaY * 0.0015));
      },
      { passive: false },
    );
  }

  /** Масштабировать мир в `factor` раз, удерживая экранную точку (sx, sy) на месте. */
  zoomAt(sx: number, sy: number, factor: number): void {
    const w = this.world;
    const next = Math.min(this.maxScale, Math.max(this.minScale, w.scale.x * factor));
    const k = next / w.scale.x;
    w.position.set(sx - (sx - w.x) * k, sy - (sy - w.y) * k);
    w.scale.set(next);
  }

  /** Поставить точку мира (x, y) в центр экрана. */
  centerOn(x: number, y: number): void {
    const s = this.world.scale.x;
    this.world.position.set(this.app.screen.width / 2 - x * s, this.app.screen.height / 2 - y * s);
  }
}
