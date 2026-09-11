import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { KnowledgeDocumentsTable } from '../KnowledgeDocumentsPage';

describe('knowledge document catalogue', () => {
  it('shows source, index state, new state and chunk count', () => {
    const html = renderToStaticMarkup(React.createElement(KnowledgeDocumentsTable, { documents: [{
      id: 1,
      title: 'Hướng dẫn kỹ thuật cà phê',
      source_name: 'VAAS',
      source_url: 'https://example.org/coffee.pdf',
      crop: 'Cà phê',
      region: 'Tây Nguyên',
      version: 2,
      status: 'approved',
      quality_score: 0.9,
      indexed: true,
      chunks: 42,
      is_new: true,
      fetched_at: '2026-09-11T02:00:00+00:00',
    }] }));

    expect(html).toContain('Hướng dẫn kỹ thuật cà phê');
    expect(html).toContain('VAAS');
    expect(html).toContain('Đã lập chỉ mục');
    expect(html).toContain('Mới');
    expect(html).toContain('42 đoạn');
  });
});
