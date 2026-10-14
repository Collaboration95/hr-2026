import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Icon, type IconName } from "../components/Primitives";
import { useModalDialog } from "./dom";

export type Command = {
  id: string;
  group: string;
  label: string;
  /** Secondary text shown at the right, e.g. a declared area. */
  hint?: string;
  /** Extra words that make the command findable. */
  keywords?: string;
  kbd?: string;
  icon?: IconName;
  disabled?: boolean;
  run: () => void;
};

const ITEM = "button.pl-palette__item:not(:disabled)";

/**
 * ⌘/Ctrl+K command palette. The filter input keeps focus while typing; ↓ moves into
 * the list, ↑/↓ walk it, Enter runs the focused (or first) command, typing returns to
 * the input, Esc closes.
 */
export default function CommandPalette({ commands, onClose, onRun }: {
  commands: Command[];
  onClose: () => void;
  onRun: (command: Command) => void;
}) {
  const dialog = useModalDialog(onClose);
  const [query, setQuery] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => input.current?.focus(), []);

  const matches = useMemo(() => {
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    return commands.filter((c) => {
      const haystack = `${c.label} ${c.group} ${c.keywords ?? ""}`.toLowerCase();
      return terms.every((term) => haystack.includes(term));
    });
  }, [commands, query]);
  const groups = useMemo(() => {
    const out: { name: string; items: Command[] }[] = [];
    for (const command of matches) {
      const last = out[out.length - 1];
      if (last && last.name === command.group) last.items.push(command);
      else out.push({ name: command.group, items: [command] });
    }
    return out;
  }, [matches]);
  const firstEnabled = matches.find((c) => !c.disabled);

  const items = () => Array.from(list.current?.querySelectorAll<HTMLButtonElement>(ITEM) ?? []);

  const onInputKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      items()[0]?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      items().at(-1)?.focus();
    } else if (event.key === "Enter" && firstEnabled) {
      event.preventDefault();
      onRun(firstEnabled);
    }
  };
  const onListKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const all = items();
    const index = all.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      all[Math.min(index + 1, all.length - 1)]?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (index <= 0) input.current?.focus();
      else all[index - 1].focus();
    } else if (event.key === "Home") {
      event.preventDefault();
      all[0]?.focus();
    } else if (event.key === "End") {
      event.preventDefault();
      all.at(-1)?.focus();
    } else if (event.key.length === 1 && !event.metaKey && !event.ctrlKey && !event.altKey) {
      // Typing from the list goes back to the filter field.
      input.current?.focus();
    }
  };

  return (
    <dialog className="pl-dialog pl-palette" aria-label="Commands" {...dialog}>
      <div className="pl-palette__field">
        <Icon name="search" size={16} />
        <input
          ref={input}
          type="text"
          className="pl-palette__input"
          aria-label="Filter commands"
          placeholder="Type a command or plot ID"
          autoComplete="off"
          spellCheck={false}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onInputKey}
        />
        <kbd className="pl-kbd" aria-hidden="true">Esc</kbd>
      </div>
      <div className="pl-palette__list" ref={list} onKeyDown={onListKey}>
        {groups.length === 0 && <p className="pl-palette__empty" role="status">No matching commands</p>}
        {groups.map((group) => (
          <div key={group.name} role="group" aria-label={group.name} className="pl-palette__group">
            <span className="pl-eyebrow" aria-hidden="true">{group.name}</span>
            {group.items.map((command) => (
              <button
                key={command.id}
                type="button"
                className="pl-palette__item"
                disabled={command.disabled}
                data-default={command === firstEnabled ? "" : undefined}
                onClick={() => onRun(command)}
              >
                {command.icon ? <Icon name={command.icon} size={16} /> : <span className="pl-palette__icon-gap" />}
                <span className="pl-palette__label">{command.label}</span>
                {command.hint && <span className="pl-palette__hint pl-num">{command.hint}</span>}
                {command.kbd && <kbd className="pl-kbd" aria-hidden="true">{command.kbd}</kbd>}
              </button>
            ))}
          </div>
        ))}
      </div>
    </dialog>
  );
}
