precision mediump float;
/** @resolution */
uniform vec2 u_resolution;
/** @time */
uniform float u_time;
/**
 * @label Line color
 * @color
 * @default #9AE6C0
 */
uniform vec3 u_color;
/**
 * @label Opacity
 * @default 0.3
 * @range 0, 1
 */
uniform float u_alpha;
/**
 * @label Levels
 * @default 9
 * @range 2, 24
 */
uniform float u_levels;
/**
 * @label Scale (px)
 * @default 420
 * @range 100, 1200
 */
uniform float u_scale;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float field(vec2 p, float t) {
  return noise(p + vec2(t, -t * 0.7)) * 0.65 + noise(p * 2.1 - vec2(t * 0.8, t)) * 0.35;
}

void main() {
  float t = u_time * 0.06;
  vec2 p = gl_FragCoord.xy / u_scale;
  float px = 1.0 / u_scale;
  float v = field(p, t);
  float gx = field(p + vec2(px, 0.0), t) - v;
  float gy = field(p + vec2(0.0, px), t) - v;
  float grad = max(length(vec2(gx, gy)) * u_levels, 0.0001);
  float x = v * u_levels;
  float d = abs(fract(x + 0.5) - 0.5) / grad;
  float a = smoothstep(1.3, 0.0, d) * u_alpha;
  gl_FragColor = vec4(u_color * a, a);
}
