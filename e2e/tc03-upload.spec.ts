/// <reference types="node" />
// TC-03 (C1): a ZIP and several loose files are uploaded; every file ends in
// a visible state (registered, duplicate, ignored, rejected), the archive
// shows as a tree, and the duplicate is identified (FRD F-05, F-02.2).
import { expect, test } from "@playwright/test";
import { SAFFRON } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("TC-03: upload a ZIP, then files including a duplicate", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${SAFFRON}/upload`);
  await expect(page.getByText("No files have been received")).toBeVisible();

  await page.getByTestId("upload-input").setInputFiles({
    name: "case-file.zip",
    mimeType: "application/zip",
    buffer: Buffer.from("PK\u0003\u0004"),
  });

  // The archive as a tree, with its folders and members.
  const tree = page.getByTestId("file-tree");
  await expect(tree.getByTestId("tree-folder").first()).toContainText("case-file.zip");
  await expect(tree.getByTestId("tree-folder").nth(1)).toContainText("KYC");
  await expect(tree.getByTestId("tree-file")).toHaveCount(4);
  await expect(tree.locator('[data-testid="tree-file"][data-status="ignored"]')).toContainText(
    "Thumbs.db",
  );

  // Documents are read in the background; the list updates without a reload.
  await expect(page.getByTestId("polling")).toBeVisible();
  await expect(tree.getByTestId("tree-document").first()).toContainText("PAN (individual)", {
    timeout: 15_000,
  });
  await expect(tree.locator('[data-document-id="doc-gst"]')).toContainText("p1–2");
  await expect(tree.locator('[data-document-id="doc-bank"]')).toContainText("p3–9");

  // Several loose files: one is the same file again, one is unsupported.
  await page.getByTestId("upload-input").setInputFiles([
    { name: "bank stmt apr-mar.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF") },
    { name: "statement.numbers", mimeType: "application/octet-stream", buffer: Buffer.from("x") },
  ]);
  const duplicate = tree.locator('[data-testid="tree-file"][data-status="duplicate"]');
  await expect(duplicate).toContainText("bank stmt apr-mar.pdf");
  await expect(duplicate.getByTestId("duplicate-of")).toContainText(
    "Duplicate of case-file.zip/bank stmt apr-mar.pdf",
  );
  await expect(tree.locator('[data-testid="tree-file"][data-status="rejected"]')).toContainText(
    "Unsupported format",
  );

  // Every file is counted in a visible state.
  await expect(page.getByTestId("count-registered")).toHaveText("3");
  await expect(page.getByTestId("count-duplicate")).toHaveText("1");
  await expect(page.getByTestId("count-ignored")).toHaveText("1");
  await expect(page.getByTestId("count-rejected")).toHaveText("1");
  expect(api.called("POST", `/api/cases/${SAFFRON}/files`)).toHaveLength(2);
});
