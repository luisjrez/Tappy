precision mediump float;
/** @resolution */
uniform vec2 u_resolution;
/** @time */
uniform float u_time;
/**
 * @label Ring color
 * @color
 * @default #185C46
 */
uniform vec3 u_color;
/**
 * @label Center X
 * @default 0.5
 * @range 0, 1
 */
uniform float u_cx;
/**
 * @label Center Y
 * @default 0.5
 * @range 0, 1
 */
uniform float u_cy;
/**
 * @label Speed
 * @default 1
 * @range 0, 4
 */
uniform float u_speed;
/**
 * @label Opacity
 * @default 0.5
 * @range 0, 1
 */
uniform float u_alpha;

void main() {
  float m = min(u_resolution.x, u_resolution.y);
  vec2 c = vec2(u_cx, u_cy) * u_resolution;
  float d = length(gl_FragCoord.xy - c) / m;
  float a = 0.0;
  for (int i = 0; i < 4; i++) {
    float t = fract(u_time * u_speed * 0.18 + float(i) * 0.25);
    float r = t * 0.75;
    float ring = smoothstep(0.006, 0.0, abs(d - r));
    float halo = smoothstep(0.08, 0.0, abs(d - r)) * 0.25;
    a += (ring + halo) * (1.0 - t) * smoothstep(0.0, 0.08, t);
  }
  a = clamp(a, 0.0, 1.0) * u_alpha;
  gl_FragColor = vec4(u_color * a, a);
}
