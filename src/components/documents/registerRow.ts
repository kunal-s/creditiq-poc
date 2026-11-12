import { useFeature } from "@/domain/features";

/** The register's columns: one row per document (a file with none has one row of its own). On a
 * phone each row is a short card: the file, then a line for each cell with its column named. The
 * row's own text size is the file name's, so every cell's first line sits on the same line. */
export const REGISTER_ROW =
  "flex flex-col gap-1.5 px-4 py-2.5 text-[12.5px] leading-normal md:grid md:py-2 md:grid-cols-[minmax(0,2.3fr)_3.5rem_minmax(0,1.6fr)_5.5rem_minmax(0,1.8fr)_minmax(0,1.3fr)] md:gap-x-3";
/** The same row without the integrity check, for a deployment that has it switched off. */
export const REGISTER_ROW_LEAN =
  "flex flex-col gap-1.5 px-4 py-2.5 text-[12.5px] leading-normal md:grid md:py-2 md:grid-cols-[minmax(0,2.3fr)_3.5rem_minmax(0,1.9fr)_5.5rem_minmax(0,1.9fr)] md:gap-x-3";

/** The register's row, with the integrity check's column only when the deployment shows it
 * (config/app.yaml `features.integrity_checks`). */
export function useRegisterRow(): string {
  return useFeature("integrity_checks") ? REGISTER_ROW : REGISTER_ROW_LEAN;
}
