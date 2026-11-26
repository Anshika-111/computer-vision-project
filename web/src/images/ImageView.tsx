// Upload an image and compare original, simulated, and recolored versions. Author: Iris.
import { useEffect, useState } from "react";

import {
  NeuralUnavailableError,
  getMethods,
  recolorImage,
  simulateImage,
  type CVDProfile,
  type Method,
} from "../api";

interface ImageViewProps {
  profile: CVDProfile;
}

interface Panel {
  label: string;
  url: string;
}

const METHOD_LABELS: Record<Method, string> = {
  none: "No recoloring",
  fixed: "Fixed daltonization",
  personalized: "Personalized",
  neural: "Neural",
};

export function ImageView({ profile }: ImageViewProps) {
  const [file, setFile] = useState<File | null>(null);
  const [methods, setMethods] = useState<Method[]>(["fixed"]);
  const [method, setMethod] = useState<Method>("fixed");
  const [panels, setPanels] = useState<Panel[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMethods()
      .then((available) => {
        const usable: Method[] = available.filter((m) => m !== "none");
        setMethods(usable);
        setMethod((current) => (usable.includes(current) ? current : (usable[0] ?? "fixed")));
      })
      .catch(() => setMethods(["fixed"]));
  }, []);

  useEffect(() => {
    if (!file) return;
    let cancelled = false;
    const urls: string[] = [];
    const track = (blob: Blob) => {
      const url = URL.createObjectURL(blob);
      urls.push(url);
      return url;
    };

    const run = async () => {
      setBusy(true);
      setError(null);
      const original: Panel = { label: "Original", url: track(file) };
      try {
        const simulated = await simulateImage(file, profile);
        const recolored = await recolorImage(file, profile, method);
        // Recolor first, then simulate: how the recolored image looks to this viewer.
        const recoloredSeen = await simulateImage(recolored, profile);
        if (cancelled) return;
        setPanels([
          original,
          { label: "As you see it (simulated)", url: track(simulated) },
          { label: `Recolored (${METHOD_LABELS[method]})`, url: track(recolored) },
          { label: "Recolored, as you see it", url: track(recoloredSeen) },
        ]);
      } catch (cause) {
        if (cancelled) return;
        setPanels([original]);
        setError(
          cause instanceof NeuralUnavailableError
            ? `${METHOD_LABELS[method]} recoloring is not available on this server.`
            : cause instanceof Error
              ? cause.message
              : String(cause),
        );
      } finally {
        if (!cancelled) setBusy(false);
      }
    };
    void run();

    return () => {
      cancelled = true;
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [file, profile, method]);

  return (
    <section>
      <div className="toolbar">
        <label>
          Image{" "}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <label>
          Method{" "}
          <select value={method} onChange={(e) => setMethod(e.target.value as Method)}>
            {methods.map((m) => (
              <option key={m} value={m}>
                {METHOD_LABELS[m]}
              </option>
            ))}
          </select>
        </label>
        {busy && <span className="muted">Processing…</span>}
      </div>
      <p className="muted">Images are processed in memory and never stored on the server.</p>
      {error && <p role="alert">{error}</p>}
      <div className="panels">
        {panels.map((panel) => (
          <figure key={panel.label}>
            <img src={panel.url} alt={panel.label} />
            <figcaption>{panel.label}</figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
