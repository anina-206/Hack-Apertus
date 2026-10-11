import { useEffect, useState } from "react";

const query = "(prefers-reduced-motion: reduce)";

/** True when the device asks for less motion. For animations that CSS cannot switch off (e.g. recharts). */
export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia?.(query).matches ?? false);
  useEffect(() => {
    const media = window.matchMedia?.(query);
    if (!media) return;
    const onChange = () => setReduced(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);
  return reduced;
}
