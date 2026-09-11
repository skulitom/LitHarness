# Source boundaries

The operator supplied a video transcript. Around 10:18 it describes adding the instruction
"Use a representative sample." to a name-generation prompt. This experiment transfers that
wording to premise batches; it does not replicate the video's unnamed models or name task.
The transcript supplies a hypothesis, not validation or a privileged model control.

Hamilton and Mimno's [paper, version 1](https://arxiv.org/html/2605.26492v1), sections 3-4,
reports recurring names, settings and professions across 20,000 stories from four models
using five short prompts. Its abstract's 88.3% means at least one of eleven tokens, not the
same complete character and setting. Section 3 reports Elias in 26.5% and a lighthouse in
51.2%; 66.6% refers to some combination of lighthouse, Elias and keeper. The transcript
overstates that last combination as a single repeated person.

Sections 1 and 6 explicitly leave the proposed safety/alignment cause for future work.
The paper does not establish that the representative-sample instruction bypasses alignment,
that prompting cannot improve diversity, or the cause of our Astra behavior. Its training
analysis concerns available OLMo data, not access to proprietary model weights or data.

Exact transcript and downloaded paper hashes live in sources.json. Raw bytes stay under
ignored runs/invention-contrast-20260911/sources. No source story, name list, third-party
prose or corpus digest is passed to generation.
