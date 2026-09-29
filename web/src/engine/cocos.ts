/**
 * Слой совместимости с cocos2d-x 2.x: геометрия узлов и правила CocosBuilder.
 *
 * Узел cocos: ось Y вверх, дети отсчитываются от левого нижнего угла contentSize родителя,
 * поворот и масштаб идут вокруг anchorPoint × contentSize (CCNode::nodeToParentTransform):
 *   parent = T(position [+ anchor в точках, если ignoreAnchorPointForPosition])
 *            · R(rotation, по часовой) · S(scale) · T(−anchor в точках) · local
 * У Container в PixiJS та же цепочка — T(position) · R(rotation) · S(scale) · T(−pivot), — только
 * ось Y смотрит вниз: точка cocos (u, v) узла высотой h — это (u, h − v) в локальных координатах Pixi.
 */

export interface Point {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

/** Геометрия узла cocos в абсолютных значениях (точки, градусы). */
export interface CocosGeometry {
  position: Point;
  /** anchorPoint, доли contentSize (0…1). */
  anchor: Point;
  /** contentSize. */
  size: Size;
  scale?: Point;
  /** Градусы по часовой стрелке, как в cocos2d-x. */
  rotation?: number;
  ignoreAnchorPointForPosition?: boolean;
}

/** Как выставить Container PixiJS, чтобы он совпал с узлом cocos. */
export interface PixiTransform {
  position: Point;
  pivot: Point;
  scale: Point;
  /** Радианы по часовой стрелке (ось Y вниз). */
  rotation: number;
}

/** Трансформация Container для узла cocos, лежащего в родителе высотой `parentHeight`. */
export function toPixiTransform(node: CocosGeometry, parentHeight: number): PixiTransform {
  const ax = node.anchor.x * node.size.width;
  const ay = node.anchor.y * node.size.height;
  const shift = node.ignoreAnchorPointForPosition ? 1 : 0;
  const x = node.position.x + shift * ax;
  const y = node.position.y + shift * ay;
  return {
    position: { x, y: parentHeight - y },
    pivot: { x: ax, y: node.size.height - ay },
    scale: { x: node.scale?.x ?? 1, y: node.scale?.y ?? 1 },
    rotation: ((node.rotation ?? 0) * Math.PI) / 180,
  };
}

/** Типы позиции CocosBuilder (kCCBPositionType*). */
export const PositionType = {
  RelativeBottomLeft: 0,
  RelativeTopLeft: 1,
  RelativeTopRight: 2,
  RelativeBottomRight: 3,
  Percent: 4,
  MultiplyResolution: 5,
} as const;

/** Типы размера CocosBuilder (kCCBSizeType*). */
export const SizeType = {
  Absolute: 0,
  Percent: 1,
  RelativeContainer: 2,
  HorizontalPercent: 3,
  VerticalPercent: 4,
  MultiplyResolution: 5,
} as const;

/** Типы масштаба CocosBuilder (kCCBScaleType*). */
export const ScaleType = {
  Absolute: 0,
  MultiplyResolution: 1,
} as const;

/** Проценты CocosBuilder обрезаются до целого, как `(int)` в CCBReader. */
const percent = (total: number, value: number) => Math.trunc((total * value) / 100);

/** Позиция из ccbi → абсолютная позиция в родителе (CCBReader::getAbsolutePosition). */
export function absolutePosition(pt: Point, type: number, container: Size, resolutionScale = 1): Point {
  switch (type) {
    case PositionType.RelativeTopLeft:
      return { x: pt.x, y: container.height - pt.y };
    case PositionType.RelativeTopRight:
      return { x: container.width - pt.x, y: container.height - pt.y };
    case PositionType.RelativeBottomRight:
      return { x: container.width - pt.x, y: pt.y };
    case PositionType.Percent:
      return { x: percent(container.width, pt.x), y: percent(container.height, pt.y) };
    case PositionType.MultiplyResolution:
      return { x: pt.x * resolutionScale, y: pt.y * resolutionScale };
    default:
      return { x: pt.x, y: pt.y };
  }
}

/** Размер из ccbi → абсолютный contentSize (CCNodeLoader::parsePropTypeSize). */
export function absoluteSize(size: Size, type: number, container: Size, resolutionScale = 1): Size {
  switch (type) {
    case SizeType.RelativeContainer:
      return { width: container.width - size.width, height: container.height - size.height };
    case SizeType.Percent:
      return { width: percent(container.width, size.width), height: percent(container.height, size.height) };
    case SizeType.HorizontalPercent:
      return { width: percent(container.width, size.width), height: size.height };
    case SizeType.VerticalPercent:
      return { width: size.width, height: percent(container.height, size.height) };
    case SizeType.MultiplyResolution:
      return { width: size.width * resolutionScale, height: size.height * resolutionScale };
    default:
      return { width: size.width, height: size.height };
  }
}

/** Масштаб из ccbi → абсолютный (CCNodeLoader::parsePropTypeScaleLock). */
export function absoluteScale(scale: Point, type: number, resolutionScale = 1): Point {
  const k = type === ScaleType.MultiplyResolution ? resolutionScale : 1;
  return { x: scale.x * k, y: scale.y * k };
}
