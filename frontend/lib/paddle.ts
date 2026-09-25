/** Loads Paddle.js v2 on demand and opens the overlay checkout. */
import type { CheckoutParams } from "@/types/api";

interface PaddleEvent {
  name?: string;
}

interface PaddleGlobal {
  Environment: { set: (env: string) => void };
  Initialize: (opts: { token: string; eventCallback?: (e: PaddleEvent) => void }) => void;
  Checkout: { open: (opts: Record<string, unknown>) => void };
}

declare global {
  interface Window {
    Paddle?: PaddleGlobal;
  }
}

const SRC = "https://cdn.paddle.com/paddle/v2/paddle.js";
let loading: Promise<PaddleGlobal> | null = null;
let listener: ((e: PaddleEvent) => void) | null = null;

function load(): Promise<PaddleGlobal> {
  if (window.Paddle) return Promise.resolve(window.Paddle);
  loading ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SRC;
    script.async = true;
    script.onload = () => (window.Paddle ? resolve(window.Paddle) : reject(new Error("Paddle failed to load")));
    script.onerror = () => {
      loading = null;
      reject(new Error("The payment window couldn't load. Check your connection or ad blocker and try again."));
    };
    document.head.appendChild(script);
  });
  return loading;
}

let initialized = false;

export async function openCheckout(params: CheckoutParams, onEvent: (name: string) => void, theme: "light" | "dark"): Promise<void> {
  const Paddle = await load();
  listener = (e) => e.name && onEvent(e.name);
  if (!initialized) {
    if (params.environment === "sandbox") Paddle.Environment.set("sandbox");
    Paddle.Initialize({ token: params.client_token, eventCallback: (e) => listener?.(e) });
    initialized = true;
  }
  Paddle.Checkout.open({
    items: [{ priceId: params.price_id, quantity: 1 }],
    customer: { email: params.customer_email },
    customData: params.custom_data,
    settings: { displayMode: "overlay", theme, allowLogout: false },
  });
}
