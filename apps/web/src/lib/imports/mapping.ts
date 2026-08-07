/** NP-172 — import mapping helpers */
export type CanonicalField = {
  key: string;
  label: string;
  required?: boolean;
};

export function isMappingComplete(
  fields: CanonicalField[],
  mapping: Record<string, string | null | undefined>,
): boolean {
  return fields
    .filter((f) => f.required)
    .every((f) => Boolean(mapping[f.key] && String(mapping[f.key]).trim()));
}

export function unmappedRequiredFields(
  fields: CanonicalField[],
  mapping: Record<string, string | null | undefined>,
): string[] {
  return fields
    .filter((f) => f.required && !(mapping[f.key] && String(mapping[f.key]).trim()))
    .map((f) => f.key);
}
