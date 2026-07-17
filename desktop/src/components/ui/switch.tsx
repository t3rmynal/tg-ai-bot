"use client";

import { Switch as RadixSwitch } from "radix-ui";

export function Switch({
  checked,
  onCheckedChange,
  disabled,
  success = false,
}: {
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  disabled?: boolean;
  // success styling is reserved for the bot on/off toggle only
  success?: boolean;
}) {
  const onColor = success ? "data-[state=checked]:bg-ok" : "data-[state=checked]:bg-accent";
  return (
    <RadixSwitch.Root
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
      className={`relative h-5 w-9 shrink-0 cursor-pointer rounded-full bg-bg-3 transition-colors
        duration-120 disabled:opacity-40 ${onColor}`}
    >
      <RadixSwitch.Thumb
        className="block size-4 translate-x-0.5 rounded-full bg-text-1 transition-transform
          duration-120 will-change-transform data-[state=checked]:translate-x-[18px]
          data-[state=checked]:bg-bg-0"
      />
    </RadixSwitch.Root>
  );
}

export function ToggleRow({
  label,
  hint,
  checked,
  onCheckedChange,
  disabled,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <div className="min-w-0">
        <p className="text-sm text-text-1">{label}</p>
        {hint ? <p className="mt-0.5 text-xs text-text-3">{hint}</p> : null}
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} disabled={disabled} />
    </div>
  );
}
