import { BrowserRouter, Routes, Route } from 'react-router';
import { useEffect } from 'react';
import { TopBar } from './components/TopBar';
import { ScrollToTop } from './components/ScrollToTop';
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
      <ScrollToTop />
      <TopBar />
      <Routes>
        <Route path="/" element={<AttractionsList />} />
        <Route path="/attractions/:slug" element={<AttractionDetail />} />
        <Route path="/settings/passes" element={<MyPasses />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
