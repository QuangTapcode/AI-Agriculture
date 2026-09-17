import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { KnowledgeUpdate } from '../AIChatPage';

describe('query discovery status', () => {
  it('prefers a server message when a repeated search already has a result', () => {
    const html = renderToStaticMarkup(React.createElement(KnowledgeUpdate, {
      update: {
        status: 'completed',
        deduplicated: true,
        message: 'Tài liệu phù hợp đã có trong kho chính.',
      },
    }));

    expect(html).toContain('Tài liệu phù hợp đã có trong kho chính.');
    expect(html).not.toContain('chưa có tài liệu đạt');
  });
});
