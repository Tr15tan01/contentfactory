import { Suspense } from "react";
import { SocialSettings } from "@/components/app/settings/social-settings";

export const metadata = { title: "Social accounts" };

export default function SocialSettingsPage() {
  return (
    <Suspense>
      <SocialSettings />
    </Suspense>
  );
}
