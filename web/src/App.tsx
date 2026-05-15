import { BrowserRouter, Routes, Route } from 'react-router';
import { useEffect } from 'react';
import { TopBar } from './components/TopBar';
import { AttractionsList } from './pages/AttractionsList';
import { AttractionDetail } from './pages/AttractionDetail';
import { MyPasses } from './pages/MyPasses';
import { NotFound } from './pages/NotFound';
import { useAuth } from './auth/store';

function App() {
  const loadFromStorage = useAuth(s => s.loadFromStorage);
  useEffect(() => { loadFromStorage(); }, [loadFromStorage]);

  return (
    <BrowserRouter>
      <TopBar />
      <main className="max-w-6xl mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<AttractionsList />} />
          <Route path="/attractions/:slug" element={<AttractionDetail />} />
          <Route path="/settings/passes" element={<MyPasses />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

export default App;
