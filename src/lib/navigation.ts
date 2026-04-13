import type { NavigateFunction } from "react-router-dom";

export function navigateBackOr(navigate: NavigateFunction, fallback: string) {
  if (window.history.length > 1) {
    navigate(-1);
    return;
  }

  navigate(fallback);
}
