// Live webcam view with a color matrix applied on the GPU. Author: Iris.
import { useEffect, useRef, useState } from "react";

import type { Mat3 } from "../api";
import { createRenderer } from "./renderer";

/** Which camera to ask for. Phones default to the back camera; laptops get their only one. */
export type Facing = "environment" | "user";

interface LiveViewProps {
  /** Row-major matrix on linear RGB, as returned by /api/matrix. */
  matrix: Mat3;
  facing: Facing;
  /** Called once the camera runs, with how many cameras the device has. */
  onCameraCount?: (count: number) => void;
}

/** Plain-language reason the camera could not start. */
function cameraError(cause: unknown): string {
  const name = cause instanceof DOMException ? cause.name : "";
  if (name === "NotAllowedError" || name === "SecurityError")
    return "Camera access was blocked. Allow the camera for this site in your browser settings, then turn it on again.";
  if (name === "NotFoundError" || name === "OverconstrainedError")
    return "No camera was found. Connect one, then turn it on again.";
  if (name === "NotReadableError")
    return "The camera is in use by another app. Close that app, then turn it on again.";
  return `The camera couldn't start: ${cause instanceof Error ? cause.message : String(cause)}`;
}

export function LiveView({ matrix, facing, onCameraCount }: LiveViewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // The render loop reads the latest matrix without restarting the camera.
  const matrixRef = useRef(matrix);
  matrixRef.current = matrix;
  const [error, setError] = useState<string | null>(null);
  const [fps, setFps] = useState<number | null>(null);
  const [starting, setStarting] = useState(true);
  const countRef = useRef(onCameraCount);
  countRef.current = onCameraCount;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    let cancelled = false;
    setStarting(true);
    setError(null);
    let frameRequest = 0;
    let stream: MediaStream | null = null;
    let renderer: ReturnType<typeof createRenderer> | null = null;
    // Frames drawn since the last FPS update, and when that update happened.
    let frames = 0;
    let windowStart = performance.now();
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;

    const render = () => {
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        renderer?.draw(video, video.videoWidth, video.videoHeight, matrixRef.current);
        frames += 1;
      }
      const now = performance.now();
      if (now - windowStart >= 500) {
        setFps(Math.round((frames * 1000) / (now - windowStart)));
        frames = 0;
        windowStart = now;
      }
      frameRequest = requestAnimationFrame(render);
    };

    const start = async () => {
      try {
        renderer = createRenderer(canvas);
        const media = await navigator.mediaDevices.getUserMedia({
          // "ideal", not "exact": a laptop with one camera still gets that camera.
          video: { facingMode: { ideal: facing } },
          audio: false,
        });
        if (cancelled) {
          media.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = media;
        video.srcObject = media;
        await video.play();
        if (!cancelled) setStarting(false);
        frameRequest = requestAnimationFrame(render);
        // Device labels and counts are only reliable after permission is granted.
        const devices = await navigator.mediaDevices.enumerateDevices();
        if (!cancelled) countRef.current?.(devices.filter((d) => d.kind === "videoinput").length);
      } catch (cause) {
        if (!cancelled) {
          setError(cameraError(cause));
          setStarting(false);
        }
      }
    };
    void start();

    return () => {
      cancelled = true;
      cancelAnimationFrame(frameRequest);
      stream?.getTracks().forEach((track) => track.stop());
      video.srcObject = null;
      renderer?.dispose();
    };
  }, [facing]);

  return (
    <div className="live-view" data-idle={starting || error ? true : undefined}>
      <canvas ref={canvasRef} />
      {fps !== null && !error && <span className="fps">{fps} fps</span>}
      {starting && <p className="live-view-msg">Starting camera…</p>}
      {error && (
        <p className="live-view-msg" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
