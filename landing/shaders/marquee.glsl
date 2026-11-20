precision mediump float;
/** @resolution */
uniform vec2 u_resolution;
/** @time */
uniform float u_time;
/** @label Strip image */
uniform sampler2D u_tex;
/**
 * @label Speed (px/s)
 * @default 60
 * @range -300, 300
 */
uniform float u_speed;

void main() {
  vec2 ts = vec2(textureSize(u_tex, 0));
  float scale = u_resolution.y / ts.y;
  float tileW = ts.x * scale;
  float x = mod(gl_FragCoord.x + u_time * u_speed, tileW) / tileW;
  gl_FragColor = texture2D(u_tex, vec2(x, gl_FragCoord.y / u_resolution.y));
}
