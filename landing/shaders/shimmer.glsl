precision mediump float;
/** @resolution */
uniform vec2 u_resolution;
/** @time */
uniform float u_time;
/** @label Content */
uniform sampler2D u_content;
/**
 * @label Strength
 * @default 0.28
 * @range 0, 1
 */
uniform float u_strength;
/**
 * @label Period (s)
 * @default 3.2
 * @range 1, 10
 */
uniform float u_period;

void main() {
  vec2 uv = gl_FragCoord.xy / u_resolution;
  vec4 base = texture2D(u_content, uv);
  float ph = fract(u_time / u_period) * 2.2 - 0.6;
  float band = smoothstep(0.12, 0.0, abs(uv.x + (uv.y - 0.5) * 0.35 - ph));
  vec3 col = base.rgb + vec3(band * u_strength) * base.a;
  gl_FragColor = vec4(col, base.a);
}
