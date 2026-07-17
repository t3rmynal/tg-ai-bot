export function Card({
  title,
  actions,
  children,
  className = "",
}: {
  title?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`bevel rounded-md border border-line-1 bg-bg-1 ${className}`}>
      {title ? (
        <header className="flex h-11 items-center justify-between border-b border-line-1 px-4">
          <h2 className="flex items-center gap-2">
            <span aria-hidden className="h-2.5 w-0.5 shrink-0 bg-accent/70" />
            <span className="label">{title}</span>
          </h2>
          {actions}
        </header>
      ) : null}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function EmptyState({ text, action }: { text: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <span aria-hidden className="h-px w-8 bg-line-2" />
      <p className="max-w-sm text-sm text-text-3">{text}</p>
      {action}
    </div>
  );
}

// mono eyebrow, heavy uppercase title, outlined page index, accent rule with a notch
export function PageHeader({
  eyebrow,
  title,
  index,
  status,
  children,
}: {
  eyebrow: string;
  title: string;
  index?: string;
  status?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-6">
      <div className="flex items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow mb-2">{eyebrow}</p>
          <div className="flex items-baseline gap-3">
            <h1 className="display text-3xl leading-none text-text-1">{title}</h1>
            {status}
          </div>
        </div>
        <div className="flex items-end gap-4">
          {children}
          {index ? (
            <span aria-hidden className="ghost-num text-3xl leading-none">
              {index}
            </span>
          ) : null}
        </div>
      </div>
      <div className="notch-rule animate-sweep mt-4" />
    </div>
  );
}
