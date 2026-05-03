/**
 * useCompare — manage the compare basket (up to 3 products) via localStorage.
 */
import { useState, useCallback } from "react";

const STORAGE_KEY = "alaqsa_compare";
const MAX_COMPARE = 3;

function readIds(): number[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function writeIds(ids: number[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
}

export function useCompare() {
  const [ids, setIds] = useState<number[]>(readIds);

  const addToCompare = useCallback((id: number) => {
    setIds((prev) => {
      if (prev.includes(id)) return prev;
      if (prev.length >= MAX_COMPARE) {
        // Drop oldest and add new
        const next = [...prev.slice(1), id];
        writeIds(next);
        return next;
      }
      const next = [...prev, id];
      writeIds(next);
      return next;
    });
  }, []);

  const removeFromCompare = useCallback((id: number) => {
    setIds((prev) => {
      const next = prev.filter((x) => x !== id);
      writeIds(next);
      return next;
    });
  }, []);

  const clearCompare = useCallback(() => {
    setIds([]);
    writeIds([]);
  }, []);

  const isInCompare = useCallback((id: number) => ids.includes(id), [ids]);

  return { ids, addToCompare, removeFromCompare, clearCompare, isInCompare, count: ids.length };
}
