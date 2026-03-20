import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';

const frontendDir = path.resolve(__dirname, '..');

describe('index.html validation', () => {
  const indexHtmlPath = path.join(frontendDir, 'index.html');
  const indexHtml = fs.readFileSync(indexHtmlPath, 'utf-8');

  it('should contain id="root" div', () => {
    expect(indexHtml).toContain('id="root"');
  });

  it('should have lang="zh-CN"', () => {
    expect(indexHtml).toContain('lang="zh-CN"');
  });

  it('should have charset="UTF-8"', () => {
    expect(indexHtml).toContain('charset="UTF-8"');
  });

  it('should have title "SuperInsight"', () => {
    expect(indexHtml).toContain('<title>SuperInsight</title>');
  });

  it('should reference main.tsx in script tag', () => {
    expect(indexHtml).toContain('src="./main.tsx"');
  });
});

describe('vite.config.ts validation', () => {
  const viteConfigPath = path.join(frontendDir, 'vite.config.ts');
  const viteConfig = fs.readFileSync(viteConfigPath, 'utf-8');

  it('should contain react plugin', () => {
    expect(viteConfig).toContain('@vitejs/plugin-react');
    expect(viteConfig).toContain('react()');
  });

  it('should have changeOrigin configuration', () => {
    expect(viteConfig).toContain('changeOrigin: true');
  });

  it('should have /api proxy configuration', () => {
    expect(viteConfig).toContain("'/api'");
    expect(viteConfig).toContain("target: 'http://localhost:8011'");
  });
});

describe('tsconfig.json validation', () => {
  const tsconfigPath = path.join(frontendDir, 'tsconfig.json');
  const tsconfig = JSON.parse(fs.readFileSync(tsconfigPath, 'utf-8'));

  it('should have jsx set to react-jsx', () => {
    expect(tsconfig.compilerOptions.jsx).toBe('react-jsx');
  });

  it('should have strict set to true', () => {
    expect(tsconfig.compilerOptions.strict).toBe(true);
  });

  it('should have moduleResolution set to bundler', () => {
    expect(tsconfig.compilerOptions.moduleResolution).toBe('bundler');
  });

  it('should include ts and tsx files', () => {
    expect(tsconfig.include).toContain('./**/*.ts');
    expect(tsconfig.include).toContain('./**/*.tsx');
  });
});