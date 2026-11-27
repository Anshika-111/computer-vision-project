// Current CVD profile plus where it came from, remembered across reloads. Author: Iris.
// Stored only in this browser's localStorage: type, severity and confidence, no identity.
import { useCallback, useState } from "react";

import type { CVDProfile, CVDType } from "../api";

/** "example" = nothing chosen yet; the app uses a demo profile until screening or manual entry. */
export type ProfileSource = "example" | "screening" | "manual";

export interface ProfileState {
  profile: CVDProfile;
  source: ProfileSource;
}

const KEY = "chromafix.profile.v1";
const TYPES: readonly CVDType[] = ["normal", "protan", "deutan", "tritan"];
const SOURCES: readonly ProfileSource[] = ["example", "screening", "manual"];

export const EXAMPLE_STATE: ProfileState = {
  profile: { type: "deutan", severity: 1, confidence: 1 },
  source: "example",
};

function inUnit(x: unknown): x is number {
  return typeof x === "number" && Number.isFinite(x) && x >= 0 && x <= 1;
}

/** Parse a stored value, rejecting anything that is not a valid profile. */
export function parseStored(raw: string | null): ProfileState | null {
  if (!raw) return null;
  try {
    const d = JSON.parse(raw) as { profile?: Partial<CVDProfile>; source?: unknown };
    const p = d.profile;
    if (!p || !TYPES.includes(p.type as CVDType)) return null;
    if (!inUnit(p.severity) || !inUnit(p.confidence)) return null;
    if (!SOURCES.includes(d.source as ProfileSource)) return null;
    return {
      profile: { type: p.type as CVDType, severity: p.severity, confidence: p.confidence },
      source: d.source as ProfileSource,
    };
  } catch {
    return null;
  }
}

function load(): ProfileState {
  try {
    return parseStored(window.localStorage.getItem(KEY)) ?? EXAMPLE_STATE;
  } catch {
    return EXAMPLE_STATE; // storage blocked (private window, policy): fall back quietly
  }
}

function save(state: ProfileState): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // Not fatal: the profile still works for this visit.
  }
}

export function useProfileStore(): [ProfileState, (next: ProfileState) => void] {
  const [state, setState] = useState<ProfileState>(load);
  const update = useCallback((next: ProfileState) => {
    setState(next);
    save(next);
  }, []);
  return [state, update];
}

export function typeLabel(type: CVDType): string {
  return type.charAt(0).toUpperCase() + type.slice(1);
}

/** Short label for the header chip, e.g. "Deutan · 0.6". */
export function profileLabel(profile: CVDProfile): string {
  if (profile.type === "normal") return "Normal vision";
  return `${typeLabel(profile.type)} · ${profile.severity.toFixed(1)}`;
}
