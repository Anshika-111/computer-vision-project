// Raw WebGL 1 renderer that applies a 3x3 color matrix to a frame. Author: Iris.
// Per pixel (CLAUDE.md Section 8): decode sRGB -> linear, multiply by the
// matrix, clamp to [0, 1], encode back to sRGB.
import type { Mat3 } from "../api";
import { toColumnMajor } from "./matrix";

const VERTEX_SHADER = `
attribute vec2 a_position;
varying vec2 v_uv;

void main() {
  v_uv = a_position * 0.5 + 0.5;
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

// IEC 61966-2-1 piecewise sRGB curve, the same one chromafix.color uses.
const FRAGMENT_SHADER = `
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif

uniform sampler2D u_frame;
uniform mat3 u_matrix;
varying vec2 v_uv;

vec3 srgbToLinear(vec3 c) {
  vec3 low = c / 12.92;
  vec3 high = pow((c + 0.055) / 1.055, vec3(2.4));
  return mix(low, high, step(vec3(0.04045), c));
}

vec3 linearToSrgb(vec3 c) {
  vec3 low = c * 12.92;
  vec3 high = 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055;
  return mix(low, high, step(vec3(0.0031308), c));
}

void main() {
  vec3 linear = srgbToLinear(texture2D(u_frame, v_uv).rgb);
  vec3 transformed = clamp(u_matrix * linear, 0.0, 1.0);
  gl_FragColor = vec4(linearToSrgb(transformed), 1.0);
}
`;

export interface Renderer {
  /** Draw one frame through the matrix. The canvas is resized to the frame. */
  draw(frame: TexImageSource, width: number, height: number, matrix: Mat3): void;
  /** Free the GL resources. */
  dispose(): void;
}

function compile(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) {
    throw new Error("Could not create shader");
  }
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error(`Shader compile failed: ${log}`);
  }
  return shader;
}

/** Create a renderer on the canvas. Throws if WebGL is not available. */
export function createRenderer(canvas: HTMLCanvasElement): Renderer {
  // preserveDrawingBuffer lets the frame be read back (snapshots, tests).
  const gl = canvas.getContext("webgl", { alpha: false, preserveDrawingBuffer: true });
  if (!gl) {
    throw new Error("WebGL is not available in this browser");
  }

  const vertex = compile(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
  const fragment = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  const program = gl.createProgram();
  if (!program) {
    throw new Error("Could not create program");
  }
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(`Program link failed: ${gl.getProgramInfoLog(program)}`);
  }
  gl.useProgram(program);

  // One full-screen quad as a triangle strip.
  const quad = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, quad);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(program, "a_position");
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

  // Video frames are not power-of-two, so WebGL 1 needs clamp + no mipmaps.
  const texture = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  // Image rows run top-down, GL texture rows bottom-up.
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
  // Keep the browser from converting colors behind our back.
  gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);

  const matrixLocation = gl.getUniformLocation(program, "u_matrix");
  gl.uniform1i(gl.getUniformLocation(program, "u_frame"), 0);

  return {
    draw(frame, width, height, matrix) {
      if (width === 0 || height === 0) {
        return;
      }
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      gl.viewport(0, 0, width, height);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, frame);
      // transpose must be false in WebGL 1; toColumnMajor does the transpose.
      gl.uniformMatrix3fv(matrixLocation, false, toColumnMajor(matrix));
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    },
    dispose() {
      gl.deleteTexture(texture);
      gl.deleteBuffer(quad);
      gl.deleteProgram(program);
      gl.deleteShader(vertex);
      gl.deleteShader(fragment);
    },
  };
}
