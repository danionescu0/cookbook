import { beforeEach, describe, expect, it } from "vitest";
import { clearPendingShareToken, getPendingShareToken, setPendingShareToken } from "../sharing/pendingShare";

beforeEach(() => {
  clearPendingShareToken();
});

describe("pendingShare", () => {
  it("returns null when nothing is stored", () => {
    expect(getPendingShareToken()).toBeNull();
  });

  it("round-trips a stored token", () => {
    setPendingShareToken("abc123");

    expect(getPendingShareToken()).toBe("abc123");
  });

  it("clears the stored token", () => {
    setPendingShareToken("abc123");

    clearPendingShareToken();

    expect(getPendingShareToken()).toBeNull();
  });

  it("a later set overwrites an earlier one", () => {
    setPendingShareToken("first");
    setPendingShareToken("second");

    expect(getPendingShareToken()).toBe("second");
  });
});
