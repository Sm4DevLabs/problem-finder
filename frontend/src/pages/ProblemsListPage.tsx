import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Problem } from "../types/problem";
import "../styles/ProblemsList.css";

export default function ProblemsListPage() {
  const [problems, setProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchProblems();
  }, []);

  const fetchProblems = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/source-items/");
      if (!response.ok) throw new Error("Failed to fetch problems");
      const data = await response.json();
      setProblems(data);
    } catch (error) {
      console.error("Error fetching problems:", error);
      alert("Failed to load problems");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="problems-container">
        <div className="loading">⏳ Loading problems...</div>
      </div>
    );
  }

  return (
    <div className="problems-container">
      <div className="problems-header">
        <div>
          <h1>🎯 Discovered Problems</h1>
          <p className="subtitle">
            {problems.length} software-solvable problems with AI-powered insights
          </p>
        </div>
        <button onClick={() => navigate("/")} className="back-button">
          ← Back to Sources
        </button>
      </div>

      {problems.length === 0 ? (
        <div className="empty-state">
          <p>No problems collected yet. Go to Sources and click "Fetch"!</p>
        </div>
      ) : (
        <div className="problems-grid">
          {problems.map((problem) => (
            <div
              key={problem.id}
              className="problem-card"
              onClick={() => navigate(`/problems/${problem.id}`)}
            >
              <h3 className="problem-title">{problem.title}</h3>
              <p className="problem-description">
                {problem.description?.substring(0, 150)}...
              </p>

              <div className="problem-meta">
                {problem.pricing_estimate && (
                  <div className="meta-item">
                    <span className="meta-label">💰 Pricing:</span>
                    <span className="meta-value">
                      {problem.pricing_estimate.substring(0, 50)}...
                    </span>
                  </div>
                )}

                {problem.problem_frequency && (
                  <div className="meta-item">
                    <span className="meta-label">📊 Frequency:</span>
                    <span className="meta-value">
                      {problem.problem_frequency.substring(0, 40)}...
                    </span>
                  </div>
                )}

                {problem.recommended_tech_stack && (
                  <div className="meta-item tech-stack-preview">
                    <span className="meta-label">🛠️ Recommended:</span>
                    <div className="tech-badges">
                      {problem.recommended_tech_stack.technologies.map((tech, idx) => (
                        <span key={idx} className="tech-badge">
                          {tech}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="problem-footer">
                <span className="view-details">View Details →</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
