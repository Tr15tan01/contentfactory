"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ImagePlus, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChipsInput } from "@/components/ui/chips-input";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { businessApi } from "@/lib/api/endpoints";
import type { Product, ProductInput } from "@/types/api";
import { FormError } from "./form-bits";
import { MediaPicker } from "./media-picker";
import { CURRENCIES } from "./options";
import { useBusiness } from "./use-business";

const blank = (currency: string): ProductInput => ({ name: "", description: null, price: null, currency, benefits: [], target_customer: null, url: null, media_ids: [] });

function ProductForm({ initial, productId, onDone }: { initial: ProductInput; productId?: string; onDone: () => void }) {
  const { workspaceId, refresh } = useBusiness();
  const [p, setP] = useState(initial);
  const [picking, setPicking] = useState(false);
  const [previews, setPreviews] = useState<string[]>([]);
  const set = <K extends keyof ProductInput>(k: K, v: ProductInput[K]) => setP((x) => ({ ...x, [k]: v }));
  const save = useMutation({
    mutationFn: () => {
      const body = { ...p, price: p.price === "" ? null : p.price };
      return productId ? businessApi.updateProduct(workspaceId, productId, body) : businessApi.createProduct(workspaceId, body);
    },
    onSuccess: () => {
      refresh();
      onDone();
    },
  });

  return (
    <form className="grid gap-4 rounded-[var(--radius-card)] bg-sunk/60 p-4 ring-1 ring-line" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <FormError error={save.error} title="Product not saved" />
      <div className="grid gap-4 sm:grid-cols-[1fr_8rem_7rem]">
        <Field id="prod-name" label="Name">
          <Input value={p.name} onChange={(e) => set("name", e.target.value)} required maxLength={160} autoFocus />
        </Field>
        <Field id="prod-price" label="Price">
          <Input value={p.price ?? ""} onChange={(e) => set("price", e.target.value.replace(",", "."))} inputMode="decimal" pattern="^\d{1,10}(\.\d{1,2})?$" title="A number like 7.50" />
        </Field>
        <Field id="prod-currency" label="Currency">
          <Select value={p.currency} onChange={(e) => set("currency", e.target.value)}>
            {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
          </Select>
        </Field>
      </div>
      <Field id="prod-desc" label="Description" hint="Optional">
        <Textarea value={p.description ?? ""} onChange={(e) => set("description", e.target.value || null)} rows={2} className="min-h-20" maxLength={4000} />
      </Field>
      <Field id="prod-benefits" label="Why people love it" hint="Optional. Press Enter after each.">
        <ChipsInput value={p.benefits} onChange={(v) => set("benefits", v)} />
      </Field>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="secondary" size="sm" onClick={() => setPicking(true)}><ImagePlus /> {p.media_ids.length ? `${p.media_ids.length} photo${p.media_ids.length === 1 ? "" : "s"}` : "Add photos"}</Button>
        {/* eslint-disable-next-line @next/next/no-img-element -- signed storage URLs */}
        {previews.slice(0, 4).map((src) => <img key={src} src={src} alt="" className="size-9 rounded-md object-cover" />)}
      </div>
      <MediaPicker workspaceId={workspaceId} open={picking} onOpenChange={setPicking} selected={p.media_ids} onConfirm={(ids, assets) => { set("media_ids", ids); setPreviews(assets.map((a) => a.thumbnail_url ?? a.url ?? "").filter(Boolean)); }} />
      <div className="flex gap-2">
        <Button type="submit" size="sm" loading={save.isPending}>{productId ? "Save product" : "Add product"}</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </form>
  );
}

function ProductRow({ product, onEdit }: { product: Product; onEdit: () => void }) {
  const { workspaceId, refresh } = useBusiness();
  const remove = useMutation({ mutationFn: () => businessApi.deleteProduct(workspaceId, product.id), onSuccess: refresh });
  return (
    <li className="flex items-center gap-3 py-3">
      <div className="size-11 shrink-0 overflow-hidden rounded-md bg-sunk">
        {/* eslint-disable-next-line @next/next/no-img-element -- signed storage URL */}
        {product.thumbnails[0] && <img src={product.thumbnails[0]} alt="" className="size-full object-cover" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{product.name}</p>
        <p className="truncate text-sm text-muted">
          {product.price ? `${product.price} ${product.currency}` : "No price"}
          {product.benefits.length ? `, ${product.benefits.join(", ")}` : ""}
        </p>
      </div>
      <Button type="button" variant="ghost" size="icon" onClick={onEdit} aria-label={`Edit ${product.name}`}><Pencil className="size-4" /></Button>
      <Button type="button" variant="ghost" size="icon" onClick={() => remove.mutate()} disabled={remove.isPending} aria-label={`Delete ${product.name}`}><Trash2 className="size-4" /></Button>
    </li>
  );
}

export function ProductsEditor({ products, defaultCurrency = "USD" }: { products: Product[]; defaultCurrency?: string }) {
  const [editing, setEditing] = useState<string | "new" | null>(products.length ? null : "new");
  const currency = products[0]?.currency ?? defaultCurrency;
  return (
    <div className="grid gap-4">
      {products.length > 0 && (
        <ul className="divide-y divide-line border-y border-line">
          {products.map((p) =>
            editing === p.id ? (
              <li key={p.id} className="py-3">
                <ProductForm productId={p.id} initial={{ name: p.name, description: p.description, price: p.price, currency: p.currency, benefits: p.benefits, target_customer: p.target_customer, url: p.url, media_ids: p.media_ids }} onDone={() => setEditing(null)} />
              </li>
            ) : (
              <ProductRow key={p.id} product={p} onEdit={() => setEditing(p.id)} />
            ),
          )}
        </ul>
      )}
      {editing === "new" ? (
        <ProductForm initial={blank(currency)} onDone={() => setEditing(null)} />
      ) : (
        <div><Button type="button" variant="secondary" onClick={() => setEditing("new")}><Plus /> Add a product or service</Button></div>
      )}
    </div>
  );
}
