import { describe, expect, it } from "vitest";

import { isMappingComplete, unmappedRequiredFields, type CanonicalField } from "./mapping";

const fields: CanonicalField[] = [
  { key: "müşteri_adı", label: "Müşteri adı", required: true },
  { key: "fatura_numarası", label: "Fatura no", required: true },
  { key: "telefon", label: "Telefon", required: false },
];

describe("import mapping helpers", () => {
  it("reports incomplete when required fields missing", () => {
    expect(isMappingComplete(fields, { müşteri_adı: "A" })).toBe(false);
    expect(unmappedRequiredFields(fields, { müşteri_adı: "A" })).toEqual(["fatura_numarası"]);
  });

  it("is complete when all required mapped", () => {
    const mapping = { müşteri_adı: "ColA", fatura_numarası: "ColB", telefon: null };
    expect(isMappingComplete(fields, mapping)).toBe(true);
    expect(unmappedRequiredFields(fields, mapping)).toEqual([]);
  });

  it("treats blank strings as unmapped", () => {
    expect(isMappingComplete(fields, { müşteri_adı: "  ", fatura_numarası: "x" })).toBe(false);
  });
});
