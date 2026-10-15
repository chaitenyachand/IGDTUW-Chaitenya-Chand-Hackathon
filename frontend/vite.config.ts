import { defineConfig } from "vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import tsConfigPaths from "vite-tsconfig-paths";
import { nitro } from "nitro/vite";

// SENTINEL terminal: TanStack Start + React 19 + Tailwind 4.
// VITE_* variables (VITE_API_BASE_URL, VITE_WS_URL) are read from .env / .env.local by Vite itself.
export default defineConfig(({ command }) => ({
  server: { host: "::", port: 8080 },
  resolve: { dedupe: ["react", "react-dom", "@tanstack/react-router", "@tanstack/react-query"] },
  plugins: [
    tsConfigPaths({ projects: ["./tsconfig.json"] }),
    tanstackStart({ server: { entry: "server" } }),
    viteReact(),
    tailwindcss(),
    ...(command === "build" ? [nitro()] : []),
  ],
}));
