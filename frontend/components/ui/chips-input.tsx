"use client";

import { useId, useState } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

/** Free-text list editor: Enter or comma adds, Backspace on empty removes the last item. */
export function ChipsInput({
  id,
  value,
  onChange,
  placeholder,
  suggestions = [],
  max = 20,
  normalize = (v) => v.trim(),
  className,
  "aria-invalid": invalid,
  "aria-describedby": describedBy,
}: {
  id?: string;
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  suggestions?: string[];
  max?: number;
  normalize?: (v: string) => string;
  className?: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
}) {
  const [draft, setDraft] = useState("");
  const listId = useId();
  const add = (raw: string) => {
    const v = normalize(raw.replace(/,$/, ""));
    if (!v || value.some((x) => x.toLowerCase() === v.toLowerCase()) || value.length >= max) return setDraft("");
    onChange([...value, v]);
    setDraft("");
  };
  const open = suggestions.filter((s) => !value.includes(s) && s.toLowerCase().includes(draft.toLowerCase())).slice(0, 8);

  return (
    <div className={cn("grid gap-2", className)}>
      <div
        className={cn(
          "flex min-h-11 flex-wrap items-center gap-1.5 rounded-[var(--radius-control)] bg-surface px-2 py-1.5 ring-1 ring-inset ring-line-strong focus-within:ring-2 focus-within:ring-lab",
          invalid && "ring-signal",
        )}
      >
        {value.map((v) => (
          <span key={v} className="inline-flex items-center gap-1 rounded-full bg-sunk py-0.5 pl-2.5 pr-1 text-sm">
            {v}
            <button type="button" onClick={() => onChange(value.filter((x) => x !== v))} className="grid size-5 place-items-center rounded-full text-muted hover:bg-line hover:text-ink" aria-label={`Remove ${v}`}>
              <X className="size-3" />
            </button>
          </span>
        ))}
        <input
          id={id}
          value={draft}
          list={suggestions.length ? listId : undefined}
          aria-invalid={invalid}
          aria-describedby={describedBy}
          onChange={(e) => (e.target.value.endsWith(",") ? add(e.target.value) : setDraft(e.target.value))}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add(draft);
            } else if (e.key === "Backspace" && !draft && value.length) {
              onChange(value.slice(0, -1));
            }
          }}
          onBlur={() => draft && add(draft)}
          placeholder={value.length ? "" : placeholder}
          className="h-8 min-w-32 flex-1 bg-transparent px-1.5 text-base outline-none placeholder:text-faint"
        />
      </div>
      {suggestions.length > 0 && (
        <datalist id={listId}>
          {open.map((s) => <option key={s} value={s} />)}
        </datalist>
      )}
    </div>
  );
}
