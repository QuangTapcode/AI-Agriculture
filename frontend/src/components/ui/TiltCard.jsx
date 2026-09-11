import { useRef } from 'react';

export function TiltCard({ children, className = '', as: Component = 'div' }) {
  const ref = useRef(null);

  const onPointerMove = (event) => {
    if (event.pointerType === 'touch') return;
    const node = ref.current;
    const rect = node.getBoundingClientRect();
    node.style.setProperty('--tilt-x', `${((event.clientY - rect.top) / rect.height - 0.5) * -5}deg`);
    node.style.setProperty('--tilt-y', `${((event.clientX - rect.left) / rect.width - 0.5) * 5}deg`);
  };

  const reset = () => {
    ref.current?.style.setProperty('--tilt-x', '0deg');
    ref.current?.style.setProperty('--tilt-y', '0deg');
  };

  return <Component ref={ref} onPointerMove={onPointerMove} onPointerLeave={reset} className={`field-tilt ${className}`}>{children}</Component>;
}

export default TiltCard;
