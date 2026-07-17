"use client";

import { forwardRef, type ButtonHTMLAttributes } from "react";

type Variant = "primary" | "outline" | "ghost" | "danger";

const styles: Record<Variant, string> = {
  primary: "bevel-sm bg-accent text-accent-fg hover:brightness-110 disabled:opacity-40",
  outline: "border border-line-2 bg-bg-2 text-text-1 hover:border-accent/60 hover:text-accent disabled:opacity-40",
  ghost: "text-text-2 hover:text-accent hover:bg-accent-dim disabled:opacity-40",
  danger: "border border-danger/40 text-danger hover:bg-danger-dim disabled:opacity-40",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
}

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "outline", size = "md", className = "", ...props },
  ref,
) {
  const pad = size === "sm" ? "h-7 px-2.5 text-xs" : "h-9 px-4 text-sm";
  return (
    <button
      ref={ref}
      className={`inline-flex items-center justify-center gap-1.5 rounded-sm font-medium
        tracking-wide transition-all duration-150 select-none active:translate-y-px
        disabled:cursor-not-allowed disabled:active:translate-y-0
        ${pad} ${styles[variant]} ${className}`}
      {...props}
    />
  );
});
