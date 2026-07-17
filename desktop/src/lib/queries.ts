"use client";

// all query and mutation hooks in one place, keys included

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./api";
import type {
  AuthStatus,
  ChatLists,
  Dialog,
  GeneratedPrompt,
  ModelsResponse,
  RefreshModelsResponse,
  PersonasResponse,
  ProvidersResponse,
  Runtime,
  Settings,
  SettingsPatch,
  TestChatReply,
  UpdateInfo,
} from "./types";

export const keys = {
  auth: ["auth"] as const,
  runtime: ["runtime"] as const,
  settings: ["settings"] as const,
  personas: ["personas"] as const,
  providers: ["providers"] as const,
  chats: ["chats"] as const,
  dialogs: ["dialogs"] as const,
};

// auth

export function useAuthStatus(pollMs?: number) {
  return useQuery({
    queryKey: keys.auth,
    queryFn: () => api.get<AuthStatus>("/auth/status"),
    refetchInterval: pollMs ?? false,
  });
}

export function useSetCredentials() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { api_id: number; api_hash: string }) =>
      api.post<AuthStatus>("/auth/credentials", body),
    onSuccess: (data) => qc.setQueryData(keys.auth, data),
  });
}

export function useBeginQr() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ url: string; expires_at: string }>("/auth/qr"),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.auth }),
  });
}

export function useSubmitPassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => api.post<AuthStatus>("/auth/password", { password }),
    onSuccess: (data) => qc.setQueryData(keys.auth, data),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post("/auth/logout"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.auth });
      qc.invalidateQueries({ queryKey: keys.runtime });
    },
  });
}

// runtime

export function useRuntime() {
  return useQuery({
    queryKey: keys.runtime,
    queryFn: () => api.get<Runtime>("/runtime"),
  });
}

export function useSetEnabled() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => api.put<{ enabled: boolean }>("/runtime/enabled", { enabled }),
    onMutate: async (enabled) => {
      await qc.cancelQueries({ queryKey: keys.runtime });
      const prev = qc.getQueryData<Runtime>(keys.runtime);
      if (prev) qc.setQueryData(keys.runtime, { ...prev, enabled });
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(keys.runtime, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: keys.runtime }),
  });
}

// settings and personas

export function useSettings() {
  return useQuery({
    queryKey: keys.settings,
    queryFn: () => api.get<Settings>("/settings"),
  });
}

export function usePatchSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: SettingsPatch) => api.patch<Settings>("/settings", patch),
    onSuccess: (data) => {
      qc.setQueryData(keys.settings, data);
      qc.invalidateQueries({ queryKey: keys.runtime });
      qc.invalidateQueries({ queryKey: keys.personas });
    },
  });
}

export function usePersonas() {
  return useQuery({
    queryKey: keys.personas,
    queryFn: () => api.get<PersonasResponse>("/settings/personas"),
  });
}

export function useGeneratePrompt() {
  return useMutation({
    mutationFn: (body: { name: string; kind: string; tone: string; language: string; extra: string }) =>
      api.post<GeneratedPrompt>("/settings/prompt/generate", body),
  });
}

// providers

export function useProviders() {
  return useQuery({
    queryKey: keys.providers,
    queryFn: () => api.get<ProvidersResponse>("/providers"),
  });
}

function useProviderMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.providers });
      qc.invalidateQueries({ queryKey: keys.runtime });
    },
  });
}

export function useSetActive() {
  return useProviderMutation((body: { name: string; model?: string }) =>
    api.put("/providers/active", body),
  );
}

export function useSetKey() {
  return useProviderMutation(({ name, api_key }: { name: string; api_key: string }) =>
    api.put(`/providers/${name}/key`, { api_key }),
  );
}

export function usePatchProvider() {
  return useProviderMutation(
    ({ name, ...patch }: { name: string; label?: string; base_url?: string; rpm?: number }) =>
      api.patch(`/providers/${name}`, patch),
  );
}

export function useCreateProvider() {
  return useProviderMutation(
    (body: { name: string; label: string; base_url: string; api_key?: string; rpm?: number }) =>
      api.post("/providers", body),
  );
}

export function useDeleteProvider() {
  return useProviderMutation((name: string) => api.del(`/providers/${name}`));
}

export function useAddModel() {
  return useProviderMutation(({ name, model }: { name: string; model: string }) =>
    api.post(`/providers/${name}/models`, { model }),
  );
}

export function useRemoveModel() {
  return useProviderMutation(({ name, model }: { name: string; model: string }) =>
    api.del(`/providers/${name}/models?model=${encodeURIComponent(model)}`),
  );
}

export function useRefreshModels() {
  return useProviderMutation((name: string) =>
    api.post<RefreshModelsResponse>(`/providers/${name}/models/refresh`),
  );
}

export function fetchLiveModels(name: string) {
  return api.get<ModelsResponse>(`/providers/${name}/models?live=true`);
}

// chats

export function useChats() {
  return useQuery({
    queryKey: keys.chats,
    queryFn: () => api.get<ChatLists>("/chats"),
  });
}

export function useDialogs(enabled: boolean) {
  return useQuery({
    queryKey: keys.dialogs,
    queryFn: () => api.get<Dialog[]>("/chats/dialogs?limit=200"),
    enabled,
    staleTime: 30_000,
  });
}

function useChatsMutation<TArgs>(fn: (args: TArgs) => Promise<ChatLists>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => qc.setQueryData(keys.chats, data),
  });
}

export function useAddToList() {
  return useChatsMutation(({ list, chatId }: { list: "whitelist" | "blacklist"; chatId: number }) =>
    api.post<ChatLists>(`/chats/${list}`, { chat_id: chatId }),
  );
}

export function useRemoveFromList() {
  return useChatsMutation(({ list, chatId }: { list: "whitelist" | "blacklist"; chatId: number }) =>
    api.del<ChatLists>(`/chats/${list}/${chatId}`),
  );
}

// updates

export function useUpdates() {
  return useQuery({
    queryKey: ["updates"],
    queryFn: () => api.get<UpdateInfo>("/updates"),
    staleTime: 60 * 60_000,
    retry: 1,
  });
}

export function useCheckUpdates() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.get<UpdateInfo>("/updates?force=true"),
    onSuccess: (data) => qc.setQueryData(["updates"], data),
  });
}

// test chat

export function useTestChat() {
  return useMutation({
    mutationFn: (body: { message: string; history: { role: string; content: string }[] }) =>
      api.post<TestChatReply>("/test-chat", body),
  });
}
