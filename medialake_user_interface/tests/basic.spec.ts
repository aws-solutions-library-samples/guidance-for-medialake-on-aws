import { test, expect } from '@playwright/test';

/**
 * Basic test file to verify Playwright is working correctly
 * These tests don't require a web server to be running
 */

test.describe('Basic tests', () => {
  test('simple passing test', async () => {
    // This test should always pass
    expect(true).toBeTruthy();
    console.log('Basic test is running successfully!');
  });

  test('basic assertion test', async () => {
    // Test basic assertions
    expect(1 + 1).toBe(2);
    expect('hello').toContain('ell');
    expect([1, 2, 3]).toHaveLength(3);
  });

  test('async test', async () => {
    // Test async functionality
    const result = await Promise.resolve('async works');
    expect(result).toBe('async works');
  });
}); 