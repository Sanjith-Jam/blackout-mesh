import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import DemoDashboard from './pages/DemoDashboard';
import HospitalPage from './pages/HospitalDemo';
import ClassroomsPage from './pages/ClassroomsDemo';
import { Header } from '@/components/ui/header';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronUp } from 'lucide-react';
import { useState, useEffect } from 'react';
import './App.css';
import { useWebSocketSync } from './useServerState';

function AppShell({ children }: { children: React.ReactNode }) {
  useWebSocketSync();
  return <>{children}</>;
}

function ScrollToTop() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const toggleVisibility = () => {
      if (window.scrollY > 300) {
        setIsVisible(true);
      } else {
        setIsVisible(false);
      }
    };
    window.addEventListener('scroll', toggleVisibility);
    return () => window.removeEventListener('scroll', toggleVisibility);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    });
  };

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.button
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          onClick={scrollToTop}
          className="fixed bottom-8 right-8 z-[100] p-3 bg-gray-900/80 backdrop-blur-md text-white rounded-full shadow-xl hover:bg-gray-800 transition-colors"
          aria-label="Scroll to top"
        >
          <ChevronUp size={24} />
        </motion.button>
      )}
    </AnimatePresence>
  );
}

function AppContent() {
  const location = useLocation();
  return (
    <div className="flex flex-col min-h-screen relative">
      <Header />
      <main className="flex-grow">
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={<motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}><LandingPage /></motion.div>} />
            <Route path="/hospital" element={<motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}><HospitalPage /></motion.div>} />
            <Route path="/classrooms" element={<motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}><ClassroomsPage /></motion.div>} />
            <Route path="/demo" element={<motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}><DemoDashboard /></motion.div>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AnimatePresence>
      </main>
      <ScrollToTop />
    </div>
  );
}

function App() {
  return (
    <Router>
      <AppShell>
        <AppContent />
      </AppShell>
    </Router>
  );
}

export default App;
