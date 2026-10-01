import { readFileSync } from "node:fs";
import { withCoordinationSchemas } from "../scripts/codex-coordination-tools.ts";
const cases = JSON.parse(readFileSync(0, "utf8"));
console.log(JSON.stringify(cases.map(test => {
  try { return { payload: withCoordinationSchemas(test.payload, test.imported) }; }
  catch (error) { return { error: String(error) }; }
})));
