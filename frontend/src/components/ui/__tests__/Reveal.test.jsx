import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Reveal } from '../Reveal';

const originalIO = global.IntersectionObserver;

afterEach(() => {
  global.IntersectionObserver = originalIO;
  vi.useRealTimers();
});

describe('Reveal', () => {
  it('reveals immediately when IntersectionObserver is unavailable', () => {
    delete global.IntersectionObserver;

    render(<Reveal>Nội dung</Reveal>);

    expect(screen.getByText('Nội dung')).toHaveClass('is-visible');
  });

  it('reveals when the element scrolls into view', () => {
    let trigger;
    global.IntersectionObserver = class {
      constructor(callback) { trigger = callback; }
      observe() {}
      disconnect() {}
    };

    render(<Reveal>Nội dung</Reveal>);
    expect(screen.getByText('Nội dung')).not.toHaveClass('is-visible');

    act(() => trigger([{ isIntersecting: true }]));
    expect(screen.getByText('Nội dung')).toHaveClass('is-visible');
  });

  it('never leaves content hidden if the observer never fires', async () => {
    vi.useFakeTimers();
    global.IntersectionObserver = class {
      observe() {}
      disconnect() {}
    };

    render(<Reveal>Nội dung</Reveal>);
    expect(screen.getByText('Nội dung')).not.toHaveClass('is-visible');

    // Quan sát viên không bao giờ báo: nội dung vẫn phải hiện ra.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });

    expect(screen.getByText('Nội dung')).toHaveClass('is-visible');
  });
});
