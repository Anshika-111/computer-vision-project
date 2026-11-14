// Live webcam view with a color matrix applied on the GPU. Author: Iris.
import { useEffect, useRef, useState } from "react";

import type { Mat3 } from "../api";
import { createRenderer } from "./renderer";

interface LiveViewProps {
  /** Row-major matrix on linear RGB, as returned by /api/matrix. */
  matrix: Mat3;
}

export function LiveView({ matrix }: LiveViewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // The render loop reads the latest matrix without restarting the camera.
  const matrixRef = useRef(matrix);
  matrixRef.current = matrix;
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    let cancelled = false;
    let frameRequest = 0;
    let stream: MediaStream | null = null;
    let renderer: ReturnType<typeof createRenderer> | null = null;
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;

    const render = () => {
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        renderer?.draw(video, video.videoWidth, video.videoHeight, matrixRef.current);
      }
      frameRequest = requestAnimationFrame(render);
    };

    const start = async () => {
      try {
        renderer = createRenderer(canvas);
        const media = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        if (cancelled) {
          media.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = media;
        video.srcObject = media;
        await video.play();
        frameRequest = requestAnimationFrame(render);
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : String(cause));
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
  }, []);

  return (
    <div className="live-view">
      <canvas ref={canvasRef} />
      {error && <p role="alert">Camera unavailable: {error}</p>}
    </div>
  );
}
