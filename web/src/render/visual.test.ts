import { describe, expect, it } from 'vitest';
import { directionOf } from './visual';

describe('directionOf', () => {
  it('восемь секторов по 45°, как смотрят кадры юнитов', () => {
    expect(directionOf(1, 0)).toBe('se'); // вправо
    expect(directionOf(1, 1)).toBe('s');
    expect(directionOf(0, 1)).toBe('sw'); // вниз, к камере
    expect(directionOf(-1, 1)).toBe('w');
    expect(directionOf(-1, 0)).toBe('nw');
    expect(directionOf(-1, -1)).toBe('n');
    expect(directionOf(0, -1)).toBe('ne'); // вверх, от камеры
    expect(directionOf(1, -1)).toBe('e');
  });

  it('отражённые направления зеркальны нарисованным (n↔e, w↔s, nw↔se)', () => {
    const mirror: Record<string, string> = { n: 'e', w: 's', nw: 'se' };
    for (const [dx, dy] of [
      [1, -1],
      [1, 1],
      [1, 0],
    ]) {
      expect(mirror[directionOf(-dx, dy)]).toBe(directionOf(dx, dy));
    }
  });
});
