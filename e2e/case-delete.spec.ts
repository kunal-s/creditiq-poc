// F-01.5: delete an application to restart a test run. The person types the
// case ID and gives a reason; the case disappears from the workbench.
import { expect, test } from "@playwright/test";
import { SAFFRON } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("delete an application after confirming its ID and a reason", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);

  await page.goto(`/docready/${SAFFRON}/checklist`);
  await page.getByTestId("delete-case").click();

  const confirm = page.getByTestId("delete-case-confirm");
  await expect(confirm).toBeDisabled();
  await page.getByLabel("Reason").fill("restarting the test run");
  await expect(confirm).toBeDisabled(); // the ID is not typed yet
  await page.getByLabel(`Type ${SAFFRON} to confirm`).fill(SAFFRON);
  await confirm.click();

  await expect(page).toHaveURL(/\/$/);
  const call = api.called("DELETE", `/api/cases/${SAFFRON}`);
  expect(call).toHaveLength(1);
  expect(call[0]!.body).toEqual({ reason: "restarting the test run" });
  await expect(page.getByText(SAFFRON)).toHaveCount(0);
});
