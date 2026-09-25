import { useQuery } from "@tanstack/react-query";

export const DOC_BASE = "/docready-documents";

export type ManifestEvidence = { page: number; snippet: string };

export type ManifestDocument = {
  filename: string | null;
  title: string;
  requirement: string;
  verdict: "satisfied" | "insufficient" | "missing";
  defect_type: "stale" | "incomplete" | "inconsistent" | null;
  reason: string;
  page_count: number;
  evidence: ManifestEvidence[];
  contradicts?: string[];
  related_documents?: string[];
};

export type DocManifest = {
  set_name: string;
  reference_date: string;
  disclaimer: string;
  document_count: number;
  total_pages: number;
  documents: ManifestDocument[];
  missing_requirements: ManifestDocument[];
};

async function fetchManifest(): Promise<DocManifest> {
  const res = await fetch(`${DOC_BASE}/manifest.json`);
  if (!res.ok) throw new Error("Document manifest unavailable");
  return (await res.json()) as DocManifest;
}

export function useDocManifest() {
  return useQuery({
    queryKey: ["docready-manifest"],
    queryFn: fetchManifest,
    staleTime: Infinity,
  });
}

export function findDoc(manifest: DocManifest | undefined, filename: string | undefined | null) {
  if (!manifest || !filename) return undefined;
  return manifest.documents.find((d) => d.filename === filename);
}

/** The page the viewer should open on: the first recorded defect page, else page one. */
export function openingPage(doc: ManifestDocument | undefined) {
  if (!doc) return 1;
  return doc.evidence[0]?.page ?? 1;
}

/** Every snippet recorded on a given page of a document. */
export function snippetsForPage(doc: ManifestDocument | undefined, page: number) {
  if (!doc) return [] as string[];
  return doc.evidence.filter((e) => e.page === page).map((e) => e.snippet);
}

export const VERDICT_LABEL: Record<ManifestDocument["verdict"], string> = {
  satisfied: "Satisfied",
  insufficient: "Insufficient",
  missing: "Missing",
};

export const DEFECT_LABEL: Record<NonNullable<ManifestDocument["defect_type"]>, string> = {
  stale: "Stale",
  incomplete: "Incomplete",
  inconsistent: "Inconsistent",
};
