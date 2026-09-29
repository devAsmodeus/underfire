import { Container, Graphics, Rectangle, Sprite, Text, type Texture } from 'pixi.js';
import {
  absolutePosition,
  absoluteScale,
  absoluteSize,
  type Point,
  PositionType,
  ScaleType,
  type Size,
  SizeType,
  toPixiTransform,
} from '../engine/cocos';
import { fontFamily } from '../engine/fonts';
import type { FrameCache } from '../engine/frames';

// ---- Формат макета: docs/formats/ccbi-json.md (собирает tools/ccbi_to_json.py) ----

export interface CcbProp {
  type: string;
  value: unknown;
  positionType?: keyof typeof PositionType;
  sizeType?: keyof typeof SizeType;
  scaleType?: keyof typeof ScaleType;
  platform?: 'iOS' | 'Mac';
}

export interface CcbNode {
  baseClass: string;
  customClass: string | null;
  memberVarAssignment: { target: string; name: string } | null;
  properties: Record<string, CcbProp>;
  customProperties: Record<string, CcbProp>;
  children: CcbNode[];
}

export interface CcbDoc {
  formatVersion: number;
  source: { layer: string | null; path: string };
  resolution: { name: string; width: number; height: number } | null;
  autoPlaySequenceId: number;
  root: CcbNode;
}

export interface BuildOptions {
  frames: FrameCache;
  /** Размер экрана в точках: контейнер корня и размер CCLayer/CCMenu по умолчанию. */
  winSize: Size;
  /** 1 для HD-атласов интерфейса, 2 — для SD. */
  resolutionScale?: number;
  /** Макеты-шаблоны строк списков (`_template`) по имени. */
  templates?: ReadonlyMap<string, CcbDoc>;
  /** Нажатие кнопки или зоны касания: селектор колбэка из макета. */
  onCallback?: (selector: string, node: Container) => void;
}

export interface Layout {
  root: Container;
  size: Size;
  /** Узлы, которые игра получает по имени (memberVarAssignment). */
  outlets: Map<string, Container>;
  missingFrames: Set<string>;
  nodes: number;
}

// Наследники CCLayer: без записанного contentSize они размером с экран (docs/formats/ccbi-json.md).
const LAYER_LIKE = new Set(['CCLayer', 'CCLayerColor', 'CCMenu', 'CCNodeSelector', 'CCTextLayout']);
const MENU_ITEMS = new Set(['CCMenuItemImage', 'CCTextButton']);
const LABELS = new Set(['CCLabelTTF', 'CCLabelTTFLocalized']);
// Конструкторы cocos2d-x ставят этим классам anchor (0.5, 0.5); у голого CCNode — (0, 0).
const CENTER_ANCHOR = new Set(['CCSprite', 'CCProgressTimer', 'CCCheckBox', ...MENU_ITEMS, ...LABELS]);
const ALIGN = [0, 0.5, 1];

const rgb = ([r, g, b]: number[]) => (r << 16) | (g << 8) | b;
const className = (n: CcbNode) => n.customClass ?? n.baseClass;

/** Кадры, шрифты и шаблоны, на которые ссылается макет, — чтобы загрузить их заранее. */
export function collectRefs(doc: CcbDoc): { frames: Set<string>; fonts: Set<string>; templates: Set<string> } {
  const refs = { frames: new Set<string>(), fonts: new Set<string>(), templates: new Set<string>() };
  const walk = (n: CcbNode) => {
    for (const [name, p] of Object.entries(n.properties)) {
      if (p.type === 'SpriteFrame') {
        const frame = (p.value as { frame: string }).frame;
        if (frame) refs.frames.add(frame);
      } else if (p.type === 'FontTTF') refs.fonts.add(p.value as string);
      else if (name === '_template' && p.value) refs.templates.add(p.value as string);
    }
    n.children.forEach(walk);
  };
  walk(doc.root);
  return refs;
}

interface Ctx extends BuildOptions {
  rs: number;
  outlets: Map<string, Container>;
  missing: Set<string>;
  nodes: number;
}

/** Собрать макет в дерево Container PixiJS с геометрией cocos2d-x 2.x. */
export function buildLayout(doc: CcbDoc, opts: BuildOptions): Layout {
  const ctx: Ctx = { ...opts, rs: opts.resolutionScale ?? 1, outlets: new Map(), missing: new Set(), nodes: 0 };
  const { view, size } = buildNode(doc.root, opts.winSize, ctx);
  return { root: view, size, outlets: ctx.outlets, missingFrames: ctx.missing, nodes: ctx.nodes };
}

function buildNode(n: CcbNode, parent: Size, ctx: Ctx): { view: Container; size: Size } {
  ctx.nodes++;
  const cls = className(n);
  const layerLike = LAYER_LIKE.has(cls) || LAYER_LIKE.has(n.baseClass);
  const view = new Container({ label: n.memberVarAssignment?.name || cls });

  // Свойства применяются по порядку файла, как в CCNodeLoader::parseProperties.
  let size: Size = layerLike ? { ...ctx.winSize } : { width: 0, height: 0 };
  let position: Point = { x: 0, y: 0 };
  let anchor: Point = layerLike || CENTER_ANCHOR.has(cls) ? { x: 0.5, y: 0.5 } : { x: 0, y: 0 };
  let scale: Point = { x: 1, y: 1 };
  let rotation = 0;
  let ignoreAnchor = layerLike;
  let opacity = 255;
  let color = [255, 255, 255];
  let dimensions: Size = { width: 0, height: 0 };
  let selector: string | undefined;
  const frames: Record<string, Texture | undefined> = {};
  const values: Record<string, unknown> = {};

  for (const [name, p] of Object.entries(n.properties)) {
    if (p.platform === 'Mac') continue; // cocos2d-x 2.2 применяет iOS-свойства везде, Mac — нигде
    switch (name) {
      case 'position':
        position = absolutePosition(p.value as Point, PositionType[p.positionType ?? 'RelativeBottomLeft'], parent, ctx.rs);
        break;
      case 'contentSize':
        size = absoluteSize(p.value as Size, SizeType[p.sizeType ?? 'Absolute'], parent, ctx.rs);
        break;
      case 'dimensions':
        dimensions = absoluteSize(p.value as Size, SizeType[p.sizeType ?? 'Absolute'], parent, ctx.rs);
        break;
      case 'anchorPoint':
        anchor = p.value as Point;
        break;
      case 'scale':
        scale =
          p.type === 'ScaleLock'
            ? absoluteScale(p.value as Point, ScaleType[p.scaleType ?? 'Absolute'], ctx.rs)
            : { x: p.value as number, y: p.value as number };
        break;
      case 'rotation':
        rotation = p.value as number;
        break;
      case 'ignoreAnchorPointForPosition':
        ignoreAnchor = p.value as boolean;
        break;
      case 'visible':
        view.visible = p.value as boolean;
        break;
      case 'opacity':
        opacity = p.value as number;
        break;
      case 'color':
        color = p.value as number[];
        break;
      case 'block':
        selector = (p.value as { selector: string }).selector || undefined;
        break;
      default:
        if (p.type === 'SpriteFrame') frames[name] = frameTexture(p, ctx);
        else values[name] = p.type === 'FloatScale' ? (p.value as number) * (p.scaleType === 'MultiplyResolution' ? ctx.rs : 1) : p.value;
    }
  }

  // Собственное содержимое узла — под детьми, как draw() в cocos. Прозрачность и цвет в cocos2d-x 2.x
  // по умолчанию не наследуются детьми, поэтому применяются к содержимому, а не ко всему Container.
  const own = (obj: Container) => {
    obj.alpha = opacity / 255;
    obj.tint = rgb(color); // у меток color — цвет текста (заливка белая, тон умножается)
    view.addChild(obj);
  };

  if (cls === 'CCSprite' || cls === 'CCProgressTimer') {
    const tex = frames.displayFrame;
    if (tex) {
      size = { width: tex.orig.width, height: tex.orig.height }; // contentSize спрайта — исходный кадр
      const sprite = new Sprite(tex);
      own(sprite);
      if (cls === 'CCProgressTimer') progressMask(sprite, size, values);
    }
  } else if (MENU_ITEMS.has(cls) || cls === 'CCCheckBox') {
    const checkbox = cls === 'CCCheckBox';
    const normal = checkbox ? frames[values.selected ? 'selectedImage' : 'normalImage'] : frames.normalSpriteFrame;
    const pressed = checkbox ? frames.selectedImage : frames.selectedSpriteFrame;
    if (normal) {
      size = { width: normal.orig.width, height: normal.orig.height }; // кадр перезаписывает contentSize
      const sprite = new Sprite(normal);
      own(sprite);
      makeButton(view, size, ctx, selector, sprite, normal, pressed);
    }
    if (cls === 'CCTextButton' && typeof values.string === 'string') {
      own(label(values.string, values, 'normal', size).text);
    }
  } else if (LABELS.has(cls)) {
    const l = label(String(values.string ?? ''), values, '', dimensions);
    size = l.size;
    own(l.text);
  } else if (cls === 'CCLayerColor') {
    own(new Graphics().rect(0, 0, size.width, size.height).fill(0xffffff));
  } else if (cls === 'CCNodeSelector') {
    makeButton(view, size, ctx, selector);
  }

  const t = toPixiTransform({ position, anchor, size, scale, rotation, ignoreAnchorPointForPosition: ignoreAnchor }, parent.height);
  view.position.copyFrom(t.position);
  view.pivot.copyFrom(t.pivot);
  view.scale.copyFrom(t.scale);
  view.rotation = t.rotation;

  const name = n.memberVarAssignment?.name;
  if (name) ctx.outlets.set(name, view);

  if (cls === 'CCScrollListView') scrollList(view, size, values, ctx);
  for (const child of n.children) view.addChild(buildNode(child, size, ctx).view);
  return { view, size };
}

function frameTexture(p: CcbProp, ctx: Ctx): Texture | undefined {
  const { frame } = p.value as { frame: string };
  if (!frame) return undefined;
  const tex = ctx.frames.texture(frame);
  if (!tex) ctx.missing.add(frame);
  return tex;
}

/** CCLabelTTF и надпись CCTextButton: бокс dimensions (0×0 — по тексту) и выравнивание по осям. */
function label(str: string, v: Record<string, unknown>, prefix: '' | 'normal', box: Size) {
  const key = (k: string) => (prefix ? prefix + k[0].toUpperCase() + k.slice(1) : k);
  const h = ALIGN[(v[key('horizontalAlignment')] as number) ?? 0] ?? 0;
  const vAlign = ALIGN[(v[key('verticalAlignment')] as number) ?? 0] ?? 0;
  const text = new Text({
    text: str,
    style: {
      fontFamily: [fontFamily(String(v[key('fontName')] ?? 'Helvetica')), 'sans-serif'],
      fontSize: (v[key('fontSize')] as number) ?? 16,
      fill: 0xffffff,
      align: (['left', 'center', 'right'] as const)[ALIGN.indexOf(h)],
      wordWrap: box.width > 0,
      wordWrapWidth: box.width,
      breakWords: true,
    },
  });
  const size = { width: box.width || text.width, height: box.height || text.height };
  const offset = (prefix && (v.normalOffset as Point)) || { x: 0, y: 0 };
  text.x = (size.width - text.width) * h + offset.x;
  text.y = (size.height - text.height) * vAlign - offset.y;
  return { text, size };
}

/** Кнопка меню или зона касания: нажатая картинка на время касания, колбэк — по отпусканию. */
function makeButton(view: Container, size: Size, ctx: Ctx, selector?: string, sprite?: Sprite, normal?: Texture, pressed?: Texture) {
  view.eventMode = 'static';
  view.cursor = 'pointer';
  view.hitArea = new Rectangle(0, 0, size.width, size.height);
  const set = (tex?: Texture) => {
    if (sprite && tex) sprite.texture = tex;
  };
  view.on('pointerdown', () => set(pressed));
  view.on('pointerup', () => set(normal));
  view.on('pointerupoutside', () => set(normal));
  view.on('pointertap', () => selector && ctx.onCallback?.(selector, view));
}

/** CCProgressTimer, тип «полоса»: видна доля percentage вдоль barChangeRate от midpoint. */
function progressMask(sprite: Sprite, size: Size, v: Record<string, unknown>) {
  if (v.type !== 1) return; // радиальный — в прототипе целиком
  const k = ((v.percentage as number) ?? 100) / 100;
  const rate = (v.barChangeRate as Point) ?? { x: 1, y: 0 };
  const mid = (v.midpoint as Point) ?? { x: 0, y: 0 };
  const w = size.width * (rate.x ? k : 1);
  const h = size.height * (rate.y ? k : 1);
  const x = (size.width - w) * mid.x;
  const y = (size.height - h) * (1 - mid.y); // midpoint в системе cocos (Y вверх)
  const mask = new Graphics().rect(x, y, w, h).fill(0xffffff);
  sprite.parent?.addChild(mask);
  sprite.mask = mask;
}

/** CCScrollListView: строки из шаблона `_template` в окне contentSize (раскладку ведёт код игры). */
function scrollList(view: Container, size: Size, v: Record<string, unknown>, ctx: Ctx) {
  const template = ctx.templates?.get(String(v._template ?? ''));
  if (!template) return;
  const rows = new Container({ label: 'rows' });
  const mask = new Graphics().rect(0, 0, size.width, size.height).fill(0xffffff);
  view.addChild(rows, mask);
  rows.mask = mask;
  const count = Math.max(1, (v._count as number) || 3);
  for (let i = 0; i < count; i++) {
    const row = buildNode(template.root, size, ctx);
    const step = v.horizontal ? row.size.width : row.size.height;
    // строки подряд от левого верхнего угла окна
    row.view.x += v.horizontal ? i * step : 0;
    row.view.y += v.horizontal ? 0 : i * step;
    rows.addChild(row.view);
  }
}
