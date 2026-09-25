"use client";

import { useMemo } from "react";
import { Select } from "@/components/ui/input";

export function TimezoneSelect(props: React.SelectHTMLAttributes<HTMLSelectElement> & { value: string }) {
  const zones = useMemo(() => {
    const list = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : ["UTC"];
    return list.includes(props.value) ? list : [props.value, ...list];
  }, [props.value]);
  return (
    <Select {...props}>
      {zones.map((z) => (
        <option key={z} value={z}>{z.replaceAll("_", " ")}</option>
      ))}
    </Select>
  );
}
