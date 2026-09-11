# Leads considered and their limits

All sources were opened on 2026-09-11. Versioned local source hashes are in sources.json.
No paper prose, examples, annotation tags or story fragments enter model requests.

- [Dynamic Context Evolution, v1](https://arxiv.org/html/2604.07147v1), sections 3.4, 8 and
  appendix A: combines generated-history context, rotating instructions, self-probability
  filtering and embedding-based rejection. Its results concern the combined method; its
  conclusion says components alone were insufficient. This pilot tests a narrower history
  intervention, without ranking, thresholds, embeddings or discarding outputs. It is not a
  replication or an adoption of the paper's quality/cluster metrics.
- [Verbalized Sampling, v4](https://arxiv.org/html/2510.01171v4), abstract, appendix D.4 and F.5:
  requests responses with verbalized probabilities and studies probability wording. This is
  distinct from the earlier representative-sample sentence. It remains another experimental
  lead; self-reported numbers do not establish calibrated probabilities for our stories and
  will not be used as a selection gate here.
- [String Seed of Thought, v1](https://arxiv.org/html/2510.21150v1), sections 3 and 5.2:
  asks a model to generate and actively use a random string; the open-ended evaluation used
  DeepSeek-R1 and NoveltyBench. That differs from our opaque external Base64 prefix. Its
  evidence does not establish this as a fix for LitHarness, and this pilot does not add it.
- [Annotations Mitigate Post-Training Mode Collapse, v1](https://arxiv.org/html/2605.09995v1),
  sections 5.1-5.2: uses annotated pretraining and masked post-training in custom small models.
  This is a training intervention, not a prompt we can directly apply to the subscription
  model. No retraining, corpus ingestion or transfer of its reported quality result is proposed.

The chosen experiment tests a local conjecture: full plot history and persistence of its
novelty instruction may address failures visible in the existing traces. The papers motivate
search directions; they do not supply evidence that this conjecture works in this project.
