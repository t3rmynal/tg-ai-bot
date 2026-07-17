"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";

import {
  useGeneratePrompt,
  usePatchSettings,
  usePersonas,
  useSettings,
} from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";

export default function PersonaPage() {
  const personas = usePersonas();
  const settings = useSettings();
  const patch = usePatchSettings();
  const toast = useToast();

  const [generatorOpen, setGeneratorOpen] = useState(false);
  const [customDraft, setCustomDraft] = useState<string | null>(null);

  const items = personas.data?.personas ?? [];
  const activeKey = items.find((p) => p.is_active)?.key;
  const language = settings.data?.language ?? "en";
  const customPrompt = settings.data?.custom_prompt ?? "";

  const pick = (key: string) =>
    patch.mutate({ persona: key }, { onError: (e) => toast(e.message, "danger") });

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <Card
        title="persona"
        actions={
          <div className="flex items-center gap-1 rounded-md border border-line-2 p-0.5">
            {(["en", "ru"] as const).map((lang) => (
              <button
                key={lang}
                onClick={() =>
                  patch.mutate({ language: lang }, { onError: (e) => toast(e.message, "danger") })
                }
                className={`rounded-sm px-2 py-0.5 text-xs transition-colors duration-120 ${
                  language === lang ? "bg-accent-dim text-accent" : "text-text-3 hover:text-text-1"
                }`}
              >
                {lang}
              </button>
            ))}
          </div>
        }
      >
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          {items.map((p) => {
            const active = p.key === activeKey;
            return (
              <button
                key={p.key}
                onClick={() => pick(p.key)}
                className={`flex flex-col items-start gap-1.5 rounded-md border p-3 text-left
                  transition-colors duration-120 ${
                    active
                      ? "border-accent/40 bg-accent-dim"
                      : "border-line-1 bg-bg-2 hover:border-line-2 hover:bg-bg-3"
                  }`}
              >
                <span className="flex w-full items-center justify-between">
                  <span className={`text-sm font-medium ${active ? "text-accent" : "text-text-1"}`}>
                    {p.label.toLowerCase()}
                  </span>
                  <Badge tone={p.kind === "human" ? "warn" : "neutral"}>
                    {p.kind === "human" ? "acts human" : p.kind === "bot" ? "honest ai" : "custom"}
                  </Badge>
                </span>
                <span className="text-xs text-text-3">{p.description}</span>
              </button>
            );
          })}
        </div>
      </Card>

      <Card
        title="custom prompt"
        actions={
          <Button size="sm" variant="ghost" onClick={() => setGeneratorOpen(true)}>
            <Sparkles size={13} strokeWidth={1.5} /> generate with ai
          </Button>
        }
      >
        <div className="flex flex-col gap-3">
          <Textarea
            rows={7}
            className="mono text-xs leading-relaxed"
            placeholder="write your own system prompt, then pick the custom persona above"
            value={customDraft ?? customPrompt}
            onChange={(e) => setCustomDraft(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            {customDraft !== null && customDraft !== customPrompt ? (
              <>
                <Button size="sm" variant="ghost" onClick={() => setCustomDraft(null)}>
                  discard
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() =>
                    patch.mutate(
                      { custom_prompt: customDraft, persona: "custom" },
                      {
                        onSuccess: () => {
                          setCustomDraft(null);
                          toast("custom prompt saved", "ok");
                        },
                        onError: (e) => toast(e.message, "danger"),
                      },
                    )
                  }
                >
                  save and use
                </Button>
              </>
            ) : null}
          </div>
        </div>
      </Card>

      <Card title="rendered system prompt">
        <pre className="mono max-h-64 overflow-y-auto text-xs leading-relaxed whitespace-pre-wrap text-text-2">
          {personas.data?.preview ?? "..."}
        </pre>
      </Card>

      <GeneratorDialog
        open={generatorOpen}
        onOpenChange={setGeneratorOpen}
        defaultName={settings.data?.bot_name ?? ""}
        defaultLanguage={language}
        onAccept={(prompt) => {
          patch.mutate(
            { custom_prompt: prompt, persona: "custom" },
            {
              onSuccess: () => {
                setGeneratorOpen(false);
                setCustomDraft(null);
                toast("generated prompt saved", "ok");
              },
              onError: (e) => toast(e.message, "danger"),
            },
          );
        }}
      />
    </div>
  );
}

function GeneratorDialog({
  open,
  onOpenChange,
  defaultName,
  defaultLanguage,
  onAccept,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  defaultName: string;
  defaultLanguage: string;
  onAccept: (prompt: string) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="generate a persona prompt" wide>
      {/* the body unmounts with the dialog, so its state resets on close */}
      <GeneratorBody
        defaultName={defaultName}
        defaultLanguage={defaultLanguage}
        onAccept={onAccept}
      />
    </Dialog>
  );
}

function GeneratorBody({
  defaultName,
  defaultLanguage,
  onAccept,
}: {
  defaultName: string;
  defaultLanguage: string;
  onAccept: (prompt: string) => void;
}) {
  const generate = useGeneratePrompt();
  const [name, setName] = useState(defaultName);
  const [kind, setKind] = useState<"human" | "bot">("human");
  const [tone, setTone] = useState("");
  const [extra, setExtra] = useState("");
  const [result, setResult] = useState<{ prompt: string; source: string } | null>(null);

  return (
    <>
      {result ? (
        <div className="flex flex-col gap-4">
          {result.source === "fallback" ? (
            <p className="text-xs text-warn">
              the ai provider was unreachable, this is the offline template instead
            </p>
          ) : null}
          <pre className="mono max-h-72 overflow-y-auto rounded-sm border border-line-1 bg-bg-2 p-3 text-xs leading-relaxed whitespace-pre-wrap text-text-2">
            {result.prompt}
          </pre>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setResult(null)}>
              back
            </Button>
            <Button variant="primary" onClick={() => onAccept(result.prompt)}>
              use this prompt
            </Button>
          </div>
        </div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            generate.mutate(
              { name, kind, tone, language: defaultLanguage, extra },
              { onSuccess: setResult },
            );
          }}
          className="flex flex-col gap-4"
        >
          <div className="grid grid-cols-2 gap-3">
            <Field label="name">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="the bot" />
            </Field>
            <Field label="acts as">
              <div className="flex h-8 items-center gap-1 rounded-md border border-line-2 p-0.5">
                {(
                  [
                    ["human", "a real person"],
                    ["bot", "an honest ai"],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setKind(value)}
                    className={`h-full flex-1 rounded-sm text-xs transition-colors duration-120 ${
                      kind === value ? "bg-accent-dim text-accent" : "text-text-3 hover:text-text-1"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </Field>
          </div>
          <Field label="tone and personality">
            <Input
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              placeholder="laid back, curious, a bit sarcastic"
            />
          </Field>
          <Field label="extra rules (optional)">
            <Textarea
              rows={3}
              value={extra}
              onChange={(e) => setExtra(e.target.value)}
              placeholder="never talks about work, loves cats"
            />
          </Field>
          <div className="flex justify-end">
            <Button type="submit" variant="primary" disabled={generate.isPending}>
              {generate.isPending ? <Spinner size={12} /> : <Sparkles size={13} strokeWidth={1.5} />}
              generate
            </Button>
          </div>
        </form>
      )}
    </>
  );
}
