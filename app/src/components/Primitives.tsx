import type * as React from 'react';

type IconName = 'arrow' | 'search' | 'layers' | 'proof' | 'close' | 'download' | 'chevron' | 'command' | 'check' | 'info';

const iconPaths: Record<IconName, React.ReactNode> = {
  arrow: <><path d="M4 12h15M13 5l7 7-7 7" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
  layers: <><path d="m12 3 10 5-10 5L2 8l10-5Zm-9 9 9 4.5 9-4.5M3 16l9 4.5 9-4.5" /></>,
  proof: <><path d="M14 3H5v18h14V8l-5-5ZM14 3v5h5M8 12h8m-8 4h5" /></>,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" /></>,
  chevron: <path d="m9 5 7 7-7 7" />,
  command: <><path d="M8 8h8v8H8z" /><path d="M8 8H5a3 3 0 1 1 3-3v3Zm8 0V5a3 3 0 1 1 3 3h-3Zm0 8h3a3 3 0 1 1-3 3v-3Zm-8 0v3a3 3 0 1 1-3-3h3Z" /></>,
  check: <path d="m4 12 5 5L20 6" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6" /><circle cx="12" cy="7.5" r=".75" fill="currentColor" stroke="none" /></>,
};

/** Decorative icon. Give the containing control an accessible text label. */
export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg className="pl-icon" width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true" focusable="false">
      {iconPaths[name]}
    </svg>
  );
}

/** Always include meaningful text; tone alone does not communicate a finding. */
export function Pill({ children, tone = 'neutral' }: {
  children: React.ReactNode;
  tone?: 'neutral' | 'accent' | 'warning' | 'positive';
}) {
  return <span className={`pl-pill pl-pill--${tone}`}>{children}</span>;
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <section className="pl-empty-state" aria-label={title}>
      <span className="pl-empty-state__mark"><Icon name="search" size={24} /></span>
      <h2 className="pl-empty-state__title">{title}</h2>
      <p className="pl-empty-state__detail">{detail}</p>
    </section>
  );
}
