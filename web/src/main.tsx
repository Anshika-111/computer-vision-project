// Entry point for the ChromaFix web app. Author: Iris.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { trackDisplayMode } from "./displayMode";
import "./styles.css";

trackDisplayMode();

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
