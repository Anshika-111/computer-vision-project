// App shell. Author: Iris.
// For now this only hosts live mode with fixed test matrices; the profile-driven
// controls arrive once /api/matrix exists.
import { useState } from "react";

import type { Mat3 } from "./api";
import { LiveView } from "./live/LiveView";
import { IDENTITY } from "./live/matrix";

// Not symmetric on purpose: if the matrix reached the shader transposed,
// red objects would turn blue instead of green.
const CYCLE_CHANNELS: Mat3 = [
  [0, 0, 1],
  [1, 0, 0],
  [0, 1, 0],
];

const TEST_MATRICES: { label: string; matrix: Mat3 }[] = [
  { label: "Original", matrix: IDENTITY },
  { label: "Test: red → green → blue → red", matrix: CYCLE_CHANNELS },
];

export function App() {
  const [selected, setSelected] = useState(0);
  const matrix = TEST_MATRICES[selected]?.matrix ?? IDENTITY;

  return (
    <main>
      <h1>ChromaFix</h1>
      <label>
        View{" "}
        <select value={selected} onChange={(event) => setSelected(Number(event.target.value))}>
          {TEST_MATRICES.map((option, index) => (
            <option key={option.label} value={index}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <LiveView matrix={matrix} />
    </main>
  );
}
