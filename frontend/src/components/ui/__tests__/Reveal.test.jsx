import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Reveal } from '../Reveal';

const originalIO = global.IntersectionObserver;
const originalMatchMedia = global.matchMedia;

afterEach(() => {
  global.IntersectionObserver = originalIO;
  global.matchMedia = originalMatchMedia;
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

  it('uses the nearest scrolling container as the observer root', () => {
    let options;
    global.IntersectionObserver = class {
      constructor(callback, observerOptions) { options = observerOptions; }
      observe() {}
      disconnect() {}
    };

    render(<div style={{ overflowY: 'auto', height: '100px' }}><Reveal>Nội dung</Reveal></div>);

    expect(options.root).toBe(screen.getByText('Nội dung').parentElement);
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
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getByText('Nội dung')).toHaveClass('is-visible');
  });

  it('reveals immediately when reduced motion is requested', () => {
    window.matchMedia = () => ({ matches: true, addEventListener() {}, removeEventListener() {} });
    global.IntersectionObserver = class {
      observe() {}
      disconnect() {}
    };

    render(<Reveal>Nội dung</Reveal>);

    expect(screen.getByText('Nội dung')).toHaveClass('is-visible');
  });
});
