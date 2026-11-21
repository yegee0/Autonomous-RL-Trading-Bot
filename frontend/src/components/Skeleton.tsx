interface Props {
  height?: string | number;
  width?: string | number;
  className?: string;
}

export function Skeleton({ height = "1rem", width = "100%", className = "" }: Props) {
  return (
    <div
      className={`animate-pulse bg-bg-panel2 rounded ${className}`}
      style={{ height, width }}
    />
  );
}

export function PanelSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="panel p-4 flex flex-col gap-3">
      <Skeleton height="0.75rem" width="30%" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} height="1rem" />
      ))}
    </div>
  );
}
