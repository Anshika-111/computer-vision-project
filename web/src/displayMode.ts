// Installed-app detection: is ChromaFix running from the home screen (standalone)? Author: Iris.
// The answer is mirrored on <html data-standalone> so the stylesheet can swap the top nav for
// the bottom tab bar and pad the notch and home indicator.

const query = "(display-mode: standalone)";

/** True when the app was opened from the home screen rather than in a browser tab. */
export function isStandalone(): boolean {
  // iOS Safari reports home-screen apps through navigator.standalone.
  const ios = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return ios || window.matchMedia(query).matches;
}

/** Keep <html data-standalone> in sync with the display mode. Call once at startup. */
export function trackDisplayMode(): void {
  const root = document.documentElement;
  const update = () => {
    if (isStandalone()) root.dataset.standalone = "";
    else delete root.dataset.standalone;
  };
  update();
  window.matchMedia(query).addEventListener("change", update);
}
