// When and how to offer "install ChromaFix" on a phone. Author: Iris.
// Rules (design canvas, Mobile page): phone browsers only, never once installed, never in
// in-app browsers, and "Not now" hides it for this visit only.
import { isStandalone } from "../displayMode";

/** Chrome's install event (not in the TypeScript DOM types). */
interface InstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export type InstallPlatform = "ios" | "android";

const DISMISS_KEY = "chromafix.installPrompt.dismissed";

// Chrome fires this once, often before React mounts, so it is caught at import time.
let deferred: InstallPromptEvent | null = null;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((fn) => fn());

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault(); // keep Chrome's own mini-bar away; our sheet asks instead
  deferred = event as InstallPromptEvent;
  notify();
});

window.addEventListener("appinstalled", () => {
  deferred = null;
  notify();
});

/** Subscribe to changes in whether Android can install; returns an unsubscribe function. */
export function onInstallChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Apps whose built-in browser can't add to the home screen. */
const IN_APP = /Instagram|FBAN|FBAV|FB_IAB|FBIOS|Line\/|TikTok|musical_ly|Bytedance|Snapchat|Twitter|LinkedInApp|Pinterest|MicroMessenger|WhatsApp|GSA\/|; wv\)/i;

function isPhone(): boolean {
  const touch = window.matchMedia("(pointer: coarse)").matches;
  return touch && Math.min(window.screen.width, window.screen.height) < 600;
}

/** Which install sheet to show right now, or null for none. */
export function installPlatform(): InstallPlatform | null {
  // Dev server only: preview either sheet on a laptop with ?install=ios or ?install=android.
  if (import.meta.env.DEV) {
    const preview = new URLSearchParams(window.location.search).get("install");
    if (preview === "ios" || preview === "android") return preview;
  }
  if (isStandalone() || !isPhone()) return null;
  const ua = navigator.userAgent;
  if (IN_APP.test(ua)) return null;
  // Safari on iPhone has no install API; other iOS browsers are left out (see the canvas note).
  const iosSafari =
    /iPhone|iPod/.test(ua) && /Safari\//.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);
  if (iosSafari) return "ios";
  // Android Chrome: only once the browser says the app can be installed.
  if (deferred) return "android";
  return null;
}

/** Show Chrome's install dialog. Resolves true if the person installed. */
export async function promptInstall(): Promise<boolean> {
  if (!deferred) return false;
  const event = deferred;
  deferred = null; // the event can be used only once
  await event.prompt();
  const { outcome } = await event.userChoice;
  notify();
  return outcome === "accepted";
}

export function dismissedThisVisit(): boolean {
  try {
    return sessionStorage.getItem(DISMISS_KEY) === "1";
  } catch {
    return false;
  }
}

/** "Not now": hide for this visit; a new visit (new tab session) shows it again. */
export function dismissForThisVisit(): void {
  try {
    sessionStorage.setItem(DISMISS_KEY, "1");
  } catch {
    // Storage blocked (private mode): the sheet still closes for this page view.
  }
}
