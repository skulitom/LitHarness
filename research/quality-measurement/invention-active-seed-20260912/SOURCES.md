# Sources and scope of the adaptation

[String Seed of Thought v1](https://arxiv.org/html/2510.21150v1), section 3, section 5.2
and Appendix A, uses a model-generated random string followed by explicit use during
generation, with a reasoning transcript in its open-ended prompt. The present adaptation
instead retains an external Base64 prefix and final story schema. It tests the active-use
instruction only; it is not a replication or evidence that the paper's results transfer
to Astra LitRPG stories. No source example enters generation.

[OpenAI reasoning guidance](https://developers.openai.com/api/docs/guides/reasoning-best-practices),
"How to prompt reasoning models effectively", favors simple instructions and does not
recommend soliciting reasoning transcripts. We keep the existing medium effort and
final-only schema in every condition. This guidance does not establish seed effectiveness.

The exact source snapshots and hashes are in sources.json, rechecked on 2026-09-12.
The [preceding report](../invention-plan-memory-20260912/REPORT.md) proposed this test;
that proposal contributes no empirical weight. Its outputs and inspection notes are not
generation inputs. The comparison, not the literature's favorable conclusion, determines
whether this registered adaptation becomes a feasibility lead.
