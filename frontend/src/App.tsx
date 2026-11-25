import { Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AnalyzePage } from './pages/AnalyzePage';
import { HistoryPage } from './pages/HistoryPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { ResultPage } from './pages/ResultPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<AnalyzePage />} />
        <Route path="analiz/:id" element={<ResultPage />} />
        <Route path="gecmis" element={<HistoryPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
