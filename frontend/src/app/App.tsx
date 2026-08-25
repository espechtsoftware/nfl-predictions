import { useEffect, useState } from "react";
import { fetchProjectionAvailability } from "../api/client";
import { Availability } from "../api/types";
import { CorpusResearchPage } from "../pages/CorpusResearch";
import { ErrorBoundary } from "./ErrorBoundary";
import { DEFAULT_VIEW } from "./routes";

export function App({
  loadAvailability = fetchProjectionAvailability,
}: {
  loadAvailability?: () => Promise<Availability>;
}) {
  const [availability, setAvailability] = useState<Availability>({
    state: "loading",
  });
  useEffect(() => {
    let cancelled = false;
    loadAvailability().then((result) => {
      if (!cancelled) setAvailability(result);
    });
    return () => {
      cancelled = true;
    };
  }, [loadAvailability]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-title">Corpus Research Observatory</span>
        <nav aria-label="observatory">
          <span className="nav-current">{DEFAULT_VIEW}</span>
        </nav>
      </header>
      <ErrorBoundary>
        <CorpusResearchPage availability={availability} />
      </ErrorBoundary>
    </div>
  );
}
