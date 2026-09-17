import { useEffect, useRef, useState } from 'react';

/**
 * Hiện nội dung khi cuộn tới.
 *
 * Lưới an toàn: `.field-reveal` chỉ dịch chuyển bằng transform khi chờ
 * IntersectionObserver. Nội dung vẫn giữ độ tương phản và có thể đọc được trong
 * lúc hiệu ứng chờ kích hoạt; hết REVEAL_FALLBACK_MS thì ta hiện ra bất kể.
 */
const REVEAL_FALLBACK_MS = 900;

function nearestScrollContainer(node) {
  let parent = node?.parentElement;
  while (parent) {
    const style = window.getComputedStyle?.(parent);
    const overflow = `${style?.overflowY || parent.style?.overflowY || ''} ${style?.overflow || parent.style?.overflow || ''}`;
    if (/(auto|scroll|overlay)/i.test(overflow)) return parent;
    parent = parent.parentElement;
  }
  return null;
}

function reducedMotionRequested() {
  return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
}

export function Reveal({ children, className = '', delay = 0, as: Component = 'div' }) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node || reducedMotionRequested() || !('IntersectionObserver' in window)) {
      setVisible(true);
      return undefined;
    }

    const root = nearestScrollContainer(node);
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15, rootMargin: '0px 0px -8% 0px', root }
    );
    observer.observe(node);

    const fallback = setTimeout(() => {
      setVisible(true);
      observer.disconnect();
    }, REVEAL_FALLBACK_MS);

    return () => {
      clearTimeout(fallback);
      observer.disconnect();
    };
  }, []);

  return (
    <Component
      ref={ref}
      style={{ '--reveal-delay': `${delay}ms` }}
      className={`field-reveal ${visible ? 'is-visible' : ''} ${className}`}
    >
      {children}
    </Component>
  );
}

export default Reveal;
