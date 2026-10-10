# EchoOps demo script

Before presenting, configure the official Hindsight client with an empty bank, an API key, and bank ID. The app has no seeded-memory mode. All service data/actions are simulated; Hindsight is the actual external memory layer.

1. Click **Run Incident #1** and **Investigate**.
2. Run **Recall historical experience**. The empty bank should return no relevant experience; the first response remains generic.
3. Generate the recommendation and simulate the restart. It fails.
4. Inspect the connection pool; the simulator reports saturation. Increase pool capacity to resolve.
5. Retain the experience. The UI reports Hindsight Retain status only after the official client call returns successfully.
6. Click **Run similar Incident #2**, investigate, and run Recall before planning.
7. Show the actual returned historical text, prior restart failure, successful pool fix, and adapted response when those facts appear in Recall.
8. Inspect the pool, apply the learned pool remediation, resolve, and retain the second experience.

Use **Reset simulator** to clear local incident state; this never deletes persistent Hindsight memories. To show a genuinely empty first recall again, make a fresh bank and update `HINDSIGHT_BANK_ID`.