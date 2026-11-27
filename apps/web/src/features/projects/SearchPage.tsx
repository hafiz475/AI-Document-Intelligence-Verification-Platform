import { useParams } from "react-router-dom";
import { SemanticSearchPanel } from "../SemanticSearchPanel";
export function SearchPage() {
  const { projectId = "" } = useParams();
  return (
    <section>
      <div className="page-heading product-heading">
        <div>
          <p className="eyebrow">Semantic evidence retrieval</p>
          <h1>Search</h1>
          <p>
            Find source passages across ready project documents. Results link
            directly to evidence context.
          </p>
        </div>
      </div>
      <SemanticSearchPanel projectId={projectId} />
    </section>
  );
}
