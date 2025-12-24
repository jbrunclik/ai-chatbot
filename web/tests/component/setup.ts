/**
 * Component test setup - mocks browser APIs not available in jsdom
 */
import { beforeEach, vi } from 'vitest';

// Reset DOM and mocks before each test
beforeEach(() => {
  // Reset document body
  document.body.innerHTML = '';

  // Clear all stores (jsdom localStorage might not have clear method)
  if (typeof localStorage.clear === 'function') {
    localStorage.clear();
  } else {
    // Fallback: manually clear all items
    Object.keys(localStorage).forEach((key) => localStorage.removeItem(key));
  }

  if (typeof sessionStorage.clear === 'function') {
    sessionStorage.clear();
  } else {
    Object.keys(sessionStorage).forEach((key) => sessionStorage.removeItem(key));
  }

  // Reset all mocks
  vi.clearAllMocks();
});

// Mock matchMedia (used by responsive checks)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock IntersectionObserver (used by lazy loading)
const mockIntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
  root: null,
  rootMargin: '',
  thresholds: [],
  takeRecords: vi.fn().mockReturnValue([]),
}));
vi.stubGlobal('IntersectionObserver', mockIntersectionObserver);

// Mock ResizeObserver
const mockResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));
vi.stubGlobal('ResizeObserver', mockResizeObserver);

// Mock requestAnimationFrame - returns ID but doesn't call callback
// (calling callback synchronously causes infinite loops in animation code)
let rafId = 0;
vi.stubGlobal(
  'requestAnimationFrame',
  vi.fn(() => {
    return ++rafId;
  })
);

vi.stubGlobal('cancelAnimationFrame', vi.fn());

// Mock SpeechRecognition (not available in jsdom)
vi.stubGlobal('SpeechRecognition', undefined);
vi.stubGlobal('webkitSpeechRecognition', undefined);

// Mock scrollTo
Element.prototype.scrollTo = vi.fn();
window.scrollTo = vi.fn();

// Mock scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

// Mock clipboard API
Object.defineProperty(navigator, 'clipboard', {
  value: {
    writeText: vi.fn().mockResolvedValue(undefined),
    readText: vi.fn().mockResolvedValue(''),
  },
  writable: true,
});

// Mock fetch globally (tests should override as needed)
vi.stubGlobal(
  'fetch',
  vi.fn().mockRejectedValue(new Error('fetch not mocked for this test'))
);

// Suppress console errors during tests (optional - remove if you want to see them)
// vi.spyOn(console, 'error').mockImplementation(() => {});
