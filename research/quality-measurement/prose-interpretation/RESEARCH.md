# Research notes, 2026-09-06

These are external findings and limits, not local mechanism qualification. No published story
text or digest is used as generation context. The next trial's conjecture comes from a located
local defect; none of these papers establishes its cause or promises a cure for AI tells.

- [DOC, Yang et al., ACL 2023](https://aclanthology.org/2023.acl-long.190/):
  detailed outlines and controlled realization target long-range coherence and outline
  relevance. Section 3.3 explicitly describes excessive control as a source of narrow,
  repetitive generation. Its OPT-175B/logit controller, short generation context and
  comparative human annotation differ from this subscription CLI setup. This supports
  investigating control strength as a design question; it does not validate our prose quality
  or license importing its evaluator. Another planning agent alone is not the tested remedy.
- [Style over Story, Jung et al., Findings ACL 2026](https://aclanthology.org/2026.findings-acl.1361/):
  six models select constraints from a 200-item library under three instruction types.
  Style selection is comparatively persistent across those instructions, with an emphasis on
  tone and mood. Sections 3 and 5 concern constraint selection, not a direct trial of generated
  chapter quality. Their results cannot establish that our model's prose style is immutable,
  that prompting cannot help, or that this repository has reproduced their mechanism.
- [Tell, Don't Show, Lucy et al., Findings ACL 2025](https://aclanthology.org/2025.findings-acl.1162/):
  Retell uses abstractions of passages to improve literary topic modeling. Its objective is
  analytical theme extraction. It is not a demonstration that reversing a thematic summary
  recovers the particulars of a compelling scene. Treating an analytical representation as
  a ready drafting representation would be an unsupported inference.
- [OpenAI GPT-6 Astra guidance](https://developers.openai.com/api/docs/guides/latest-model):
  the current prompting section notes sensitivity to instructions and a tendency toward
  detailed formatting and recurring phrases. It recommends auditing accessible instructions
  and specifying desired writing structure. Our prior isolation trial already removed tools,
  project documents, host skills and inherited configuration. This guidance does not diagnose
  the remaining literary problem. Documentation was read; no model API was invoked.
- [Agents' Room, Huot et al., ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/0fbc8a83d93dd8021a4dd8d2d34138eb-Abstract-Conference.html):
  the system separates four planning roles and five sequential writing roles through a shared
  scratchpad. Its concrete orchestrator uses a fixed exposition-to-resolution structure and
  studies prompted and fine-tuned agents. The reported preferences are evidence about that
  evaluated system, not evidence that adding one generic narrative agent to LitHarness will
  remove its opening defects. The separation of planning from realization is relevant; the
  fixed structure, training setup and evaluator are not adopted in this diagnostic.

## Local design implication, still a conjecture

Keep event construction, world constraints and prose realization distinguishable. A plan can
explain why a transition is valid for internal checking without requiring the narrator to
deliver that explanation. The bounded ablation tests removing such prescriptions while keeping
the earlier-step actions and background fixed. Repeated thesis/wage exposition may have a
different source: those facts appear in several unchanged input sections.

Do not respond to an unsuccessful arm by accumulating a larger list of banned phrases.
If prescription removal leaves the located mismatch, inspect whether the common world/scene
design itself demands stationary interpretation, or whether a substantially different
realization process is needed. These are possible discriminating questions, not a roadmap
commitment or evidence that another named agent will solve the problem.
