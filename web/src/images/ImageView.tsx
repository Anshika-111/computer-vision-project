// Recolor an uploaded image and compare it with the original, side by side. Author: Iris.
import { useEffect, useId, useRef, useState, type DragEvent } from "react";

import {
  NeuralUnavailableError,
  getMethods,
  recolorImage,
  simulateImage,
  type CVDProfile,
  type Method,
} from "../api";
import { typeLabel } from "../profile/profileStore";
import { routeHref } from "../router";

interface ImageViewProps {
  profile: CVDProfile;
}

/** Display order; only the methods the server lists are shown. */
const METHOD_ORDER: Method[] = ["none", "fixed", "personalized", "neural"];
const METHOD_LABELS: Record<Method, string> = {
  none: "None",
  fixed: "Fixed",
  personalized: "Personalized",
  neural: "Neural",
};
const ACCEPT = "image/png,image/jpeg,image/webp";

interface Result {
  original: string;
  recolored: string;
}

function describe(profile: CVDProfile): string {
  return `${typeLabel(profile.type).toLowerCase()} ${profile.severity.toFixed(1)}`;
}

function defaultMethod(available: Method[]): Method {
  if (available.includes("personalized")) return "personalized";
  if (available.includes("fixed")) return "fixed";
  return available[0] ?? "fixed";
}

function downloadName(file: File): string {
  const stem = file.name.replace(/\.[^.]+$/, "") || "image";
  return `${stem}-recolored.png`;
}

export function ImageView({ profile }: ImageViewProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [methods, setMethods] = useState<Method[]>(["none", "fixed"]);
  const [method, setMethod] = useState<Method>("fixed");
  const [simulated, setSimulated] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

  const isNormal = profile.type === "normal";
  const showSimulated = simulated && !isNormal;

  useEffect(() => {
    getMethods()
      .then((available) => {
        const usable = METHOD_ORDER.filter((m) => available.includes(m));
        setMethods(usable);
        setMethod((current) => (usable.includes(current) ? current : defaultMethod(usable)));
      })
      .catch(() => setMethods(["none", "fixed"]));
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
      try {
        const recolored = await recolorImage(file, profile, method);
        // Recolor first, then simulate (S @ R): how the recolored image looks to this viewer.
        const [left, right] = showSimulated
          ? await Promise.all([simulateImage(file, profile), simulateImage(recolored, profile)])
          : [file, recolored];
        if (cancelled) return;
        setResult({ original: track(left), recolored: track(right) });
        // Keep the unsimulated recolored PNG for download.
        setDownloadUrl(track(recolored));
      } catch (cause) {
        if (cancelled) return;
        setResult(null);
        setError(
          cause instanceof NeuralUnavailableError
            ? `${METHOD_LABELS[method]} recoloring isn't available on this server right now. Pick another method.`
            : `Couldn't recolor the image: ${cause instanceof Error ? cause.message : String(cause)}`,
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
  }, [file, profile, method, showSimulated]);

  const pick = (f: File | null | undefined) => {
    if (!f) return;
    if (!ACCEPT.split(",").includes(f.type)) {
      setError("That file isn't a PNG, JPEG or WebP image. Choose another one.");
      return;
    }
    setResult(null);
    setDownloadUrl(null);
    setFile(f);
  };

  const onDrop = (e: DragEvent<HTMLElement>) => {
    e.preventDefault();
    setDragging(false);
    pick(e.dataTransfer.files[0]);
  };

  const fileInput = (
    <input
      ref={inputRef}
      className="visually-hidden"
      tabIndex={-1}
      aria-hidden="true"
      type="file"
      accept={ACCEPT}
      onChange={(e) => {
        pick(e.target.files?.[0]);
        e.target.value = ""; // allow choosing the same file again
      }}
    />
  );

  const profileText = describe(profile);
  const recoloredCaption =
    method === "none" ? "Not recolored" : `Recolored · ${METHOD_LABELS[method].toLowerCase()}`;
  const seenBy = `, as ${profileText} sees it`;
  const forWhom = isNormal || method === "none" ? "" : ` for ${profileText}`;

  return (
    <section className="image-page">
      <h1>Recolor an image</h1>

      {!file ? (
        <div
          className="dropzone"
          data-dragging={dragging || undefined}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          {fileInput}
          <p className="dropzone-title">Drop an image here, or choose one from your device.</p>
          <button
            type="button"
            className="primary button-lg"
            onClick={() => inputRef.current?.click()}
          >
            Choose an image
          </button>
          <p className="muted">PNG, JPEG or WebP.</p>
        </div>
      ) : (
        <>
          <div className="image-toolbar">
            <div className="field">
              <span className="field-label" id={`${inputId}-m`}>
                Recoloring method
              </span>
              <div className="segmented" role="group" aria-labelledby={`${inputId}-m`}>
                {methods.map((m) => (
                  <button
                    key={m}
                    type="button"
                    aria-pressed={m === method}
                    onClick={() => setMethod(m)}
                  >
                    {METHOD_LABELS[m]}
                  </button>
                ))}
              </div>
            </div>
            {!isNormal && (
              <label className="image-sim">
                <input
                  type="checkbox"
                  checked={simulated}
                  onChange={(e) => setSimulated(e.target.checked)}
                />
                Show both as a {profileText} viewer would see them
              </label>
            )}
            <div className="image-actions">
              {fileInput}
              <button type="button" onClick={() => inputRef.current?.click()}>
                Choose another image
              </button>
              {downloadUrl && !busy ? (
                <a className="button primary" href={downloadUrl} download={downloadName(file)}>
                  Download recolored PNG
                </a>
              ) : (
                <button type="button" className="primary" disabled>
                  Download recolored PNG
                </button>
              )}
            </div>
          </div>

          <p className="image-status" aria-live="polite">
            {busy ? "Recoloring…" : ""}
          </p>
          {error && <p role="alert">{error}</p>}
          {isNormal && (
            <p className="muted">
              Your profile is typical color vision, so recoloring leaves the image unchanged.{" "}
              <a href={routeHref("profile")}>Change your profile</a> to try another type.
            </p>
          )}

          {result && (
            <div className="compare">
              <figure>
                <figcaption>{showSimulated ? `Original${seenBy}` : "Original"}</figcaption>
                <img src={result.original} alt={`${file.name}, original`} />
              </figure>
              <figure>
                <figcaption>
                  {recoloredCaption}
                  {showSimulated ? seenBy : forWhom}
                </figcaption>
                <img src={result.recolored} alt={`${file.name}, ${recoloredCaption.toLowerCase()}`} />
              </figure>
            </div>
          )}
        </>
      )}

      <p className="muted">
        Your image is sent to the server to be recolored and is not stored. Neural appears only
        when the model is available.
      </p>
    </section>
  );
}
