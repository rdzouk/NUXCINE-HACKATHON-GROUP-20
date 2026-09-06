import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MockAuthProvider } from './app/MockAuthContext';
import DevIndex from './app/DevIndex';

import SplashPage from './features/auth/pages/SplashPage';
import LoginPage from './features/auth/pages/LoginPage';
import SignupPage from './features/auth/pages/SignupPage';

import HomePage from './features/passenger/pages/HomePage';
import MapBookingPage from './features/passenger/pages/MapBookingPage';
import ConfirmRidePage from './features/passenger/pages/ConfirmRidePage';
import SearchingDriverPage from './features/passenger/pages/SearchingDriverPage';
import PassengerRideInProgressPage from './features/passenger/pages/RideInProgressPage';
import RideCompletedPage from './features/passenger/pages/RideCompletedPage';
import PassengerHistoryPage from './features/passenger/pages/HistoryPage';
import PassengerProfilePage from './features/passenger/pages/ProfilePage';
import SupportPage from './features/passenger/pages/SupportPage';

import DriverDashboardPage from './features/driver/pages/DashboardPage';
import IncomingRequestPage from './features/driver/pages/IncomingRequestPage';

import AdminDashboardPage from './features/admin/pages/DashboardPage';

export default function App() {
  return (
    <MockAuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<DevIndex />} />
          <Route path="/splash" element={<SplashPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/passenger/home" element={<HomePage />} />
          <Route path="/passenger/book" element={<MapBookingPage />} />
          <Route path="/passenger/confirm" element={<ConfirmRidePage />} />
          <Route path="/passenger/searching" element={<SearchingDriverPage />} />
          <Route path="/passenger/ride" element={<PassengerRideInProgressPage />} />
          <Route path="/passenger/completed" element={<RideCompletedPage />} />
          <Route path="/passenger/history" element={<PassengerHistoryPage />} />
          <Route path="/passenger/profile" element={<PassengerProfilePage />} />
          <Route path="/passenger/support" element={<SupportPage />} />
          <Route path="/driver/dashboard" element={<DriverDashboardPage />} />
          <Route path="/driver/request" element={<IncomingRequestPage />} />
          <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
        </Routes>
      </BrowserRouter>
    </MockAuthProvider>
  );
}