import { EmptyState } from "./components/Primitives";
import { useDemo } from "./shell/useDemo";
import Workspace from "./shell/Workspace";

/**
 * App shell. Loads the frozen export, then hands off to the routed workspace
 * (src/shell/*). A failed reload keeps the last accepted artifact on screen.
 */
export default function App() {
  const { data, error, loading, load } = useDemo();
  if (!data)
    return (
      <main className="pl-boot">
        <div className="pl-brand pl-brand--boot">plotline</div>
        {error ? (
          <>
            <div role="alert">
              <EmptyState title="Evidence could not be loaded" detail={error} />
            </div>
            <button type="button" className="pl-btn pl-btn--primary" onClick={load}>Retry loading</button>
          </>
        ) : (
          <p className="pl-boot__status" role="status">
            <span className="pl-spinner" aria-hidden="true" />
            Loading local evidence…
          </p>
        )}
      </main>
    );
  return <Workspace data={data} reloadError={error} reloading={loading} onReload={load} />;
}
