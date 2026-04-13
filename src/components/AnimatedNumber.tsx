import { animate, useInView } from "framer-motion";
import { useEffect, useRef, useState } from "react";

interface Props {
  value: number;
  format?: (n: number) => string;
  duration?: number;
  className?: string;
}

/**
 * Counts up to `value` when the element scrolls into view.
 * Uses Framer Motion's `animate` driver for the tween and `useInView` to
 * fire the animation only once — avoids re-triggering on scroll-back.
 * The easing curve [0.22, 1, 0.36, 1] matches the app's spring-like feel.
 */
export function AnimatedNumber({ value, format, duration = 1.6, className }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.4 });
  const [display, setDisplay] = useState(format ? format(0) : "0");

  useEffect(() => {
    if (!inView) return;
    const controls = animate(0, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setDisplay(format ? format(v) : Math.round(v).toString()),
    });
    return () => controls.stop();
  }, [inView, value, duration, format]);

  return (
    <span ref={ref} className={className}>
      {display}
    </span>
  );
}
