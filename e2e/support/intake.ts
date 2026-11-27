/// <reference types="node" />
// Helpers for the New appraisal specs (mock engine): a document to start with, and the case
// part of the one-request create as the screen sent it.
import type { Page } from "@playwright/test";
import type { CaseCreate } from "../../src/api/types";
import { MockApi, multipartBody } from "./api";

export const PDF = (name = "kyc.pdf") => ({
  name,
  mimeType: "application/pdf",
  buffer: Buffer.from("%PDF-1.7"),
});

/** The case part of the n-th POST /api/cases/intake, and the names of the files sent with it. */
export function sentCase(api: MockApi, n = 0): { body: CaseCreate; files: string[] } {
  const sent = api.called("POST", "/api/cases/intake")[n]!.body as ReturnType<typeof multipartBody>;
  return { body: JSON.parse(sent.fields["case"]!) as CaseCreate, files: sent.files };
}

/** A field of a row of a repeating section: `row(page, "applicants", 0, "name")`. */
export function cell(page: Page, section: string, n: number, field: string) {
  return page.getByTestId(`row-${section}`).nth(n).getByTestId(`cell-${field}`);
}
