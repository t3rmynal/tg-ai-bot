type Tone = "neutral" | "accent" | "warn" | "danger";

const tones: Record<Tone, string> = {
  neutral: "border-line-2 text-text-2",
  accent: "border-accent/40 text-accent bg-accent-dim",
  warn: "border-warn/30 text-warn bg-warn-dim",
  danger: "border-danger/30 text-danger bg-danger-dim",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span
      className={`mono inline-flex items-center rounded-sm border px-1.5 py-px text-[10px]
        tracking-wider uppercase ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
