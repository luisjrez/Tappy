precision mediump float;
/** @resolution */
uniform vec2 u_resolution;
/** @time */
uniform float u_time;
/**
 * @label Dot color
 * @color
 * @default #185C46
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
 * @default 24
 * @range 8, 64
 */
uniform float u_spacing;
/**
 * @label Wave center X
 * @default 0.7
 * @range 0, 1
 */
uniform float u_cx;
/**
 * @label Wave center Y
 * @default 0.5
 * @range 0, 1
 */
uniform float u_cy;

void main() {
  float m = min(u_resolution.x, u_resolution.y);
  vec2 cellId = floor(gl_FragCoord.xy / u_spacing);
  vec2 center = (cellId + 0.5) * u_spacing;
  vec2 local = gl_FragCoord.xy - center;
  float d = length(center - vec2(u_cx, u_cy) * u_resolution) / m;
  float wave = 0.5 + 0.5 * sin(d * 16.0 - u_time * 1.8);
  float r = mix(0.7, 2.1, wave);
  float dotA = smoothstep(r + 0.6, r - 0.6, length(local));
  float fade = smoothstep(1.25, 0.05, d);
  float a = dotA * u_alpha * (0.3 + 0.7 * wave) * fade;
  gl_FragColor = vec4(u_color * a, a);
}
