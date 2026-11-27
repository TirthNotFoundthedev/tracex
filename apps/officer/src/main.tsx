import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { apiBaseFromEnv } from "./api/client";
import { App } from "./App";
import "./officer.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element");
}

createRoot(root).render(
  <StrictMode>
    <App baseUrl={apiBaseFromEnv()} />
  </StrictMode>,
);
