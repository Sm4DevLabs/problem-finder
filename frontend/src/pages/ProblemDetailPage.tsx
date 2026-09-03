import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import type { Problem, TechStackOption } from "../types/problem";
import { sourceLabel } from "../types/problem";
import "../styles/ProblemDetail.css";

gsap.registerPlugin(useGSAP);

export default function ProblemDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [problem, setProblem] = useState<Problem | null>(null);
  const [loading, setLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

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

  useGSAP(
    () => {
      if (loading || !problem) return;
      gsap.from(".section", {
        opacity: 0,
        y: 16,
        duration: 0.45,
        ease: "power2.out",
        stagger: 0.08,
      });
    },
    { scope: containerRef, dependencies: [loading, problem] }
  );

  if (loading) {
    return (
      <div className="detail-container">
        <div className="loading">LOADING RECORD&hellip;</div>
      </div>
    );
  }

  if (!problem) {
    return (
      <div className="detail-container">
        <div className="error">[ RECORD NOT FOUND ]</div>
      </div>
    );
  }

  const category = problem.raw_data?.category;
  const score = problem.raw_data?.score;

  return (
    <div className="detail-container" ref={containerRef}>
      <div className="detail-header">
        <button onClick={() => navigate("/problems")} className="brut-btn">
          &lt; Back to Problems
        </button>
        {problem.url && (
          <a href={problem.url} target="_blank" rel="noopener noreferrer" className="brut-btn brut-btn--accent">
            View Source
          </a>
        )}
      </div>

      <div className="record-meta-strip">
        <span className="badge badge--fill">{sourceLabel(problem.raw_data)}</span>
        {category && <span className="badge">{category}</span>}
        {typeof score === "number" && <span className="badge badge--accent">SCORE {score}</span>}
        {problem.raw_data?.host && <span className="mono-tag">HOST / {problem.raw_data.host}</span>}
      </div>

      <div className="detail-content">
        <section className="section overview-section">
          <h1 className="problem-title">{problem.title}</h1>
          {problem.description && <p className="problem-description">{problem.description}</p>}
        </section>

        {(problem.problem_frequency || problem.existing_solutions || problem.pricing_estimate) && (
          <section className="section analysis-section">
            <h2>[ Problem Analysis ]</h2>
            <div className="analysis-grid">
              {problem.problem_frequency && (
                <div className="analysis-card">
                  <h3>Frequency</h3>
                  <p>{problem.problem_frequency}</p>
                </div>
              )}

              {problem.existing_solutions && (
                <div className="analysis-card">
                  <h3>Existing Solutions</h3>
                  <p>{problem.existing_solutions}</p>
                </div>
              )}

              {problem.pricing_estimate && (
                <div className="analysis-card analysis-card--accent">
                  <h3>Pricing Estimate</h3>
                  <p>{problem.pricing_estimate}</p>
                </div>
              )}
            </div>
          </section>
        )}

        {problem.tech_stack_options && problem.tech_stack_options.length > 0 && (
          <section className="section tech-section">
            <h2>[ Tech Stack Options ]</h2>
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
                    {isRecommended && <div className="recommended-badge">RECOMMENDED</div>}
                    <h3>{stack.name}</h3>
                    <div className="technologies">
                      {stack.technologies.map((tech, idx) => (
                        <span key={idx} className="badge">
                          {tech}
                        </span>
                      ))}
                    </div>
                    <div className="pros-cons">
                      <div className="pros">
                        <strong>Pros</strong>
                        <p>{stack.pros}</p>
                      </div>
                      <div className="cons">
                        <strong>Cons</strong>
                        <p>{stack.cons}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {problem.tech_stack_justification && (
          <section className="section justification-section">
            <h2>[ Why This Stack ]</h2>
            <p className="justification-text">{problem.tech_stack_justification}</p>
          </section>
        )}

        {problem.raw_data?.scraped_at && (
          <div className="record-footer-strip">
            REC. ID / {problem.external_id} &nbsp;&nbsp; SCRAPED / {new Date(problem.raw_data.scraped_at).toISOString()}
          </div>
        )}
      </div>
    </div>
  );
}
