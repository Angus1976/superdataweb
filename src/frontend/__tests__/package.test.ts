import { describe, it, expect } from 'vitest';
import packageJson from '../package.json';

describe('package.json validation', () => {
  it('should have correct name, version, and private field', () => {
    expect(packageJson.name).toBe('superinsight-frontend');
    expect(packageJson.version).toBe('0.1.0');
    expect(packageJson.private).toBe(true);
  });

  it('should have dev, build, and preview scripts', () => {
    expect(packageJson.scripts).toHaveProperty('dev');
    expect(packageJson.scripts).toHaveProperty('build');
    expect(packageJson.scripts).toHaveProperty('preview');
    expect(packageJson.scripts.dev).toBe('vite');
    expect(packageJson.scripts.build).toBe('vite build');
    expect(packageJson.scripts.preview).toBe('vite preview');
  });

  it('should have all 8 runtime dependencies', () => {
    const runtimeDeps = [
      'react',
      'react-dom',
      'react-router-dom',
      'antd',
      '@ant-design/icons',
      'axios',
      'i18next',
      'react-i18next',
    ];
    runtimeDeps.forEach((dep) => {
      expect(packageJson.dependencies).toHaveProperty(dep);
    });
    expect(Object.keys(packageJson.dependencies)).toHaveLength(8);
  });

  it('should have all 5 development dependencies', () => {
    const devDeps = [
      'vite',
      '@vitejs/plugin-react',
      'typescript',
      '@types/react',
      '@types/react-dom',
    ];
    devDeps.forEach((dep) => {
      expect(packageJson.devDependencies).toHaveProperty(dep);
    });
    // Note: vitest and fast-check are also in devDependencies
    expect(Object.keys(packageJson.devDependencies).length).toBeGreaterThanOrEqual(5);
  });
});