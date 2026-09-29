import { ASSETS_URL } from './frames';

/** Имя семейства для шрифта из макета: 'fonts/Play-Bold.ttf' → 'Play-Bold'; системные — как есть. */
export const fontFamily = (fontName: string) =>
  fontName.endsWith('.ttf') ? (fontName.split('/').pop() ?? fontName).slice(0, -4) : fontName;

const loaded = new Map<string, Promise<void>>();

/** Подгрузить TTF из assets/fonts/ (системные шрифты вроде Helvetica пропускаются). */
export function loadFonts(fontNames: Iterable<string>): Promise<void[]> {
  const jobs: Promise<void>[] = [];
  for (const name of fontNames) {
    if (!name.endsWith('.ttf')) continue;
    const family = fontFamily(name);
    let job = loaded.get(family);
    if (!job) {
      const face = new FontFace(family, `url(${ASSETS_URL}fonts/${family}.ttf)`);
      job = face.load().then(
        (f) => void document.fonts.add(f),
        () => console.warn(`шрифт ${family} не загрузился — будет системный`),
      );
      loaded.set(family, job);
    }
    jobs.push(job);
  }
  return Promise.all(jobs);
}
