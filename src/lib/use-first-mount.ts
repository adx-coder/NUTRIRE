import { useRef } from "react";

const visited = new Set<string>();

/**
 * Returns true only on the very first mount of a page in this session.
 * Subsequent navigations back to the same path return false,
 * so entrance animations can be skipped on return visits.
 */
export function useFirstMount(key: string): boolean {
  const isFirst = useRef(!visited.has(key));
  visited.add(key);
  return isFirst.current;
}
