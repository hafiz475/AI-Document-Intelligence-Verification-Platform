import { useParams } from "react-router-dom";
import { RagQuestionPanel } from "../RagQuestionPanel";
export function AskPage() {
  const { projectId = "" } = useParams();
  return (
    <section>
      <div className="page-heading product-heading">
        <div>
          <p className="eyebrow">Grounded project Q&A</p>
          <h1>Ask AssureAI</h1>
          <p>
            Ask questions against project evidence. Every accepted citation is
            validated against its source.
          </p>
        </div>
      </div>
      <RagQuestionPanel projectId={projectId} />
    </section>
  );
}
