/**
 * Required jsdom shims for @xyflow/react component tests — jsdom has no
 * layout engine, so React Flow can't measure nodes without these.
 * Base setup from reactflow.dev/learn/advanced-use/testing; extended
 * with `contentRect` on the observer entry because the installed
 * @xyflow/system version reads `entry.contentRect.width/height`
 * (node_modules/@xyflow/system/dist/esm/index.mjs, extentResizeObserver)
 * which the docs' bare `{ target }` entry doesn't provide.
 */

class ResizeObserverMock {
  callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }

  observe(target: Element) {
    setTimeout(() => {
      const rect = target.getBoundingClientRect();
      const entry = { target, contentRect: rect } as ResizeObserverEntry;
      this.callback([entry], this as unknown as ResizeObserver);
    }, 0);
  }

  unobserve() {}
  disconnect() {}
}

class DOMMatrixReadOnlyMock {
  m22: number;

  constructor(transform: string) {
    const scale = transform?.match(/scale\(([1-9.])\)/)?.[1];
    this.m22 = scale !== undefined ? +scale : 1;
  }
}

let initialized = false;

export function mockReactFlow() {
  if (initialized) return;
  initialized = true;

  global.ResizeObserver = ResizeObserverMock;
  // @ts-expect-error -- test-only jsdom shim, missing static DOMMatrixReadOnly helpers we never call
  global.DOMMatrixReadOnly = DOMMatrixReadOnlyMock;

  Object.defineProperties(global.HTMLElement.prototype, {
    offsetHeight: {
      get() {
        return parseFloat(this.style.height) || 1;
      },
    },
    offsetWidth: {
      get() {
        return parseFloat(this.style.width) || 1;
      },
    },
  });

  // @ts-expect-error -- test-only jsdom shim
  global.SVGElement.prototype.getBBox = () => ({ x: 0, y: 0, width: 0, height: 0 });
}
