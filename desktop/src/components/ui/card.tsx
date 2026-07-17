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
          <h2 className="label">{title}</h2>
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
      <p className="max-w-sm text-sm text-text-3">{text}</p>
      {action}
    </div>
  );
}

// mono eyebrow, big uppercase title, accent rule with a notch: the page masthead
export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="eyebrow mb-1.5">{eyebrow}</p>
          <h1 className="display text-2xl text-text-1">{title}</h1>
        </div>
        {children}
      </div>
      <div className="notch-rule animate-sweep mt-4" />
    </div>
  );
}
