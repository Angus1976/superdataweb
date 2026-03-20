import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as fc from 'fast-check';

const frontendDir = path.resolve(__dirname, '..');

/**
 * Feature: frontend-scaffold, Property 3: 组件导入路径有效性
 * Validates: Requirements 8.1, 8.2, 8.3, 8.4
 */
describe('Property 3: 组件导入路径有效性', () => {
  // Helper to extract relative imports from a file
  function extractRelativeImports(filePath: string): { importPath: string; resolvedPath: string }[] {
    const content = fs.readFileSync(filePath, 'utf-8');
    const dir = path.dirname(filePath);
    const imports: { importPath: string; resolvedPath: string }[] = [];
    
    // Match relative import statements: import X from './path' or import './path'
    const importRegex = /import\s+(?:(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)\s+from\s+)?['"](\.[^'"]+)['"]/g;
    let match;
    
    while ((match = importRegex.exec(content)) !== null) {
      const importPath = match[1];
      // Resolve the relative path
      const resolvedPath = path.resolve(dir, importPath);
      
      // Check if the file exists (with .ts, .tsx, .json extensions)
      const extensions = ['.ts', '.tsx', '.json', '/index.ts', '/index.tsx'];
      let exists = false;
      
      for (const ext of extensions) {
        if (fs.existsSync(resolvedPath + ext)) {
          exists = true;
          break;
        }
        if (fs.existsSync(path.join(resolvedPath, 'index.ts')) || 
            fs.existsSync(path.join(resolvedPath, 'index.tsx'))) {
          exists = true;
          break;
        }
      }
      
      // Also check if the resolved path itself is a file
      if (fs.existsSync(resolvedPath)) {
        const stat = fs.statSync(resolvedPath);
        if (stat.isFile()) {
          exists = true;
        }
      }
      
      imports.push({ importPath, resolvedPath });
    }
    
    return imports;
  }

  it('should have all relative imports in App.tsx resolve to existing files', () => {
    const appPath = path.join(frontendDir, 'App.tsx');
    const imports = extractRelativeImports(appPath);
    
    const invalidImports: string[] = [];
    for (const imp of imports) {
      // Check if the resolved path exists
      const exists = 
        fs.existsSync(imp.resolvedPath) ||
        fs.existsSync(imp.resolvedPath + '.ts') ||
        fs.existsSync(imp.resolvedPath + '.tsx') ||
        fs.existsSync(path.join(imp.resolvedPath, 'index.ts')) ||
        fs.existsSync(path.join(imp.resolvedPath, 'index.tsx'));
      
      if (!exists) {
        invalidImports.push(imp.importPath);
      }
    }
    
    expect(invalidImports).toEqual([]);
  });

  it('should have all relative imports in main.tsx resolve to existing files', () => {
    const mainPath = path.join(frontendDir, 'main.tsx');
    const imports = extractRelativeImports(mainPath);
    
    const invalidImports: string[] = [];
    for (const imp of imports) {
      const exists = 
        fs.existsSync(imp.resolvedPath) ||
        fs.existsSync(imp.resolvedPath + '.ts') ||
        fs.existsSync(imp.resolvedPath + '.tsx') ||
        fs.existsSync(path.join(imp.resolvedPath, 'index.ts')) ||
        fs.existsSync(path.join(imp.resolvedPath, 'index.tsx'));
      
      if (!exists) {
        invalidImports.push(imp.importPath);
      }
    }
    
    expect(invalidImports).toEqual([]);
  });

  it('should verify all relative import paths are valid using property-based testing', () => {
    const appPath = path.join(frontendDir, 'App.tsx');
    const mainPath = path.join(frontendDir, 'main.tsx');
    
    const allImports = [
      ...extractRelativeImports(appPath),
      ...extractRelativeImports(mainPath),
    ];
    
    // Property: for any relative import in App.tsx or main.tsx, the path should resolve to an existing file
    // Using fast-check to generate and verify
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: Math.max(0, allImports.length - 1) }),
        (idx) => {
          if (allImports.length > 0) {
            const imp = allImports[idx % allImports.length];
            const exists = 
              fs.existsSync(imp.resolvedPath) ||
              fs.existsSync(imp.resolvedPath + '.ts') ||
              fs.existsSync(imp.resolvedPath + '.tsx') ||
              fs.existsSync(path.join(imp.resolvedPath, 'index.ts')) ||
              fs.existsSync(path.join(imp.resolvedPath, 'index.tsx'));
            
            expect(exists).toBe(true);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});