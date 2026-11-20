precision mediump float;
/** @resolution */
uniform vec2 u_resolution;
/** @time */
uniform float u_time;
/**
 * @label Color
 * @color
 * @default #9AE6C0
 */
uniform vec3 u_color;
/**
 * @label Opacity
 * @default 0.35
 * @range 0, 1
 */
uniform float u_alpha;
/**
 * @label Spacing
 * @default 40
 * @range 16, 96
 */
uniform float u_spacing;

void main() {
  vec2 id = floor(gl_FragCoord.xy / u_spacing);
  vec2 local = gl_FragCoord.xy - (id + 0.5) * u_spacing;
  float wave = 0.5 + 0.5 * sin((id.x + id.y) * 0.45 - u_time * 1.4);
  float arm = mix(2.0, u_spacing * 0.22, wave);
  float th = 0.9;
  float h = step(abs(local.y), th) * step(abs(local.x), arm);
  float v = step(abs(local.x), th) * step(abs(local.y), arm);
  float a = clamp(h + v, 0.0, 1.0) * u_alpha * (0.35 + 0.65 * wave);
  gl_FragColor = vec4(u_color * a, a);
}
