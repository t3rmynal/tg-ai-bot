"use client";

import { forwardRef, type ButtonHTMLAttributes } from "react";

type Variant = "primary" | "outline" | "ghost" | "danger";

const styles: Record<Variant, string> = {
  primary:
    "bg-text-1 text-bg-0 hover:opacity-90 disabled:opacity-40",
  outline:
    "border border-line-2 bg-bg-2 text-text-1 hover:bg-bg-3 disabled:opacity-40",
  ghost: "text-text-2 hover:text-text-1 hover:bg-bg-3 disabled:opacity-40",
  danger:
    "border border-danger/40 text-danger hover:bg-danger-dim disabled:opacity-40",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
}

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "outline", size = "md", className = "", ...props },
  ref,
) {
  const pad = size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-sm";
  return (
    <button
      ref={ref}
      className={`inline-flex items-center justify-center gap-1.5 rounded-md font-medium
        transition-colors duration-120 select-none disabled:cursor-not-allowed
        ${pad} ${styles[variant]} ${className}`}
      {...props}
    />
  );
});
