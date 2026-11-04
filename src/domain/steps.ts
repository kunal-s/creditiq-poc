import { t } from "@/config/terminology";

/** "Appraisal BBG-… · Files": the kicker of a case step's header. */
export function stepKicker(caseId: string, tab: string): string {
  return t("caseStep.kicker", { id: caseId, step: t(`caseTab.${tab}`) });
}
