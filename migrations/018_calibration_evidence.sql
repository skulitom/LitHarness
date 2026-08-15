-- What a calibration's numbers are *about*, and the population a corpus threshold came from.
--
-- 014 recorded numbers and 015 recorded the denominator one of them is computed over. Neither
-- recorded the **referent**, and that omission is why corpus evidence has never been refused
-- here: a percentile over 13,000 strangers' chapters fills `holdout_size`, `precision`,
-- `threshold` and `verdicts_digest` without any single column being false, and the row as a
-- whole still claims a metric predicts what a reader said about prose this system wrote.
-- `why_not_promotable` checked seven things and not one of them was provenance.
--
-- **`evidence_class` is NOT NULL with a default of 'unclassified', which breaks 015's
-- nullable precedent on purpose.** 015 argued that a row written before its column existed
-- genuinely does not know its flagged count, so inventing a default would turn "unrecorded"
-- into a number. The same argument reaches the opposite conclusion here, because the two
-- defaults point in opposite directions: NULL flagged is *refused* by the domain, so it is
-- the safe direction; a NULL class would have to be interpreted, and every interpretation
-- except "refuse" is a guess that admits evidence nobody labelled. 'unclassified' is not an
-- invented measurement — it is the refusing direction, spelled so the refusal can name
-- itself instead of arriving as a NULL check.
--
-- The table is empty in every installation (`litharness calibrations` prints nothing
-- anywhere), so this is the last moment a required field costs nothing.
ALTER TABLE calibrations ADD COLUMN evidence_class TEXT NOT NULL DEFAULT 'unclassified';

-- The unit the label is attached to. A craft gate refuses a scene, so evidence whose label
-- describes a whole story refuses nothing here however large its sample — which is the
-- ecological fallacy made checkable rather than warned about. `followers / total_views`, the
-- revealed-preference label PLAN.md §20 action 10 calls the critical path for §1a, is
-- story-grain and therefore cannot promote a scene gate. That concession was already written
-- in plan/craft-corpus.md §4.1 and enforced nowhere.
ALTER TABLE calibrations ADD COLUMN grain TEXT NOT NULL DEFAULT 'unit';

-- The reference distribution a population threshold was read out of, and the control measured
-- beside it in the same pass. All nullable: they are present iff `evidence_class` is
-- 'population', and the domain refuses a population row that lacks them.
--
-- `control_cohort`, `control_n` and `control_exceedance` are the point of the whole block.
-- research/quality-measurement/BRIEF.md §2's rule is "compute the control in the same pass",
-- and its worked example is `tricolon_rate` — 0.629 against pre-2023 prose, which reads as
-- this project's first working AI-tell detector for exactly as long as it takes to notice the
-- 0.606 beside it. Storing the control as columns is that rule expressed as a schema instead
-- of as a habit: a population calibration that omits it cannot be recorded, so the number
-- cannot exist without the thing that refutes it.
ALTER TABLE calibrations ADD COLUMN population_cohort TEXT;
ALTER TABLE calibrations ADD COLUMN population_band TEXT;
ALTER TABLE calibrations ADD COLUMN population_quantile TEXT;
ALTER TABLE calibrations ADD COLUMN population_reference_n INTEGER;
ALTER TABLE calibrations ADD COLUMN population_tail_support INTEGER;
ALTER TABLE calibrations ADD COLUMN population_control_cohort TEXT;
ALTER TABLE calibrations ADD COLUMN population_control_n INTEGER;
ALTER TABLE calibrations ADD COLUMN population_reference_exceedance REAL;
ALTER TABLE calibrations ADD COLUMN population_control_exceedance REAL;
ALTER TABLE calibrations ADD COLUMN population_profile_digest TEXT;
