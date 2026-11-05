import { Navigate, Route, Routes } from "react-router-dom";

const capabilities = [
  { title: "Document intake", detail: "PDF, DOCX, and TXT validation begins in Milestone 1." },
  { title: "Evidence-first extraction", detail: "Structured values will retain page and text references." },
  { title: "Reviewable intelligence", detail: "Human review, grounded Q&A, and evaluation follow later." },
];

function Dashboard() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-white/10">
        <nav aria-label="Primary navigation" className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <a className="flex items-center gap-3 font-semibold tracking-tight" href="/">
            <span aria-hidden="true" className="grid size-9 place-items-center rounded-xl bg-cyan-300 text-sm font-black text-slate-950">A</span>
            AssureAI
          </a>
          <span className="rounded-full border border-cyan-300/30 bg-cyan-300/10 px-3 py-1 text-xs font-medium text-cyan-200">
            Foundation scaffold
          </span>
        </nav>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl gap-12 px-6 py-20 lg:grid-cols-[1.25fr_0.75fr] lg:items-center">
          <div>
            <p className="mb-4 text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">AI document intelligence</p>
            <h1 className="max-w-3xl text-5xl font-semibold leading-tight tracking-tight sm:text-6xl">
              Technical evidence, made easier to verify.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
              AssureAI is being built for traceable extraction, review, and evidence-backed answers across engineering documents.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <span className="rounded-lg bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950">Milestone 0 foundation</span>
              <span className="rounded-lg border border-white/15 px-4 py-2 text-sm text-slate-300">Document workflow comes next</span>
            </div>
          </div>

          <aside aria-label="Implementation status" className="rounded-3xl border border-white/10 bg-white/[0.04] p-6 shadow-2xl shadow-cyan-950/30">
            <p className="text-sm font-medium text-slate-400">Implementation status</p>
            <p className="mt-2 text-2xl font-semibold">Platform foundation</p>
            <div className="mt-6 h-2 overflow-hidden rounded-full bg-slate-800">
              <div className="h-full w-1/4 rounded-full bg-cyan-300" />
            </div>
            <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
              <div className="rounded-2xl bg-slate-900 p-4"><dt className="text-slate-400">Available</dt><dd className="mt-1 font-medium">Service shells</dd></div>
              <div className="rounded-2xl bg-slate-900 p-4"><dt className="text-slate-400">Next</dt><dd className="mt-1 font-medium">Document intake</dd></div>
            </dl>
          </aside>
        </section>

        <section aria-labelledby="capabilities-heading" className="mx-auto max-w-6xl px-6 pb-20">
          <h2 id="capabilities-heading" className="text-2xl font-semibold">Designed for auditable workflows</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {capabilities.map((capability, index) => (
              <article className="rounded-2xl border border-white/10 bg-slate-900/60 p-6" key={capability.title}>
                <p className="text-sm font-semibold text-cyan-300">0{index + 1}</p>
                <h3 className="mt-3 text-lg font-semibold">{capability.title}</h3>
                <p className="mt-2 leading-7 text-slate-400">{capability.detail}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<Dashboard />} path="/" />
      <Route element={<Navigate replace to="/" />} path="*" />
    </Routes>
  );
}
