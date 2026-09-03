import { useEffect, useState } from "react";
import SourcesTable from "./components/SourcesTable";
import type { Source } from "./types/source";

function App() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSources = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch("http://localhost:8000/api/sources/");

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setSources(data);
    } catch (error) {
      console.error("Error fetching sources:", error);
      setError(
        error instanceof Error
          ? error.message
          : "Failed to connect to backend. Please ensure FastAPI is running on http://localhost:8000"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSources();
  }, []);

  const handleSourceUpdated = (updatedSource: Source) => {
    setSources((prevSources) =>
      prevSources.map((source) =>
        source.id === updatedSource.id ? updatedSource : source
      )
    );
  };

  const handleAssessAll = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/sources/assess-all", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`Batch assessment failed: ${response.status}`);
      }

      const result = await response.json();
      console.log("Batch assessment result:", result);

      // Refresh the entire source list
      await fetchSources();

      // Show summary
      alert(
        `ASSESSMENT COMPLETE\n\n` +
        `Assessed: ${result.assessed_count}\n` +
        `Skipped: ${result.skipped_count}\n` +
        `Failed: ${result.failed_count}`
      );
    } catch (error) {
      console.error("Batch assessment error:", error);
      alert(`Batch assessment failed: ${error instanceof Error ? error.message : "Unknown error"}`);
    }
  };

  return (
    <div className="App">
      <header className="app-header">
        <div>
          <div className="eyebrow">// PROBLEM DISCOVERY ENGINE</div>
          <h1>ProblemFinder</h1>
        </div>
        <p className="tagline">Real-world problems worth building for.</p>
      </header>

      <main className="app-main">
        {loading && (
          <div className="loading-state">
            <p>Loading sources&hellip;</p>
          </div>
        )}

        {error && (
          <div className="error-state">
            <h3>[ ERROR ]</h3>
            <p>{error}</p>
            <p className="error-help">
              Make sure the FastAPI server is running:
              <code>fastapi dev app/main.py</code>
            </p>
          </div>
        )}

        {!loading && !error && (
          <SourcesTable
            sources={sources}
            onSourceUpdated={handleSourceUpdated}
            onAssessAll={handleAssessAll}
          />
        )}
      </main>
    </div>
  );
}

export default App;
