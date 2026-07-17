"use client";

import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";

const base = `w-full rounded-sm border border-line-2 bg-bg-2 px-2.5 text-sm text-text-1
  placeholder:text-text-3 transition-colors duration-120 hover:border-line-glow
  focus:border-accent/50`;

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className = "", ...props }, ref) {
    return <input ref={ref} className={`${base} h-8 ${className}`} {...props} />;
  },
);

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className = "", ...props }, ref) {
  return <textarea ref={ref} className={`${base} py-2 leading-relaxed ${className}`} {...props} />;
});

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="label">{label}</span>
      {children}
      {hint ? <span className="text-xs text-text-3">{hint}</span> : null}
    </label>
  );
}
