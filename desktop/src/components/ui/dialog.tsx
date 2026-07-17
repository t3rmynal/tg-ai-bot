"use client";

import { Dialog as RadixDialog } from "radix-ui";
import { X } from "lucide-react";

export function Dialog({
  open,
  onOpenChange,
  title,
  children,
  wide = false,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-bg-0/70 backdrop-blur-[2px]" />
        <RadixDialog.Content
          className={`fixed top-1/2 left-1/2 z-50 max-h-[85vh] w-full -translate-x-1/2
            -translate-y-1/2 overflow-y-auto rounded-lg border border-line-2 bg-bg-1 p-5
            shadow-2xl duration-200 ${wide ? "max-w-xl" : "max-w-md"}`}
        >
          <div className="mb-4 flex items-center justify-between">
            <RadixDialog.Title className="text-lg font-medium text-text-1">
              {title}
            </RadixDialog.Title>
            <RadixDialog.Close asChild>
              <button
                aria-label="close"
                className="rounded-sm p-1 text-text-3 transition-colors duration-120
                  hover:bg-bg-3 hover:text-text-1"
              >
                <X size={16} strokeWidth={1.5} />
              </button>
            </RadixDialog.Close>
          </div>
          {children}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
