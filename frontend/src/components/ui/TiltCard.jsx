import { useEffect, useRef } from 'react';

/**
 * Nghiêng nhẹ theo con trỏ chuột.
 *
 * Lớp `.field-tilt` ghi đè thẳng thuộc tính `transform`, nên nó phải nằm ở một
 * element riêng bên trong. Trước đây tilt dùng chung element với `className` của
 * nơi gọi, và một utility như `-translate-x-1/2` bị nuốt mất — thẻ trên trang chủ
 * vì thế lệch sang phải 215px và tràn khỏi khung nhìn.
 *
 * Cảm ứng không kích hoạt tilt: trên điện thoại, pointermove xảy ra trong lúc
 * người dùng đang chạm để thao tác, nghiêng thẻ lúc đó chỉ gây nhiễu.
 */
export function TiltCard({ children, className = '', as: Component = 'div' }) {
  const ref = useRef(null);
  const frame = useRef(null);
  const pointerFine = useRef(true);

  useEffect(() => {
    pointerFine.current = window.matchMedia?.('(pointer: fine)').matches ?? true;
    return () => {
      if (frame.current != null) window.cancelAnimationFrame?.(frame.current);
    };
  }, []);

  const onPointerMove = (event) => {
    if (event.pointerType === 'touch' || !pointerFine.current || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
    const node = ref.current;
    if (!node) return;
    const rect = node.getBoundingClientRect();
    const x = `${Math.max(-4, Math.min(4, ((event.clientY - rect.top) / rect.height - 0.5) * -4))}deg`;
    const y = `${Math.max(-4, Math.min(4, ((event.clientX - rect.left) / rect.width - 0.5) * 4))}deg`;
    if (frame.current != null) window.cancelAnimationFrame?.(frame.current);
    const apply = () => {
      node.style.setProperty('--tilt-x', x);
      node.style.setProperty('--tilt-y', y);
      frame.current = null;
    };
    frame.current = window.requestAnimationFrame?.(apply) ?? (apply(), null);
  };

  const reset = () => {
    if (frame.current != null) window.cancelAnimationFrame?.(frame.current);
    frame.current = null;
    ref.current?.style.setProperty('--tilt-x', '0deg');
    ref.current?.style.setProperty('--tilt-y', '0deg');
  };

  return (
    <Component className={className} onPointerMove={onPointerMove} onPointerLeave={reset}>
      <div ref={ref} className="field-tilt">
        {children}
      </div>
    </Component>
  );
}

export default TiltCard;
