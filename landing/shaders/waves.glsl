precision mediump float;
/** @resolution */
uniform vec2 u_resolution;
/** @time */
uniform float u_time;
/**
 * @label Line color
 * @color
 * @default #185C46
 */
uniform vec3 u_color;
/**
 * @label Opacity
 * @default 0.4
 * @range 0, 1
 */
uniform float u_alpha;
/**
 * @label Lines
 * @default 18
 * @range 4, 40
 */
uniform float u_count;
/**
 * @label Amplitude
 * @default 0.06
 * @range 0, 0.3
 */
uniform float u_amp;
/**
 * @label Line width (px)
 * @default 1.4
 * @range 0.5, 4
 */
uniform float u_width;

void main() {
  vec2 uv = gl_FragCoord.xy / u_resolution;
  float t = u_time * 0.5;
  float a = 0.0;
  for (int i = 0; i < 40; i++) {
    float fi = float(i);
    if (fi >= u_count) break;
    float base = (fi + 0.5) / u_count;
    float off = u_amp * (sin(uv.x * 5.0 + t + fi * 0.32) * 0.65 + sin(uv.x * 11.0 - t * 0.7 + fi * 0.55) * 0.35);
    float d = abs(uv.y - base - off) * u_resolution.y;
    float line = smoothstep(u_width, 0.0, d);
    float pulse = 0.55 + 0.45 * sin(uv.x * 3.0 - t * 1.6 + fi * 0.4);
    a = max(a, line * pulse);
  }
  a *= u_alpha;
  gl_FragColor = vec4(u_color * a, a);
}
