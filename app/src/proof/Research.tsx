import { Chip } from "../components/Primitives";

/**
 * What was tried, what lost and what was kept. Summaries of the retained research
 * reports (docs/HANDOVER.md section 5-6, docs/lab/results-index.md). These are
 * SEPARATE studies with their own inputs and timings, so none of their figures are
 * mixed into the frozen run measured above.
 */
const items: { title: string; status: string; body: string; docs: string[] }[] = [
  {
    title: "Learned codec selector",
    status: "Rejected",
    body: "On a held-out spatial split, the learned joint selector (811,164 B) lost to a fixed custom option (810,764 B) and to a fixed optimized standard GeoTIFF (806,058 B). Not used in production; the experiment and its losing result are kept.",
    docs: ["docs/lab/engine-selector-report.md", "docs/lab/engine-selector-review.md"],
  },
  {
    title: "Indexed custom reads",
    status: "Kept full preload",
    body: "The indexed window reader was slower than the original under the implemented cache and integrity policy (repeated chunk decode and hash work). The small demo region keeps a full preload; the slower result is preserved.",
    docs: ["docs/lab/research-methodology.md", "docs/lab/engine-report.md"],
  },
  {
    title: "Footprint-overlap rule",
    status: "Production unchanged",
    body: "Counting any cell whose footprint overlaps the parcel adds 337 plot/cell memberships and changes 5 period flags compared with the centre rule. Original and compact still agree 17/17 under both. It does not explain the five supplier 2021–23 indications, so production stays centre-rule.",
    docs: ["docs/lab/engine-spatial-sensitivity-report.md"],
  },
  {
    title: "Hansen 2023 v1.11 vintage",
    status: "No 2021–23 change",
    body: "A preregistered comparison against the official Hansen 2023 v1.11 release left every shared 2021–23 count and flag unchanged across the 17 plots. The supplier’s actual release is unknown, so this rules out one explanation, not all.",
    docs: ["docs/lab/engine-vintage-report.md"],
  },
  {
    title: "JRC standard-format study",
    status: "Research only",
    body: "On the JRC 2020 chip a standard one-bit GeoTIFF is smaller (19,901 B vs 21,459 B custom, 7.26%), while the custom store loads faster and uses less peak memory. No production adapter, and not comparable with the Hansen percentages.",
    docs: ["docs/lab/engine-jrc-standard-report.md"],
  },
  {
    title: "Independent validation catches",
    status: "Fixed",
    body: "Independent review found null shown as zero in the UI, false equality rendering, off-plot corruption hidden by plot-only comparison, forged-but-rehashed receipts and measurements, intermediate timed answers accepted, and stale live responses. Each fix keeps a positive and a negative check.",
    docs: ["docs/lab/validator-report.md", "docs/lab/validator-jrc-report.md", "docs/lab/validator-strong-spatial-report.md"],
  },
];

export default function Research() {
  return (
    <details className="pl-disclosure proof-research">
      <summary>
        Research: what was tried, kept and rejected <span className="pl-disclosure__meta">{items.length} studies</span>
      </summary>
      <div className="pl-disclosure__body">
        <p className="pl-fine">
          Separate studies with their own inputs and timings, summarised from the reports. None of these figures belong to the
          frozen run above.
        </p>
        <ul className="proof-research__list">
          {items.map((it) => (
            <li key={it.title}>
              <div className="proof-research__title">
                <strong>{it.title}</strong>
                <Chip>{it.status}</Chip>
              </div>
              <p>{it.body}</p>
              <p className="proof-research__docs">
                {it.docs.map((d) => (
                  <code key={d}>{d}</code>
                ))}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}
