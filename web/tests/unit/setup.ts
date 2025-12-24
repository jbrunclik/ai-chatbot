/**
 * Unit test setup - mocks browser APIs before any modules are loaded
 */
import { vi } from 'vitest';

// Mock localStorage (zustand persist middleware needs this)
const mockStorage: Record<string, string> = {};
const mockLocalStorage = {
  getItem: vi.fn((key: string) => mockStorage[key] ?? null),
  setItem: vi.fn((key: string, value: string) => {
    mockStorage[key] = value;
  }),
  removeItem: vi.fn((key: string) => {
    delete mockStorage[key];
  }),
  clear: vi.fn(() => {
    Object.keys(mockStorage).forEach((key) => delete mockStorage[key]);
  }),
  get length() {
    return Object.keys(mockStorage).length;
  },
  key: vi.fn((index: number) => Object.keys(mockStorage)[index] ?? null),
};
Object.defineProperty(global, 'localStorage', { value: mockLocalStorage, writable: true });

// Mock sessionStorage as well
Object.defineProperty(global, 'sessionStorage', { value: mockLocalStorage, writable: true });

// Export for tests that need to clear storage
export { mockStorage, mockLocalStorage };
