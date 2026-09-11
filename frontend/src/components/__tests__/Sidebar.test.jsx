import { describe, expect, it } from 'vitest';
import { navigation } from '../Sidebar';

describe('sidebar navigation', () => {
  it('exposes the shared knowledge catalogue', () => {
    expect(navigation).toEqual(expect.arrayContaining([
      expect.objectContaining({
        key: 'knowledgeDocuments',
        href: '/knowledge-documents',
      }),
    ]));
  });
});
