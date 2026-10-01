import { readFileSync } from "node:fs";

type Tool = { type: string; name?: string; tools?: Tool[]; [key: string]: unknown };
type Item = { type?: string; namespace?: string; name?: string; arguments?: string; call_id?: string; tools?: Tool[]; encrypted_function_args?: string[]; [key: string]: unknown };
type Choice = { type: string; name?: string; namespace?: string; tools?: Choice[]; [key: string]: unknown };
export type CoordinationPayload = { input: Item[]; tools?: Tool[]; tool_choice?: string | Choice; [key: string]: unknown };
type DeclaredTool = { tool: Tool; namespace?: Tool };
const snapshot = JSON.parse(readFileSync(new URL("codex-coordination-tools.json", import.meta.url), "utf8")) as { tools: Tool[] };

/** @example declarations([{ type: "function", name: "read" }])[0].tool.name // "read" */
function declarations(tools: Tool[]): DeclaredTool[] {
  return tools.flatMap(tool => tool.type === "namespace" ? tool.tools!.map(member => ({ tool: member, namespace: tool })) : [{ tool }]);
}

/** @example choice({ tool: { type: "function", name: "read" } }) // { type: "function", name: "read" } */
function choice(declaration: DeclaredTool): Choice {
  return { type: declaration.tool.type,
    ...(declaration.tool.name ? { name: declaration.tool.name } : {}),
    ...(declaration.namespace ? { namespace: declaration.namespace.name } : {}),
    ...(declaration.tool.server_label ? { server_label: declaration.tool.server_label } : {}) };
}

/** @example identifier({ type: "function", namespace: "probe", name: "echo" }) // "function:probe:echo" */
function identifier(selection: Choice): string {
  return `${selection.type}:${selection.namespace ?? ""}:${selection.name ?? selection.server_label ?? ""}`;
}

/** @example grouped([{ tool: { type: "function", name: "read" } }])[0].name // "read" */
function grouped(declarations: DeclaredTool[]): Tool[] {
  const result: Tool[] = [];
  const namespaces = new Map<string, Tool>();
  for (const declaration of declarations) {
    if (!declaration.namespace) {
      result.push(declaration.tool);
      continue;
    }
    const name = declaration.namespace.name!;
    if (!namespaces.has(name)) {
      const namespace = { ...declaration.namespace, tools: [] };
      namespaces.set(name, namespace);
      result.push(namespace);
    }
    namespaces.get(name)!.tools!.push(declaration.tool);
  }
  return result;
}

/** Add native encrypted-field schemas without granting any new tool execution.
 * @example withCoordinationSchemas({ input: [] }, []).input // []
 */
export function withCoordinationSchemas(payload: CoordinationPayload, imported: Item[]): CoordinationPayload {
  const activeCalls = new Set(payload.input.filter(item => item.type === "function_call").map(item => item.call_id));
  const names = new Set(imported.filter(item => item.type === "function_call" && item.namespace === "collaboration" && activeCalls.has(item.call_id))
    .filter(item => item.encrypted_function_args?.length !== 0)
    .filter(item => item.encrypted_function_args?.length || Object.values(JSON.parse(item.arguments!)).some(value => typeof value === "string" && value.startsWith("gAAAAA")))
    .map(item => item.name!));
  if (names.size === 0) return payload;
  const schemas = snapshot.tools.filter(tool => names.has(tool.name!));
  if (schemas.length !== names.size) throw new Error(`Unsupported encrypted coordination schema: ${[...names].join(", ")}`);
  const originals = new Map<string, DeclaredTool>();
  const initial = [...(payload.tools ?? []), ...payload.input.filter(item => item.type === "additional_tools").flatMap(item => item.tools!)];
  for (const declaration of declarations(initial)) originals.set(identifier(choice(declaration)), declaration);
  const allowed = [...originals.values()].map(choice);
  const historical = schemas.filter(tool => !originals.has(identifier({ type: tool.type, namespace: "collaboration", name: tool.name })));
  if (historical.length === 0) return payload;
  let toolChoice = payload.tool_choice ?? "auto";
  if (typeof toolChoice === "object") {
    const selections = toolChoice.type === "allowed_tools" ? toolChoice.tools! : [toolChoice];
    const enablesHistory = selections.some(selection => !originals.has(identifier(selection)) && historical.some(tool =>
      (selection.namespace === "collaboration" && selection.name === tool.name) ||
      (!selection.namespace && selection.name === tool.name) ||
      selection.name === `collaboration.${tool.name}` ||
      (selection.type === "namespace" && selection.name === "collaboration")));
    if (enablesHistory) throw new Error("Tool choice cannot enable replay-only Codex coordination tools");
  }
  if (toolChoice === "required" && allowed.length === 0) throw new Error("No original Pi tool can satisfy required tool choice");
  if (toolChoice === "auto" || toolChoice === "required") {
    toolChoice = allowed.length ? { type: "allowed_tools", mode: toolChoice, tools: allowed } : "none";
  }
  const namespace = { type: "namespace", name: "collaboration", description: "Historical encrypted coordination schemas. Replay only, not available for new execution.", tools: historical };
  return { ...payload, tools: grouped([...originals.values(), ...declarations([namespace])]), tool_choice: toolChoice };
}
