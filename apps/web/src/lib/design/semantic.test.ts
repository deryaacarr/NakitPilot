import { describe, expect, it } from "vitest";

import { FINANCIAL_COLOR_MEANING, toneFromRisk } from "./semantic";

describe("financial color semantics", () => {
  it("keeps one meaning per tone key", () => {
    const meanings = Object.values(FINANCIAL_COLOR_MEANING).map((m) => m.label);
    expect(new Set(meanings).size).toBe(meanings.length);
  });

  it("maps risk statuses consistently", () => {
    expect(toneFromRisk("LOW")).toBe("success");
    expect(toneFromRisk("MEDIUM")).toBe("warning");
    expect(toneFromRisk("CRITICAL")).toBe("danger");
    expect(toneFromRisk("OVERDUE")).toBe("danger");
    expect(toneFromRisk("AI")).toBe("analysis");
    expect(toneFromRisk("COMPLETED")).toBe("neutral");
  });
});
