import { useRef, useState } from "react";

const MAX_BYTES = 20 * 1024 * 1024;
const EXTENSIONS = [".pdf", ".docx", ".txt"];

export function FileUpload({
  busy,
  onUpload,
}: {
  busy: boolean;
  onUpload: (file: File) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [validation, setValidation] = useState<string | null>(null);

  function choose(file?: File) {
    if (!file) return;
    const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!EXTENSIONS.includes(extension)) {
      setValidation("Choose a PDF, DOCX, or TXT file.");
      return;
    }
    if (file.size === 0 || file.size > MAX_BYTES) {
      setValidation("The file must be non-empty and no larger than 20 MB.");
      return;
    }
    setValidation(null);
    onUpload(file);
  }

  return (
    <div
      className="upload-zone"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        choose(event.dataTransfer.files[0]);
      }}
    >
      <input
        accept=".pdf,.docx,.txt"
        className="sr-only"
        disabled={busy}
        onChange={(event) => choose(event.target.files?.[0])}
        ref={input}
        type="file"
      />
      <p>
        <strong>Drop a document here</strong> or select one from your computer.
      </p>
      <p className="muted">PDF, DOCX, or UTF-8 TXT · maximum 20 MB</p>
      <button
        disabled={busy}
        onClick={() => input.current?.click()}
        type="button"
      >
        {busy ? "Uploading…" : "Choose document"}
      </button>
      {validation && (
        <p className="field-error" role="alert">
          {validation}
        </p>
      )}
    </div>
  );
}
