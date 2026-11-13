import type { Meta } from "@/api/types";
import { useMeta } from "./cases";

// Features a deployment switches on or off (config/app.yaml `features:`), as the engine reports them
// in /api/meta. Off, the screens show nothing of the feature. Until the engine has answered a
// feature is treated as off, so it never shows and then disappears; an engine that predates a
// switch reports it on.

export type Feature = keyof NonNullable<Meta["features"]>;

export function useFeature(name: Feature): boolean {
  return useFeatureState(name) ?? false;
}

/** The same, with `undefined` until the engine has answered (for a page that leads elsewhere when
 * the feature is off, and must not do so before it knows). */
export function useFeatureState(name: Feature): boolean | undefined {
  const meta = useMeta();
  if (!meta.data) return undefined;
  return meta.data.features?.[name] ?? true;
}
