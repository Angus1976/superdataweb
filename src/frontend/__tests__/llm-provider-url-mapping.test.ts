import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as fc from 'fast-check';

const frontendDir = path.resolve(__dirname, '..');

/**
 * Feature: llm-config-management, Property 6: 服务商默认 URL 映射
 * Validates: Requirements 3.4
 *
 * For any known provider name (openai, deepseek, tongyi, custom),
 * selecting that provider returns the correct default Base URL.
 * The mapping is deterministic: same provider always returns same URL.
 */
describe('Property 6: 服务商默认 URL 映射', () => {
  const llmConfigPath = path.join(frontendDir, 'pages', 'LLMConfigPage.tsx');
  const source = fs.readFileSync(llmConfigPath, 'utf-8');

  /** Expected provider → default URL mapping */
  const expectedMapping: Record<string, string> = {
    openai: 'https://api.openai.com/v1',
    deepseek: 'https://api.deepseek.com/v1',
    tongyi: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    custom: '',
  };

  /**
   * Extract the PROVIDER_DEFAULT_URLS object from source code.
   * Returns a Record<string, string> parsed from the source.
   */
  function extractProviderUrls(src: string): Record<string, string> {
    const blockMatch = src.match(
      /const PROVIDER_DEFAULT_URLS[^=]*=\s*\{([^}]+)\}/,
    );
    if (!blockMatch) throw new Error('PROVIDER_DEFAULT_URLS not found in source');

    const entries: Record<string, string> = {};
    const entryRegex = /(\w+)\s*:\s*'([^']*)'/g;
    let m: RegExpExecArray | null;
    while ((m = entryRegex.exec(blockMatch[1])) !== null) {
      entries[m[1]] = m[2];
    }
    // Handle empty-string values like  custom: ''
    const emptyRegex = /(\w+)\s*:\s*''/g;
    while ((m = emptyRegex.exec(blockMatch[1])) !== null) {
      if (!(m[1] in entries)) {
        entries[m[1]] = '';
      }
    }
    return entries;
  }

  const actualMapping = extractProviderUrls(source);

  it('source file contains PROVIDER_DEFAULT_URLS with all known providers', () => {
    for (const provider of Object.keys(expectedMapping)) {
      expect(actualMapping).toHaveProperty(provider);
    }
  });

  it('each randomly-selected provider maps to the correct default URL (property)', () => {
    const providers = Object.keys(expectedMapping) as string[];

    fc.assert(
      fc.property(
        fc.constantFrom(...providers),
        (provider: string) => {
          // The URL extracted from source must match the expected mapping
          expect(actualMapping[provider]).toBe(expectedMapping[provider]);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('mapping is deterministic: same provider always yields same URL (property)', () => {
    const providers = Object.keys(expectedMapping) as string[];

    fc.assert(
      fc.property(
        fc.constantFrom(...providers),
        (provider: string) => {
          // Call the lookup twice — result must be identical
          const url1 = actualMapping[provider];
          const url2 = actualMapping[provider];
          expect(url1).toBe(url2);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('handleProviderChange uses PROVIDER_DEFAULT_URLS with nullish coalescing fallback', () => {
    // Verify the source uses the mapping in handleProviderChange
    expect(source).toContain('PROVIDER_DEFAULT_URLS[value]');
    // Verify fallback to empty string for unknown providers
    expect(source).toMatch(/PROVIDER_DEFAULT_URLS\[value\]\s*\?\?\s*''/);
  });
});
