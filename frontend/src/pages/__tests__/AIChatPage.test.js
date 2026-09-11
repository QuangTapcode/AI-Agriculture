import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { Sources } from '../AIChatPage';


describe('assistant source rendering', () => {
  it('uses a readable source label and never renders an encoded URL as visible text', () => {
    const html = renderToStaticMarkup(React.createElement(Sources, {
      rag: {
        status: 'ready',
        sources: [{
          citation: 'TL1',
          name: 'H%C6%B0%E1%BB%9Bng%20d%E1%BA%ABn%20c%C3%A0%20ph%C3%AA.pdf',
          source_name: 'VAAS - Sách kỹ thuật',
          source_url: 'https://vaas.vn/H%C6%B0%E1%BB%9Bng%20d%E1%BA%ABn.pdf',
          page: 1,
          excerpt: 'Nội dung kỹ thuật cà phê.',
        }],
      },
    }));

    expect(html).toContain('[TL1] VAAS - Sách kỹ thuật · Trang 1');
    expect(html).toContain('Mở tài liệu gốc');
    expect(html).not.toMatch(/>[^<]*H%C6%B0%E1%BB%9Bng/);
  });
});
