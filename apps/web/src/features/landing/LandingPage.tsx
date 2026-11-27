import { Link } from "react-router-dom";

const flow = ["Upload", "Extract", "Verify", "Search", "Ask", "Evaluate"];
const features = [
  [
    "Document intelligence",
    "Process PDF, DOCX, and TXT files into structured, searchable evidence.",
  ],
  [
    "Structured extraction",
    "Turn technical reports into typed fields with immutable prompt provenance.",
  ],
  [
    "Evidence verification",
    "Inspect the exact source quote behind each extracted field before review.",
  ],
  [
    "Semantic search",
    "Find relevant passages across project documents using pgvector retrieval.",
  ],
  [
    "Grounded Q&A",
    "Ask project questions and receive answers constrained to retrieved evidence.",
  ],
  [
    "Validated citations",
    "Every accepted citation is checked against the source document chunk.",
  ],
  [
    "Human review",
    "Verify, correct, or reject AI output while retaining the original value.",
  ],
  [
    "AI evaluation",
    "Measure extraction, retrieval, and RAG quality with reproducible datasets.",
  ],
  [
    "Security & auditability",
    "Project RBAC, durable audit events, private storage paths, and safe errors.",
  ],
];

export function LandingPage() {
  return (
    <div className="landing-page">
      <header className="landing-nav">
        <Link className="brand" to="/">
          <span aria-hidden="true">A</span>AssureAI
        </Link>
        <nav aria-label="Public navigation">
          <a href="#workflow">How it works</a>
          <a href="#architecture">Architecture</a>
          <Link className="button compact" to="/app">
            Launch AssureAI
          </Link>
        </nav>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">Evidence-backed document intelligence</p>
            <h1>
              Turn complex documents into verified, evidence-backed
              intelligence.
            </h1>
            <p className="hero-lede">
              Upload technical documents, extract structured information, verify
              every AI result against source evidence, search semantically, and
              ask grounded questions with validated citations.
            </p>
            <div className="hero-actions">
              <Link className="button" to="/app">
                Launch AssureAI
              </Link>
              <a className="button secondary" href="#workflow">
                See how it works
              </a>
            </div>
            <p className="trust-note">
              Deterministic demo providers are available. No paid AI credentials
              are required.
            </p>
          </div>
          <div
            className="hero-proof"
            aria-label="AssureAI evidence review preview"
          >
            <div className="proof-toolbar">
              <span>Inspection report</span>
              <span className="status status-verified">VERIFIED</span>
            </div>
            <div className="proof-grid">
              <div className="proof-source">
                <small>SOURCE EVIDENCE</small>
                <p>
                  Finding: Drive-end bearing vibration measured{" "}
                  <mark>8.4 mm/s RMS</mark>.
                </p>
              </div>
              <div className="proof-field">
                <small>EXTRACTED FIELD</small>
                <strong>Abnormal vibration</strong>
                <span>8.4 mm/s RMS</span>
                <p>Exact quote validated</p>
              </div>
            </div>
          </div>
        </section>

        <section className="landing-section" id="workflow">
          <p className="eyebrow">One accountable workflow</p>
          <h2>From upload to measured quality</h2>
          <ol className="product-flow">
            {flow.map((step, index) => (
              <li key={step}>
                <span>{index + 1}</span>
                <strong>{step}</strong>
              </li>
            ))}
          </ol>
        </section>

        <section className="landing-section">
          <p className="eyebrow">Implemented capabilities</p>
          <h2>Trust is built into every result</h2>
          <div className="feature-grid">
            {features.map(([title, detail]) => (
              <article key={title}>
                <h3>{title}</h3>
                <p>{detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section
          className="landing-section architecture-section"
          id="architecture"
        >
          <div>
            <p className="eyebrow">Production-oriented architecture</p>
            <h2>One evidence chain, end to end</h2>
            <p>
              Authentication and project authorization protect every API
              boundary. Audit and telemetry follow work through the queue to
              each provider operation.
            </p>
          </div>
          <div
            className="architecture-map"
            role="img"
            aria-label="Browser to FastAPI, PostgreSQL pgvector, Redis workers, providers, evidence, search, citations, audit, evaluation, storage, and authentication"
          >
            <div className="arch-node accent">React workspace</div>
            <span>↓</span>
            <div className="arch-node">FastAPI · Auth · RBAC</div>
            <span>↓</span>
            <div className="arch-row">
              <div className="arch-node">PostgreSQL + pgvector</div>
              <div className="arch-node">Redis + Dramatiq</div>
              <div className="arch-node">Private storage</div>
            </div>
            <span>↓</span>
            <div className="arch-row">
              <div className="arch-node">Extract → Evidence</div>
              <div className="arch-node">Embed → Search</div>
              <div className="arch-node">RAG → Citations</div>
            </div>
            <div className="arch-row subtle">
              <div>Audit</div>
              <div>Evaluation</div>
              <div>OpenTelemetry</div>
            </div>
          </div>
        </section>

        <section className="landing-cta">
          <h2>Inspect the evidence, not just the answer.</h2>
          <Link className="button" to="/app">
            Open the workspace
          </Link>
        </section>
      </main>
      <footer>
        AssureAI · synthetic demo data · capabilities shown are implemented and
        test-backed
      </footer>
    </div>
  );
}
