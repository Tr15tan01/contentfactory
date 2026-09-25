import { cn } from "@/lib/utils";

// Painted stand-ins for a business's own photos in product illustrations (no stock imagery).
const palettes = {
  espresso: "radial-gradient(circle at 35% 40%, #c68a55 0 14%, #5a321d 15% 30%, transparent 31%), radial-gradient(circle at 70% 75%, #2d1a10 0 20%, transparent 21%), linear-gradient(135deg, #3b2418, #8a5a3c)",
  latte: "radial-gradient(circle at 50% 45%, #f4e6d4 0 18%, #c79b6d 19% 28%, #7a4f31 29% 34%, transparent 35%), linear-gradient(160deg, #d9c2a5, #9c7652)",
  coldbrew: "radial-gradient(ellipse 16% 5% at 50% 30%, #e7cfae 0 70%, transparent 72%), linear-gradient(180deg, transparent 29%, #24140c 30% 82%, transparent 83%) 50% 0 / 32% 100% no-repeat, radial-gradient(ellipse 30% 6% at 50% 84%, #1a0f0a 0 60%, transparent 62%), linear-gradient(180deg, #b98d63 0 55%, #6b4a33 56%)",
  pastry: "radial-gradient(ellipse at 45% 55%, #e9b867 0 22%, #b8732f 23% 32%, transparent 33%), radial-gradient(circle at 75% 30%, #f2dfc0 0 9%, transparent 10%), linear-gradient(145deg, #efe2cf, #c9a57c)",
  bar: "repeating-linear-gradient(90deg, #3a2a20 0 18px, #4a3629 18px 36px), linear-gradient(180deg, transparent 60%, #1f1510 60%)",
} as const;

export type PhotoKind = keyof typeof palettes;

export function PhotoTile({ kind, label, className }: { kind: PhotoKind; label?: string; className?: string }) {
  return (
    <div
      role="img"
      aria-label={label ?? "Business photo"}
      className={cn("relative overflow-hidden rounded-[10px]", className)}
      style={{ background: palettes[kind] }}
    >
      {label && (
        <span className="absolute bottom-1.5 left-1.5 rounded bg-black/45 px-1.5 py-0.5 text-[0.6875rem] text-white/90 backdrop-blur-sm">
          {label}
        </span>
      )}
    </div>
  );
}
