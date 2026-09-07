// The whole-book debugging read (stage-0, first whole-volume draw, 2026-09-07): six lens
// readers over one drafted arc, one skeptic per finding with the text in hand, one harvest.
// Descriptions, never scores; the harvest is a diagnostic for a person and nothing in it
// becomes a prompt, directive, finding or plan item (§97.1). Every agent runs on Opus and the
// fan-out is capped (Artem, 2026-09-07). Invoke with Workflow({name: 'volume-arc-review',
// args: {...}}); tools/arc_review_args.py writes the args from a run folder.
export const meta = {
  name: 'volume-arc-review',
  description: 'Read one drafted arc of a LitRPG serial through six lenses on Opus, refute the strongest findings against the text, and harvest what survives',
  phases: [
    { title: 'Read', detail: 'six lens readers over the whole arc, at most ten findings each', model: 'opus' },
    { title: 'Refute', detail: 'one skeptic per finding, at most forty findings', model: 'opus' },
    { title: 'Harvest', detail: 'one synthesis, descriptions not scores', model: 'opus' },
  ],
}

// args: { title, arc, chapters: [{chapter, path}], concept, listing, worldSummary, priorHarvest, debts }
// `debts`: the concept's named debts with due scenes, as one string, for the promises lens.
const MODEL = 'opus'
const MAX_PER_LENS = 10
const MAX_REFUTE = 40
const chapterList = args.chapters.map(c => `- Chapter ${c.chapter}: ${c.path}`).join('\n')

const FINDINGS = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          family: { type: 'string' },
          title: { type: 'string' },
          chapters: { type: 'array', items: { type: 'integer' } },
          quote: { type: 'string' },
          claim: { type: 'string' },
          why_a_reader_hits_it: { type: 'string' },
          severity: { type: 'string', enum: ['breaks-the-story', 'reader-notices', 'minor'] },
        },
        required: ['family', 'title', 'chapters', 'quote', 'claim', 'why_a_reader_hits_it', 'severity'],
      },
    },
    what_works: { type: 'array', items: { type: 'string' } },
  },
  required: ['findings', 'what_works'],
}

const VERDICT = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    reason: { type: 'string' },
    evidence_quote: { type: 'string' },
  },
  required: ['refuted', 'reason'],
}

const common = `You are reading arc ${args.arc} of a LitRPG serial, *${args.title}*, as a careful editor.
Read EVERY chapter file below in full with the Read tool before you answer (plain text, ~2,000 words each):
${chapterList}

The book's settled concept (what the writer intended):
${args.concept}

The listing readers were sold:
${args.listing}

The world the Architect declared (summary):
${args.worldSummary}

${args.priorHarvest ? `Findings already harvested from earlier arcs (do not repeat them; do report if they recur or are resolved):\n${args.priorHarvest}` : ''}

Rules for findings: at most ${MAX_PER_LENS}, the ones a reader would actually hit, ordered most serious first. Every finding carries a verbatim quote (under 25 words) from a chapter and the chapter numbers involved. Describe; do not score. A finding is a place where two parts of the book disagree, where a reader loses the thread, or where the story asserts something it has not earned. If the lens finds nothing, return an empty list and say what works instead.`

const LENSES = [
  { key: 'plot', prompt: `${common}\n\nLENS: PLOT LOGIC. Causality and motivation scene to scene: does each scene follow from the last, do characters act on what they know and want, are stakes clear and consequences kept, are there events with no setup or setups with no consequence, does the arc close on something?` },
  { key: 'world', prompt: `${common}\n\nLENS: WORLD AND SYSTEM RULES. The book's declared systems, ladders, grants, currencies, timers and threats: is each rule stated the same way every time it appears, are numbers consistent (seconds, Credit, Marks), is anything used before it is granted or paid for, does the status line agree with the prose around it, does a rule stated in one chapter get broken silently in another?` },
  { key: 'cast', prompt: `${common}\n\nLENS: CHARACTER CONTINUITY. Every named person: who they are, what they know, where they are, whether the dead stay dead and the filed stay filed, whether names/roles/descriptions drift, whether a character vanishes without the story noticing or appears without introduction, whether anyone acts out of character without cause. Head counts included.` },
  { key: 'time', prompt: `${common}\n\nLENS: TIME AND PLACE. Clock times, night/day, elapsed durations, the geography of the storage yard and beyond: does the timeline run in one direction, do durations add up, can a reader draw the map, does anyone teleport between scenes?` },
  { key: 'debts', prompt: `${common}\n\nLENS: PROMISES AND PAYOFFS. What the book set up (mysteries, threats, named debts from the concept: ${args.debts || 'see the concept'}), and whether each is remembered, advanced, paid, or dropped. Also payoffs with no setup.` },
  { key: 'reader', prompt: `${common}\n\nLENS: THE READER'S EXPERIENCE. Popcorn LitRPG readership, 20-30, reading on a phone: where does a reader get lost, bored, or confused; where is exposition dumped; where does the prose slip register; where is the System's voice inconsistent; which sentences and similes repeat across chapters; what would make them stop reading? Name the exact passages.` },
]

phase('Read')
const reads = (await parallel(LENSES.map(l => () =>
  agent(l.prompt, { label: `read:${l.key}`, phase: 'Read', schema: FINDINGS, model: MODEL })
))).filter(Boolean)

const all = reads.flatMap((r, i) => (r.findings || []).slice(0, MAX_PER_LENS).map(f => ({ ...f, lens: LENSES[i].key })))
const seen = new Set()
const unique = []
for (const f of all) {
  const key = `${(f.chapters || []).join(',')}|${(f.quote || '').slice(0, 40).toLowerCase()}`
  if (seen.has(key)) continue
  seen.add(key)
  unique.push(f)
}
const rank = { 'breaks-the-story': 0, 'reader-notices': 1, 'minor': 2 }
unique.sort((a, b) => (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3))
const toVerify = unique.slice(0, MAX_REFUTE)
const unverified = unique.slice(MAX_REFUTE)
log(`${all.length} findings from ${reads.length} lenses, ${unique.length} after dedupe, ${toVerify.length} sent to refutation, ${unverified.length} carried unverified`)

phase('Refute')
const judged = (await parallel(toVerify.map(f => () =>
  agent(`${common}\n\nA reader claimed the following defect. Your job is to REFUTE it against the text: read the chapters named (and neighbours if needed) and say whether the text actually contains the problem as stated. Default to refuted=true if the quote is not in the text, if the claim misreads the passage, if the story itself explains it within the arc, or if it is a matter of taste rather than a disagreement in the text. Quote the passage that decides it.\n\nCLAIM (${f.lens} lens, ${f.family}, ${f.severity}): ${f.title}\nChapters: ${f.chapters.join(', ')}\nQuote: "${f.quote}"\nClaim: ${f.claim}\nWhy a reader hits it: ${f.why_a_reader_hits_it}`,
    { label: `refute:${f.lens}:${f.title.slice(0, 30)}`, phase: 'Refute', schema: VERDICT, model: MODEL })
    .then(v => ({ ...f, verdict: v, survives: !!v && !v.refuted }))
))).filter(Boolean)
const survivors = judged.filter(j => j.survives)
log(`${survivors.length} of ${judged.length} findings survive refutation`)

phase('Harvest')
const harvest = await agent(`${common}\n\nWrite the DEFECT HARVEST for arc ${args.arc} as Markdown. Header it "DEFECT HARVEST — arc ${args.arc} — descriptions, not scores; n is one; nothing here becomes a prompt". Group the surviving findings below by family (plot / world-rules / cast / time-place / debts / reader), each as a bullet with chapters, the quote, the claim in one sentence, and the skeptic's note in one clause. Then a section "Refuted" listing the refuted claims in one line each with why. Then "Unverified" listing findings that were not sent to a skeptic, one line each. Then "What works" in five bullets drawn from the readers. Then "What the next arc must carry": open debts and threads a continuation must remember, as a list a planner could read. Be concrete; no praise inflation; no numbers in prose except chapter numbers.\n\nSURVIVING FINDINGS:\n${JSON.stringify(survivors, null, 1)}\n\nREFUTED:\n${JSON.stringify(judged.filter(j => !j.survives).map(j => ({ title: j.title, lens: j.lens, chapters: j.chapters, verdict: j.verdict })), null, 1)}\n\nUNVERIFIED:\n${JSON.stringify(unverified.map(f => ({ title: f.title, lens: f.lens, chapters: f.chapters, severity: f.severity })), null, 1)}\n\nWHAT WORKS (from the readers):\n${JSON.stringify(reads.flatMap(r => r.what_works || []), null, 1)}`,
  { label: 'harvest', phase: 'Harvest', model: MODEL })

return { arc: args.arc, findings: survivors, refuted: judged.filter(j => !j.survives).length, unverified: unverified.length, harvest }
