// Focus mode: while a plate or a study round is on screen, phones hide the nav. Author: Iris.
// The flag lives on <html data-focus> so the stylesheet decides what to hide per screen size.
import { useEffect } from "react";

/** Turn focus mode on while `active` is true (and off when the caller unmounts). */
export function useFocusMode(active: boolean): void {
  useEffect(() => {
    if (!active) return;
    const root = document.documentElement;
    root.dataset.focus = "";
    return () => {
      delete root.dataset.focus;
    };
  }, [active]);
}
