import { Outlet } from 'react-router-dom';
import { Footer } from './Footer';
import { Header } from './Header';
import { NavBar } from './NavBar';

export function Layout() {
  return (
    <div className="app">
      <Header />
      <div className="app-body">
        <NavBar />
        <main className="app-main">
          <Outlet />
        </main>
      </div>
      <Footer />
    </div>
  );
}
