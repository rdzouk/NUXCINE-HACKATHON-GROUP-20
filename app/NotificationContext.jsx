import { createContext, useContext, useState } from 'react';

const NotificationContext = createContext(null);

const mockNotifications = [
  { id: 1, title: 'Driver assigned', body: 'Jean is on the way — 6 min', time: '2 min ago', read: false },
  { id: 2, title: 'Ride completed', body: 'Your ride to Mvan is complete', time: '1 hr ago', read: true },
  { id: 3, title: 'SOS resolved', body: 'Your emergency alert was reviewed by support', time: 'Yesterday', read: true },
];

export function NotificationProvider({ children }) {
  const [notifications] = useState(mockNotifications);
  const unreadCount = notifications.filter((n) => !n.read).length;
  return (
    <NotificationContext.Provider value={{ notifications, unreadCount }}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  return useContext(NotificationContext);
}