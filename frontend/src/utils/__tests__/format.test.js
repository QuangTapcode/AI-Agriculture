import { describe, expect, it } from 'vitest';
import { MISSING, formatConfidence, formatNumber, hasValue } from '../format';

describe('formatConfidence', () => {
  it('returns an em dash when no confidence was reported', () => {
    expect(formatConfidence(null)).toBe(MISSING);
    expect(formatConfidence(undefined)).toBe(MISSING);
    expect(formatConfidence('')).toBe(MISSING);
  });

  it('renders a reported ratio as a whole percentage', () => {
    expect(formatConfidence(0.91)).toBe('91%');
    expect(formatConfidence(0.725)).toBe('73%');
  });

  it('treats a reported zero as a real measurement', () => {
    expect(formatConfidence(0)).toBe('0%');
  });

  it('accepts a value already expressed as a percentage', () => {
    expect(formatConfidence(91, { scale: 1 })).toBe('91%');
  });
});

describe('existing number helpers still hold', () => {
  it('separates missing from zero', () => {
    expect(formatNumber(null)).toBe(MISSING);
    expect(formatNumber(0)).toBe('0');
    expect(hasValue(0)).toBe(true);
    expect(hasValue(null)).toBe(false);
  });
});
