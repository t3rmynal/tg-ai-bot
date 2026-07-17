// mirrors the backend api contract, see tgai/api/*

export type AuthStateName =
  | "no_credentials"
  | "connecting"
  | "unauthorized"
  | "qr_pending"
  | "password_needed"
  | "authorized";

export interface AuthStatus {
  state: AuthStateName;
  user: { id: number; username: string; first_name: string } | null;
  qr: { url: string; expires_at: string | null } | null;
}

export interface Behavior {
  enabled: boolean;
  reply_in_dm: boolean;
  reply_in_groups: boolean;
  reply_to_mentions: boolean;
  reply_to_replies: boolean;
  dm_new_dialogues_only: boolean;
  history_limit: number;
  response_delay: number;
  per_chat_cooldown: number;
  ai_temperature: number;
  ai_max_tokens: number;
  ai_thinking: boolean;
}

export interface Settings {
  behavior: Behavior;
  persona: string;
  custom_prompt: string;
  language: string;
  bot_name: string;
}

export interface SettingsPatch {
  behavior?: Partial<Behavior>;
  persona?: string;
  custom_prompt?: string;
  language?: string;
  bot_name?: string;
}

export interface Persona {
  key: string;
  label: string;
  kind: string;
  description: string;
  is_active: boolean;
}

export interface PersonasResponse {
  personas: Persona[];
  preview: string;
}

export interface Provider {
  name: string;
  label: string;
  base_url: string;
  key_set: boolean;
  api_key_masked: string;
  key_hint: string;
  needs_key: boolean;
  supports_thinking: boolean;
  recommended: boolean;
  signup: string;
  rpm: number;
  models: string[];
  builtin: boolean;
}

export interface ProvidersResponse {
  active: { name: string; model: string };
  providers: Provider[];
}

export interface ModelsResponse {
  models: string[];
  source: "static" | "live";
  error?: string;
}

export interface RefreshModelsResponse {
  models: string[];
  added: string[];
  source: "live";
}

export interface ChatLists {
  whitelist: number[];
  blacklist: number[];
}

export interface Dialog {
  id: number;
  title: string;
  type: "user" | "group" | "channel";
  unread_count: number;
}

export interface RuntimeStats {
  ai_calls: number;
  ai_errors: number;
  messages_processed: number;
  rate_limited: number;
  chats_with_history: number;
}

export interface Runtime {
  enabled: boolean;
  auth_state: AuthStateName;
  provider: string;
  provider_label: string;
  model: string;
  persona: string;
  language: string;
  rpm: number;
  uptime_s: number;
  version: string;
  stats: RuntimeStats;
}

export interface ActivityEvent {
  id: number;
  kind: "incoming" | "reply" | "wait" | "error" | "info";
  text: string;
  ts: number;
}

export interface HistoryEntry {
  chat_id: number;
  message_count: number;
  last_role: string | null;
}

export interface GeneratedPrompt {
  prompt: string;
  source: "ai" | "fallback";
}

export interface TestChatReply {
  reply: string;
  latency_ms: number;
}
