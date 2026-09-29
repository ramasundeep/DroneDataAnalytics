import { NavLink } from 'react-router-dom';
import { NAV_ITEMS } from '../nav';

export function NavBar() {
  return (
    <nav className="app-nav" aria-label="Main">
      <ul>
        {NAV_ITEMS.map((item) => (
          <li key={item.path}>
            <NavLink
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                [
                  'app-nav__link',
                  item.kind === 'planned' ? 'app-nav__link--planned' : '',
                  isActive ? 'active' : '',
                ]
                  .filter(Boolean)
                  .join(' ')
              }
              title={item.kind === 'planned' ? `Planned — Phase ${item.phase}` : undefined}
            >
              {item.label}
              {item.kind === 'planned' && <span className="app-nav__phase">P{item.phase}</span>}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
