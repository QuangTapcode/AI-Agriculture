import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TiltCard } from '../TiltCard';

describe('TiltCard', () => {
  it('tilts towards the pointer for a mouse', () => {
    render(<TiltCard>Nội dung</TiltCard>);
    const card = screen.getByText('Nội dung');
    card.getBoundingClientRect = () => ({ top: 0, left: 0, width: 200, height: 100 });

    fireEvent.pointerMove(card, { pointerType: 'mouse', clientX: 200, clientY: 100 });

    expect(card.style.getPropertyValue('--tilt-y')).toBe('2.5deg');
    expect(card.style.getPropertyValue('--tilt-x')).toBe('-2.5deg');
  });

  it('never tilts for a touch pointer', () => {
    render(<TiltCard>Nội dung</TiltCard>);
    const card = screen.getByText('Nội dung');
    card.getBoundingClientRect = () => ({ top: 0, left: 0, width: 200, height: 100 });

    fireEvent.pointerMove(card, { pointerType: 'touch', clientX: 200, clientY: 100 });

    expect(card.style.getPropertyValue('--tilt-y')).toBe('');
    expect(card.style.getPropertyValue('--tilt-x')).toBe('');
  });

  it('returns to flat when the pointer leaves', () => {
    render(<TiltCard>Nội dung</TiltCard>);
    const card = screen.getByText('Nội dung');
    card.getBoundingClientRect = () => ({ top: 0, left: 0, width: 200, height: 100 });

    fireEvent.pointerMove(card, { pointerType: 'mouse', clientX: 200, clientY: 100 });
    fireEvent.pointerLeave(card, { pointerType: 'mouse' });

    expect(card.style.getPropertyValue('--tilt-x')).toBe('0deg');
    expect(card.style.getPropertyValue('--tilt-y')).toBe('0deg');
  });
});

describe('TiltCard composition', () => {
  it('keeps the caller layout classes off the element that owns the tilt transform', () => {
    render(<TiltCard className="absolute left-1/2 -translate-x-1/2">Nội dung</TiltCard>);

    const positioned = document.querySelector('[class~="absolute"]');
    expect(positioned).not.toBeNull();
    expect(positioned.className).toContain('-translate-x-1/2');
    // .field-tilt ghi đè thẳng thuộc tính transform, nên nó không được nằm chung
    // element với utility transform của Tailwind — nếu chung, translate bị nuốt.
    expect(positioned.classList.contains('field-tilt')).toBe(false);
    expect(positioned.querySelector('.field-tilt')).not.toBeNull();
  });
});
