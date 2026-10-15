import { useId } from "react";
import { Icon } from "../components/Primitives";
import ReceiptDetails from "../ReceiptDetails";
import type { Demo, Plot } from "../types";
import { useModalDialog } from "./dom";

function download(name: string, value: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function JsonDetails({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="pl-disclosure pl-receipt-json">
      <summary>{title}</summary>
      <div className="pl-disclosure__body">
        <pre>{value == null ? "Unavailable — not computed or supplied." : JSON.stringify(value, null, 2)}</pre>
      </div>
    </details>
  );
}

/** Evidence receipt for one plot: readable summary, raw JSON, and the exact JSON download. */
export default function ReceiptDialog({ data, plot, year, onClose }: {
  data: Demo;
  plot: Plot;
  year: number;
  onClose: () => void;
}) {
  const dialog = useModalDialog(onClose);
  const title = useId();
  return (
    <dialog className="pl-dialog pl-dialog--receipt" aria-labelledby={title} {...dialog}>
      <div className="pl-dialog__head">
        <div className="pl-receipt-head">
          <span className="pl-eyebrow">Evidence receipt</span>
          <h2 id={title}>{plot.plot_id} evidence receipt</h2>
          <p>A reproducibility record, not a certification. Hashes identify local integrity; they are not signatures.</p>
        </div>
        <button type="button" className="pl-btn pl-btn--ghost pl-btn--icon" aria-label="Close dialog" onClick={onClose}>
          <Icon name="close" />
        </button>
      </div>
      <div className="pl-dialog__body">
        <div>
          <button
            type="button"
            className="pl-btn pl-btn--primary"
            onClick={() =>
              download(`${plot.plot_id}-receipt.json`, {
                schema_version: data.schema_version,
                plot_id: plot.plot_id,
                receipt: plot.receipt,
                supplier: plot.supplier,
                comparison: plot.comparison,
              })
            }
          >
            <Icon name="download" size={16} />
            Download receipt JSON
          </button>
        </div>
        <ReceiptDetails data={data} plot={plot} year={year} />
        <div className="pl-receipt-raw">
          <JsonDetails title="Hashes, grid and source provenance" value={plot.receipt} />
          <JsonDetails title="Exact supplier CSV fields" value={plot.supplier} />
          <JsonDetails title="Dataset metadata" value={data.dataset} />
          <JsonDetails title="Evidence limitations" value={data.limitations} />
        </div>
      </div>
    </dialog>
  );
}
