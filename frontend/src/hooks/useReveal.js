import { useEffect } from "react";

// Fades sections in as they scroll into view. Skipped when the visitor
// prefers reduced motion, and everything stays visible if it is unsupported.
export default function useReveal(selector = ".lp-section, .lp-honest, .lp-cta, .lp-facts") {
  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) return undefined;

    const nodes = Array.from(document.querySelectorAll(selector));
    nodes.forEach((node) => node.classList.add("reveal"));

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("reveal-in");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );

    nodes.forEach((node) => observer.observe(node));

    // Fast jumps (anchor links, End key): reveal everything above the fold edge.
    const sweep = () => {
      nodes.forEach((node) => {
        if (node.getBoundingClientRect().top < window.innerHeight * 0.95) {
          node.classList.add("reveal-in");
        }
      });
    };
    window.addEventListener("scroll", sweep, { passive: true });
    sweep();

    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", sweep);
    };
  }, [selector]);
}
