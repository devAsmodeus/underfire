import { describe, expect, it } from 'vitest';
import {
  absolutePosition,
  absoluteScale,
  absoluteSize,
  type CocosGeometry,
  type Point,
  PositionType,
  ScaleType,
  SizeType,
  toPixiTransform,
} from './cocos';

/** Эталон cocos2d-x 2.x: точка local (ось Y вверх) узла → координаты родителя (ось Y вверх). */
function cocosToParent(n: CocosGeometry, local: Point): Point {
  const ax = n.anchor.x * n.size.width;
  const ay = n.anchor.y * n.size.height;
  const sx = n.scale?.x ?? 1;
  const sy = n.scale?.y ?? 1;
  const a = ((n.rotation ?? 0) * Math.PI) / 180;
  const u = (local.x - ax) * sx;
  const v = (local.y - ay) * sy;
  const ox = n.ignoreAnchorPointForPosition ? ax : 0;
  const oy = n.ignoreAnchorPointForPosition ? ay : 0;
  // поворот по часовой в системе с осью Y вверх
  return {
    x: n.position.x + ox + u * Math.cos(a) + v * Math.sin(a),
    y: n.position.y + oy - u * Math.sin(a) + v * Math.cos(a),
  };
}

/** То же через трансформацию Pixi (ось Y вниз) с переводом координат туда и обратно. */
function pixiToParent(n: CocosGeometry, local: Point, parentHeight: number): Point {
  const t = toPixiTransform(n, parentHeight);
  const lx = local.x - t.pivot.x;
  const ly = n.size.height - local.y - t.pivot.y; // локальная точка в системе Pixi
  const u = lx * t.scale.x;
  const v = ly * t.scale.y;
  const c = Math.cos(t.rotation);
  const s = Math.sin(t.rotation);
  const px = t.position.x + u * c - v * s;
  const py = t.position.y + u * s + v * c;
  return { x: px, y: parentHeight - py }; // обратно в систему cocos
}

describe('toPixiTransform', () => {
  const cases: [string, CocosGeometry][] = [
    ['без трансформаций', { position: { x: 10, y: 20 }, anchor: { x: 0, y: 0 }, size: { width: 50, height: 30 } }],
    ['anchor по центру', { position: { x: 100, y: 80 }, anchor: { x: 0.5, y: 0.5 }, size: { width: 60, height: 40 } }],
    [
      'масштаб, поворот, отражение',
      {
        position: { x: 300, y: 200 },
        anchor: { x: 0.25, y: 0.75 },
        size: { width: 80, height: 50 },
        scale: { x: -0.5, y: 2 },
        rotation: 30,
      },
    ],
    [
      'ignoreAnchorPointForPosition (CCMenu, CCLayer)',
      {
        position: { x: 0, y: 0 },
        anchor: { x: 0.5, y: 0.5 },
        size: { width: 1024, height: 768 },
        scale: { x: 0.8, y: 0.8 },
        ignoreAnchorPointForPosition: true,
      },
    ],
  ];
  const probes: Point[] = [
    { x: 0, y: 0 },
    { x: 13, y: 7 },
    { x: 60, y: 40 },
  ];

  for (const [name, node] of cases) {
    it(`совпадает с cocos2d-x: ${name}`, () => {
      for (const p of probes) {
        const want = cocosToParent(node, p);
        const got = pixiToParent(node, p, 500);
        expect(got.x).toBeCloseTo(want.x, 6);
        expect(got.y).toBeCloseTo(want.y, 6);
      }
    });
  }

  it('меню с масштабом сжимается к центру экрана, а не к углу', () => {
    const menu = cases[3][1];
    const corner = cocosToParent(menu, { x: 0, y: 0 });
    expect(corner.x).toBeCloseTo(512 - 512 * 0.8);
    expect(corner.y).toBeCloseTo(384 - 384 * 0.8);
  });
});

describe('CocosBuilder: позиции, размеры, масштаб', () => {
  const box = { width: 1024, height: 768 };

  it('позиция от разных углов родителя', () => {
    const p = { x: 10, y: 20 };
    expect(absolutePosition(p, PositionType.RelativeBottomLeft, box)).toEqual({ x: 10, y: 20 });
    expect(absolutePosition(p, PositionType.RelativeTopLeft, box)).toEqual({ x: 10, y: 748 });
    expect(absolutePosition(p, PositionType.RelativeTopRight, box)).toEqual({ x: 1014, y: 748 });
    expect(absolutePosition(p, PositionType.RelativeBottomRight, box)).toEqual({ x: 1014, y: 20 });
    expect(absolutePosition(p, PositionType.MultiplyResolution, box, 2)).toEqual({ x: 20, y: 40 });
  });

  it('проценты обрезаются до целого', () => {
    expect(absolutePosition({ x: 33.3, y: 50 }, PositionType.Percent, box)).toEqual({ x: 340, y: 384 });
    expect(absoluteSize({ width: 33.3, height: 100 }, SizeType.Percent, box)).toEqual({ width: 340, height: 768 });
  });

  it('размер относительно родителя и по одной оси', () => {
    const s = { width: 24, height: 50 };
    expect(absoluteSize(s, SizeType.Absolute, box)).toEqual(s);
    expect(absoluteSize(s, SizeType.RelativeContainer, box)).toEqual({ width: 1000, height: 718 });
    expect(absoluteSize(s, SizeType.HorizontalPercent, box)).toEqual({ width: 245, height: 50 });
    expect(absoluteSize(s, SizeType.VerticalPercent, box)).toEqual({ width: 24, height: 384 });
    expect(absoluteSize(s, SizeType.MultiplyResolution, box, 2)).toEqual({ width: 48, height: 100 });
  });

  it('масштаб умножается на разрешение только в своём режиме', () => {
    expect(absoluteScale({ x: 0.5, y: 0.5 }, ScaleType.Absolute, 2)).toEqual({ x: 0.5, y: 0.5 });
    expect(absoluteScale({ x: 0.5, y: 0.5 }, ScaleType.MultiplyResolution, 2)).toEqual({ x: 1, y: 1 });
  });
});
