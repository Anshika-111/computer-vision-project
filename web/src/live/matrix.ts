// 3x3 matrix helpers for live mode. Author: Iris.
// Matrices are row-major and act on linear RGB column vectors (out = M @ in),
// exactly as /api/matrix returns them.
import type { Mat3 } from "../api";

export const IDENTITY: Mat3 = [
  [1, 0, 0],
  [0, 1, 0],
  [0, 0, 1],
];

/** Matrix product a @ b: applies b first, then a. */
export function multiply(a: Mat3, b: Mat3): Mat3 {
  const cell = (r: 0 | 1 | 2, c: 0 | 1 | 2): number =>
    a[r][0] * b[0][c] + a[r][1] * b[1][c] + a[r][2] * b[2][c];
  return [
    [cell(0, 0), cell(0, 1), cell(0, 2)],
    [cell(1, 0), cell(1, 1), cell(1, 2)],
    [cell(2, 0), cell(2, 1), cell(2, 2)],
  ];
}

/**
 * Matrix for the "simulated + recolored" preview: recolor first, then simulate,
 * which is S @ R. The order must never be swapped.
 *
 * Note: this skips the clip to [0, 1] that the Python path applies between the
 * two steps, so the preview can differ slightly on colors the recoloring
 * pushes out of range.
 */
export function simulateAfterRecolor(simulate: Mat3, recolor: Mat3): Mat3 {
  return multiply(simulate, recolor);
}

/**
 * Flatten a row-major matrix into the column-major order GLSL mat3 expects.
 * WebGL 1 requires transpose=false in uniformMatrix3fv, so the transpose
 * happens here.
 */
export function toColumnMajor(m: Mat3): Float32Array {
  return new Float32Array([
    m[0][0], m[1][0], m[2][0],
    m[0][1], m[1][1], m[2][1],
    m[0][2], m[1][2], m[2][2],
  ]);
}
