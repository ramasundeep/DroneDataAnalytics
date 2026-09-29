import logoUrl from '../assets/cdpl-logo-placeholder.svg';

export function Header() {
  return (
    <header className="app-header">
      <img
        className="app-header__logo"
        src={logoUrl}
        alt="Chakravyuha Dynamics logo placeholder"
        width={40}
        height={40}
      />
      <div className="app-header__text">
        <span className="app-header__company">Chakravyuha Dynamics</span>
        <span className="app-header__product">CD Sim — Instructor Console</span>
      </div>
    </header>
  );
}
