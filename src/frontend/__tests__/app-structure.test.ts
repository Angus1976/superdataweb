import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';

const frontendDir = path.resolve(__dirname, '..');

describe('App.tsx validation', () => {
  const appPath = path.join(frontendDir, 'App.tsx');
  const appContent = fs.readFileSync(appPath, 'utf-8');

  it('should contain BrowserRouter', () => {
    expect(appContent).toContain('BrowserRouter');
  });

  it('should contain AuthProvider', () => {
    expect(appContent).toContain('AuthProvider');
  });

  it('should contain Suspense', () => {
    expect(appContent).toContain('Suspense');
  });

  it('should contain Routes', () => {
    expect(appContent).toContain('Routes');
  });

  it('should redirect root path to /login', () => {
    expect(appContent).toContain('path="/"');
    expect(appContent).toContain('to="/login"');
  });

  it('should import interviewRoutes', () => {
    expect(appContent).toContain("from './routes/interviewRoutes'");
  });
});

describe('main.tsx validation', () => {
  const mainPath = path.join(frontendDir, 'main.tsx');
  const mainContent = fs.readFileSync(mainPath, 'utf-8');

  it('should use createRoot', () => {
    expect(mainContent).toContain('createRoot');
  });

  it('should use StrictMode', () => {
    expect(mainContent).toContain('StrictMode');
  });

  it('should import i18n before rendering', () => {
    // i18n import should appear before App import
    const i18nImportIndex = mainContent.indexOf("import './i18n'");
    const appImportIndex = mainContent.indexOf("import App from './App'");
    expect(i18nImportIndex).toBeLessThan(appImportIndex);
    expect(i18nImportIndex).toBeGreaterThan(-1);
  });

  it('should render to root element', () => {
    expect(mainContent).toContain("getElementById('root')");
  });
});