import { AnimatedSprite, Assets, Container, type Spritesheet, type Texture, type Ticker } from 'pixi.js';
import { ASSETS_URL } from '../engine/frames';

/** Визуал из assets/visuals/*.json (tools/visuals_to_json.py). */
export interface VisualJson {
  name: string;
  fps: number;
  scale: number;
  atlases: string[];
  directions: Record<
    string,
    {
      prefix: string;
      mirror: boolean;
      offsetX: number;
      offsetY: number;
      atlases: string[];
      states: Record<string, { frameCount: number; frames: number[] }[]>;
    }
  >;
}

/**
 * Куда на экране смотрит направление (определено по кадрам юнитов): ne — вверх, e — вверх-вправо,
 * se — вправо, s — вниз-вправо, sw — вниз (к камере); n, nw, w — их отражения влево.
 * Индекс — сектор по 45° от «вправо» по часовой (ось Y вниз).
 */
const BY_SECTOR = ['se', 's', 'sw', 'w', 'nw', 'n', 'ne', 'e'] as const;

export function directionOf(dx: number, dy: number): string {
  const sector = Math.round(Math.atan2(dy, dx) / (Math.PI / 4));
  return BY_SECTOR[(sector + 8) % 8];
}

/** Загруженный визуал: кадры каждого состояния по направлениям. */
export class Visual {
  private constructor(
    readonly json: VisualJson,
    private readonly sheets: Spritesheet[],
  ) {}

  static async load(path: string): Promise<Visual> {
    const json: VisualJson = await (await fetch(`${ASSETS_URL}visuals/${path}.json`)).json();
    const atlases = new Set(json.atlases);
    for (const d of Object.values(json.directions)) d.atlases.forEach((a) => atlases.add(a));
    const sheets = await Promise.all([...atlases].map((a) => Assets.load<Spritesheet>(ASSETS_URL + a)));
    return new Visual(json, sheets);
  }

  private frame(name: string): Texture | undefined {
    for (const s of this.sheets) {
      const t = s.textures[name];
      if (t) return t;
    }
    return undefined;
  }

  /** Кадры слоя 0 состояния в направлении (имя кадра — <name>_<prefix>_<номер>.png). */
  textures(state: string, direction: string): Texture[] {
    const d = this.json.directions[direction];
    const layer = d?.states[state]?.[0];
    if (!layer) return [];
    return layer.frames.map((n) => this.frame(`${this.json.name}_${d.prefix}_${n}.png`)).filter((t): t is Texture => !!t);
  }
}

/**
 * Объект на карте с анимацией — как RjAnimationLayer::run: спрайт кадра с anchor (0, 0),
 * масштаб (sx, s), позиция (trunc(offsetX·sx), trunc(offsetY·s)) от точки объекта;
 * s = scale визуала, sx = −s у отражённых направлений.
 */
export class Animated extends Container {
  private readonly sprite: AnimatedSprite;
  private direction = '';

  constructor(
    private readonly visual: Visual,
    private readonly state: string,
    direction: string,
  ) {
    super();
    this.sprite = new AnimatedSprite({ textures: [visual.textures(state, direction)[0]], autoUpdate: false });
    this.sprite.animationSpeed = visual.json.fps / 60; // кадров анимации на тик при 60 Гц
    this.addChild(this.sprite);
    this.face(direction);
  }

  face(direction: string): void {
    if (direction === this.direction) return;
    const d = this.visual.json.directions[direction];
    const textures = this.visual.textures(this.state, direction);
    if (!d || !textures.length) return;
    const frame = this.sprite.currentFrame;
    this.direction = direction;
    this.sprite.textures = textures;
    this.sprite.gotoAndPlay(frame % textures.length); // шаг не сбивается при повороте
    const s = this.visual.json.scale;
    const sx = d.mirror ? -s : s;
    this.sprite.scale.set(sx, s);
    this.sprite.position.set(Math.trunc(d.offsetX * sx), Math.trunc(d.offsetY * s));
  }

  update(ticker: Ticker): void {
    this.sprite.update(ticker);
  }
}
