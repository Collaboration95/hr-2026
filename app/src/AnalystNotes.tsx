import { useId, useState } from 'react';
import { Icon } from './components/Primitives';
import './styles/notes.css';

type Props = { plotId: string; contextKey: string };
type Draft = {
  plotId: string;
  text: string;
  savedText: string;
  savedAt: string | null;
  storageIssue: string;
};
type SavedNote = {
  schema_version: 'plotline.analyst-note.v1';
  plot_id: string;
  context_key: string;
  text: string;
  saved_at: string;
};

// Survives plot switches and declaration unmounts, but never persists unsaved text.
const drafts = new Map<string, Draft>();
const limit = 4000;
const storageKey = ({ plotId, contextKey }: Props) =>
  `plotline:analyst-note:v1:${JSON.stringify([contextKey, plotId])}`;

function loadDraft(key: string, { plotId, contextKey }: Props): Draft {
  const existing = drafts.get(key);
  if (existing) return existing;
  const draft: Draft = { plotId, text: '', savedText: '', savedAt: null, storageIssue: '' };
  try {
    const raw = window.localStorage.getItem(key);
    if (raw !== null) {
      const note: unknown = JSON.parse(raw);
      if (typeof note !== 'object' || note === null ||
        !('schema_version' in note) || note.schema_version !== 'plotline.analyst-note.v1' ||
        !('plot_id' in note) || note.plot_id !== plotId ||
        !('context_key' in note) || note.context_key !== contextKey ||
        !('text' in note) || typeof note.text !== 'string' || note.text.length > limit ||
        !('saved_at' in note) || typeof note.saved_at !== 'string' || !Number.isFinite(Date.parse(note.saved_at))) {
        throw new Error('Invalid saved note');
      }
      draft.text = draft.savedText = note.text;
      draft.savedAt = note.saved_at;
    }
  } catch {
    draft.storageIssue = 'The saved note could not be read. Browser storage may be unavailable or the note may be damaged. Nothing has been overwritten. You can write and export a draft; Save will try browser storage again.';
  }
  drafts.set(key, draft);
  return draft;
}

/** Local annotation only. contextKey must identify the exact supplier row. */
export default function AnalystNotes(props: Props) {
  const key = storageKey(props);
  // A fresh editor instance prevents a prop change from briefly showing another plot's text.
  return <NoteEditor key={key} {...props} noteKey={key} />;
}

function NoteEditor({ plotId, contextKey, noteKey }: Props & { noteKey: string }) {
  const id = useId();
  const [draft, setDraft] = useState(() => loadDraft(noteKey, { plotId, contextKey }));
  const [feedback, setFeedback] = useState('');
  const dirty = draft.text !== draft.savedText;
  const otherDrafts = [...drafts.entries()].filter(([key, value]) => key !== noteKey && value.text !== value.savedText);
  const update = (next: Draft) => { drafts.set(noteKey, next); setDraft(next); };

  function save() {
    const savedAt = new Date().toISOString();
    const note: SavedNote = { schema_version: 'plotline.analyst-note.v1', plot_id: plotId, context_key: contextKey, text: draft.text, saved_at: savedAt };
    try {
      window.localStorage.setItem(noteKey, JSON.stringify(note));
      update({ ...draft, savedText: draft.text, savedAt, storageIssue: '' });
      setFeedback(draft.text.length ? 'Note saved in this browser.' : 'Note cleared and saved in this browser.');
    } catch {
      update({ ...draft, storageIssue: 'Save failed. Browser storage is unavailable or full. Your draft remains in this tab; export it before refreshing or closing.' });
      setFeedback('');
    }
  }

  function exportNote() {
    let url: string | undefined;
    try {
      const payload = {
        schema_version: 'plotline.analyst-note.v1',
        annotation_type: 'local_analyst_note',
        plot_id: plotId,
        context_key: contextKey,
        text: draft.text,
        saved_locally: !dirty && draft.savedAt !== null,
        saved_at: dirty ? null : draft.savedAt,
        exported_at: new Date().toISOString(),
      };
      url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2) + '\n'], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `${plotId.replace(/[^a-zA-Z0-9_-]/g, '_')}-analyst-note.json`;
      document.body.append(link);
      link.click();
      link.remove();
      setFeedback(dirty ? 'Draft export requested. The draft is still unsaved in this browser.' : 'Note export requested.');
    } catch {
      setFeedback('Export could not start. Copy the text below to keep it.');
    } finally {
      if (url) { const downloadUrl = url; window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000); }
    }
  }

  return <section className="pl-notes" aria-labelledby={`${id}-heading`}>
    <div className="pl-notes__heading"><h3 id={`${id}-heading`}>Analyst question</h3><span>Local-only annotation</span></div>
    <p className="pl-notes__scope" id={`${id}-scope`}>For {plotId} and this supplier record. Kept in this browser; not sent or added to source evidence.</p>
    {otherDrafts.length > 0 && <p className="pl-notes__warning" role="status">Unsaved drafts retained for {Array.from(new Set(otherDrafts.map(([, value]) => value.plotId))).join(', ')} (other plots or supplier versions). Return to that record to save. Refreshing or closing loses unsaved drafts.</p>}
    <label htmlFor={`${id}-text`}>Question or observation</label>
    <textarea id={`${id}-text`} value={draft.text} maxLength={limit} rows={4}
      aria-describedby={`${id}-scope ${id}-limit ${id}-state`}
      onChange={event => { update({ ...draft, text: event.target.value.slice(0, limit) }); setFeedback(''); }} />
    <div className="pl-notes__meta"><span id={`${id}-state`}>{dirty ? 'Unsaved draft · Save before refreshing or closing.' : draft.savedAt ? `Saved locally ${new Date(draft.savedAt).toLocaleString()}` : 'No saved note.'}</span><span id={`${id}-limit`}>{draft.text.length} / {limit}</span></div>
    <div className="pl-notes__actions">
      <button type="button" className="pl-button--accent" onClick={save} disabled={!dirty && !draft.storageIssue}>Save note</button>
      <button type="button" onClick={exportNote} disabled={!draft.text && !draft.savedAt}><Icon name="download" size={16} />Export note JSON</button>
    </div>
    <p className="pl-notes__feedback" role="status" aria-live="polite" aria-atomic="true">{feedback}</p>
    {draft.storageIssue && <p className="pl-notes__warning" role="alert">{draft.storageIssue}</p>}
  </section>;
}
