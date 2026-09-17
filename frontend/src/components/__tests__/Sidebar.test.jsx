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

  it('keeps harvest forecasting inside season management', () => {
    expect(navigation).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        key: 'harvest',
      }),
    ]));
    expect(navigation).toEqual(expect.arrayContaining([
      expect.objectContaining({
        key: 'seasonManagement',
        href: '/season-management',
      }),
    ]));
  });

  it('does not expose the removed market analysis page', () => {
    expect(navigation).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        key: 'market',
        href: '/market',
      }),
    ]));
  });
});
