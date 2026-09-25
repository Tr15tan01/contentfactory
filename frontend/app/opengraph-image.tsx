import { ImageResponse } from "next/og";

export const alt = "ContentFactory — Your AI Marketing Team, On Autopilot";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", background: "#102326", color: "#e6eeec", padding: 72 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 34 }}>
          <div style={{ width: 40, height: 40, borderRadius: 999, border: "7px solid #4fc1b1", display: "flex" }} />
          ContentFactory
        </div>
        <div style={{ fontSize: 92, lineHeight: 0.98, letterSpacing: -3, fontWeight: 700, maxWidth: 980 }}>
          Your AI Marketing Team, On Autopilot.
        </div>
        <div style={{ display: "flex", gap: 14, fontSize: 28, color: "#9db0ae" }}>
          <span style={{ background: "#e8c93a", color: "#102326", padding: "4px 14px", borderRadius: 8 }}>Plan</span>
          <span style={{ padding: "4px 0" }}>Create, publish, learn. Every week.</span>
        </div>
      </div>
    ),
    size,
  );
}
