import { useEffect, useRef } from "react";

/**
 * Moves the keyboard / screen-reader focus to a screen's heading when the screen opens,
 * so a screen reader announces the new screen. The heading needs tabIndex={-1}.
 */
export function useFocusHeading<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    ref.current?.focus({ preventScroll: true });
  }, []);
  return ref;
}
