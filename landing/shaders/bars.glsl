precision mediump float;
/** @resolution */
uniform vec2 u_resolution;
/** @time */
uniform float u_time;
/**
 * @label Bar color
 * @color
 * @default #CFE3D8
 */
uniform vec3 u_bar;
/**
 * @label Highlight
 * @color
 * @default #185C46
 */
uniform vec3 u_hi;
/**
 * @label Loop (s)
 * @default 6
 * @range 2, 12
 */
uniform float u_loop;

float h(int i) {
  if (i == 0) return 0.42;
  if (i == 1) return 0.58;
  if (i == 2) return 0.36;
  if (i == 3) return 0.71;
  if (i == 4) return 0.52;
  if (i == 5) return 0.88;
  return 0.64;
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_resolution;
  float ph = fract(u_time / u_loop + 0.5);
  float n = 7.0;
  float slot = uv.x * n;
  float i = floor(slot);
  float fx = fract(slot);
  int ii = int(i);
  float delay = i * 0.045;
  float g = smoothstep(0.0, 0.28, ph - delay);
  g = 1.0 - pow(1.0 - g, 3.0);
  float out_ = 1.0 - smoothstep(0.86, 0.98, ph);
  float top = h(ii) * g * out_;
  float r = 0.5 * 0.62 * u_resolution.x / n;
  vec2 px = vec2((fx - 0.5) * u_resolution.x / n, uv.y * u_resolution.y);
  float topPx = top * u_resolution.y;
  float inX = step(abs(px.x), r);
  float inY = step(px.y, topPx - r);
  vec2 capC = vec2(0.0, topPx - r);
  float cap = step(length(px - capC), r) * step(r * 2.0, topPx);
  float body = inX * inY * step(r * 2.0, topPx);
  float a = clamp(body + cap, 0.0, 1.0);
  vec3 col = ii == 5 ? u_hi : u_bar;
  gl_FragColor = vec4(col * a, a);
}
