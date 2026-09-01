import type { Source } from "../types/source";
import {
  formatSourceType,
  formatCollectionMethod,
  formatAssessmentStatus,
} from "../types/source";

interface SourcesTableProps {
  sources: Source[];
}

export default function SourcesTable({ sources }: SourcesTableProps) {
  return (
    <div className="sources-container">
      <div className="sources-header">
        <h2>Sources</h2>
        <span className="source-count">{sources.length} total</span>
      </div>

      <table className="sources-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Category</th>
            <th>Collection Method</th>
            <th>Assessment Status</th>
            <th>Website</th>
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
                    Visit source ↗
                  </a>
                ) : (
                  <span className="no-link">No URL</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
