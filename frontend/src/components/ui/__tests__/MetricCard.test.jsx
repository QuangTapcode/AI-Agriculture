import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { MetricCard } from '../MetricCard';

describe('MetricCard', () => {
  it('shows the exact real value with source metadata', () => {
    const html = renderToStaticMarkup(
      <MetricCard
        label="Người dùng"
        value={1}
        unit="người"
        metadata={{ source: 'database', source_name: 'Users DB' }}
      />,
    );

    expect(html).toContain('>1<');
    expect(html).toContain('người');
    expect(html).toContain('Users DB');
  });

  it('hides fabricated values and explains why', () => {
    const html = renderToStaticMarkup(
      <MetricCard label="Người dùng" value={100} metadata={{ source: 'demo' }} />,
    );

    expect(html).not.toContain('>100<');
    expect(html).toContain('>—<');
    expect(html).toContain('Dữ liệu minh họa không được sử dụng.');
  });
});
