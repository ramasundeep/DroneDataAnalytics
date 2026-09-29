import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <section>
      <h1>Not found</h1>
      <p className="muted">
        There is no console page at this address. <Link to="/">Back to system status</Link>.
      </p>
    </section>
  );
}
