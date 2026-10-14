// STUB (owner: Map agent). Replace with the real scrubber. See design/DESIGN.md §5.1 and §8.
export type TimeScrubberProps = {
  year: number;
  onYear: (y: number) => void;
  counts: (number | null)[] | null;
  mode: "plot" | "region";
  label: string;
  onProof?: () => void;
};
const YEARS = Array.from({ length: 25 }, (_, i) => 2001 + i);
export default function TimeScrubber({ year, onYear, counts, label }: TimeScrubberProps) {
  return (
    <section aria-label={label}>
      {YEARS.map((y, i) => (
        <button key={y} aria-pressed={y === year} onClick={() => onYear(y)}>
          {y} {counts?.[i] ?? "–"}
        </button>
      ))}
    </section>
  );
}
