import { Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { NAV_ITEMS } from './nav';
import { AreasPage } from './pages/AreasPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { PlannedPage } from './pages/PlannedPage';
import { PlatformsPage } from './pages/PlatformsPage';
import { ScenariosPage } from './pages/ScenariosPage';
import { StatusPage } from './pages/StatusPage';

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<StatusPage />} />
        <Route path="platforms" element={<PlatformsPage />} />
        <Route path="areas" element={<AreasPage />} />
        <Route path="scenarios" element={<ScenariosPage />} />
        {NAV_ITEMS.filter((i) => i.kind === 'planned').map((i) => (
          <Route
            key={i.path}
            path={i.path.slice(1)}
            element={<PlannedPage label={i.label} phase={i.phase} />}
          />
        ))}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
