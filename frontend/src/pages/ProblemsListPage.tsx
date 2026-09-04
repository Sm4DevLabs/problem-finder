import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Facets, Problem } from "../types/problem";
import { sourceLabel } from "../types/problem";
import "../styles/ProblemsList.css";

const API = "http://localhost:8000/api/source-items/";
const PAGE_SIZE = 20;
const EMPTY_FACETS: Facets = { total: 0, tags: [], sources: [] };

function buildQuery(params: Record<string, string>): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v && v !== "ALL") q.set(k, v);
  });
  return q.toString();
}

export default function ProblemsListPage() {
  const [problems, setProblems] = useState<Problem[]>([]);
  const [facets, setFacets] = useState<Facets>(EMPTY_FACETS);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  // Active filters (server-side)
  const [sourceId, setSourceId] = useState<string>("ALL");
  const [tag, setTag] = useState<string>("ALL");
  const [query, setQuery] = useState<string>("");
  const [debouncedQuery, setDebouncedQuery] = useState<string>("");

  const navigate = useNavigate();
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const offsetRef = useRef(0);
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);

  // Debounce the search box so we don't hit the API on every keystroke.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 350);
    return () => clearTimeout(t);
  }, [query]);

  const filterParams = useCallback(
    () => ({ source_id: sourceId, tag, search: debouncedQuery }),
    [sourceId, tag, debouncedQuery]
  );

  const fetchPage = useCallback(
    async (offset: number): Promise<Problem[]> => {
      const qs = buildQuery({ ...filterParams(), limit: String(PAGE_SIZE), offset: String(offset) });
      const res = await fetch(`${API}?${qs}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    [filterParams]
  );

  const fetchFacets = useCallback(async (): Promise<Facets> => {
    const qs = buildQuery(filterParams());
    const res = await fetch(`${API}facets${qs ? `?${qs}` : ""}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }, [filterParams]);

  // Reload from scratch whenever a filter changes.
  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset UI state on filter change
    setLoading(true);
    loadingRef.current = true;
    offsetRef.current = 0;
    hasMoreRef.current = true;
    setHasMore(true);

    (async () => {
      try {
        const [firstPage, facetData] = await Promise.all([fetchPage(0), fetchFacets()]);
        if (cancelled) return;
        setProblems(firstPage);
        setFacets(facetData);
        offsetRef.current = firstPage.length;
        if (firstPage.length < PAGE_SIZE) {
          hasMoreRef.current = false;
          setHasMore(false);
        }
      } catch (e) {
        if (!cancelled) {
          console.error("Error loading problems:", e);
          setProblems([]);
          setFacets(EMPTY_FACETS);
          hasMoreRef.current = false;
          setHasMore(false);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          loadingRef.current = false;
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [fetchPage, fetchFacets]);

  const loadMore = useCallback(async () => {
    if (loadingRef.current || !hasMoreRef.current) return;
    loadingRef.current = true;
    setLoadingMore(true);
    try {
      const page = await fetchPage(offsetRef.current);
      setProblems((prev) => {
        const seen = new Set(prev.map((p) => p.id));
        return [...prev, ...page.filter((p) => !seen.has(p.id))];
      });
      offsetRef.current += page.length;
      if (page.length < PAGE_SIZE) {
        hasMoreRef.current = false;
        setHasMore(false);
      }
    } catch (e) {
      console.error("Error loading more:", e);
      hasMoreRef.current = false;
      setHasMore(false);
    } finally {
      setLoadingMore(false);
      loadingRef.current = false;
    }
  }, [fetchPage]);

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

  const hasActiveFilter = sourceId !== "ALL" || tag !== "ALL" || debouncedQuery !== "";
  const clearFilters = () => {
    setSourceId("ALL");
    setTag("ALL");
    setQuery("");
  };

  return (
    <div className="problems-container">
      <div className="problems-header">
        <div>
          <div className="eyebrow">// PROBLEMS WORTH BUILDING FOR</div>
          <h1>ProblemFinder</h1>
        </div>
        <p className="feed-tagline">Find a real problem. Build it. Ship it.</p>
      </div>

      {/* Compact, scalable filter toolbar: two dropdowns + search */}
      <div className="filter-toolbar">
        <label className="filter-field">
          <span className="filter-label">SOURCE</span>
          <select className="filter-select" value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
            <option value="ALL">All sources</option>
            {facets.sources.map((s) => (
              <option key={s.source_id} value={s.source_id}>
                {s.name} ({s.count})
              </option>
            ))}
          </select>
        </label>

        <label className="filter-field">
          <span className="filter-label">SOLVABLE BY</span>
          <select className="filter-select" value={tag} onChange={(e) => setTag(e.target.value)}>
            <option value="ALL">All solutions</option>
            {facets.tags.map((t) => (
              <option key={t.tag} value={t.tag}>
                {t.tag} ({t.count})
              </option>
            ))}
          </select>
        </label>

        <input
          type="text"
          className="record-search"
          placeholder="SEARCH PROBLEMS..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        {hasActiveFilter && (
          <button className="clear-filters" onClick={clearFilters}>
            CLEAR ✕
          </button>
        )}
      </div>

      <div className="record-count-strip">
        {loading
          ? "LOADING PROBLEMS..."
          : `SHOWING ${facets.total} PROBLEM${facets.total === 1 ? "" : "S"}${
              hasActiveFilter ? " (FILTERED)" : ""
            }`}
      </div>

      {!loading && problems.length === 0 ? (
        <div className="empty-state">No problems match your filters.</div>
      ) : (
        <div className="record-list">
          {problems.map((problem, idx) => (
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
                    {problem.solution_tags.map((t) => (
                      <span
                        key={t}
                        className={`badge badge--solution ${
                          t === "Not Software-Solvable" ? "badge--warn" : ""
                        }`}
                      >
                        {t}
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

      <div ref={sentinelRef} className="scroll-sentinel" aria-hidden="true" />
      {!loading && loadingMore && <div className="feed-status">LOADING MORE...</div>}
      {!loading && !hasMore && problems.length > 0 && (
        <div className="feed-status feed-status--end">END OF RECORDS</div>
      )}
    </div>
  );
}
