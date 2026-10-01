"use client";

import { useEffect, useState } from "react";

/**
 * true, sobald das Element ins Bild kommt (mit Vorlauf rootMargin), und danach dauerhaft: Bloecke laden ihren
 * Inhalt erst dann. Ohne IntersectionObserver (sehr alte Browser) gilt das Element als sichtbar; beim Rendern
 * auf dem Server ist es nie sichtbar.
 */
export function useInView<T extends Element>(rootMargin = "200px"): [(node: T | null) => void, boolean] {
  const [node, setNode] = useState<T | null>(null);
  const [seen, setSeen] = useState(false);
  const supported = typeof IntersectionObserver !== "undefined";

  useEffect(() => {
    if (!node || seen || !supported) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setSeen(true);
          observer.disconnect();
        }
      },
      { rootMargin },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [node, seen, supported, rootMargin]);

  return [setNode, seen || (node !== null && !supported)];
}
