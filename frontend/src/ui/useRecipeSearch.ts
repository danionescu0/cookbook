import { useState } from "react";
import { useDebouncedValue } from "./useDebouncedValue";

const SEARCH_DEBOUNCE_MS = 1500;
const MIN_SEARCH_LENGTH = 3;

interface UseRecipeSearchResult {
  // Drives the controlled <input> — updates on every keystroke.
  text: string;
  setText: (value: string) => void;
  // The debounced, threshold-gated value actually used for filtering/fetching. Undefined below
  // MIN_SEARCH_LENGTH characters — same as no filter — so a short in-progress query doesn't
  // narrow the list before the user's finished typing a real word.
  search: string | undefined;
}

export function useRecipeSearch(delayMs = SEARCH_DEBOUNCE_MS): UseRecipeSearchResult {
  const [text, setText] = useState("");
  const debounced = useDebouncedValue(text, delayMs).trim();
  const search = debounced.length >= MIN_SEARCH_LENGTH ? debounced : undefined;
  return { text, setText, search };
}
