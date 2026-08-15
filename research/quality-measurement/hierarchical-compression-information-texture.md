# Hierarchical Compression Analysis and Multi-Scale Information Texture for Detecting and Localizing AI-Like Prose

## A Formal Framework and Experimental Protocol

**Manuscript type:** Methods paper / preregistration-ready research proposal  
**Version:** 1.0 — 15 August 2026  
**Empirical status:** This paper proposes hypotheses and an evaluation protocol; it does not report experimental results.

---

## Abstract

Text attributed to large language models is often criticized not because it contains a single diagnostic phrase, but because its statistical texture is excessively regular across several scales: exact phrases recur, semantic novelty decays, sentence rhythms homogenize, and token-level surprise varies less or differently than it does in matched human prose. This paper formalizes a method for detecting and localizing that texture. A document is represented by a boundary-respecting binary interval tree. At every node, the method measures corrected compression rate, cross-child compression gain, order asymmetry, language-model surprisal moments, multiscale surprisal coefficients, structural variation, and semantic redundancy. These measurements form a *multi-scale information-texture field* rather than a single document-level “AI probability.” Scores are calibrated against human and machine reference corpora matched by genre, register, length, document position, and other observable covariates.

We establish five theoretical connections. First, ideal cross-child code-length gain is pointwise mutual information and has mutual information as its expectation. Second, a contrast between human-trained and machine-trained code lengths is a normalized log-likelihood ratio and therefore yields the Neyman–Pearson test under simple hypotheses. Third, Haar coefficients on token surprisal provide an exact scale decomposition of centered information energy. Fourth, conformal nodewise p-values combined with depth-weighted Bonferroni thresholds control family-wise false positives over a fixed tree without requiring independence among overlapping spans. Fifth, no detector can reliably distinguish two source distributions that are close in total variation; consequently, “AI-like texture” must not be interpreted as proof of machine authorship.

The proposed evaluation separates three targets that are frequently conflated: provenance discrimination, localization of machine-written spans, and prediction of human judgments of low-quality or formulaic prose. It uses held-out generators, domains, authors, prompts, decoding schemes, edited outputs, adversarial transformations, and demographic subgroups. Primary outcomes include document AUROC, true-positive rate at a prespecified low false-positive rate, token-level average precision, intersection-over-union, boundary error, calibration, subgroup false-positive rates, and blinded reader judgments. The central hypothesis is not that gzip alone detects authorship, but that hierarchical compression supplies a cheap and interpretable surface channel within a reference-calibrated, multi-channel diagnostic system.

**Keywords:** AI-generated text detection; compression; normalized compression distance; information theory; multiscale analysis; stylometry; surprisal; semantic redundancy; change-point localization; prose quality

---

## 1. Introduction

The phrase *AI slop* has no stable scientific definition. In ordinary use it can refer to cliché, repetition, generic exposition, excessive signposting, flattened rhythm, low semantic novelty, factual carelessness, or merely the reader's belief that a machine wrote the text. These are not equivalent properties. A rigorous method must therefore begin by separating at least three questions:

1. **Provenance:** Was a span sampled from a specified machine distribution rather than a specified human distribution?
2. **Texture:** Does a span exhibit statistical regularities associated with a matched corpus of generated prose?
3. **Quality:** Do readers judge the span to be formulaic, redundant, vague, or otherwise poor?

This paper addresses all three but does not identify them with one another. Its core object is *AI-like prose*: prose whose observed features are more probable under a declared machine-text reference distribution than under a declared, matched human-text reference distribution. This is an operational comparison between distributions, not a metaphysical property of a string and not proof of authorship.

The starting intuition is simple. Let \(C(x)\) denote the bit length produced by a lossless compressor for text \(x\). A global compression ratio \(C(x)/|x|\) measures only one coarse property. A stronger measurement compares adjacent regions \(L\) and \(R\):

\[
C(L)+C(R)-C(LR).
\]

If the joint encoding is much shorter than two independent encodings, the children share reusable structure. Repeating this comparison over a segmentation tree localizes the scales and regions at which redundancy appears. The resulting map resembles a compression flame graph for prose.

The idea is plausible but incomplete. gzip operates on bytes and predominantly captures local orthographic recurrence. DEFLATE permits backward references only within the previous 32 KiB of input [3], so naive whole-document gzip cannot directly recover arbitrary long-range rhetorical or semantic repetition. Short spans also suffer disproportionately from container headers and compressor startup effects. Finally, highly compressible text is not necessarily bad, and low compressibility is not necessarily human. Poetry, legal boilerplate, dialogue, source code, and carefully repeated motifs illustrate the confounding role of genre and intention.

We therefore propose **Hierarchical Multi-Scale Information Texture** (HMIT): a boundary-aware tree in which compression is one channel in a vector field containing lexical, predictive, rhythmic, syntactic, semantic, and reference-contrast measurements.

### 1.1 Contributions

This paper contributes:

1. A precise distinction among provenance, AI-like texture, and prose-quality inference.
2. A formal interval-tree representation of a document and a corrected family of self-compression, conditional-compression, and sibling-coupling statistics.
3. A multichannel definition of information texture, including an exact Haar decomposition of token-surprisal variation.
4. Reference-calibrated likelihood-ratio and conformal localization procedures.
5. Algorithms with explicit computational complexity and a non-overlapping localization rule.
6. An evaluation plan designed to test in-domain performance, generator and domain transfer, mixed-authorship localization, robustness, fairness, calibration, and usefulness to editors.
7. Failure criteria that can falsify the proposed method rather than merely produce a favorable benchmark number.

---

## 2. Scope and operational definitions

### 2.1 Text and provenance distributions

Let \(\mathcal X\) be the set of finite Unicode strings after a declared normalization procedure. Let \(Z\) denote observable strata such as language, genre, register, scene type, document position, length band, and dialogue proportion. For a fixed stratum \(z\), define:

- \(P_H^z\): a distribution of human-authored spans;
- \(P_A^z\): a distribution of machine-generated spans;
- \(P_E^z\): a distribution of professionally edited or otherwise target-quality human spans;
- \(P_S^z\): a distribution of spans judged by humans to exhibit specified “slop” defects, regardless of provenance.

These are empirical populations defined by sampling protocols. There is no universal distribution called “human writing.” All claims in this paper are conditional on the corpora, time period, language, matching variables, and generator family used to estimate these distributions.

### 2.2 AI-likeness

For densities or probability masses \(p_A^z\) and \(p_H^z\), the ideal local AI-likeness of span \(x\) is the log-density ratio

\[
\Lambda_{A/H}(x;z)
=
\log \frac{p_A^z(x)}{p_H^z(x)}.
\tag{1}
\]

Positive values favor the declared machine distribution; negative values favor the declared human distribution. Equation (1) defines a relative property. Changing \(P_A^z\), \(P_H^z\), or \(z\) can change the answer.

### 2.3 Slop as a rated construct

Let \(Y=(Y_1,\ldots,Y_q)\) contain blinded reader ratings for defects such as semantic repetition, cliché, vagueness, unnecessary signposting, rhythmic monotony, and low specificity. A quality-defect score is

\[
S_Q(x;z)=\mathbb E[w^\top Y\mid X=x,Z=z],
\tag{2}
\]

where \(w\) is declared before evaluation. Provenance and quality are then separate prediction tasks:

\[
\Lambda_{A/H}(x;z) \neq S_Q(x;z)
\quad\text{in general.}
\tag{3}
\]

Equation (3) is a design constraint. A system that predicts authorship but not reader-rated defects is a detector, not an editing diagnostic. A system that predicts defects but not authorship may still be valuable for revision.

### 2.4 Localization

For a document of \(n\) atomic units, let \(y_i\in\{H,A\}\) denote the latent source of unit \(i\), or let \(q_i\in\mathbb R\) denote its latent quality-defect intensity. Localization estimates either

\[
\widehat p_i=\Pr(y_i=A\mid x_{1:n})
\tag{4}
\]

or a set of anomalous intervals \(\widehat{\mathcal I}=\{[a_k,b_k)\}\). The desired system should both identify anomalous spans and expose the feature channels responsible for each decision.

---

## 3. Background and related work

### 3.1 Compression as an information proxy

Shannon's source-coding framework connects expected code length to entropy [1]. Kolmogorov complexity gives an individual-sequence analogue but is not computable. Cilibrasi and Vitányi replaced it with real compressor lengths to define the normalized compression distance (NCD) [2]:

\[
\operatorname{NCD}_C(x,y)
=
\frac{C(xy)-\min\{C(x),C(y)\}}
{\max\{C(x),C(y)\}}.
\tag{5}
\]

For an idealized *normal compressor*, NCD approximates a universal similarity metric. Production gzip is a useful engineering instrument, not a universal code and not automatically a normal compressor at every input length. Its format combines LZ77 matches and Huffman coding, with backward distances limited to 32 KiB [3].

Compression-based text classification has empirical precedent. Jiang et al. combine gzip NCD with \(k\)-nearest neighbors and report competitive low-resource and out-of-distribution classification results on their evaluated datasets [4]. That result supports the claim that ordinary compressors contain useful classification signal. It does not establish that gzip alone is a reliable authorship detector.

### 3.2 Machine-text detection

Statistical detectors exploit regularities in model likelihoods or ranks. GLTR visualizes token-rank statistics and improved human discrimination in its study [5]. DetectGPT measures the curvature of a candidate text under a source model by comparing it with perturbations [6]. Binoculars contrasts scores from two related language models [7]. These methods motivate the use of *relative* predictive fit rather than raw perplexity alone.

The limitations are equally important. Sadasivan et al. connect the best achievable detector performance to total variation distance and demonstrate vulnerabilities to paraphrasing [8]. RAID evaluates detectors across models, domains, decoding strategies, and adversarial transformations and finds substantial robustness failures [11]. False positives are not evenly distributed: Liang et al. report severe misclassification of non-native English writing by several evaluated detectors [12]. A texture system must therefore be calibrated by stratum, report uncertainty, and never be used as sole evidence of misconduct.

### 3.3 Mixed-text localization

Most early work classified whole documents. Machine-Generated Text Localization explicitly studies mixed human/machine documents and emphasizes that short spans contain limited standalone evidence; contextual scoring improves localization [9]. SemEval-2024 Task 8 likewise includes a boundary-identification subtask alongside multidomain, multimodel, and multilingual detection [10]. HMIT differs by making the scale hierarchy and diagnostic feature decomposition primary objects.

### 3.4 Semantic and structural channels

Byte compression recognizes literal reuse but can miss paraphrase. Sentence embeddings provide a computable proxy for semantic similarity; for example, Sentence-BERT produces fixed representations compared by cosine similarity [13]. Such embeddings remain model-dependent and can confuse topical relatedness with redundancy. They are therefore included as one calibrated channel rather than treated as ground truth.

Watermarking is conceptually separate. A watermark deliberately changes the generation distribution to embed a detectable signal [14]. HMIT is a post hoc distributional diagnostic and assumes no cooperation from the generator.

---

## 4. Document trees

### 4.1 Atomic units and serialization

After Unicode normalization, a document is represented as an ordered sequence

\[
D=(u_1,u_2,\ldots,u_n),
\tag{6}
\]

where an atomic unit is normally a sentence, but may be a clause, line, or fixed token block. Let \(\sigma(u_{a:b})\) be an injective, length-prefixed UTF-8 serialization of the contiguous interval \([a,b)\). Injectivity prevents concatenation ambiguity. The preprocessing configuration—normalization form, whitespace policy, quotation normalization, case preservation, tokenizer, and sentence segmenter—is part of the model specification and must be frozen before testing.

### 4.2 Boundary-respecting binary interval tree

A document tree \(T(D)=(V,E)\) is a rooted binary tree. Each node \(v\in V\) corresponds to an interval

\[
I_v=[a_v,b_v)\subseteq[1,n+1).
\tag{7}
\]

The root covers \([1,n+1)\). If internal node \(v\) has children \(v_L,v_R\), then for some split point \(m_v\),

\[
I_{v_L}=[a_v,m_v),\qquad
I_{v_R}=[m_v,b_v),
\tag{8}
\]

and the children are disjoint and exhaustive. Splits minimize token imbalance subject to legal linguistic boundaries. Recursion stops when a child would contain fewer than \(m_{\min}\) tokens, fewer than \(s_{\min}\) sentences, or exceed a maximum depth \(D_{\max}\).

Balanced trees support efficient dyadic analysis; paragraph- or section-aligned trees improve editorial meaning. Both should be evaluated. Tree construction must not use provenance labels.

### 4.3 Node scale

For node \(v\), let \(n_v\) be its token count, \(B_v\) its raw UTF-8 length in bits, and \(d_v\) its depth. A scale descriptor is

\[
\kappa(v)=(d_v,n_v,B_v,\pi_v),
\tag{9}
\]

where \(\pi_v=a_v/n\) is relative document position. Calibration should condition on or match these quantities because many features depend strongly on span length and narrative position.

---

## 5. Compression measurements

### 5.1 Corrected code length

Let \(C:\{0,1\}^*\rightarrow\mathbb N\) return the length in bits of a complete lossless encoded object. Let

\[
h_C=C(\sigma(\epsilon))
\tag{10}
\]

be an empty-object estimate of fixed overhead, and define

\[
C_0(x)=C(\sigma(x))-h_C.
\tag{11}
\]

This subtraction removes only a first-order header term. Block decisions, checksums, dictionaries, and end markers can create length-dependent overhead; consequently, all short-span statistics require empirical calibration against same-length null spans. Negative \(C_0\) values, while inconvenient, are not silently clipped before calibration.

The corrected self-compression rate in bits per raw bit is

\[
\rho_C(x)=\frac{C_0(x)}{\max(B_x,1)}.
\tag{12}
\]

Bits per byte or bits per token may be reported as secondary views. Comparisons must use the same denominator.

### 5.2 Directional conditional gain

Let \(\langle x,y\rangle\) be an unambiguous paired serialization. Define the incremental code length of \(y\) after \(x\) by

\[
C_0(y\mid x)=C_0(\langle x,y\rangle)-C_0(x).
\tag{13}
\]

The directional reuse gain is

\[
G_C(y\leftarrow x)
=C_0(y)-C_0(y\mid x)
=C_0(x)+C_0(y)-C_0(\langle x,y\rangle).
\tag{14}
\]

A positive value means that encoding \(y\) after \(x\) is shorter than encoding \(y\) independently. Because practical compressors are order-sensitive, define the symmetric sibling gain

\[
J_C(x,y)
=\frac{G_C(y\leftarrow x)+G_C(x\leftarrow y)}{2}
\tag{15}
\]

and order asymmetry

\[
A_C(x,y)
=
\frac{C_0(\langle x,y\rangle)-C_0(\langle y,x\rangle)}
{\max\{C_0(x)+C_0(y),\varepsilon\}}.
\tag{16}
\]

The normalized sibling coupling is

\[
R_C(x,y)
=
\frac{J_C(x,y)}
{\max\{\min(C_0(x),C_0(y)),\varepsilon\}}.
\tag{17}
\]

Unlike ideal mutual information, \(J_C\) and \(R_C\) need not be nonnegative or bounded for an arbitrary compressor. Negative values are informative diagnostics of overhead or compressor non-normality; they are not mathematical contradictions.

For each internal tree node \(v\), equations (15)–(17) are evaluated on its left and right child spans. High \(R_C\) can reveal shared phrasing distributed across two individually unexceptional children.

### 5.3 Ideal-code interpretation

**Proposition 1 (sibling gain and mutual information).** Let random variables \(X,Y\) have joint mass \(p(x,y)\) and marginals \(p_X,p_Y\). Under ideal Shannon code lengths

\[
c_X(x)=-\log_2 p_X(x),\quad
c_Y(y)=-\log_2 p_Y(y),\quad
c_{XY}(x,y)=-\log_2 p(x,y),
\tag{18}
\]

the joint code-length gain is

\[
j^*(x,y)=c_X(x)+c_Y(y)-c_{XY}(x,y)
=\log_2\frac{p(x,y)}{p_X(x)p_Y(y)}.
\tag{19}
\]

Therefore \(j^*(x,y)\) is pointwise mutual information and

\[
\mathbb E[j^*(X,Y)]=I(X;Y)\ge 0.
\tag{20}
\]

*Proof.* Substitute (18) into (19), combine logarithms, and take expectation under \(p(x,y)\). The resulting sum is the Kullback–Leibler divergence \(D_{\mathrm{KL}}(p_{XY}\|p_Xp_Y)\), which is nonnegative. \(\square\)

Practical \(J_C\) is only an operational proxy for (19). gzip reuses byte strings, not latent propositions; its measured gain depends on headers, serialization, search heuristics, and finite history.

### 5.4 Reference-conditioned compression

Absolute compressibility conflates genre and source. A more relevant statistic compares conditional code lengths under reference sets \(\mathcal R_H^z\) and \(\mathcal R_A^z\). For a compressor that can preserve or preload state, define

\[
\bar C_H(x;z)=\operatorname{Agg}_{r\in\mathcal R_H^z} C_0(x\mid r),
\qquad
\bar C_A(x;z)=\operatorname{Agg}_{r\in\mathcal R_A^z} C_0(x\mid r),
\tag{21}
\]

where \(\operatorname{Agg}\) is a prespecified mean, trimmed mean, or nearest-neighbor aggregate. The reference contrast is

\[
D_C(x;z)=\frac{\bar C_H(x;z)-\bar C_A(x;z)}{n_x}.
\tag{22}
\]

Positive \(D_C\) means that machine references code the span more economically. With gzip, the reference must occur immediately before the candidate and only its last 32 KiB can affect LZ77 matches. Dictionary compressors, prediction-by-partial-matching models, byte language models, or arithmetic coders are better suited to long reference contexts.

### 5.5 Dual-model coding as a likelihood ratio

Let \(q_H(t_i\mid t_{<i},z)\) and \(q_A(t_i\mid t_{<i},z)\) be probabilistic predictors trained on matched human and machine corpora. Their ideal arithmetic-code lengths are

\[
L_H(x)=-\sum_{i=1}^{n_x}\log_2 q_H(t_i\mid t_{<i},z),
\quad
L_A(x)=-\sum_{i=1}^{n_x}\log_2 q_A(t_i\mid t_{<i},z).
\tag{23}
\]

Define

\[
D_{H,A}(x;z)=\frac{L_H(x)-L_A(x)}{n_x}.
\tag{24}
\]

**Proposition 2 (code contrast is a likelihood-ratio test).** If \(q_H=p_H^z\) and \(q_A=p_A^z\), then

\[
n_x\ln 2\;D_{H,A}(x;z)
=\log\frac{p_A^z(x)}{p_H^z(x)}
=\Lambda_{A/H}(x;z).
\tag{25}
\]

For testing the simple hypotheses \(H_0:X\sim P_H^z\) against \(H_1:X\sim P_A^z\), thresholding (24) is the most powerful test at any fixed size by the Neyman–Pearson lemma.

*Proof.* Expand (23), subtract, convert base-2 logarithms to natural logarithms, and apply the Neyman–Pearson lemma to the resulting likelihood ratio. \(\square\)

This proposition motivates two-distribution coding. It does not imply that learned \(q_H\) and \(q_A\) equal the real populations or that the test transfers to unseen generators and domains.

---

## 6. Multi-scale information texture

Compression is the first channel, not the entire system. Each node receives a feature vector

\[
F_v=
\bigl[
F_v^{\mathrm{cmp}},
F_v^{\mathrm{sur}},
F_v^{\mathrm{str}},
F_v^{\mathrm{sem}},
F_v^{\mathrm{sty}}
\bigr]\in\mathbb R^p.
\tag{26}
\]

The feature schema and all model checkpoints must be recorded so that a score can be reproduced.

### 6.1 Compression channel

For one or more compressors \(C\), include:

\[
F_v^{\mathrm{cmp}}=
\left[
\rho_C(x_v),
R_C(x_{v_L},x_{v_R}),
A_C(x_{v_L},x_{v_R}),
D_C(x_v;z),
\operatorname{NCD}_C(x_{v_L},x_{v_R})
\right].
\tag{27}
\]

Leaf nodes omit sibling quantities. Multiple compressor families should be retained as separate features rather than averaged before calibration.

### 6.2 Surprisal channel

For an external evaluator language model \(q\), token surprisal is

\[
s_i=-\log_2 q(t_i\mid t_{<i}).
\tag{28}
\]

At node \(v\), compute the mean, variance, robust spread, quantiles, and lag correlations:

\[
\mu_v=\frac{1}{n_v}\sum_{i\in I_v}s_i,
\tag{29}
\]

\[
\nu_v=\frac{1}{n_v-1}\sum_{i\in I_v}(s_i-\mu_v)^2,
\tag{30}
\]

\[
\gamma_v(k)=
\frac{\sum_{i\in I_v:i+k\in I_v}(s_i-\mu_v)(s_{i+k}-\mu_v)}
{\sum_{i\in I_v}(s_i-\mu_v)^2+\varepsilon}.
\tag{31}
\]

Because likelihood is evaluator-dependent, use multiple evaluator models where feasible and report sensitivity to tokenizer and checkpoint.

### 6.3 Exact multiscale decomposition

Assume for clarity that a node contains \(n_v\) equally weighted tokens and is recursively split into left and right children with sizes \(n_L,n_R\). For any additive scalar signal \(a_i\), define the tree-Haar coefficient

\[
w_v=
\sqrt{\frac{n_Ln_R}{n_v}}
\left(\bar a_{v_L}-\bar a_{v_R}\right),
\tag{32}
\]

where \(\bar a_v=n_v^{-1}\sum_{i\in I_v}a_i\).

**Proposition 3 (information-energy identity).** For a full binary partition down to single-token leaves,

\[
\sum_{i=1}^{n}(a_i-\bar a)^2
=
\sum_{v\in V_{\mathrm{internal}}} w_v^2.
\tag{33}
\]

*Proof sketch.* The root mean vector and the normalized left-minus-right contrast form orthogonal components. Applying the same orthogonal decomposition recursively to both children yields an orthonormal basis consisting of the constant vector and all tree-Haar contrasts. Parseval's identity gives (33). \(\square\)

Setting \(a_i=s_i\) makes (33) an exact decomposition of centered surprisal energy by location and scale. Define depth energy

\[
E_d=\sum_{v:d_v=d}w_v^2,
\qquad
e_d=\frac{E_d}{\sum_{d'}E_{d'}+\varepsilon}.
\tag{34}
\]

The vector \((e_0,\ldots,e_{D-1})\) distinguishes signals with equal mean and variance but different scale organization. A uniformly bland span, a regularly alternating span, and a span with one abrupt information transition can have similar global moments and different \(e_d\).

### 6.4 Structural channel

Let sentences in node \(v\) have token lengths \(\ell_1,\ldots,\ell_m\). Candidate features include:

- mean, standard deviation, median absolute deviation, and entropy of sentence length;
- paragraph-length distribution;
- punctuation and function-word frequencies;
- part-of-speech \(n\)-gram entropy;
- parse-depth and dependency-relation distributions;
- type-token and moving-average type-token ratios;
- frequencies of prespecified discourse transitions and rhetorical templates.

The core quantities should be distributional rather than blacklist-based. A word such as *delve* is not evidence by itself; its relevance, if any, is corpus- and time-dependent.

For any histogram \(p_v(k)\), sibling structural contrast may be measured with Jensen–Shannon divergence:

\[
\operatorname{JSD}(p_L,p_R)
=\frac12D_{\mathrm{KL}}(p_L\|m)
+\frac12D_{\mathrm{KL}}(p_R\|m),
\quad m=\frac12(p_L+p_R).
\tag{35}
\]

### 6.5 Semantic-redundancy channel

Let \(e_i\in\mathbb R^d\) be a normalized sentence embedding. Define lag-\(k\) semantic similarity

\[
M_v(k)=
\frac{1}{N_{v,k}}
\sum_{i,i+k\in I_v} e_i^\top e_{i+k},
\tag{36}
\]

and backward novelty over a horizon \(h\):

\[
N_i^{(h)}=1-\max_{j\in[i-h,i-1]\cap I_v}e_i^\top e_j.
\tag{37}
\]

Node features include the mean, lower quantiles, slope, and autocorrelation of \(N_i^{(h)}\). To reduce topical confounding, a proposition-level variant should compare predicate–argument or entailment representations and distinguish legitimate elaboration from paraphrastic restatement. Embedding model and horizon are preregistered hyperparameters.

### 6.6 Cross-channel texture

Some defects are interactions. Semantic reiteration with ordinary lexical novelty may indicate paraphrase; low surprisal variation with low syntactic variation may indicate homogenization. Include only prespecified interactions or learn them with regularization:

\[
F_v^{\mathrm{int}}=
\left[
Z(R_C)Z(M_v),
Z(\nu_v)Z(\operatorname{Var}(\ell)),
Z(D_{H,A})Z(1-\bar N_v)
\right],
\tag{38}
\]

where \(Z\) denotes training-set calibration. Post hoc interaction mining must be labeled exploratory.

---

## 7. Reference calibration and statistical decisions

### 7.1 Matched calibration

For feature \(j\), scale \(\kappa\), and stratum \(z\), let human calibration values be \(f_{1j},\ldots,f_{mj}\). A robust score is

\[
Z_{vj}^{H}
=
\frac{F_{vj}-\operatorname{median}(f_{1j},\ldots,f_{mj})}
{1.4826\operatorname{MAD}(f_{1j},\ldots,f_{mj})+\varepsilon}.
\tag{39}
\]

Matching or conditional regression is required for at least length, depth, genre, register, and dialogue proportion. If the calibration corpus cannot support a declared stratum, the system should abstain rather than silently extrapolate.

### 7.2 Density-ratio estimation

Let \(\eta(F,z)=\Pr(A\mid F,z)\) and training prior \(\pi_A=\Pr(A)\). If \(\eta\) is calibrated, the feature-space log-density ratio is

\[
\widehat\Lambda_F(F;z)
=
\operatorname{logit}\widehat\eta(F,z)
-\log\frac{\pi_A}{1-\pi_A}.
\tag{40}
\]

Candidate estimators include regularized logistic regression, gradient-boosted trees with monotonic constraints where justified, and explicit class-conditional density models. A simple model is preferred unless a more complex model improves held-out generator and domain transfer, not merely random-split accuracy.

Separate estimators are fit for:

\[
\widehat\Lambda_{A/H}(F;z)
\quad\text{and}\quad
\widehat S_Q(F;z).
\tag{41}
\]

The first predicts source labels; the second predicts blinded quality ratings. Their correlation is an empirical result, not an assumption.

### 7.3 Conformal nodewise p-values

For a scalar anomaly score \(T_v\), let \(T_1^H,\ldots,T_m^H\) be exchangeable scores from matched human calibration nodes at the same scale. Define

\[
p_v=
\frac{1+\sum_{j=1}^{m}\mathbf 1[T_j^H\ge T_v]}
{m+1}.
\tag{42}
\]

Under exchangeability, \(p_v\) is marginally super-uniform for a human node. This finite-sample statement does not require a parametric feature distribution, but exchangeability can fail under domain, author, or temporal shift.

### 7.4 Tree-wide false-positive control

Suppose the fixed tree has maximum depth \(D\). For each node at depth \(d\), use

\[
\alpha_v=\frac{\alpha}{(D+1)2^d}.
\tag{43}
\]

**Proposition 4 (family-wise error control).** If every null-node p-value is super-uniform, rejecting node \(v\) when \(p_v\le\alpha_v\) controls the probability of one or more false rejections over the fixed tree at at most \(\alpha\), regardless of dependence among nodes.

*Proof.* There are at most \(2^d\) nodes at depth \(d\). By the union bound,

\[
\Pr(\text{any false rejection})
\le\sum_{d=0}^{D}\sum_{v:d_v=d}\alpha_v
\le\sum_{d=0}^{D}\frac{\alpha}{D+1}
=\alpha.
\quad\square
\tag{44}
\]

Equation (43) is conservative. Hierarchical false-discovery-rate procedures may offer more power but should be evaluated separately. Ancestor gating may be used to simplify visualization, not to claim (44) unless the adaptive testing rule is covered by the proof.

### 7.5 Non-overlapping output frontier

Significant tree nodes overlap. Define the reported frontier \(\mathcal F\) by recursively replacing a significant node with its significant children whenever at least one child is significant. A significant node is emitted only if neither child is significant. Non-significant ancestors do not suppress significant descendants. The result is an antichain of maximally resolved flagged intervals. Each emitted interval includes:

- its calibrated source and quality scores;
- uncertainty or p-value;
- the top signed feature contributions;
- comparisons with matched human quantiles;
- its parent and child scores to expose scale dependence.

---

## 8. Algorithms

### Algorithm 1: Tree construction and feature extraction

```text
INPUT:
    document D
    minimum leaf size m_min
    maximum depth D_max
    compressors C_1,...,C_K
    evaluator models q_1,...,q_M
    semantic encoder E
    frozen preprocessing configuration P

1. Normalize and segment D under P into atomic units u_1,...,u_n.
2. Build a balanced interval tree T using legal sentence/paragraph boundaries.
3. For each evaluator q_m, compute token surprisals once over the document.
4. Compute sentence embeddings once with E.
5. Traverse T bottom-up:
       a. serialize span x_v unambiguously;
       b. for each compressor, compute corrected self-rate;
       c. aggregate surprisal, structure, style, and semantic statistics;
       d. if v is internal, compute bidirectional sibling gains,
          NCD, order asymmetry, and multiscale contrasts;
       e. store F_v and metadata κ(v).
6. Return {T, F_v : v in V}.
```

### Algorithm 2: Calibration and localization

```text
INPUT:
    tree features {F_v}
    trained source estimator η_A
    trained quality estimator η_Q
    matched human calibration bank B_H
    family-wise level α

1. For every fixed node v:
       a. select calibration nodes matched on stratum and scale;
       b. compute source score Λ_hat_v and quality score S_hat_v;
       c. compute conformal p_v from the matched human scores;
       d. set α_v = α / ((D + 1) 2^{depth(v)});
       e. mark v significant if p_v <= α_v.
2. Construct the non-overlapping significant frontier F.
3. For each v in F, compute signed channel contributions and uncertainty.
4. Return a document score, per-unit score field, frontier intervals,
   and diagnostic explanations.
```

### 8.1 Complexity

**Proposition 5 (compression complexity).** Assume a balanced tree with \(n\) bytes, minimum leaf size \(m\), \(K\) compressors whose runtime is linear in input length, and a constant number of serializations per node. Then the total compression work is

\[
O\!\left(Kn\log_2\frac{n}{m}\right),
\tag{45}
\]

and the number of nodes is \(O(n/m)\).

*Proof.* At any depth, node spans partition the document, so their total length is \(O(n)\); bidirectional sibling concatenations also total \(O(n)\) up to a constant factor. There are \(O(\log(n/m))\) depths. Multiply by \(K\). \(\square\)

Caching code lengths avoids redundant calls. Surprisal and embeddings are computed once at token or sentence level and aggregated with prefix sums where the statistic permits it.

---

## 9. Fundamental limits and identifiable claims

### 9.1 Detectability ceiling

Let \(P_H\) and \(P_A\) be the complete distributions visible to a detector. Their total variation distance is

\[
\operatorname{TV}(P_H,P_A)
=\sup_{E\subseteq\mathcal X}|P_H(E)-P_A(E)|.
\tag{46}
\]

With equal priors, the minimum possible classification error over all measurable classifiers is

\[
R^*=\frac{1-\operatorname{TV}(P_H,P_A)}{2}.
\tag{47}
\]

Thus, if generated and human prose have the same observable distribution, no post hoc detector can outperform chance. Related bounds for AI-text detection are developed by Sadasivan et al. [8]. Hierarchical analysis can localize available signal; it cannot create information that is absent from the observed text.

### 9.2 What compression can identify

Compression features can identify *compressor-relative regularity*: repeated substrings, predictable byte contexts, dictionary reuse, and some morphosyntactic recurrence. They cannot, without additional representation, identify truth, originality of ideas, rhetorical necessity, author intention, or semantic equivalence.

### 9.3 Resolution–variance trade-off

Finer nodes improve spatial precision but contain less evidence. If \(\widehat\Lambda_v\) is an average of weakly dependent token contributions with finite long-run variance \(\sigma^2\), then its standard error is approximately \(O(n_v^{-1/2})\). Localization therefore has an unavoidable trade-off:

\[
\text{smaller span} \Rightarrow \text{higher spatial resolution and higher score variance}.
\tag{48}
\]

Tree smoothing, contextual features, and minimum span sizes reduce variance but blur boundaries. Evaluation must report performance by span length.

### 9.4 Dependence and pseudo-replication

Nodes from one document are not independent. Random node-level train/test splits leak author, prompt, topic, and neighboring text. All primary splits and bootstrap intervals must be grouped at the document and underlying-source level; when human judgments repeat passages or readers, the analysis must model both sources of clustering.

---

## 10. Experimental evaluation plan

### 10.1 Research questions

- **RQ1 — Detection:** Does hierarchical compression improve source discrimination beyond a global gzip ratio or NCD baseline?
- **RQ2 — Localization:** Does the multi-scale tree localize machine-written or anomalous spans more accurately than fixed windows and whole-document classifiers?
- **RQ3 — Diagnostic validity:** Do channel scores predict blinded human judgments of repetition, cliché, vagueness, rhythmic monotony, and overall quality?
- **RQ4 — Generalization:** Which signals survive held-out generators, domains, prompts, decoding schemes, time periods, and editing operations?
- **RQ5 — Calibration and fairness:** Are node and document scores calibrated, and are false-positive rates acceptably stable across declared human subgroups?
- **RQ6 — Usefulness:** Do localized explanations help editors improve prose quality without encouraging random novelty or degrading coherence?

### 10.2 Confirmatory hypotheses

The primary hypotheses should be preregistered:

- **H1:** A compression-tree model using only \(F^{\mathrm{cmp}}\) has higher held-out-generator AUROC than global gzip ratio, with a paired document-bootstrap 95% confidence interval for the difference excluding zero.
- **H2:** Full HMIT has higher token-level average precision than the best fixed-window baseline on mixed-authorship documents.
- **H3:** Full HMIT predicts reader-rated semantic redundancy better than compression-only HMIT, measured by held-out-document Spearman correlation or ordinal-regression log loss.
- **H4:** Domain- and scale-matched calibration reduces the worst-group human false-positive rate relative to unstratified calibration at the same aggregate true-positive rate.
- **H5:** No claimed improvement is accepted if it disappears when generators and underlying prompts are both held out.

### 10.3 Corpus construction

#### Human corpus

Sample human documents from verifiable, licensed sources created before widespread public LLM use when possible. Include professionally edited and unedited writing, but label them separately. The minimum design crosses:

- fiction, essays, journalism, academic prose, technical documentation, and informal discussion;
- narrative, dialogue, exposition, argument, and instruction;
- native and non-native English where ethically sourced and self-identification is available;
- multiple authors per domain, with no author crossing train and final test partitions.

Do not treat post-2022 web text as certainly human without provenance checks. Remove duplicates and near-duplicates *before* splitting.

#### Machine corpus

Generate matched documents from at least eight model families spanning open and closed systems, multiple sizes, and multiple release periods. Cross:

- greedy, low-temperature, moderate-temperature, nucleus, and repetition-penalized decoding;
- zero-shot, style-conditioned, outline-conditioned, and continuation prompts;
- raw output, lightly human-edited output, heavily edited output, and model-revised output;
- short and long contexts.

Prompts should be derived from held-out content specifications, not copied human passages. Save model identifier, version/date, decoding parameters, system prompt, user prompt, seed where available, and all revision operations.

#### Matched pairs and leakage prevention

Construct human/machine pairs matched on domain, topic specification, target length, register, and structural constraints. If several outputs share a prompt, source document, outline, or continuation prefix, they must remain in the same partition. Exact and MinHash-style deduplication should be applied across all partitions.

#### Recommended initial scale

An initial main corpus of 32,000 documents—2,000 human and 2,000 machine per domain across eight domains—provides room for grouped transfer tests. Generator families, authors, and prompts, rather than isolated spans, are the effective independent units; final sample sizes should be revised from a pilot using cluster-aware variance estimates.

### 10.4 Mixed-authorship localization corpus

Create controlled splices at legal sentence boundaries. For every source document, sample machine proportions from \(\{0.05,0.10,0.25,0.50,0.75\}\) and patterns including:

- one contiguous machine suffix;
- one contiguous internal insertion;
- several separated insertions;
- alternating human and machine paragraphs;
- machine draft followed by human revision;
- human draft followed by machine revision.

Match topics and discourse roles across the splice boundary so that trivial topic shifts do not solve the task. Include negative controls formed by splicing two human authors and two sections by the same human author. Ground truth is stored at character, token, sentence, and paragraph resolution.

### 10.5 Reader-rated quality corpus

Provenance labels cannot validate “slop.” Recruit blinded readers and editors to rate passages independently on anchored ordinal scales for:

1. exact or near-exact repetition;
2. semantic restatement without added information;
3. cliché or formulaic phrasing;
4. vagueness versus concrete specificity;
5. rhythmic and syntactic monotony;
6. unnecessary signposting;
7. coherence;
8. overall writing quality.

Readers also answer separate questions: “Which passage is machine-generated?” and “Which passage is better written?” Pair order and source are randomized. Estimate inter-rater reliability, retain disagreement rather than forcing a false consensus, and fit ordinal mixed-effects models with random intercepts for reader and passage.

### 10.6 Data partitions

Use five complementary evaluations:

1. **Matched in-domain:** held-out authors, prompts, and documents.
2. **Held-out generator:** one or more model families absent from training.
3. **Held-out domain:** an entire prose domain absent from training.
4. **Temporal transfer:** newer generators and later human text held out.
5. **Cross-edit transfer:** raw-generation training, edited-generation testing.

Model selection uses no final-test labels. Hyperparameters—including tree depth, leaf size, embedding horizon, and feature set—are selected on a grouped validation partition.

### 10.7 Baselines

Compare against:

- majority and length-only baselines;
- global gzip ratio;
- gzip NCD \(k\)-nearest neighbors [4];
- fixed non-overlapping and sliding windows at matched token budgets;
- character and word \(n\)-gram logistic regression;
- classical stylometric features;
- mean perplexity, token-rank features, and GLTR-style statistics [5];
- DetectGPT where source-model access assumptions hold [6];
- Binoculars [7];
- a fine-tuned transformer document classifier;
- a sequence-labeling or contextual localization model based on prior mixed-text work [9];
- human-only and machine-only reference-conditioned compressors.

Every baseline receives the same train/test documents and must be tuned without access to held-out generators or domains.

### 10.8 Ablations

At minimum, remove or vary:

- tree hierarchy versus same-count fixed windows;
- gzip header correction;
- bidirectional versus single-order joint compression;
- each feature channel in (26);
- reference matching variables;
- reference-conditioned versus self-compression features;
- one versus multiple evaluator language models;
- one versus multiple compressors;
- sentence-aligned versus paragraph-aligned versus token-balanced trees;
- minimum leaf sizes of 64, 128, 256, 512, and 1,024 tokens;
- supervised density-ratio estimation versus conformal anomaly scoring;
- unedited versus edited reference corpora.

The key ablation is not “does the full model win?” but “what incremental information does the tree add beyond length-matched windows and global aggregation?”

### 10.9 Metrics

#### Document detection

- AUROC and area under the precision–recall curve;
- true-positive rate at prespecified 0.1% and 1% human false-positive rates;
- balanced accuracy and Matthews correlation coefficient;
- Brier score, expected calibration error, and reliability curves;
- coverage and risk when abstention is allowed.

Threshold-free metrics are insufficient for high-stakes use; operating-point false-positive rates must be reported with confidence intervals.

#### Localization

- token- and sentence-level average precision;
- token AUROC as a secondary metric;
- intersection-over-union of predicted and true intervals;
- boundary mean absolute error in tokens and sentences;
- segment recall at IoU thresholds \(0.25,0.50,0.75\);
- over-segmentation and under-segmentation counts;
- performance stratified by true span length and machine proportion.

#### Quality and explanation

- Spearman correlation and ordinal log loss for each reader-rated defect;
- pairwise preference accuracy for overall quality;
- sufficiency: score change when the top diagnosed span is removed;
- stability: overlap of reported spans across harmless formatting perturbations;
- editor time, accepted-revision rate, and quality improvement in a blinded editing study.

#### Efficiency

- CPU/GPU time, peak memory, compressed bytes processed, and energy where measurable;
- scaling with document length and leaf size;
- marginal cost of each feature channel.

### 10.10 Statistical analysis

Use document- or source-cluster bootstrap confidence intervals. For comparisons, bootstrap paired differences because systems score the same items. For human ratings, use mixed-effects regression with crossed random effects for reader and passage. Report effect sizes and intervals, not only p-values. Control multiplicity within declared hypothesis families using Holm's method; label all remaining analyses exploratory.

For a simple reader discrimination test with independent binary judgments, detecting accuracy \(p_1\) against chance \(p_0=0.5\) with two-sided level \(\alpha\) and power \(1-\beta\) has the normal-approximation requirement

\[
n\approx
\frac{\left[z_{1-\alpha/2}\sqrt{p_0(1-p_0)}
+z_{1-\beta}\sqrt{p_1(1-p_1)}\right]^2}
{(p_1-p_0)^2}.
\tag{49}
\]

At \(\alpha=0.05\), power \(0.80\), and \(p_1=0.55\), equation (49) gives approximately 783 independent judgments. Repeated readers and passages reduce the effective sample size; inflate by a pilot-estimated design effect and analyze with the mixed model rather than a naive binomial test.

### 10.11 Robustness suite

Apply transformations that preserve meaning to varying degrees:

- Unicode normalization and whitespace changes;
- quote style, punctuation, and capitalization changes;
- spelling variants;
- sentence reordering where discourse permits;
- human copy-editing;
- model paraphrasing at several strengths;
- translation and back-translation;
- insertion of quotations, citations, lists, and code;
- deliberate repetition penalties and unusual decoding settings.

Report the transformation's effect on both detection and human-rated quality. A transformation that defeats a detector by destroying prose quality is not equivalent to one that preserves it. RAID provides precedent for evaluating model, domain, decoding, and adversarial variation [11].

### 10.12 Fairness and subgroup analysis

For every human subgroup with adequate, ethically sourced sample size, report:

\[
\operatorname{FPR}_g
=\Pr(\widehat Y=A\mid Y=H,G=g)
\tag{50}
\]

with confidence intervals, as well as worst-group FPR and FPR disparity. Prespecified groups may include language background, dialect, proficiency, domain, and assistive-tool use. Do not infer sensitive attributes from text for this purpose. A system fails the proposed deployment criterion if a subgroup's upper FPR confidence bound exceeds a preregistered tolerance, even when aggregate AUROC is high. The non-native-writer failures documented by Liang et al. make this a primary, not optional, analysis [12].

### 10.13 Editorial intervention study

To test usefulness rather than detector gaming, randomly assign drafts to:

1. no diagnostic;
2. document-level score only;
3. localized HMIT score without channel explanation;
4. localized HMIT score with channel explanation.

Editors revise under a time budget. Independent blinded readers then compare original and revised passages for quality and coherence. The primary endpoint is reader preference for the revision; secondary endpoints include editing time, change magnitude, and whether intentional motifs were incorrectly removed.

The revision model or editor must not optimize a differentiable detector score directly. Diagnostics identify where and why to inspect; they do not prescribe arbitrary synonym substitution or surprise injection.

### 10.14 Reproducibility checklist

Release, subject to licenses and privacy constraints:

- immutable corpus manifests and hashes;
- generation metadata and prompts;
- preprocessing and serialization code;
- compressor implementations, versions, flags, and dictionaries;
- evaluator and embedding checkpoints;
- tree configurations and feature schema;
- grouped split identifiers;
- preregistration, analysis scripts, and all seeds;
- raw predictions, abstentions, and confidence intervals;
- subgroup and failure-case reports.

---

## 11. Expected failure modes and mitigations

### 11.1 Compressor overhead on short spans

**Failure:** Headers and block decisions dominate leaf scores.  
**Mitigation:** subtract first-order overhead, calibrate by exact length/scale, set a minimum leaf size, and compare raw-stream or dictionary-capable compressor modes.

### 11.2 Finite gzip history

**Failure:** Repetition outside the 32 KiB DEFLATE history is invisible to ordinary joint compression [3].  
**Mitigation:** use explicit pairwise paragraph comparisons, reorder only in a separate diagnostic, add longer-context compressors, or maintain a nonlocal NCD graph alongside the interval tree.

### 11.3 Surface-form blindness

**Failure:** Paraphrases express the same proposition with few shared bytes.  
**Mitigation:** semantic novelty and proposition-overlap channels; preserve the compression channel as an interpretable indicator of literal reuse.

### 11.4 Topic and genre confounding

**Failure:** Technical manuals, romance dialogue, or legal templates differ in compressibility for reasons unrelated to source.  
**Mitigation:** domain matching, held-out-domain tests, conditional calibration, topic-masked ablations, and abstention outside support.

### 11.5 Intentional repetition

**Failure:** Refrains, motifs, parallelism, and pedagogical recap are flagged as defects.  
**Mitigation:** separate descriptive anomaly from quality judgment, present context to editors, and include high-quality repetitive human prose as a hard negative.

### 11.6 Evaluator-model dependence

**Failure:** Surprisal scores reflect the evaluator's training data and tokenizer.  
**Mitigation:** ensemble heterogeneous evaluators, record versions, report sensitivity, and retain model-free channels.

### 11.7 Generator and time drift

**Failure:** A classifier learns artifacts of known generators and fails on later systems.  
**Mitigation:** held-out-family and temporal splits, continual recalibration, and explicit expiration dates for operational thresholds.

### 11.8 Editing and paraphrase

**Failure:** Small revisions erase source cues while leaving quality unchanged, or change quality while retaining cues.  
**Mitigation:** treat editing as a continuum, evaluate transformation severity, and avoid categorical authorship claims.

### 11.9 Goodhart effects

**Failure:** Direct optimization produces gratuitous rarity, erratic rhythm, or incoherent novelty that lowers the detector score.  
**Mitigation:** use scores for localization and diagnosis, constrain revisions by meaning and quality, keep a blinded human endpoint, and periodically rotate unreleased audit sets.

### 11.10 Reference contamination

**Failure:** “Human” web corpora contain generated text or training/test documents appear in evaluator pretraining.  
**Mitigation:** prefer verified pre-LLM sources, audit provenance, deduplicate, document uncertainty, and repeat core tests on controlled newly written material.

---

## 12. Falsification criteria

The method should be considered unsupported for a claimed use if any primary condition holds:

1. The tree does not improve held-out localization over equal-budget fixed windows.
2. Compression gains vanish after exact matching on length, domain, and formatting.
3. Performance collapses to chance on held-out generator families while in-domain performance remains high.
4. Reader-rated quality is uncorrelated with the proposed defect scores.
5. Explanations are unstable under harmless formatting changes.
6. Worst-group human false-positive rates exceed the preregistered tolerance.
7. Editors using the diagnostic do not improve blinded quality or instead damage coherence and intentional style.
8. A length-only or topic-only baseline accounts for the reported gain.

Negative outcomes remain informative. They would show that compression is a limited descriptive channel rather than a robust localization instrument.

---

## 13. Ethical and deployment constraints

HMIT should be designed as a prose diagnostic, not an accusation engine. A high score means “unusual relative to these declared references under these features.” It does not mean “this person cheated,” “this passage was certainly generated,” or “this prose is bad.”

Deployment should satisfy the following minimum conditions:

- show the reference population and calibration date;
- expose uncertainty and abstain outside supported strata;
- provide span-level reasons rather than a naked percentage;
- never use a score as sole evidence in education, employment, publishing, or discipline;
- give affected writers access to the text, method summary, and appeal process;
- monitor subgroup false-positive rates;
- retain provenance logs when genuine attribution matters;
- prefer cryptographic provenance or cooperative watermarking when those are available and appropriate.

The term *slop* should be avoided in interfaces shown to authors. A diagnostic should name observable concerns—such as “high semantic restatement with low sentence-length variation”—rather than assign a pejorative identity.

---

## 14. Discussion

The original compression-tree idea is valid in a bounded sense. Its strongest contribution is not a universal AI detector, but a cheap, model-independent means of asking *where* reusable surface structure appears and *at what scale*. The joint compression term is more informative than isolated compression ratios because it measures cross-region reuse. A tree makes this signal local and interpretable.

The decisive extension is to represent prose as a multichannel field. Exact phrase recurrence, semantic restatement, token surprise, sentence rhythm, syntax, and discourse structure live in different representations. Collapsing them into one raw score discards the very explanation an editor needs. Conversely, preserving the vector at every scale allows a statement such as:

> Paragraphs 14–19 are anomalous relative to matched edited fantasy prose because semantic novelty falls to the 3rd percentile and sentence-length variation to the 5th percentile, while byte-level repetition remains ordinary.

That statement is testable and actionable. “AI probability: 73%” is usually neither.

The framework also clarifies why a reference corpus is more important than a clever scalar formula. Variation among human genres, authors, dialects, and intentions can exceed the difference between human and machine samples. The scientifically defensible target is therefore not resemblance to an undifferentiated human population, but fit to a declared distribution such as professionally edited human prose in the intended genre and scene type.

Finally, successful revision and successful evasion are not synonymous. The end criterion for a writing system should combine low blind authorship discrimination with equal or better reader-rated quality. If a system becomes harder to detect by inserting noise, rare words, or arbitrary syntactic variation, it has optimized the metric while failing the writing task.

---

## 15. Conclusion

Hierarchical compression analysis is a defensible component of a text-quality and machine-text localization system, provided its claims are narrow. Corrected self-compression describes local surface regularity; cross-child compression gain approximates shared information; reference-conditioned code length compares fit to declared corpora; and a tree localizes these effects across scale. Adding surprisal, multiscale energy, structure, and semantic novelty produces a richer object: the multi-scale information texture of prose.

The framework's mathematical interpretation is strongest for ideal codes and declared source models. gzip is an approximation with severe finite-window and surface-form limitations. Accordingly, the proposed system must be evaluated under held-out generators and domains, calibrated at low false-positive rates, audited across human subgroups, and validated against direct reader judgments. Its proper output is a ranked, uncertainty-aware map of spans and contributing signals—not a verdict about who wrote them.

---

## Appendix A. Compact notation

| Symbol | Meaning |
|---|---|
| \(D=(u_1,\ldots,u_n)\) | document as atomic units |
| \(T(D)\) | boundary-respecting binary interval tree |
| \(I_v\) | interval represented by node \(v\) |
| \(C(x)\) | complete compressed length in bits |
| \(C_0(x)\) | first-order header-corrected length |
| \(\rho_C(x)\) | self-compression rate |
| \(G_C(y\leftarrow x)\) | directional reuse gain |
| \(J_C(x,y)\) | symmetric sibling gain |
| \(R_C(x,y)\) | normalized sibling coupling |
| \(A_C(x,y)\) | compression order asymmetry |
| \(s_i\) | token surprisal under evaluator \(q\) |
| \(w_v\) | tree-Haar coefficient |
| \(F_v\) | multi-channel feature vector at node \(v\) |
| \(\Lambda_{A/H}\) | machine-versus-human log-density ratio |
| \(S_Q\) | expected reader-rated quality-defect score |
| \(p_v\) | conformal human-null p-value for node \(v\) |

---

## Appendix B. Minimum viable prototype

A falsifiable first implementation can be smaller than the full study:

1. Sentence-segment 4,000 matched documents from one genre: 2,000 verified human and 2,000 generated.
2. Split by author, prompt, and generator family.
3. Build paragraph-aligned balanced trees with 128-token minimum leaves.
4. Compute gzip \(\rho_C\), \(R_C\), \(A_C\), sibling NCD, sentence-length moments, and surprisal Haar energies.
5. Compare global gzip, fixed windows, compression-only trees, and full trees.
6. Construct 1,000 controlled mixed documents and report token average precision, IoU, and boundary error.
7. Obtain blinded defect ratings for a stratified subset.
8. Stop or redesign if tree features fail the held-out-generator and length-matched tests.

This prototype tests the central claim without requiring a production detector.

---

## References

1. Shannon, C. E. (1948). [A Mathematical Theory of Communication](https://doi.org/10.1002/j.1538-7305.1948.tb00917.x). *Bell System Technical Journal*, 27, 379–423 and 623–656.
2. Cilibrasi, R., & Vitányi, P. M. B. (2005). [Clustering by Compression](https://doi.org/10.1109/TIT.2005.844059). *IEEE Transactions on Information Theory*, 51(4), 1523–1545. [Open preprint](https://arxiv.org/abs/cs/0312044).
3. Deutsch, P. (1996). [DEFLATE Compressed Data Format Specification version 1.3](https://www.rfc-editor.org/rfc/rfc1951.html). RFC 1951.
4. Jiang, Z., Yang, M., Tsirlin, M., Tang, R., Dai, Y., & Lin, J. (2023). [“Low-Resource” Text Classification: A Parameter-Free Classification Method with Compressors](https://aclanthology.org/2023.findings-acl.426/). *Findings of ACL 2023*, 6810–6828.
5. Gehrmann, S., Strobelt, H., & Rush, A. (2019). [GLTR: Statistical Detection and Visualization of Generated Text](https://aclanthology.org/P19-3019/). *ACL 2019 System Demonstrations*, 111–116.
6. Mitchell, E., Lee, Y., Khazatsky, A., Manning, C. D., & Finn, C. (2023). [DetectGPT: Zero-Shot Machine-Generated Text Detection Using Probability Curvature](https://proceedings.mlr.press/v202/mitchell23a.html). *Proceedings of ICML 2023*, 24950–24962.
7. Hans, A., Schwarzschild, A., Cherepanova, V., Kazemi, H., Saha, A., Goldblum, M., Geiping, J., & Goldstein, T. (2024). [Spotting LLMs With Binoculars: Zero-Shot Detection of Machine-Generated Text](https://proceedings.mlr.press/v235/hans24a.html). *Proceedings of ICML 2024*, 17519–17537.
8. Sadasivan, V. S., Kumar, A., Balasubramanian, S., Wang, W., & Feizi, S. (2023). [Can AI-Generated Text Be Reliably Detected?](https://arxiv.org/abs/2303.11156). arXiv:2303.11156.
9. Zhang, Z., Qin, W., & Plummer, B. (2024). [Machine-Generated Text Localization](https://aclanthology.org/2024.findings-acl.495/). *Findings of ACL 2024*, 8357–8371.
10. Wang, Y., et al. (2024). [SemEval-2024 Task 8: Multidomain, Multimodel and Multilingual Machine-Generated Text Detection](https://aclanthology.org/2024.semeval-1.279/). *SemEval 2024*, 2057–2079.
11. Dugan, L., Hwang, A., Trhlík, F., Zhu, A., Ludan, J. M., Xu, H., Ippolito, D., & Callison-Burch, C. (2024). [RAID: A Shared Benchmark for Robust Evaluation of Machine-Generated Text Detectors](https://aclanthology.org/2024.acl-long.674/). *ACL 2024*, 12463–12492.
12. Liang, W., Yuksekgonul, M., Mao, Y., Wu, E., & Zou, J. (2023). [GPT Detectors Are Biased Against Non-Native English Writers](https://doi.org/10.1016/j.patter.2023.100779). *Patterns*, 4(7), 100779.
13. Reimers, N., & Gurevych, I. (2019). [Sentence-BERT: Sentence Embeddings Using Siamese BERT-Networks](https://aclanthology.org/D19-1410/). *EMNLP-IJCNLP 2019*, 3982–3992.
14. Kirchenbauer, J., Geiping, J., Wen, Y., Katz, J., Miers, I., & Goldstein, T. (2023). [A Watermark for Large Language Models](https://proceedings.mlr.press/v202/kirchenbauer23a.html). *Proceedings of ICML 2023*, 17061–17084.

