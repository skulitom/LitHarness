# External context and inference limits

Inspected 2026-09-07. These exact sources motivate alternatives; they neither label our
chapters nor license a production intervention. No paper examples enter generation.

- Reinhart et al., *Do LLMs write like humans? Variation in grammatical and rhetorical
  styles*, author preprint v2, https://arxiv.org/html/2410.16107v2, methods and results on
  matched continuations and instruction-tuned/base comparisons. The sampled models show
  systematic stylistic differences across genres; the available Llama comparison also
  differs by tuning. Inference: a style default is plausible alongside prompt effects.
  Limit: the study does not test this model, source, fiction failure or proposed repair;
  grammatical differences are not literary quality measures.
- *Controllable Narrative Rendering for Enhanced Assisted Writing*, v1,
  https://arxiv.org/html/2607.00009v1, framework and evaluation sections. It separates
  event structure from rendering and controls kinds of elaboration. Inference: narrative
  expansion is a separable design choice worth inspecting. Limit: its short-story setup
  and model rubric do not validate a quality claim for this chapter, and its evaluation
  does not supply this repository's containment or transfer controls. We adopt no rubric,
  density quota or agent stack from it.
- OpenAI Codex configuration reference,
  https://learn.chatgpt.com/docs/config-file/config-reference,
  model_instructions_file, developer_instructions and project_doc_max_bytes entries.
  These document instruction replacement, additional developer instructions and project
  document allowance. The frozen CLI uses these isolation settings. Inference: ordinary
  default coding instructions should not be assumed to explain the prose without evidence.
  Limit: recorded argv is not a complete capture of upstream model context or resolution.

The independent local input audit also verified a material scope difference: production
writes scenes with a different provider and context, whereas this fixture reconstructs a
complete chapter. This experiment can reveal a local input problem, not establish that the
same intervention fixes production. The source-free result should retain this limitation.
