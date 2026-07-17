export function Spinner({ size = 14 }: { size?: number }) {
  return (
    <span
      aria-label="loading"
      className="inline-block animate-spin rounded-full border-2 border-line-2 border-t-accent"
      style={{ width: size, height: size }}
    />
  );
}
