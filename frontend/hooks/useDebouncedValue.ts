import { useEffect, useState } from "react";

/**
 * Returns `value` delayed by `delay` ms. Used so the filter bars give instant typing feedback while
 * the (now server-side) data fetch only fires once the user pauses.
 */
export function useDebouncedValue<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}
