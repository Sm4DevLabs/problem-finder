import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import type { Problem } from "../types/problem";
import { sourceLabel } from "../types/problem";
import "../styles/ProblemsList.css";

gsap.registerPlugin(useGSAP);

export default function ProblemsListPage() {
  const [problems, setProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState<string>("ALL");
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchProblems();
  }, []);

  const fetchProblems = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/source-items/?limit=1000");
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

  const sourceKeys = useMemo(() => {
    const keys = new Set<string>();
    problems.forEach((p) => {
      if (p.raw_data?.source) keys.add(p.raw_data.source);
    });
    return Array.from(keys);
  }, [problems]);

  const filtered = useMemo(() => {
    return problems.filter((p) => {
      if (sourceFilter !== "ALL" && p.raw_data?.source !== sourceFilter) return false;
      if (query.trim()) {
        const haystack = `${p.title} ${p.description ?? ""}`.toLowerCase();
        if (!haystack.includes(query.trim().toLowerCase())) return false;
      }
      return true;
    });
  }, [problems, sourceFilter, query]);

  useGSAP(
    () => {
      if (loading || !listRef.current) return;
      const rows = gsap.utils.toArray<HTMLElement>(".record-row");
      gsap.from(rows, {
        opacity: 0,
        y: 12,
        duration: 0.4,
        ease: "power2.out",
        stagger: 0.025,
      });
    },
    { scope: listRef, dependencies: [loading, sourceFilter, query] }
  );

  if (loading) {
    return (
      <div className="problems-container">
        <div className="loading">LOADING RECORDS&hellip;</div>
      </div>
    );
  }

  return (
    <div className="problems-container">
      <div className="problems-header">
        <div>
          <div className="eyebrow">// PROBLEM RECORDS</div>
          <h1>Discovered Problems</h1>
        </div>
        <button onClick={() => navigate("/")} className="brut-btn">
          &lt; Back to Sources
        </button>
      </div>

      <div className="problems-toolbar">
        <div className="source-tabs">
          <button
            className={`source-tab ${sourceFilter === "ALL" ? "active" : ""}`}
            onClick={() => setSourceFilter("ALL")}
          >
            ALL ({problems.length})
          </button>
          {sourceKeys.map((key) => {
            const count = problems.filter((p) => p.raw_data?.source === key).length;
            return (
              <button
                key={key}
                className={`source-tab ${sourceFilter === key ? "active" : ""}`}
                onClick={() => setSourceFilter(key)}
              >
                {sourceLabel({ source: key })} ({count})
              </button>
            );
          })}
        </div>

        <input
          type="text"
          className="record-search"
          placeholder="SEARCH RECORDS..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="record-count-strip">
        REC. 001&ndash;{String(filtered.length).padStart(3, "0")} / {problems.length} TOTAL
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">No records match. Go to Sources and click Fetch.</div>
      ) : (
        <div className="record-list" ref={listRef}>
          {filtered.map((problem, idx) => {
            const category = problem.raw_data?.category?.split(",")[0]?.trim();
            const score = problem.raw_data?.score;
            return (
              <div
                key={problem.id}
                className="record-row"
                onClick={() => navigate(`/problems/${problem.id}`)}
              >
                <div className="record-index">{String(idx + 1).padStart(3, "0")}</div>
                <div className="record-tags">
                  <span className="badge badge--fill">
                    {sourceLabel(problem.raw_data)}
                  </span>
                  {category && <span className="badge">{category}</span>}
                  {typeof score === "number" && (
                    <span className="badge badge--accent">SCORE {score}</span>
                  )}
                </div>
                <div className="record-body">
                  <h3 className="record-title">{problem.title}</h3>
                  {problem.description && (
                    <p className="record-description">
                      {problem.description.slice(0, 160)}
                      {problem.description.length > 160 ? "..." : ""}
                    </p>
                  )}
                </div>
                <div className="record-arrow">&gt;&gt;&gt;</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
