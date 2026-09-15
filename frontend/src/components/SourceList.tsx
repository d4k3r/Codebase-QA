import type { RetrievedSource } from "../types";

interface SourceListProps {
  sources: RetrievedSource[];
}

export function SourceList({ sources }: SourceListProps) {
  return (
    <section className="sources-panel" aria-labelledby="sources-heading">
      <div className="section-heading">
        <p className="eyebrow">Evidence</p>
        <h2 id="sources-heading">Sources ({sources.length})</h2>
      </div>
      <div className="source-list">
        {sources.map((source, index) => {
          const symbol = source.symbol_name ?? "module";
          return (
            <article className="source-card" key={`${source.file_path}-${source.start_line}-${index}`}>
              <div className="source-card-header">
                <div>
                  <p className="source-path">
                    {source.repository}/{source.file_path}
                  </p>
                  <p className="source-symbol">
                    {source.symbol_type}: {symbol} · lines {source.start_line}–{source.end_line}
                  </p>
                </div>
                <span className="distance">distance {source.cosine_distance.toFixed(3)}</span>
              </div>
              <details>
                <summary>Show chunk</summary>
                <pre className="source-content"><code>{source.content}</code></pre>
              </details>
            </article>
          );
        })}
      </div>
    </section>
  );
}
