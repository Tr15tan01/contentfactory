import { SettingsTabs } from "@/components/app/settings/settings-tabs";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto grid max-w-6xl gap-8">
      <SettingsTabs />
      {children}
    </div>
  );
}
