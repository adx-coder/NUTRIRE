/** Vite `base` without trailing slash — use as React Router `basename` (omit when serving at `/`). */
export function routerBasename(): string | undefined {
  const b = import.meta.env.BASE_URL.replace(/\/$/, "");
  return b || undefined;
}
