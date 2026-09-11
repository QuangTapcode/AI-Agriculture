export function Skeleton({ className = '' }) {
  return <span aria-hidden="true" className={`field-skeleton block rounded-xl ${className}`} />;
}

export default Skeleton;
