import { describe, expect, it } from 'vitest';
import type { FrameCache } from '../engine/frames';
import { buildLayout, type CcbDoc, type CcbNode, type CcbProp, collectRefs } from './ccb';

const prop = (type: string, value: unknown, extra: Partial<CcbProp> = {}): CcbProp => ({ type, value, ...extra });

function node(baseClass: string, properties: Record<string, CcbProp>, children: CcbNode[] = [], name?: string): CcbNode {
  return {
    baseClass,
    customClass: null,
    memberVarAssignment: name ? { target: 'Owner', name } : null,
    properties,
    customProperties: {},
    children,
  };
}

const doc = (root: CcbNode): CcbDoc => ({
  formatVersion: 1,
  source: { layer: 'obb_patch', path: 'test.ccbi' },
  resolution: { name: '1024x768', width: 1024, height: 768 },
  autoPlaySequenceId: -1,
  root,
});

// Кэш без атласов: любой кадр «не найден».
const noFrames = { texture: () => undefined } as unknown as FrameCache;
const winSize = { width: 1024, height: 768 };

describe('collectRefs', () => {
  it('собирает кадры, шрифты и шаблоны строк', () => {
    const d = doc(
      node('CCNode', {}, [
        node('CCSprite', { displayFrame: prop('SpriteFrame', { sheet: '', frame: 'icon.png' }) }),
        node('CCLabelTTF', { fontName: prop('FontTTF', 'fonts/Play.ttf') }),
        node('CCScrollListView', { _template: prop('Text', 'row_template') }),
      ]),
    );
    const refs = collectRefs(d);
    expect([...refs.frames]).toEqual(['icon.png']);
    expect([...refs.fonts]).toEqual(['fonts/Play.ttf']);
    expect([...refs.templates]).toEqual(['row_template']);
  });
});

describe('buildLayout', () => {
  const layout = buildLayout(
    doc(
      node('CCLayer', { contentSize: prop('Size', { width: 100, height: 100 }, { sizeType: 'Percent' }) }, [
        node(
          'CCNode',
          {
            position: prop('Position', { x: 50, y: 50 }, { positionType: 'Percent' }),
            contentSize: prop('Size', { width: 200, height: 100 }, { sizeType: 'Absolute' }),
            anchorPoint: prop('Point', { x: 0.5, y: 0.5 }),
          },
          [node('CCSprite', { displayFrame: prop('SpriteFrame', { sheet: '', frame: 'missing.png' }) })],
          'panel',
        ),
        node('CCMenu', { position: prop('Position', { x: 0, y: 0 }, { positionType: 'RelativeBottomLeft' }) }),
      ]),
    ),
    { frames: noFrames, winSize },
  );

  it('корень CCLayer 100 % — размером с экран', () => {
    expect(layout.size).toEqual(winSize);
    expect(layout.nodes).toBe(4);
  });

  it('узел в процентах от родителя, anchor по центру, ось Y перевёрнута', () => {
    const panel = layout.outlets.get('panel');
    expect(panel).toBeDefined();
    expect(panel?.position.x).toBe(512);
    expect(panel?.position.y).toBe(768 - 384);
    expect(panel?.pivot.x).toBe(100);
    expect(panel?.pivot.y).toBe(50);
  });

  it('CCMenu без размера — размером с экран, позиция — угол (ignoreAnchorPointForPosition)', () => {
    const menu = layout.root.children.find((c) => c.label === 'CCMenu');
    expect(menu?.pivot.x).toBe(512);
    expect(menu?.pivot.y).toBe(384);
    expect(menu?.position.x).toBe(512);
    expect(menu?.position.y).toBe(384);
  });

  it('недостающие кадры собираются в отчёт', () => {
    expect([...layout.missingFrames]).toEqual(['missing.png']);
  });
});
