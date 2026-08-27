import { useCallback, useEffect, useRef } from "react";

/** One request at a time: a new one cancels the previous, unmounting cancels whatever is left. */
export const useAbortableRequest = () => {
  const inFlight = useRef<AbortController | null>(null);

  const abort = useCallback(() => {
    inFlight.current?.abort();
    inFlight.current = null;
  }, []);

  const nextSignal = useCallback(() => {
    inFlight.current?.abort();
    inFlight.current = new AbortController();
    return inFlight.current.signal;
  }, []);

  useEffect(() => abort, [abort]);

  return { nextSignal, abort };
};
