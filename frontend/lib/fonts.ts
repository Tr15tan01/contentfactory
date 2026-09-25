import localFont from "next/font/local";

// Self-hosted from @fontsource-variable (no runtime request to Google). The "standard" files
// carry both axes: weight 400–700 and width 75–100%, so headlines can run condensed.
export const instrument = localFont({
  src: "../node_modules/@fontsource-variable/instrument-sans/files/instrument-sans-latin-standard-normal.woff2",
  variable: "--font-instrument",
  weight: "400 700",
  display: "swap",
  declarations: [{ prop: "font-stretch", value: "75% 100%" }],
  fallback: ["ui-sans-serif", "system-ui", "sans-serif"],
});

export const instrumentExt = localFont({
  src: "../node_modules/@fontsource-variable/instrument-sans/files/instrument-sans-latin-ext-standard-normal.woff2",
  variable: "--font-instrument-ext",
  weight: "400 700",
  display: "swap",
  preload: false,
  declarations: [
    { prop: "font-stretch", value: "75% 100%" },
    { prop: "unicode-range", value: "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF" },
  ],
});
