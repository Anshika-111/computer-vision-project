// Typed client for the ChromaFix API (CLAUDE.md Section 8). Author: Iris.
// Every network call in the frontend goes through this file.

export type CVDType = "normal" | "protan" | "deutan" | "tritan";
export type Method = "none" | "fixed" | "personalized" | "neural";
/** Methods that have a 3x3 matrix form. Neural is image-only. */
export type MatrixMethod = Exclude<Method, "neural">;

export interface CVDProfile {
  type: CVDType;
  /** 0.0-1.0; 0.0 when type is "normal". */
  severity: number;
  /** 0.0-1.0, from screening. */
  confidence: number;
}

/** Row-major 3x3 matrix acting on linear RGB column vectors: out = M @ in. */
export type Mat3 = [
  [number, number, number],
  [number, number, number],
  [number, number, number],
];

/** Plate metadata as served to the client (never includes fail_severity). */
export interface PlateMeta {
  plate_id: string;
  target_type: CVDType;
  difficulty: number;
  is_control: boolean;
}

export interface PlateAnswer {
  plate_id: string;
  /** A digit "0"-"9", or "none". */
  answer: string;
}

/**
 * One mini-game trial. The trial shape is not defined in CLAUDE.md yet
 * (pending a [contract] PR), so only the fields the log format implies are typed.
 */
export interface GameTrial {
  trial_id: number;
  image_id: string;
  condition: Method;
  [key: string]: unknown;
}

/** One study-log object (CLAUDE.md Section 7). */
export interface StudyLog {
  session_id: string;
  participant_id: string;
  profile: CVDProfile;
  game: string;
  trial_id: number;
  image_id: string;
  condition: Method;
  answer: string;
  correct: boolean;
  rt_ms: number;
  /** ISO 8601 with timezone, e.g. new Date().toISOString(). */
  timestamp: string;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Thrown by recolorImage when the neural model is not available (HTTP 503). */
export class NeuralUnavailableError extends ApiError {
  constructor() {
    super(503, "Neural recoloring is not available on this server");
    this.name = "NeuralUnavailableError";
  }
}

const BASE = "/api";

async function request(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${BASE}${path}`, init);
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new ApiError(response.status, `${response.status} ${response.statusText} ${body}`.trim());
  }
  return response;
}

async function getJSON<T>(path: string): Promise<T> {
  return (await request(path)).json() as Promise<T>;
}

function postJSON(path: string, body: unknown): Promise<Response> {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// --- Screening -------------------------------------------------------------

export function getPlates(n = 24): Promise<PlateMeta[]> {
  return getJSON(`/plates?n=${n}`);
}

/** URL of a plate image, for use as an <img> src. */
export function plateImageUrl(plateId: string): string {
  return `${BASE}/plates/${encodeURIComponent(plateId)}.png`;
}

export async function scoreScreening(answers: PlateAnswer[]): Promise<CVDProfile> {
  return (await postJSON("/screening/score", { answers })).json() as Promise<CVDProfile>;
}

// --- Matrices (live mode) --------------------------------------------------

export async function getSimulationMatrix(type: CVDType, severity: number): Promise<Mat3> {
  const query = new URLSearchParams({ mode: "simulate", type, severity: String(severity) });
  return (await getJSON<{ matrix: Mat3 }>(`/matrix?${query}`)).matrix;
}

export async function getRecolorMatrix(
  method: MatrixMethod,
  type: CVDType,
  severity: number,
): Promise<Mat3> {
  const query = new URLSearchParams({
    mode: "recolor",
    method,
    type,
    severity: String(severity),
  });
  return (await getJSON<{ matrix: Mat3 }>(`/matrix?${query}`)).matrix;
}

// --- Images ----------------------------------------------------------------

/** Returns the simulated image as a PNG blob. The server does not store the upload. */
export async function simulateImage(image: Blob, profile: CVDProfile): Promise<Blob> {
  const form = new FormData();
  form.append("image", image);
  form.append("profile", JSON.stringify(profile));
  return (await request("/simulate", { method: "POST", body: form })).blob();
}

/** Returns the recolored image as a PNG blob. Throws NeuralUnavailableError on 503. */
export async function recolorImage(
  image: Blob,
  profile: CVDProfile,
  method: Method,
): Promise<Blob> {
  const form = new FormData();
  form.append("image", image);
  form.append("profile", JSON.stringify(profile));
  form.append("method", method);
  try {
    return await (await request("/recolor", { method: "POST", body: form })).blob();
  } catch (error) {
    if (error instanceof ApiError && error.status === 503) {
      throw new NeuralUnavailableError();
    }
    throw error;
  }
}

export function getMethods(): Promise<Method[]> {
  return getJSON("/methods");
}

// --- Mini-games and study logging -----------------------------------------

export function getGameTrials(game: string, participantId: string): Promise<GameTrial[]> {
  const query = new URLSearchParams({ participant_id: participantId });
  return getJSON(`/games/${encodeURIComponent(game)}/trials?${query}`);
}

export async function postLog(log: StudyLog): Promise<void> {
  await postJSON("/logs", log);
}
