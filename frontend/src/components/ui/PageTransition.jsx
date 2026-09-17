import { useLocation } from 'react-router-dom';

/** A small route enter animation that never changes layout dimensions. */
export function PageTransition({ children, pageKey }) {
  const location = useLocation();
  const key = pageKey || location.pathname;
  return (
    <div key={key} data-page-transition={key} className="field-page-transition">
      {children}
    </div>
  );
}

export default PageTransition;
