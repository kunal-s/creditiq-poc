// Run with: npm run test:copilot-ui
import { expect, test } from "@playwright/test";
import { asTurnResult, parseBlock, parseSse } from "../src/sse.ts";

const stream = (...chunks: string[]) =>
  new ReadableStream<Uint8Array>({
    start(c) {
      for (const s of chunks) c.enqueue(new TextEncoder().encode(s));
      c.close();
    },
  });

async function all(s: ReadableStream<Uint8Array>) {
  const out = [];
  for await (const e of parseSse(s)) out.push(e);
  return out;
}

test("events split across chunks and CRLF are reassembled", async () => {
  const events = await all(stream('event: session\r\ndata: {"session_id":"s1"}\r', '\n\r\nevent: result\ndata: {"a"', ":1}\n\n"));
  expect(events).toEqual([
    { event: "session", data: { session_id: "s1" } },
    { event: "result", data: { a: 1 } },
  ]);
});

test("a final block without the blank line is still delivered; junk is skipped", async () => {
  expect(await all(stream('event: error\ndata: {"code":"internal"}'))).toEqual([{ event: "error", data: { code: "internal" } }]);
  expect(parseBlock("event: x\ndata: not json")).toBeNull();
  expect(parseBlock(": comment only")).toBeNull();
});

test("a result is validated before it is trusted", () => {
  const ok = { session_id: "s", terminal: "answer", text: "hi", columns: ["a"], rows: [{ a: "1" }], sources: [] };
  expect(asTurnResult(ok)?.rows).toEqual([{ a: "1" }]);
  expect(asTurnResult({ ...ok, terminal: "other" })).toBeNull();
  expect(asTurnResult({ ...ok, text: 5 })).toBeNull();
  expect(asTurnResult({ session_id: "s", terminal: "cannot_do", text: "x" })?.rows).toEqual([]);
  expect(asTurnResult(null)).toBeNull();
  expect(asTurnResult(ok)?.action).toBeNull();
  const card = { id: "p_1", fields: { to: "", subject: "S", body: "B" } };
  expect(asTurnResult({ ...ok, terminal: "confirm", action: card })?.action).toEqual(card);
  expect(asTurnResult({ ...ok, terminal: "confirm", action: { id: "p_1", fields: { to: 5 } } })?.action).toBeNull();
});
