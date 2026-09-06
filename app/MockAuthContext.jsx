import { createContext, useContext } from 'react';

const MockAuthContext = createContext(null);

export function MockAuthProvider({ children }) {
  const value = {
    user: { id: 'mock-user', name: 'Demo passenger', role: 'passenger' },
    ride: { id: 'mock-ride', status: 'searching' },
  };

  return <MockAuthContext.Provider value={value}>{children}</MockAuthContext.Provider>;
}

export function useMockAuth() {
  return useContext(MockAuthContext);
}
