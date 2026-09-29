import { Filter, GlProgram } from 'pixi.js';

// Порт shaders/GaussianBlur.{vert,frag} из оригинала: 5 выборок с линейной интерполяцией
// (эквивалент 9-точечного гаусса) по диагонали. Отличия — только обвязка PixiJS 8: имена
// атрибутов и униформ фильтра; веса и смещения 1.3846…/3.2307… — как в игре. В оригинале шаг
// задан в долях текстуры (0.002), здесь — в пикселях (uStep), чтобы не зависеть от её размера.
const vertex = /* glsl */ `
in vec2 aPosition;
out vec2 vCenter;
out vec2 vOneLeft;
out vec2 vTwoLeft;
out vec2 vOneRight;
out vec2 vTwoRight;

uniform vec4 uInputSize;
uniform vec4 uOutputFrame;
uniform vec4 uOutputTexture;
uniform vec2 uStep;

void main(void) {
  vec2 position = aPosition * uOutputFrame.zw + uOutputFrame.xy;
  position.x = position.x * (2.0 / uOutputTexture.x) - 1.0;
  position.y = position.y * (2.0 * uOutputTexture.z / uOutputTexture.y) - uOutputTexture.z;
  gl_Position = vec4(position, 0.0, 1.0);

  vec2 uv = aPosition * (uOutputFrame.zw * uInputSize.zw);
  vec2 texel = uStep * uInputSize.zw;
  vec2 firstOffset = 1.3846153846 * texel;
  vec2 secondOffset = 3.2307692308 * texel;
  vCenter = uv;
  vOneLeft = uv - firstOffset;
  vTwoLeft = uv - secondOffset;
  vOneRight = uv + firstOffset;
  vTwoRight = uv + secondOffset;
}`;

const fragment = /* glsl */ `
in vec2 vCenter;
in vec2 vOneLeft;
in vec2 vTwoLeft;
in vec2 vOneRight;
in vec2 vTwoRight;
out vec4 finalColor;

uniform sampler2D uTexture;

void main(void) {
  vec3 color = texture(uTexture, vCenter).rgb * 0.2270270270;
  color += texture(uTexture, vOneLeft).rgb * 0.3162162162;
  color += texture(uTexture, vOneRight).rgb * 0.3162162162;
  color += texture(uTexture, vTwoLeft).rgb * 0.0702702703;
  color += texture(uTexture, vTwoRight).rgb * 0.0702702703;
  finalColor = vec4(color, 1.0);
}`;

/** Размытие как в игре. Шаг — в пикселях; несколько проходов — несколько фильтров подряд. */
export function infernoBlur(stepPx = 2): Filter {
  return new Filter({
    glProgram: GlProgram.from({ vertex, fragment, name: 'inferno-gaussian-blur' }),
    resources: {
      blurUniforms: { uStep: { value: new Float32Array([stepPx, stepPx]), type: 'vec2<f32>' } },
    },
  });
}
