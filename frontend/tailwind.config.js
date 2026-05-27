/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
    "./node_modules/flowbite-react/lib/esm/**/*.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["Ubuntu Mono", "IBM Plex Mono", "monospace"],
        display: ["IBM Plex Mono", "Ubuntu Mono", "monospace"],
      },
      colors: {
        neurallog: {
          ink: "#081211",
          panel: "#0f1b1b",
          mint: "#b8ff7c",
          fog: "#96b5ae",
          line: "rgba(255,255,255,0.08)"
        }
      },
      boxShadow: {
        panel: "0 24px 70px rgba(0,0,0,0.28)"
      },
      backgroundImage: {
        "neurallog-grid":
          "radial-gradient(circle at top left, rgba(184,255,124,0.18), transparent 24%), radial-gradient(circle at 82% 10%, rgba(89,163,255,0.14), transparent 22%), linear-gradient(180deg, #081211 0%, #0b1516 48%, #091112 100%)"
      }
    },
  },
  plugins: [require("flowbite/plugin")],
};
