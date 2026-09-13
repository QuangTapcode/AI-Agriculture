import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const indexPath = resolve(process.cwd(), 'index.html');
const html = readFileSync(indexPath, 'utf8');

describe('production document shell', () => {
  it('uses bundled assets without a runtime font dependency', () => {
    expect(html).not.toContain('fonts.googleapis.com');
    expect(html).not.toContain('fonts.gstatic.com');
  });

  it('uses the AgriAI brand image as its favicon', () => {
    expect(html).toContain('/src/assets/agri-ai-logo-header.png');
    expect(html).not.toContain('/vite.svg');
  });
});
