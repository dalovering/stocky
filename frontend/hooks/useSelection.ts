"use client";

import { useState } from "react";

/**
 * Row-selection state for the admin tables: a Set of ids plus toggles for one row, a group of
 * rows (per-group select-all), and clear-all. Shared by the users and inventory pages so
 * multi-select behaves identically.
 */
export function useSelection() {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const toggleOne = (id: string, checked: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });

  const toggleMany = (ids: string[], checked: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev);
      for (const id of ids) {
        if (checked) next.add(id);
        else next.delete(id);
      }
      return next;
    });

  const clear = () => setSelected(new Set());

  return { selected, toggleOne, toggleMany, clear };
}
