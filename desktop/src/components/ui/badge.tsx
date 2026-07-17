type Tone = "neutral" | "ok" | "warn" | "danger" | "accent";

const tones: Record<Tone, string> = {
  neutral: "border-line-2 text-text-2",
  ok: "border-ok/30 text-ok bg-ok-dim",
  warn: "border-warn/30 text-warn bg-warn-dim",
  danger: "border-danger/30 text-danger bg-danger-dim",
  accent: "border-accent/30 text-accent bg-accent-dim",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-sm border px-1.5 py-px text-xs ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
