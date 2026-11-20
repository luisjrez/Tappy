precision mediump float;
/** @resolution */
uniform vec2 u_resolution;
/** @time */
uniform float u_time;
/**
 * @label Base
 * @color
 * @default #0E3328
 */
uniform vec3 u_base;
/**
 * @label Glow A
 * @color
 * @default #1F7A5C
 */
uniform vec3 u_glowA;
/**
 * @label Glow B
 * @color
 * @default #9AE6C0
 */
uniform vec3 u_glowB;
/**
 * @label Intensity
 * @default 0.7
 * @range 0, 1
 */
uniform float u_intensity;

float blob(vec2 p, vec2 c, float r) {
  float d = length(p - c);
  return exp(-(d * d) / (r * r));
}

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_resolution;
  float asp = u_resolution.x / u_resolution.y;
  vec2 p = vec2(uv.x * asp, uv.y);
  float t = u_time * 0.12;
  float a1 = blob(p, vec2(asp * (0.70 + 0.12 * sin(t * 1.3)), 0.55 + 0.18 * cos(t)), 0.55);
  float a2 = blob(p, vec2(asp * (0.25 + 0.10 * cos(t * 0.9)), 0.15 + 0.12 * sin(t * 1.7)), 0.45);
  float b1 = blob(p, vec2(asp * (0.80 + 0.08 * cos(t * 1.1)), 0.80 + 0.10 * sin(t * 1.4)), 0.28);
  float b2 = blob(p, vec2(asp * (0.45 + 0.15 * sin(t * 0.7)), 0.95), 0.22);
  vec3 col = u_base;
  col = mix(col, u_glowA, clamp((a1 + a2) * 0.75 * u_intensity, 0.0, 1.0));
  col = mix(col, u_glowB, clamp((b1 + b2 * 0.6) * 0.35 * u_intensity, 0.0, 1.0));
  col += (hash(gl_FragCoord.xy + fract(u_time)) - 0.5) * 0.025;
  gl_FragColor = vec4(col, 1.0);
}
