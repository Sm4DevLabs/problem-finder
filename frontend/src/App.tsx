import { useEffect, useState } from "react";
import SourcesTable from "./components/SourcesTable";
import type { Source } from "./types/source";

function App() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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

    fetchSources();
  }, []);

  return (
    <div className="App">
      <header className="app-header">
        <h1>ProblemFinder</h1>
        <p className="tagline">Discover real-world problems worth building for.</p>
      </header>

      <main className="app-main">
        {loading && (
          <div className="loading-state">
            <p>Loading sources...</p>
          </div>
        )}

        {error && (
          <div className="error-state">
            <h3>❌ Error</h3>
            <p>{error}</p>
            <p className="error-help">
              Make sure the FastAPI server is running:
              <code>fastapi dev app/main.py</code>
            </p>
          </div>
        )}

        {!loading && !error && <SourcesTable sources={sources} />}
      </main>
    </div>
  );
}

export default App;
