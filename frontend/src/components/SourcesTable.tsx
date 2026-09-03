import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Source } from "../types/source";
import {
  formatSourceType,
  formatCollectionMethod,
  formatAssessmentStatus,
} from "../types/source";

interface SourcesTableProps {
  sources: Source[];
  onSourceUpdated: (updatedSource: Source) => void;
  onAssessAll: () => void;
}

export default function SourcesTable({ sources, onSourceUpdated, onAssessAll }: SourcesTableProps) {
  const navigate = useNavigate();
  const [assessingId, setAssessingId] = useState<string | null>(null);
  const [assessingAll, setAssessingAll] = useState(false);
  const [fetchingId, setFetchingId] = useState<string | null>(null);

  const handleAssess = async (sourceId: string) => {
    try {
      setAssessingId(sourceId);
      const response = await fetch(`http://localhost:8000/api/sources/${sourceId}/assess`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`Assessment failed: ${response.status}`);
      }

      const updatedSource = await response.json();
      onSourceUpdated(updatedSource);
    } catch (error) {
      console.error("Assessment error:", error);
      alert(`Failed to assess source: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setAssessingId(null);
    }
  };

  const handleAssessAll = async () => {
    try {
      setAssessingAll(true);
      await onAssessAll();
    } finally {
      setAssessingAll(false);
    }
  };

  const handleFetch = async (sourceId: string, sourceName: string) => {
    try {
      setFetchingId(sourceId);
      const response = await fetch(`http://localhost:8000/api/source-items/${sourceId}/fetch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`Fetch failed: ${response.status}`);
      }

      const result = await response.json();
      alert(
        `FETCH COMPLETE -- ${sourceName}\n\n` +
        `Items fetched: ${result.items_fetched}\n` +
        `New: ${result.items_new}\n` +
        `Updated: ${result.items_updated}\n` +
        `Duration: ${result.duration_seconds}s`
      );

      // Navigate to problems page
      navigate("/problems");
    } catch (error) {
      console.error("Fetch error:", error);
      alert(`Failed to fetch from ${sourceName}: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setFetchingId(null);
    }
  };

  const pendingCount = sources.filter(s => s.assessment_status === "PENDING").length;

  return (
    <div className="sources-container">
      <div className="sources-header">
        <div>
          <h2>Sources</h2>
          <span className="source-count">{sources.length} total</span>
        </div>
        <div className="header-actions">
          <button
            onClick={() => navigate("/problems")}
            className="view-problems-button"
          >
            View Problems
          </button>
          <button
            onClick={handleAssessAll}
            disabled={assessingAll || pendingCount === 0}
            className="assess-all-button"
          >
            {assessingAll ? "Assessing All..." : `Assess All (${pendingCount})`}
          </button>
        </div>
      </div>

      <table className="sources-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Category</th>
            <th>Collection Method</th>
            <th>Assessment Status</th>
            <th>Website</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => (
            <tr key={source.id}>
              <td className="source-name">{source.name}</td>
              <td>{formatSourceType(source.source_type)}</td>
              <td>{formatCollectionMethod(source.collection_method)}</td>
              <td>
                <span className={`status-badge status-${source.assessment_status?.toLowerCase()}`}>
                  {formatAssessmentStatus(source.assessment_status)}
                </span>
              </td>
              <td>
                {source.homepage_url ? (
                  <a
                    href={source.homepage_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="source-link"
                  >
                    Visit source
                  </a>
                ) : (
                  <span className="no-link">No URL</span>
                )}
              </td>
              <td>
                <div className="action-buttons">
                  <button
                    onClick={() => handleAssess(source.id)}
                    disabled={assessingId === source.id}
                    className="assess-button"
                    title={source.assessment_status === "ASSESSED" ? "Re-assess this source" : "Assess this source"}
                  >
                    {assessingId === source.id ? "..." : "Assess"}
                  </button>
                  {source.collection_method && (
                    <button
                      onClick={() => handleFetch(source.id, source.name)}
                      disabled={fetchingId === source.id}
                      className="fetch-button"
                      title="Fetch problems from this source"
                    >
                      {fetchingId === source.id ? "..." : "Fetch"}
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
