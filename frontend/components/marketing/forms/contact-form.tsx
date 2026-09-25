"use client";

import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { publicApi, type ContactTopic } from "@/lib/api/endpoints";

const topics: { value: ContactTopic; label: string }[] = [
  { value: "sales", label: "Plans and pricing" },
  { value: "support", label: "Help with my account" },
  { value: "partnership", label: "Partnership" },
  { value: "press", label: "Press" },
  { value: "other", label: "Something else" },
];

export function ContactForm() {
  const [status, setStatus] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const message = String(data.get("message") ?? "").trim();
    if (message.length < 10) {
      setFieldErrors({ message: "Add a little more detail (at least 10 characters)." });
      return;
    }
    setStatus("sending");
    setError(null);
    setFieldErrors({});
    try {
      await publicApi.contact({
        name: String(data.get("name") ?? "").trim(),
        email: String(data.get("email") ?? "").trim(),
        topic: data.get("topic") as ContactTopic,
        message,
      });
      setStatus("sent");
    } catch (err) {
      setStatus("idle");
      if (err instanceof ApiError && err.status === 429) setError("You've sent several messages recently. Try again in an hour, or email us directly.");
      else if (err instanceof ApiError && err.status === 422) setError("Check the email address and try again.");
      else setError(err instanceof ApiError ? err.message : "Your message wasn't sent. Try again.");
    }
  }

  if (status === "sent") {
    return (
      <Alert tone="success" title="Message sent">
        Thanks. We&apos;ll reply to your email within one business day.
      </Alert>
    );
  }

  return (
    <form onSubmit={onSubmit} className="grid max-w-xl gap-5" noValidate={false}>
      {error && <Alert tone="error" title="Message not sent">{error}</Alert>}
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="name" label="Your name">
          <Input name="name" required maxLength={120} autoComplete="name" />
        </Field>
        <Field id="email" label="Email">
          <Input name="email" type="email" required autoComplete="email" />
        </Field>
      </div>
      <Field id="topic" label="What is it about?">
        <Select name="topic" defaultValue="sales">
          {topics.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </Select>
      </Field>
      <Field id="message" label="Message" error={fieldErrors.message}>
        <Textarea name="message" required minLength={10} maxLength={5000} rows={6} />
      </Field>
      <div>
        <Button type="submit" size="lg" loading={status === "sending"}>Send message</Button>
      </div>
    </form>
  );
}
