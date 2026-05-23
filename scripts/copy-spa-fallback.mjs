import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(__dirname, "..", "dist");
const index = path.join(dist, "index.html");
const fallback = path.join(dist, "404.html");

if (!fs.existsSync(index)) {
  console.error("copy-spa-fallback: dist/index.html missing — run vite build first");
  process.exit(1);
}
fs.copyFileSync(index, fallback);
console.log("copy-spa-fallback: wrote dist/404.html (GitHub Pages SPA refresh)");
