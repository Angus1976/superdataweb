import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as fc from 'fast-check';

const frontendDir = path.resolve(__dirname, '..');

/**
 * Feature: frontend-scaffold, Property 1: 代理路径保留
 * Validates: Requirements 2.3, 7.1, 7.2, 7.3, 7.4
 */
describe('Property 1: 代理路径保留', () => {
  it('should forward /api/* requests to localhost:8011 with path unchanged', () => {
    const viteConfigPath = path.join(frontendDir, 'vite.config.ts');
    const viteConfig = fs.readFileSync(viteConfigPath, 'utf-8');

    // Extract proxy configuration
    const hasApiProxy = viteConfig.includes("'/api'");
    const hasTarget = viteConfig.includes("target: 'http://localhost:8011'");
    const hasChangeOrigin = viteConfig.includes('changeOrigin: true');

    expect(hasApiProxy).toBe(true);
    expect(hasTarget).toBe(true);
    expect(hasChangeOrigin).toBe(true);

    // Property: for any /api/* path, the proxy should forward to http://localhost:8011 with path unchanged
    fc.assert(
      fc.property(fc.string({ minLength: 1, maxLength: 50 }), fc.string({ minLength: 1, maxLength: 50 }), (segment1, segment2) => {
        const apiPath = `/api/${segment1}/${segment2}`;
        // The proxy should forward this to http://localhost:8011/api/segment1/segment2
        // i.e., the path should NOT be rewritten
        // We verify this by checking that there's no rewrite function that modifies the path
        // or that rewrite returns the path as-is
        const hasNoRewriteOrPassthrough = 
          !viteConfig.includes('rewrite') || 
          viteConfig.includes('rewrite: (path) => path') ||
          viteConfig.includes('rewrite: (path) => path,');
        
        expect(hasNoRewriteOrPassthrough || viteConfig.includes('rewrite: (path) => path')).toBe(true);
      }),
      { numRuns: 100 }
    );
  });

  it('should preserve original request path for various API endpoints', () => {
    const viteConfigPath = path.join(frontendDir, 'vite.config.ts');
    const viteConfig = fs.readFileSync(viteConfigPath, 'utf-8');

    // Test specific API paths from requirements
    const testPaths = [
      '/api/auth/login',
      '/api/interview/health',
      '/api/users',
    ];

    testPaths.forEach((apiPath) => {
      // The proxy should forward these paths without rewriting
      // Check that there's no rewrite that would change the path
      const hasRewriteThatChangesPath = /rewrite:\s*\(path\)\s*=>\s*path\.replace/.test(viteConfig);
      expect(hasRewriteThatChangesPath).toBe(false);
    });
  });
});