import { createContext, useContext, useState } from 'react';

const MockAuthContext = createContext(null);

const defaultState = {
  user: { name: 'Aminata', phone: '+237699000000', rating: 4.8 },
  ride: {
    status: 'in_progress',
    origin: 'Carrefour Warda',
    destination: 'Total Nsimeyong',
    driver: { name: 'Jean', vehicle: 'Toyota Corolla, gris, LT 1234 AB', rating: 4.9 },
    fareXaf: 1800,
    distanceKm: 4.2,
    durationMin: 14,
  },
  rideHistory: [
    { id: 1, date: '2026-09-04', from: 'Bastos', to: 'Mvan', fareXaf: 1500 },
    { id: 2, date: '2026-09-03', from: 'Mokolo', to: 'Etoudi', fareXaf: 2200 },
  ],
  adminUsers: [
    { id: 1, name: 'Aminata', role: 'passenger', status: 'active' },
    { id: 2, name: 'Paul', role: 'passenger', status: 'suspended' },
  ],
  adminDrivers: [
    { id: 1, name: 'Jean', vehicle: 'Toyota Corolla', status: 'online' },
    { id: 2, name: 'Marc', vehicle: 'Hyundai Accent', status: 'offline' },
  ],
  adminRides: [
    { id: 101, passenger: 'Aminata', driver: 'Jean', status: 'in_progress', fareXaf: 1800 },
    { id: 102, passenger: 'Paul', driver: 'Marc', status: 'completed', fareXaf: 2200 },
  ],
  adminReports: [
    { id: 1, type: 'SOS', ride: 101, note: 'Passenger triggered SOS near Mvan', status: 'open' },
  ],
};

export function MockAuthProvider({ children }) {
  const [state] = useState(defaultState);
  return <MockAuthContext.Provider value={state}>{children}</MockAuthContext.Provider>;
}

export function useMockAuth() {
  return useContext(MockAuthContext);
}