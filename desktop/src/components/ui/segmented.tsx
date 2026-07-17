"use client";

// one segmented control for every mode picker in the app

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  size = "md",
  className = "",
}: {
  options: readonly { value: T; label: string }[];
  value: T | undefined;
  onChange: (v: T) => void;
  size?: "sm" | "md";
  className?: string;
}) {
  const height = size === "sm" ? "h-7" : "h-9";
  return (
    <div
      role="group"
      className={`flex ${height} items-center gap-0.5 rounded-sm border border-line-2 bg-bg-2 p-0.5 ${className}`}
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={`h-full flex-1 rounded-sm px-2 text-xs whitespace-nowrap transition-colors
              duration-150 ${
                active ? "bg-accent-dim text-accent" : "text-text-3 hover:text-text-1"
              }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
