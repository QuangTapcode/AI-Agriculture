import { useEffect, useRef, useState } from 'react';

/**
 * Hiện nội dung khi cuộn tới.
 *
 * Lưới an toàn: `.field-reveal` bắt đầu ở opacity 0, nên nếu IntersectionObserver
 * không bao giờ báo — element nằm trong khối bị ẩn, trình duyệt lạ, hay ảnh chụp
 * toàn trang không cuộn — nội dung sẽ biến mất vĩnh viễn. Hết REVEAL_FALLBACK_MS
 * thì ta hiện ra bất kể, vì hiệu ứng không bao giờ được phép nuốt nội dung.
 */
const REVEAL_FALLBACK_MS = 2500;

export function Reveal({ children, className = '', delay = 0, as: Component = 'div' }) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node || !('IntersectionObserver' in window)) {
      setVisible(true);
      return undefined;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15, rootMargin: '0px 0px -8% 0px' }
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
