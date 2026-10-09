import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import DemoDashboard from './pages/DemoDashboard';
import HospitalPage from './pages/HospitalDemo';
import ClassroomsPage from './pages/ClassroomsDemo';
import './App.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/hospital" element={<HospitalPage />} />
        <Route path="/classrooms" element={<ClassroomsPage />} />
        <Route path="/demo" element={<DemoDashboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
