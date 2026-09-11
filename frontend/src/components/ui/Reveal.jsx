import { useEffect, useRef, useState } from 'react';

export function Reveal({ children, className = '', delay = 0, as: Component = 'div' }) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node || !('IntersectionObserver' in window)) {
      setVisible(true);
      return undefined;
    }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setVisible(true);
        observer.disconnect();
      }
    }, { threshold: 0.15, rootMargin: '0px 0px -8% 0px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return <Component ref={ref} style={{ '--reveal-delay': `${delay}ms` }} className={`field-reveal ${visible ? 'is-visible' : ''} ${className}`}>{children}</Component>;
}

export default Reveal;
