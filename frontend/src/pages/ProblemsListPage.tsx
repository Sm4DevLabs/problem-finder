import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Problem } from "../types/problem";
import { sourceLabel } from "../types/problem";
import "../styles/ProblemsList.css";

const API = "http://localhost:8000/api/source-items/";
const PAGE_SIZE = 15;

export default function ProblemsListPage() {
  const [problems, setProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [tagFilter, setTagFilter] = useState<string>("ALL");
  const [query, setQuery] = useState("");

  const navigate = useNavigate();
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const offsetRef = useRef(0);
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);

  const loadMore = useCallback(async () => {
    if (loadingRef.current || !hasMoreRef.current) return;
    loadingRef.current = true;
    setLoadingMore(true);
    try {
      const res = await fetch(`${API}?limit=${PAGE_SIZE}&offset=${offsetRef.current}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const page: Problem[] = await res.json();
      setProblems((prev) => {
        const seen = new Set(prev.map((p) => p.id));
        return [...prev, ...page.filter((p) => !seen.has(p.id))];
      });
      offsetRef.current += page.length;
      if (page.length < PAGE_SIZE) {
        hasMoreRef.current = false;
        setHasMore(false);
      }
    } catch (error) {
      console.error("Error loading problems:", error);
      hasMoreRef.current = false;
      setHasMore(false);
    } finally {
      loadingRef.current = false;
      setLoadingMore(false);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMore();
  }, [loadMore]);

  // Prefetch the next page shortly before the sentinel scrolls into view.
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore();
      },
      { rootMargin: "800px 0px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [loadMore]);

  const tagKeys = useMemo(() => {
    const counts = new Map<string, number>();
    problems.forEach((p) => {
      (p.solution_tags ?? []).forEach((tag) => counts.set(tag, (counts.get(tag) ?? 0) + 1));
    });
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [problems]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return problems.filter((p) => {
      if (tagFilter !== "ALL" && !(p.solution_tags ?? []).includes(tagFilter)) return false;
      if (q) {
        const haystack = `${p.title} ${p.description ?? ""}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [problems, tagFilter, query]);

  return (
    <div className="problems-container">
      <div className="problems-header">
        <div>
          <div className="eyebrow">// PROBLEMS WORTH BUILDING FOR</div>
          <h1>ProblemFinder</h1>
        </div>
        <p className="feed-tagline">Find a real problem. Build it. Ship it.</p>
      </div>

      <div className="problems-toolbar">
        <input
          type="text"
          className="record-search"
          placeholder="SEARCH PROBLEMS..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {tagKeys.length > 0 && (
        <div className="tag-filter-bar">
          <span className="tag-filter-label">SOLVABLE BY /</span>
          <button
            className={`tag-chip ${tagFilter === "ALL" ? "active" : ""}`}
            onClick={() => setTagFilter("ALL")}
          >
            ALL
          </button>
          {tagKeys.map(([tag, count]) => (
            <button
              key={tag}
              className={`tag-chip ${tagFilter === tag ? "active" : ""} ${
                tag === "Not Software-Solvable" ? "tag-chip--warn" : ""
              }`}
              onClick={() => setTagFilter(tag)}
            >
              {tag} ({count})
            </button>
          ))}
        </div>
      )}

      <div className="record-count-strip">
        {loading
          ? "LOADING PROBLEMS..."
          : `SHOWING ${String(filtered.length).padStart(3, "0")} PROBLEM${filtered.length === 1 ? "" : "S"}`}
      </div>

      {!loading && filtered.length === 0 ? (
        <div className="empty-state">No problems match your filters.</div>
      ) : (
        <div className="record-list">
          {filtered.map((problem, idx) => (
            <div
              key={problem.id}
              className="record-row"
              onClick={() => navigate(`/problems/${problem.id}`)}
            >
              <div className="record-index">{String(idx + 1).padStart(3, "0")}</div>
              <div className="record-tags">
                <span className="badge badge--fill">{sourceLabel(problem.raw_data)}</span>
                {typeof problem.raw_data?.score === "number" && (
                  <span className="badge badge--accent">SCORE {problem.raw_data.score}</span>
                )}
              </div>
              <div className="record-body">
                <h3 className="record-title">{problem.title}</h3>
                {problem.description && (
                  <p className="record-description">
                    {problem.description.slice(0, 180)}
                    {problem.description.length > 180 ? "..." : ""}
                  </p>
                )}
                {problem.solution_tags && problem.solution_tags.length > 0 && (
                  <div className="record-solution-tags">
                    {problem.solution_tags.map((tag) => (
                      <span
                        key={tag}
                        className={`badge badge--solution ${
                          tag === "Not Software-Solvable" ? "badge--warn" : ""
                        }`}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="record-arrow">&gt;&gt;&gt;</div>
            </div>
          ))}
        </div>
      )}

      {/* Infinite-scroll sentinel + status */}
      <div ref={sentinelRef} className="scroll-sentinel" aria-hidden="true" />
      {!loading && loadingMore && <div className="feed-status">LOADING MORE...</div>}
      {!loading && !hasMore && problems.length > 0 && (
        <div className="feed-status feed-status--end">END OF RECORDS</div>
      )}
    </div>
  );
}
