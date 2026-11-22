import "@testing-library/jest-dom/vitest";

import { afterEach, vi } from "vitest";
import { resetDemoState } from "./demo/tennesseeSeed";

if (typeof window !== "undefined") {
  if (!window.matchMedia) {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }),
    });
  }

  if (!window.ResizeObserver) {
    window.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }

  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {};
  }
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {};
  }
  if (!URL.createObjectURL) {
    URL.createObjectURL = vi.fn(() => "blob:mock-download");
  }
  if (!URL.revokeObjectURL) {
    URL.revokeObjectURL = vi.fn();
  }
}

afterEach(() => {
  resetDemoState();
  window.history.replaceState(null, "", "/");
});
