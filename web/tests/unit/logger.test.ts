/**
 * Tests for the frontend logging utility
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// We need to mock import.meta.env before importing logger
vi.mock('../../src/config', () => ({
  LOG_LEVEL: 'debug',
  LOG_LEVELS: {
    debug: 0,
    info: 1,
    warn: 2,
    error: 3,
  },
}));

describe('Logger', () => {
  let consoleSpy: {
    log: ReturnType<typeof vi.spyOn>;
    warn: ReturnType<typeof vi.spyOn>;
    error: ReturnType<typeof vi.spyOn>;
  };

  beforeEach(() => {
    consoleSpy = {
      log: vi.spyOn(console, 'log').mockImplementation(() => {}),
      warn: vi.spyOn(console, 'warn').mockImplementation(() => {}),
      error: vi.spyOn(console, 'error').mockImplementation(() => {}),
    };
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  it('createLogger returns a logger with all methods', async () => {
    const { createLogger } = await import('../../src/utils/logger');
    const log = createLogger('test');

    expect(log.debug).toBeDefined();
    expect(log.info).toBeDefined();
    expect(log.warn).toBeDefined();
    expect(log.error).toBeDefined();
  });

  it('logs debug messages when level is debug', async () => {
    const { createLogger } = await import('../../src/utils/logger');
    const log = createLogger('test-module');

    log.debug('Debug message');

    expect(consoleSpy.log).toHaveBeenCalled();
    const call = consoleSpy.log.mock.calls[0];
    expect(call[0]).toContain('[test-module]');
    expect(call[2]).toBe('Debug message');
  });

  it('logs info messages', async () => {
    const { createLogger } = await import('../../src/utils/logger');
    const log = createLogger('test-module');

    log.info('Info message');

    expect(consoleSpy.log).toHaveBeenCalled();
    const call = consoleSpy.log.mock.calls[0];
    expect(call[0]).toContain('[test-module]');
    expect(call[2]).toBe('Info message');
  });

  it('logs warn messages', async () => {
    const { createLogger } = await import('../../src/utils/logger');
    const log = createLogger('test-module');

    log.warn('Warning message');

    expect(consoleSpy.warn).toHaveBeenCalled();
    const call = consoleSpy.warn.mock.calls[0];
    expect(call[0]).toBe('[test-module]');
    expect(call[1]).toBe('Warning message');
  });

  it('logs error messages', async () => {
    const { createLogger } = await import('../../src/utils/logger');
    const log = createLogger('test-module');

    log.error('Error message');

    expect(consoleSpy.error).toHaveBeenCalled();
    const call = consoleSpy.error.mock.calls[0];
    expect(call[0]).toBe('[test-module]');
    expect(call[1]).toBe('Error message');
  });

  it('includes context in log output', async () => {
    const { createLogger } = await import('../../src/utils/logger');
    const log = createLogger('test-module');

    log.info('Message with context', { userId: '123', action: 'login' });

    expect(consoleSpy.log).toHaveBeenCalled();
    const call = consoleSpy.log.mock.calls[0];
    expect(call[3]).toEqual({ userId: '123', action: 'login' });
  });

  it('handles Error objects in context', async () => {
    const { createLogger } = await import('../../src/utils/logger');
    const log = createLogger('test-module');
    const testError = new Error('Test error');

    log.error('Failed operation', { error: testError });

    expect(consoleSpy.error).toHaveBeenCalled();
    const call = consoleSpy.error.mock.calls[0];
    expect(call[2]).toHaveProperty('error');
    expect(call[2].error).toHaveProperty('name', 'Error');
    expect(call[2].error).toHaveProperty('message', 'Test error');
    expect(call[2].error).toHaveProperty('stack');
  });

  it('supports request ID correlation', async () => {
    const { createLogger, setRequestId, getRequestId, generateRequestId } =
      await import('../../src/utils/logger');

    const requestId = generateRequestId();
    expect(requestId).toMatch(/^\d+-[a-z0-9]+$/);

    setRequestId(requestId);
    expect(getRequestId()).toBe(requestId);

    const log = createLogger('test-module');
    log.info('Request started');

    expect(consoleSpy.log).toHaveBeenCalled();
    const call = consoleSpy.log.mock.calls[0];
    expect(call[3]).toHaveProperty('requestId', requestId);

    // Clean up
    setRequestId(null);
    expect(getRequestId()).toBeNull();
  });

  it('default logger is available', async () => {
    const { logger } = await import('../../src/utils/logger');

    expect(logger.debug).toBeDefined();
    expect(logger.info).toBeDefined();
    expect(logger.warn).toBeDefined();
    expect(logger.error).toBeDefined();
  });
});

describe('Logger with warn level', () => {
  let consoleSpy: {
    log: ReturnType<typeof vi.spyOn>;
    warn: ReturnType<typeof vi.spyOn>;
    error: ReturnType<typeof vi.spyOn>;
  };

  beforeEach(() => {
    vi.resetModules();
    consoleSpy = {
      log: vi.spyOn(console, 'log').mockImplementation(() => {}),
      warn: vi.spyOn(console, 'warn').mockImplementation(() => {}),
      error: vi.spyOn(console, 'error').mockImplementation(() => {}),
    };
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('filters debug and info when level is warn', async () => {
    // Override mock for this test
    vi.doMock('../../src/config', () => ({
      LOG_LEVEL: 'warn',
      LOG_LEVELS: {
        debug: 0,
        info: 1,
        warn: 2,
        error: 3,
      },
    }));

    const { createLogger } = await import('../../src/utils/logger');
    const log = createLogger('test');

    log.debug('Should not appear');
    log.info('Should not appear');
    log.warn('Should appear');
    log.error('Should appear');

    expect(consoleSpy.log).not.toHaveBeenCalled();
    expect(consoleSpy.warn).toHaveBeenCalledTimes(1);
    expect(consoleSpy.error).toHaveBeenCalledTimes(1);
  });
});
