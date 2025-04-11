// src/hooks/use-on-click-outside.ts (adjust path as needed)

import { useEffect, RefObject } from 'react';

type Event = MouseEvent | TouchEvent;

/**
 * Custom hook that triggers a callback when a click occurs outside the referenced element.
 *
 * @param {RefObject<T>} ref - The React ref attached to the element to monitor.
 * @param {(event: Event) => void} handler - The callback function to execute on an outside click.
 * @template T - The type of the HTML element.
 */
export function useOnClickOutside<T extends HTMLElement = HTMLElement>(
  ref: RefObject<T>,
  handler: (event: Event) => void
): void {
  useEffect(() => {
    const listener = (event: Event) => {
      const el = ref?.current;

      // Do nothing if clicking ref's element or descendent elements
      // Also do nothing if the element is not currently mounted in the DOM
      if (!el || el.contains(event.target as Node)) {
        return;
      }

      handler(event); // Call the handler only if the click is outside
    };

    // Add event listeners
    document.addEventListener('mousedown', listener);
    document.addEventListener('touchstart', listener);

    // Cleanup function to remove event listeners
    return () => {
      document.removeEventListener('mousedown', listener);
      document.removeEventListener('touchstart', listener);
    };
  }, [ref, handler]); // Re-run effect only if ref or handler changes
}

// Export as default or named export based on your preference
// export default useOnClickOutside;