// "Add ChromaFix to your home screen" sheet for phone browsers. Author: Iris.
// Non-modal and docked at the bottom: the page stays usable, and the page gets extra bottom
// padding while the sheet is open so nothing is out of reach.
import { useEffect, useId, useReducer, useRef, useState, type ReactNode } from "react";

import type { Route } from "../router";
import {
  dismissForThisVisit,
  dismissedThisVisit,
  installPlatform,
  onInstallChange,
  promptInstall,
} from "./install";

/** Never during a screening or a study round, and never over a plate, image or camera view. */
const PROMPT_ROUTES: Route[] = ["welcome", "home", "profile"];

function Check() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 22 22" className="install-check">
      <circle cx="11" cy="11" r="11" fill="currentColor" />
      <path
        d="M6 11.5l3.2 3.2L16 8"
        fill="none"
        stroke="var(--surface-strong)"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** An icon drawn as a small key, the way it looks in Safari's menus. */
function Key({ label, children }: { label?: string; children: ReactNode }) {
  const a11y = label ? { role: "img", "aria-label": label } : { "aria-hidden": true };
  return (
    <span className="install-key">
      <svg {...a11y} width="18" height="18" viewBox="0 0 24 24">
        {children}
      </svg>
    </span>
  );
}

export function InstallPrompt({ route }: { route: Route }) {
  const titleId = useId();
  const [closed, setClosed] = useState(dismissedThisVisit);
  // Re-render when Chrome reports the app can (or can no longer) be installed.
  const [, refresh] = useReducer((n: number) => n + 1, 0);
  useEffect(() => onInstallChange(refresh), []);

  const platform = installPlatform();
  const open = !closed && platform !== null && PROMPT_ROUTES.includes(route);

  // Reserve room under the page for the sheet while it is open.
  const sheetRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const sheet = sheetRef.current;
    if (!open || !sheet) return;
    const root = document.documentElement;
    const observer = new ResizeObserver(() => {
      root.style.setProperty("--install-sheet-h", `${sheet.offsetHeight + 24}px`);
    });
    observer.observe(sheet);
    return () => {
      observer.disconnect();
      root.style.removeProperty("--install-sheet-h");
    };
  }, [open]);

  if (!open) return null;

  const notNow = () => {
    dismissForThisVisit();
    setClosed(true);
  };

  return (
    <aside ref={sheetRef} className="install-sheet" aria-labelledby={titleId}>
      <div className="install-head">
        <img src="/icons/icon.svg" alt="" width="44" height="44" className="install-icon" />
        <h2 id={titleId}>
          {platform === "ios" ? "Add ChromaFix to your Home Screen" : "Install ChromaFix"}
        </h2>
      </div>
      <ul className="install-benefits">
        <li>
          <Check />
          Opens full screen, without the browser bars
        </li>
        <li>
          <Check />
          Quicker to open: one tap from your home screen
        </li>
      </ul>

      {platform === "ios" ? (
        <>
          <ol className="install-steps">
            <li>
              <span className="install-step-n" aria-hidden="true">
                1
              </span>
              <span>
                Tap{" "}
                <Key label="the Share icon">
                  <path d="M8 10H6v10h12V10h-2M12 3v12M8.5 6.5L12 3l3.5 3.5" />
                </Key>{" "}
                <strong>Share</strong> in Safari. Don't see it? Tap{" "}
                <Key label="More">
                  <circle cx="5" cy="12" r="1.6" />
                  <circle cx="12" cy="12" r="1.6" />
                  <circle cx="19" cy="12" r="1.6" />
                </Key>{" "}
                first.
              </span>
            </li>
            <li>
              <span className="install-step-n" aria-hidden="true">
                2
              </span>
              <span>
                Then <strong>Add to Home Screen</strong>{" "}
                <Key>
                  <rect x="4" y="4" width="16" height="16" rx="4" />
                  <path d="M12 8.5v7M8.5 12h7" />
                </Key>
              </span>
            </li>
          </ol>
          <button type="button" className="install-not-now" onClick={notNow}>
            Not now
          </button>
        </>
      ) : (
        <>
          <div className="install-actions">
            <button type="button" onClick={notNow}>
              Not now
            </button>
            <button
              type="button"
              className="primary"
              onClick={() => {
                void promptInstall().then((installed) => {
                  if (!installed) notNow();
                });
              }}
            >
              Install app
            </button>
          </div>
          <p className="muted">Chrome asks you to confirm. You can remove it like any other app.</p>
        </>
      )}
    </aside>
  );
}
