// The memo's recommendation (F-23.4) is stored as paragraphs, like every other section. Each heading
// credit completes ("Recommendation", "Terms and conditions", ...) is kept as one paragraph: the
// heading on its first line and the answer under it, so the memo on screen, its downloads and the
// Rating step all read the same record. A paragraph under no heading (words written in Outputs) is
// kept as it is, above the headings.

export type Answer = { prompt: string; text: string };

const clean = (s: string) => s.trim().replace(/:$/, "").trim();

/** The answer under each heading, in the configured order, and any paragraph under none. */
export function readRecommendation(
  text: string,
  prompts: string[],
): { answers: Answer[]; other: string[] } {
  const found = new Map<string, string>();
  const other: string[] = [];
  for (const para of text.split("\n\n").filter((p) => p.trim())) {
    const [first = "", ...rest] = para.split("\n");
    const prompt = prompts.find((p) => clean(p) === clean(first));
    if (prompt && rest.join("\n").trim()) found.set(prompt, rest.join("\n").trim());
    else other.push(para.trim());
  }
  return { answers: prompts.map((prompt) => ({ prompt, text: found.get(prompt) ?? "" })), other };
}

/** The paragraphs to store: any paragraph under no heading first, then each answered heading. */
export function writeRecommendation(answers: Answer[], other: string[]): string[] {
  return [
    ...other.map((p) => p.trim()).filter(Boolean),
    ...answers
      .filter((a) => a.text.trim())
      .map((a) => `${a.prompt}\n${a.text.trim().replace(/\n{2,}/g, "\n")}`),
  ];
}
