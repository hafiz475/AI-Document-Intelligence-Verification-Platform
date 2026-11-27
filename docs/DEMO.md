# AssureAI five-minute demo

This deterministic scenario uses synthetic data and the offline development providers.
It does not require paid AI credentials or represent real OpenAI execution.

## Prepare

1. Start the verified local stack using the README Docker Compose steps.
2. Open `http://localhost:5173`, select **Launch AssureAI**, and use the clearly labelled
   development sign-in.
3. Create a project named **Industrial Equipment Inspection Demo**.
4. Open **Documents** and upload `sample-data/sample-pump-inspection.txt`. Wait until the
   status is **READY**.

## Demonstrate

1. Open the document workspace and show the processing lifecycle and source metadata.
2. Select **Extraction**, run AI extraction, and wait for **COMPLETED**. Point out prompt,
   provider/model, latency, tokens, and the field summary.
3. Select **Evidence**, choose a field, and show its exact quote highlighted inside
   authorized TXT context, without a fabricated page number.
4. Verify a field. Correct another with a reason and show that its original AI value
   remains visible.
5. Open project **Search**, search for `abnormal vibration`, and open the ranked source.
6. Open **Ask AssureAI** and ask `What abnormal condition was detected?`. Show the
   supported answer and open the exact citation for `8.4 mm/s RMS`.
7. Ask `What was the motor winding temperature?`. Show **INSUFFICIENT EVIDENCE** and the
   absence of accepted citations.
8. Open **Evaluations**. Show Extraction, Retrieval, and RAG quality, then compare two
   compatible completed runs and explain the measured PASS/WARNING/REGRESSION reason.
9. Open **Review report** and **Audit**. Finish on **Overview** with persisted usage and
   recent activity.

## Trust points

- Evidence and citations are validated against project-scoped stored chunks.
- Human correction never overwrites the original AI output.
- Unknown tokens or latency remain **Unknown**; the UI does not invent metrics.
- VIEWER membership is read-only, and reports remain authenticated and project-scoped.
