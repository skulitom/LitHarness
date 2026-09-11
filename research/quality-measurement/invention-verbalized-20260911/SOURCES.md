# Primary source and adaptation

[Zhang et al., Verbalized Sampling, v4](https://arxiv.org/html/2510.01171v4), sections
F.4-F.5 and G.1-G.3, examines probability wording and tail thresholds. Its published decoding
settings and tasks differ from this native Codex experiment. Calibration on constrained
answer spaces does not calibrate long story probabilities for our model. F.5's setup uses
word-level wording where surrounding descriptions discuss responses; this pilot explicitly
uses response-level estimates, following the authors' project prompt.

The [authors' project page](https://www.verbalized-sampling.com/) supplies the response-level
tail-prompt concept. Our wording is adapted to six JSON premises and adds an explicit full-space
interpretation. It uses no source examples or third-party story prose. Snapshots and hashes
are in sources.json; none enters a model request. Our random precommitted position is an
experimental control, not a calibrated draw from the model's stated distribution.

The [Codex config reference](https://learn.chatgpt.com/docs/config-file/config-reference)
and [CLI reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli), checked
2026-09-11, did not document temperature or sampling-seed controls for the native surface.
This absence does not establish what the backend can do. We retain the previously frozen
transport and audit requested versus captured fields rather than inventing a sampler knob.
