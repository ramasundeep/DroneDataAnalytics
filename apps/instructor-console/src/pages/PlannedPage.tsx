interface Props {
  label: string;
  phase: string;
}

export function PlannedPage({ label, phase }: Props) {
  return (
    <section>
      <h1>{label}</h1>
      <div className="banner banner--planned" role="note">
        Planned — Phase {phase} (see <code>docs/10_ROADMAP.md</code>)
      </div>
      <p className="muted">
        This screen is not built yet. It is listed here so the navigation reflects the roadmap; it
        shows no data, real or sample.
      </p>
    </section>
  );
}
