import { describe, it, expect } from "vitest";
import { toMinor } from "./money";
describe("integer money parsing", () => {
  it.each([
    ["0,01", 1],
    ["12.50", 1250],
    ["200", 20000],
    ["10000000000", 1000000000000],
  ])("converts %s exactly", (input, result) =>
    expect(toMinor(input)).toBe(result),
  );
  it.each([
    "0",
    "-1",
    "1.001",
    "1e3",
    "NaN",
    "",
    "10000000000.01",
    "01.2",
    "1,2.3",
  ])("rejects %s", (input) => expect(() => toMinor(input)).toThrow());
});
