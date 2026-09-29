import { Assets, Container, Rectangle, Sprite, Texture } from 'pixi.js';
import { ASSETS_URL } from '../engine/frames';

/** Тайл фона: страница `img` и её видимая часть (x, y, width, height) на общей картинке. */
export interface BackFrame {
  img: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Фон миссии: пререндеренная картинка, нарезанная на страницы до 1024². Страницы дополнены до
 * полного размера, видимую часть каждой задаёт textures_etc/maps/mission/<name>.xml
 * (<back_atlas><frame img x y width height>) — берём из страницы только её.
 */
export async function loadMapBackground(frames: BackFrame[]): Promise<Container> {
  const map = new Container({ label: 'map' });
  const pages = await Promise.all(
    frames.map((f) => Assets.load<Texture>(`${ASSETS_URL}textures_etc/maps/mission/${f.img}.webp`)),
  );
  frames.forEach((f, i) => {
    const visible = new Texture({ source: pages[i].source, frame: new Rectangle(0, 0, f.width, f.height) });
    const tile = new Sprite(visible);
    tile.position.set(f.x, f.y);
    map.addChild(tile);
  });
  return map;
}

/** Раскладка фона star_1_map_01 (из textures_etc/maps/mission/star_1_map_01.xml). */
export const STAR_1_MAP_01: BackFrame[] = [
  { img: 'star_1_map_01_0_0', x: 0, y: 0, width: 1024, height: 1024 },
  { img: 'star_1_map_01_0_1', x: 0, y: 1024, width: 1024, height: 138 },
  { img: 'star_1_map_01_1_0', x: 1024, y: 0, width: 589, height: 1024 },
  { img: 'star_1_map_01_1_1', x: 1024, y: 1024, width: 589, height: 138 },
];
