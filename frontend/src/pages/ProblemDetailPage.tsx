import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import type { Problem, TechStackOption } from "../types/problem";
import "../styles/ProblemDetail.css";

export default function ProblemDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [problem, setProblem] = useState<Problem | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      fetchProblem(id);
    }
  }, [id]);

  const fetchProblem = async (problemId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/source-items/item/${problemId}`);
      if (!response.ok) throw new Error("Failed to fetch problem");
      const data = await response.json();
      setProblem(data);
    } catch (error) {
      console.error("Error fetching problem:", error);
      alert("Failed to load problem details");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="detail-container">
        <div className="loading">⏳ Loading problem details...</div>
      </div>
    );
  }

  if (!problem) {
    return (
      <div className="detail-container">
        <div className="error">Problem not found</div>
      </div>
    );
  }

  return (
    <div className="detail-container">
      <div className="detail-header">
        <button onClick={() => navigate("/problems")} className="back-button">
          ← Back to Problems
        </button>
        {problem.url && (
          <a href={problem.url} target="_blank" rel="noopener noreferrer" className="source-link">
            View Source ↗
          </a>
        )}
      </div>

      <div className="detail-content">
        {/* Problem Overview */}
        <section className="section overview-section">
          <h1 className="problem-title">{problem.title}</h1>
          <p className="problem-description">{problem.description}</p>
        </section>

        {/* Problem Analysis */}
        <section className="section analysis-section">
          <h2>📊 Problem Analysis</h2>
          <div className="analysis-grid">
            {problem.problem_frequency && (
              <div className="analysis-card">
                <h3>⏰ Frequency</h3>
                <p>{problem.problem_frequency}</p>
              </div>
            )}

            {problem.existing_solutions && (
              <div className="analysis-card">
                <h3>🔍 Existing Solutions</h3>
                <p>{problem.existing_solutions}</p>
              </div>
            )}

            {problem.pricing_estimate && (
              <div className="analysis-card pricing-card">
                <h3>💰 Pricing Estimate</h3>
                <p>{problem.pricing_estimate}</p>
              </div>
            )}
          </div>
        </section>

        {/* Tech Stack Options */}
        {problem.tech_stack_options && problem.tech_stack_options.length > 0 && (
          <section className="section tech-section">
            <h2>🛠️ Tech Stack Options</h2>
            <div className="tech-options-grid">
              {problem.tech_stack_options.map((stack: TechStackOption, index: number) => {
                const isRecommended =
                  problem.recommended_tech_stack &&
                  stack.name === problem.recommended_tech_stack.name;
                return (
                  <div
                    key={index}
                    className={`tech-stack-card ${isRecommended ? "recommended" : ""}`}
                  >
                    {isRecommended && <div className="recommended-badge">⭐ Recommended</div>}
                    <h3>{stack.name}</h3>
                    <div className="technologies">
                      {stack.technologies.map((tech, idx) => (
                        <span key={idx} className="tech-badge">
                          {tech}
                        </span>
                      ))}
                    </div>
                    <div className="pros-cons">
                      <div className="pros">
                        <strong>✅ Pros:</strong>
                        <p>{stack.pros}</p>
                      </div>
                      <div className="cons">
                        <strong>❌ Cons:</strong>
                        <p>{stack.cons}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Tech Stack Justification */}
        {problem.tech_stack_justification && (
          <section className="section justification-section">
            <h2>💡 Why This Stack?</h2>
            <p className="justification-text">{problem.tech_stack_justification}</p>
          </section>
        )}
      </div>
    </div>
  );
}
