import { vi } from "vitest";

interface ObserverInstance {
  callback: IntersectionObserverCallback;
}

const instances: ObserverInstance[] = [];

class MockIntersectionObserver implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = "";
  readonly thresholds: ReadonlyArray<number> = [];
  private callback: IntersectionObserverCallback;

  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
  }

  observe = vi.fn(() => {
    instances.push({ callback: this.callback });
  });
  unobserve = vi.fn();
  disconnect = vi.fn();
  takeRecords = vi.fn((): IntersectionObserverEntry[] => []);
}

export function installIntersectionObserverMock(): void {
  instances.length = 0;
  // jsdom doesn't implement IntersectionObserver at all — this stub is only ever driven manually
  // via triggerIntersection() in a test, never a real layout/scroll.
  window.IntersectionObserver = MockIntersectionObserver;
}

// Simulates the most-recently-observed sentinel scrolling into view. `index` selects an earlier
// one if a test has more than one infinite-scroll list on the page at once.
export function triggerIntersection(index = instances.length - 1): void {
  const instance = instances[index];
  if (!instance) throw new Error("No IntersectionObserver instance has been observed yet");
  instance.callback(
    [{ isIntersecting: true } as IntersectionObserverEntry],
    {} as IntersectionObserver
  );
}
