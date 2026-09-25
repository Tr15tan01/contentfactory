"use client";

import { useState } from "react";
import Link from "next/link";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { useSession } from "../session";
import { SettingsSection } from "../settings/section";
import { BrandForm } from "./brand-form";
import { PreferencesForm } from "./preferences-form";
import { ProductsEditor } from "./products-editor";
import { AudienceForm, ProfileForm } from "./profile-form";
import { useBusiness } from "./use-business";

function SavedNote({ show }: { show: boolean }) {
  return show ? <span role="status" className="text-sm text-lab">Saved</span> : null;
}

export function BusinessSettings() {
  const { workspace } = useSession();
  const biz = useBusiness();
  const [saved, setSaved] = useState<string | null>(null);
  const mark = (id: string) => () => {
    setSaved(id);
    window.setTimeout(() => setSaved((s) => (s === id ? null : s)), 3000);
  };

  if (biz.isPending) return <div className="grid gap-4"><Skeleton className="h-40" /><Skeleton className="h-40" /></div>;
  if (biz.error || !biz.data) {
    return <Alert tone="error" title="Business profile didn't load">{biz.error instanceof ApiError ? biz.error.message : "Try again."}</Alert>;
  }
  const b = biz.data;
  if (!biz.canManage) {
    return <Alert tone="info" title="Only owners and admins can edit the business profile">You can still add products and media.</Alert>;
  }

  return (
    <div className="grid gap-10">
      {!b.onboarding.completed && (
        <Alert tone="info" title="Setup isn't finished">
          The <Link href="/onboarding">guided setup</Link> walks through everything below, one step at a time.
        </Alert>
      )}
      <SettingsSection title="Business" description="Name, category, location and a short description.">
        <ProfileForm business={b} fallbackName={workspace.name} submitLabel="Save" onSaved={mark("profile")} secondary={<SavedNote show={saved === "profile"} />} />
      </SettingsSection>
      <SettingsSection title="Customers and goals" description="Who you're talking to and what marketing should achieve.">
        <AudienceForm business={b} fallbackName={workspace.name} submitLabel="Save" onSaved={mark("audience")} secondary={<SavedNote show={saved === "audience"} />} />
      </SettingsSection>
      <SettingsSection title="Brand" description="Voice, words, forbidden topics, colours and logo.">
        <BrandForm business={b} fallbackName={workspace.name} submitLabel="Save" onSaved={mark("brand")} secondary={<SavedNote show={saved === "brand"} />} />
      </SettingsSection>
      <SettingsSection title="Products and services" description="What you sell, with photos from your library.">
        <ProductsEditor products={b.products} />
      </SettingsSection>
      <SettingsSection title="Media and publishing" description="Media preference, platforms, rhythm, approval and reminders.">
        <PreferencesForm business={b} submitLabel="Save" onSaved={mark("prefs")} secondary={<SavedNote show={saved === "prefs"} />} />
      </SettingsSection>
    </div>
  );
}
