import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRecipeSearch } from "../ui/useRecipeSearch";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useRecipeSearch", () => {
  it("stays undefined until 1.5s after typing stops", () => {
    const { result } = renderHook(() => useRecipeSearch());

    act(() => result.current.setText("cake"));
    expect(result.current.search).toBeUndefined();

    act(() => vi.advanceTimersByTime(1499));
    expect(result.current.search).toBeUndefined();

    act(() => vi.advanceTimersByTime(1));
    expect(result.current.search).toBe("cake");
  });

  it("never activates a search under 3 characters, even after the debounce settles", () => {
    const { result } = renderHook(() => useRecipeSearch());

    act(() => result.current.setText("ca"));
    act(() => vi.advanceTimersByTime(1500));

    expect(result.current.search).toBeUndefined();
  });

  it("resets the debounce timer on every keystroke", () => {
    const { result } = renderHook(() => useRecipeSearch());

    act(() => result.current.setText("cak"));
    act(() => vi.advanceTimersByTime(1000));
    act(() => result.current.setText("cake"));
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.search).toBeUndefined();

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.search).toBe("cake");
  });
});
