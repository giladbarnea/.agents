import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import type { AgentMessage } from "@earendil-works/pi-agent-core";
import { compact, convertToLlm, serializeConversation, SettingsManager } from "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/index.js";
import { withCoordinationSchemas, type CoordinationPayload } from "./codex-coordination-tools.ts";

type ReplayItem = {
  type: string;
  call_id?: string;
  content?: string | Array<{ type: string; text?: string }>;
  [key: string]: unknown;
};
type ReplayState = { model: string; items: ReplayItem[] };
type ReplayEntry = { id: string; codexReplay?: ReplayState; content?: unknown; message?: { content?: unknown }; codex?: Array<{ type: string; payload: ReplayItem & { replacement_history?: ReplayItem[] } }> };
type Payload = { input: ReplayItem[]; [key: string]: unknown };

/** @example family("gpt-6-sol") === family("gpt-6-luna") // true */
function family(model: string): string {
  const identifier = model.replace(/^openai-codex\//, "");
  return ["gpt-6-", "gpt-5.6-"].find(prefix => identifier.startsWith(prefix)) ?? identifier;
}

function activeReplays(context: ExtensionContext): Map<string, ReplayState> {
  const selected = new Map<string, ReplayState>();
  for (const projected of context.sessionManager.buildSessionProjection().entries) {
    const entry = projected.sourceEntry as ReplayEntry;
    if (!entry.codexReplay || projected.messages.length !== 1) continue;
    const content = entry.message?.content ?? entry.content;
    const message = projected.messages[0];
    if (!("content" in message)) throw new Error(`Codex replay entry ${entry.id} has no context content`);
    if (!isDeepStrictEqual(message.content, content)) continue;
    selected.set(entry.id, entry.codexReplay);
  }
  return selected;
}

function verifyModel(states: Iterable<ReplayState>, context: ExtensionContext): void {
  for (const state of states) {
    if (context.model?.provider !== "openai-codex" || family(state.model) !== family(context.model.id)) {
      throw new Error(`Cannot replay encrypted Codex coordination with ${context.model?.provider}/${context.model?.id}`);
    }
  }
}

/** @example toolKey({ type: "function_call_output", call_id: "c" }) // "output:c" */
function toolKey(item: ReplayItem): string | undefined {
  if (!item.call_id) return undefined;
  return `${item.type.endsWith("_output") ? "output" : "call"}:${item.call_id}`;
}

/** @example markerText({ type: "message", content: [{ type: "input_text", text: "marker" }] }) // "marker" */
function markerText(item: ReplayItem): string | undefined {
  if (typeof item.content === "string") return item.content;
  if (item.content?.length !== 1 || item.content[0].type !== "input_text") return undefined;
  return item.content[0].text;
}

type SummarySpan = { prefix: string; items: ReplayItem[] };

function summaryItems(messages: AgentMessage[], context: ExtensionContext): ReplayItem[] {
  const projection = context.sessionManager.buildSessionProjection();
  const selected = projection.entries.filter(entry => entry.messages.some(message => messages.some(candidate => isDeepStrictEqual(candidate, message))));
  const active = activeReplays(context);
  const states = selected.flatMap(entry => active.get(entry.sourceEntry.id) ? [active.get(entry.sourceEntry.id)!] : [])
    .map(state => ({ ...state, items: state.items.filter(item => !Array.isArray(item.encrypted_function_args) || item.encrypted_function_args.length > 0) }));
  verifyModel(states, context);
  const callIds = new Set(states.flatMap(state => state.items.flatMap(item => item.call_id ? [item.call_id] : [])));
  const originals = new Map<string, ReplayItem>();
  for (const source of context.sessionManager.getBranch()) {
    const entry = source as ReplayEntry;
    const items = (entry.codex ?? []).flatMap(record => record.type === "response_item" ? [record.payload] : record.type === "compacted" ? record.payload.replacement_history ?? [] : []);
    for (const item of [...items, ...(entry.codexReplay?.items ?? [])]) {
      const key = toolKey(item);
      if (key) originals.set(key, item);
    }
  }
  const items: ReplayItem[] = [];
  const included = new Set<string>();
  const appendTool = (key: string): void => {
    const original = originals.get(key);
    if (!original) throw new Error(`Missing original Codex item for summarization: ${key}`);
    included.add(key);
    items.push(original);
  };
  for (const entry of selected) {
    const state = active.get(entry.sourceEntry.id);
    items.push(...(state?.items.filter(item => item.type === "agent_message") ?? []));
    for (const message of entry.messages) {
      if (message.role === "assistant") {
        for (const block of message.content) {
          const checkpoint = state && block.type === "thinking" && block.thinkingSignature ? JSON.parse(block.thinkingSignature) as ReplayItem : undefined;
          if (checkpoint && ["compaction", "context_compaction"].includes(checkpoint.type)) items.push(checkpoint);
          if (block.type === "toolCall" && callIds.has(block.id.split("|")[0])) appendTool(`call:${block.id.split("|")[0]}`);
        }
      }
      if (message.role === "toolResult" && callIds.has(message.toolCallId.split("|")[0])) appendTool(`output:${message.toolCallId.split("|")[0]}`);
    }
  }
  for (const callId of callIds) {
    if (!included.has(`call:${callId}`) || !included.has(`output:${callId}`)) throw new Error(`Compaction would split encrypted Codex call ${callId}`);
  }
  return items;
}

function rewriteSummary(payload: Payload, spans: SummarySpan[]): CoordinationPayload {
  const texts = payload.input.flatMap(item => typeof item.content === "string" ? [item.content] : item.content?.flatMap(block => block.text ? [block.text] : []) ?? []);
  const matching = spans.filter(span => texts.some(text => text.startsWith(span.prefix)));
  if (matching.length !== 1) throw new Error("Cannot identify the exact Codex coordination summarization span");
  return withCoordinationSchemas({ ...payload, input: [...matching[0].items, ...payload.input] }, matching[0].items);
}

/** Replay imported opaque Codex context through supported Pi hooks without changing ordinary reasoning serialization. */
export default function (pi: ExtensionAPI): void {
  let markers = new Map<string, ReplayItem>();
  let restoredTeams: Array<{ id: string; name: string }> = [];
  const clearSummary = (): void => { markers.clear(); };
  pi.on("session_compact", clearSummary);
  pi.on("session_compact_failed", clearSummary);
  pi.on("session_shutdown", clearSummary);

  pi.on("session_before_compact", async (event, context) => {
    clearSummary();
    try {
      const preparation = event.preparation;
      const history = preparation.messagesToSummarize;
      const prefix = preparation.turnPrefixMessages;
      const spans: SummarySpan[] = [];
      if (!preparation.isSplitTurn || history.length > 0) {
        spans.push({ prefix: `<conversation>\n${serializeConversation(convertToLlm(history))}\n</conversation>`, items: summaryItems(history, context) });
      }
      if (preparation.isSplitTurn && prefix.length > 0) {
        spans.push({ prefix: `# Conversation\n${serializeConversation(convertToLlm(prefix))}\n\n# Instructions\n`, items: summaryItems(prefix, context) });
      }
      if (!spans.some(span => span.items.length > 0)) return;
      const settings = SettingsManager.create(context.cwd);
      const providerRetry = settings.getProviderRetrySettings();
      const result = await compact(preparation, context.model!, undefined, undefined, event.customInstructions, event.signal, context.thinkingLevel,
        (model, providerContext, options) => context.modelRegistry.streamSimple(model, providerContext, {
          ...options,
          ...providerRetry,
          timeoutMs: providerRetry.timeoutMs ?? (settings.getHttpIdleTimeoutMs() || 2147483647),
          websocketConnectTimeoutMs: settings.getWebSocketConnectTimeoutMs(),
          onPayload: payload => {
            const rewritten = rewriteSummary(payload as Payload, spans);
            pi.events.emit("codex-replay:summary-request", rewritten);
            return rewritten;
          },
        }), undefined, settings.getRetrySettings());
      return { compaction: result };
    } catch (error) {
      clearSummary();
      context.ui.notify(`Codex coordination compaction cancelled: ${String(error)}`, "error");
      return { cancel: true };
    }
  });

  pi.on("session_start", (_event, context) => {
    restoredTeams = [];
    clearSummary();
    if (!(context.sessionManager.getHeader() as { codex?: unknown })?.codex) return;
    const session = context.sessionManager.getSessionFile();
    if (!session) throw new Error("Codex runtime restoration requires a persisted Pi session");
    const paths = JSON.parse(execFileSync("uv", ["run", "--script", fileURLToPath(new URL("pi_runtime.py", import.meta.url)), session], { encoding: "utf8" })) as string[];
    restoredTeams = paths.map(path => JSON.parse(readFileSync(path, "utf8")) as { id: string; name: string; originMainSessionId: string })
      .filter(team => team.originMainSessionId === context.sessionManager.getSessionId());
  });

  pi.on("tool_call", event => {
    if (event.toolName !== "team_resume") return;
    const requested = (event.input as { team?: string }).team;
    if (!restoredTeams.some(team => team.id === requested || team.name === requested)) return;
    const schema = pi.getAllTools().find(tool => tool.name === "team_spawn")?.parameters as { properties?: { teammates?: { items?: { properties?: { extensionPaths?: unknown } } } } } | undefined;
    if (!schema?.properties?.teammates?.items?.properties?.extensionPaths) {
      return { block: true, reason: "Restored teams require a pi-simple-team build with extensionPaths support; older builds omit the replay extension." };
    }
  });

  pi.on("before_agent_start", event => {
    if (restoredTeams.length === 0) return;
    return { systemPrompt: `${event.systemPrompt}\nConverted teams are available through team_list/team_resume. Resume them idle before sending new instructions. Team IDs: ${restoredTeams.map(team => team.id).join(", ")}.` };
  });

  pi.on("context", (event, context) => {
    try {
      const selected = activeReplays(context);
      verifyModel(selected.values(), context);
      markers = new Map();
      return { messages: event.messages.map(message => {
        if (message.role !== "custom") return message;
        const identifier = (message.details as { codexReplayEntryId?: string } | undefined)?.codexReplayEntryId;
        if (!identifier || !selected.has(identifier)) return message;
        const items = selected.get(identifier)!.items;
        if (items.length !== 1 || items[0].type !== "agent_message") throw new Error(`Invalid Codex delivery replay marker ${identifier}`);
        const marker = `[[codex-replay:${identifier}]]`;
        markers.set(marker, items[0]);
        return { ...message, content: marker };
      }) };
    } catch (error) {
      context.abort();
      throw error;
    }
  });

  pi.on("before_provider_request", (event, context) => {
    try {
      const payload = event.payload as Payload;
      const selected = activeReplays(context);
      verifyModel(selected.values(), context);
      if (selected.size === 0) return;
      const tools = new Map<string, ReplayItem>();
      for (const state of selected.values()) {
        for (const item of state.items) {
          const key = toolKey(item);
          if (key) tools.set(key, item);
        }
      }
      const seen = new Set<string>();
      const input = payload.input.map(item => {
        const marker = markerText(item);
        if (marker && markers.has(marker)) {
          seen.add(marker);
          return markers.get(marker)!;
        }
        const key = toolKey(item);
        return key && tools.has(key) ? tools.get(key)! : item;
      });
      if (seen.size !== markers.size) throw new Error("Codex coordination replay marker was removed before the provider request");
      return withCoordinationSchemas({ ...payload, input }, [...selected.values()].flatMap(state => state.items));
    } catch (error) {
      context.abort();
      throw error;
    }
  });
}
