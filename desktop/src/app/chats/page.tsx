"use client";

import { Hash, Megaphone, Plus, UserRound, Users, X } from "lucide-react";
import { useMemo, useState } from "react";

import {
  useAddToList,
  useChats,
  useDialogs,
  usePatchSettings,
  useRemoveFromList,
  useSettings,
} from "@/lib/queries";
import { isChatId } from "@/lib/format";
import type { Dialog as TgDialog } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, EmptyState, PageHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { ToggleRow } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";

type ListName = "whitelist" | "blacklist";

export default function ChatsPage() {
  const settings = useSettings();
  const patch = usePatchSettings();
  const chats = useChats();
  const toast = useToast();
  const [picker, setPicker] = useState<ListName | null>(null);

  const b = settings.data?.behavior;
  const setBehavior = (key: string, value: boolean) =>
    patch.mutate({ behavior: { [key]: value } }, { onError: (e) => toast(e.message, "danger") });

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader eyebrow="where the bot answers" title="chats" />
      <div className="flex flex-col gap-4">
      <Card title="when to reply">
        <div className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
          <ToggleRow
            label="direct messages"
            hint="answer people who write to you directly"
            checked={b?.reply_in_dm ?? false}
            onCheckedChange={(v) => setBehavior("reply_in_dm", v)}
          />
          <ToggleRow
            label="new dialogues only"
            hint="in dms, skip chats that already have history"
            checked={b?.dm_new_dialogues_only ?? false}
            onCheckedChange={(v) => setBehavior("dm_new_dialogues_only", v)}
          />
          <ToggleRow
            label="groups"
            hint="master switch for group chats"
            checked={b?.reply_in_groups ?? false}
            onCheckedChange={(v) => setBehavior("reply_in_groups", v)}
          />
          <ToggleRow
            label="mentions"
            hint="answer when someone @mentions you in a group"
            checked={b?.reply_to_mentions ?? false}
            onCheckedChange={(v) => setBehavior("reply_to_mentions", v)}
          />
          <ToggleRow
            label="replies"
            hint="answer when someone replies to your message"
            checked={b?.reply_to_replies ?? false}
            onCheckedChange={(v) => setBehavior("reply_to_replies", v)}
          />
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChatListCard
          list="whitelist"
          title="whitelist"
          hint="reply only here, always. empty list means reply everywhere the switches allow."
          ids={chats.data?.whitelist ?? []}
          onAdd={() => setPicker("whitelist")}
        />
        <ChatListCard
          list="blacklist"
          title="blacklist"
          hint="never reply here. wins over everything else."
          ids={chats.data?.blacklist ?? []}
          onAdd={() => setPicker("blacklist")}
        />
      </div>

      <DialogPicker
        list={picker}
        onClose={() => setPicker(null)}
        taken={new Set([...(chats.data?.whitelist ?? []), ...(chats.data?.blacklist ?? [])])}
      />
      </div>
    </div>
  );
}

function ChatListCard({
  list,
  title,
  hint,
  ids,
  onAdd,
}: {
  list: ListName;
  title: string;
  hint: string;
  ids: number[];
  onAdd: () => void;
}) {
  const remove = useRemoveFromList();
  const toast = useToast();
  // dialogs may be cached from the picker: use titles when we have them
  const dialogs = useDialogs(false);
  const titles = useMemo(() => {
    const map = new Map<number, string>();
    for (const d of dialogs.data ?? []) map.set(d.id, d.title);
    return map;
  }, [dialogs.data]);

  return (
    <Card
      title={title}
      actions={
        <Button size="sm" variant="ghost" onClick={onAdd} aria-label={`add to ${title}`}>
          <Plus size={14} strokeWidth={1.5} />
        </Button>
      }
    >
      <p className="mb-2 text-xs text-text-3">{hint}</p>
      {ids.length === 0 ? (
        <EmptyState text="empty" />
      ) : (
        <ul className="-my-1 flex flex-col">
          {ids.map((id) => (
            <li
              key={id}
              className="group flex items-center justify-between gap-2 border-b border-line-1
                py-1.5 last:border-b-0"
            >
              <span className="min-w-0 truncate text-sm text-text-1">
                {titles.get(id) ?? <span className="mono text-text-2">{id}</span>}
              </span>
              <span className="flex items-center gap-2">
                {titles.has(id) ? <span className="mono text-xs text-text-3">{id}</span> : null}
                <button
                  aria-label={`remove ${id}`}
                  className="rounded-sm p-1 text-text-3 opacity-0 transition-all duration-120
                    group-hover:opacity-100 hover:bg-bg-3 hover:text-danger"
                  onClick={() =>
                    remove.mutate({ list, chatId: id }, { onError: (e) => toast(e.message, "danger") })
                  }
                >
                  <X size={13} strokeWidth={1.5} />
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const TYPE_ICON = { user: UserRound, group: Users, channel: Megaphone } as const;

function DialogPicker({
  list,
  onClose,
  taken,
}: {
  list: ListName | null;
  onClose: () => void;
  taken: Set<number>;
}) {
  const open = list !== null;
  const dialogs = useDialogs(open);
  const add = useAddToList();
  const toast = useToast();
  const [filter, setFilter] = useState("");
  const [manual, setManual] = useState("");

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return (dialogs.data ?? []).filter(
      (d) => !taken.has(d.id) && (!q || d.title.toLowerCase().includes(q) || String(d.id).includes(q)),
    );
  }, [dialogs.data, filter, taken]);

  const addId = (chatId: number) => {
    if (!list) return;
    add.mutate(
      { list, chatId },
      {
        onSuccess: () => toast(`added to ${list}`, "ok"),
        onError: (e) => toast(e.message, "danger"),
      },
    );
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
      title={`add to ${list ?? ""}`}
      wide
    >
      <div className="flex flex-col gap-4">
        <Input
          placeholder="search your dialogs"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        {dialogs.isLoading ? (
          <div className="flex items-center gap-2 py-4 text-sm text-text-2">
            <Spinner size={13} /> loading dialogs from telegram
          </div>
        ) : dialogs.isError ? (
          <p className="text-sm text-warn">
            could not load dialogs ({(dialogs.error as Error).message}). add a chat id by hand
            below.
          </p>
        ) : (
          <ul className="max-h-72 overflow-y-auto rounded-sm border border-line-1">
            {filtered.length === 0 ? (
              <li className="p-3 text-sm text-text-3">no dialogs match</li>
            ) : (
              filtered.map((d: TgDialog) => {
                const Icon = TYPE_ICON[d.type] ?? Hash;
                return (
                  <li key={d.id} className="border-b border-line-1 last:border-b-0">
                    <button
                      className="flex w-full items-center gap-2.5 px-3 py-1.5 text-left text-sm
                        text-text-2 transition-colors duration-120 hover:bg-bg-3 hover:text-text-1"
                      onClick={() => addId(d.id)}
                    >
                      <Icon size={14} strokeWidth={1.5} className="shrink-0 text-text-3" />
                      <span className="min-w-0 flex-1 truncate">{d.title || "untitled"}</span>
                      <span className="mono text-xs text-text-3">{d.id}</span>
                    </button>
                  </li>
                );
              })
            )}
          </ul>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (isChatId(manual)) {
              addId(Number(manual.trim()));
              setManual("");
            }
          }}
          className="flex items-center gap-2"
        >
          <Input
            className="mono"
            placeholder="or paste a chat id, like -1001234567890"
            value={manual}
            onChange={(e) => setManual(e.target.value)}
          />
          <Button type="submit" disabled={!isChatId(manual)}>
            add id
          </Button>
        </form>
      </div>
    </Dialog>
  );
}
