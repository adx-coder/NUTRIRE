import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import App from "./App";
import { routerBasename } from "./lib/router-base";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter basename={routerBasename()}>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>
);
