export type Confidence = "high" | "medium" | "low";

export type ResolvedField = {
  label: string;
  value: string;
  confidence: Confidence;
  source: string;
  note?: string;
};

export type Director = {
  slug: string;
  name: string;
  din: string;
  role: string;
  appointed: string;
  age: number;
  nationality: string;
  shareholding: string;
  otherDirectorships: { name: string; entitySlug?: string; role: string; status: string }[];
  disqualified: boolean;
  source: string;
};

export type EntityRecord = {
  slug: string;
  name: string;
  cin: string;
  pan: string;
  panMasked: string;
  gstin: string;
  lei?: string;
  leiValidTo?: string;
  leiNote?: string;
  incorporated: string;
  registeredOffice: string;
  status: string;
  sector: string;
  authorisedCapital: string;
  paidUpCapital: string;
  lastFilingAgm: string;
  directorSlugs: string[];
  exposure?: string;
  appraisalId?: string;
  relationship: "Borrower" | "Related party";
};

// No entities or directors are resolved yet in this deployment.
export const DIRECTORS: Director[] = [];
export const getDirector = (slug: string) => DIRECTORS.find((d) => d.slug === slug);

export const ENTITIES: EntityRecord[] = [];
export const getEntity = (slug: string) => ENTITIES.find((e) => e.slug === slug);

export const RESOLVED_FIELDS: ResolvedField[] = [];

export type RelatedLink = {
  entitySlug: string;
  name: string;
  pan: string;
  gstin: string;
  basis: string;
  confidence: Confidence;
  source: string;
  leiNote?: string;
  suggested: boolean;
};

export const SUGGESTED_LINKS: RelatedLink[] = [];

export type DuplicateCandidate = {
  name: string;
  cin: string;
  pan: string;
  gstin: string;
  incorporated: string;
  registeredOffice: string;
  status: string;
  distinguishers: string[];
};

export const NEAR_DUPLICATE: DuplicateCandidate | null = null;
