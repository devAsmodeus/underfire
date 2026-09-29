import { Assets, type Spritesheet, type Texture } from 'pixi.js';

/** Базовый адрес игровых ассетов: в dev — /assets/ (см. vite.config.ts), в сборке — VITE_ASSETS_URL. */
export const ASSETS_URL: string = import.meta.env.VITE_ASSETS_URL ?? '/assets/';

/** Имена кадров в .atlas начинаются с «/», в ccbi и индексе — без него. */
export const frameKey = (name: string) => (name.startsWith('/') ? name.slice(1) : name);

/**
 * Кэш кадров по имени — аналог CCSpriteFrameCache. Индекс `frames_index.json`
 * (tools/convert_atlases.py) говорит, в каком атласе лежит кадр; атлас — спрайт-лист PixiJS
 * (JSON + WebP), грузится при первом обращении и выгружается целиком при смене сцены.
 */
export class FrameCache {
  private index: Record<string, string> = {};
  private readonly sheets = new Map<string, Promise<Spritesheet>>();
  private readonly loaded = new Map<string, Spritesheet>();

  async init(indexFile = 'frames_index.json'): Promise<void> {
    const res = await fetch(ASSETS_URL + indexFile);
    if (res.ok) this.index = await res.json();
    else console.warn(`нет ${indexFile}: кадров не будет — соберите ассеты (tools/convert_atlases.py)`);
  }

  /** Путь к атласу с кадром (относительно ASSETS_URL) или undefined. */
  atlasOf(name: string): string | undefined {
    return this.index[frameKey(name)];
  }

  sheet(atlas: string): Promise<Spritesheet> {
    let p = this.sheets.get(atlas);
    if (!p) {
      p = Assets.load<Spritesheet>(ASSETS_URL + atlas).then((sheet) => {
        this.loaded.set(atlas, sheet);
        return sheet;
      });
      this.sheets.set(atlas, p);
    }
    return p;
  }

  /** Текстура кадра из уже загруженных атласов (после preload) или undefined. */
  texture(name: string): Texture | undefined {
    const atlas = this.atlasOf(name);
    return atlas ? this.loaded.get(atlas)?.textures[frameKey(name)] : undefined;
  }

  /** Загрузить атласы, где лежат кадры, — заранее, пачкой. */
  async preload(names: Iterable<string>): Promise<void> {
    const atlases = new Set<string>();
    for (const n of names) {
      const a = this.atlasOf(n);
      if (a) atlases.add(a);
    }
    await Promise.all([...atlases].map((a) => this.sheet(a)));
  }

  /** Текстура кадра; атлас должен быть загружен (preload), иначе undefined. */
  async frame(name: string): Promise<Texture | undefined> {
    const atlas = this.atlasOf(name);
    if (!atlas) return undefined;
    const sheet = await this.sheet(atlas);
    return sheet.textures[frameKey(name)];
  }

  /** Выгрузить все загруженные атласы (смена сцены). */
  async unloadAll(): Promise<void> {
    const urls = [...this.sheets.keys()].map((a) => ASSETS_URL + a);
    this.sheets.clear();
    this.loaded.clear();
    await Assets.unload(urls);
  }
}
