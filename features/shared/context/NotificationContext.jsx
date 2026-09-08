import { createContext, useContext, useEffect, useState } from 'react';
import { getAccessToken } from '../../auth/services/session';
import { getLocale } from '../services/locale';

const NotificationContext = createContext(null);

/**
 * Notifications derived from the caller's own rides.
 *
 * There is no notification table and no push channel, so this reads the same
 * `GET /rides` the history screen reads and turns each ride into the event it
 * represents. That is a real limitation, and it is the honest version of one.
 *
 * It replaced three hardcoded entries, one of which claimed "Your emergency
 * alert was reviewed by support". Inventing a completed safety response is the
 * worst thing in this app to invent: a passenger who believes SOS is watched
 * by a person behaves differently from one who knows it is not.
 *
 * Read state lives in this browser only. Without a server-side record there is
 * nowhere else to put it, and pretending otherwise would be the same mistake
 * one layer down.
 */

const LIVE = new Set([
  'accepted', 'arriving', 'arrived', 'in_progress',
]);

function toNotification(ride, en) {
  const to = ride.dropoff?.label ?? '';

  if (ride.status === 'completed') {
    return {
      id: ride.id,
      title: en ? 'Trip complete' : 'Course terminee',
      body: en
        ? `Your trip to ${to} is finished.`
        : `Votre trajet vers ${to} est termine.`,
      at: ride.ended_at ?? ride.created_at,
      read: true,
    };
  }

  if (ride.status === 'cancelled') {
    return {
      id: ride.id,
      title: en ? 'Trip cancelled' : 'Course annulee',
      body: en
        ? `Your trip to ${to} was cancelled.`
        : `Votre trajet vers ${to} a ete annule.`,
      at: ride.ended_at ?? ride.created_at,
      read: true,
    };
  }

  if (LIVE.has(ride.status)) {
    return {
      id: ride.id,
      title: en ? 'Trip in progress' : 'Course en cours',
      body: ride.driver?.first_name
        ? en
          ? `${ride.driver.first_name} is driving you to ${to}.`
          : `${ride.driver.first_name} vous conduit vers ${to}.`
        : en
          ? `Your trip to ${to} is under way.`
          : `Votre trajet vers ${to} est en cours.`,
      at: ride.accepted_at ?? ride.created_at,
      read: false,
    };
  }

  return null;
}

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    // Nothing to read before there is a session, and asking anyway would
    // bounce the visitor to the login screen from the splash.
    if (!getAccessToken()) return;

    const en = getLocale() === 'en';

    import('../../passenger/services/ridesApi')
      .then(({ listRides }) => listRides({ limit: 10 }))
      .then((data) =>
        setNotifications(
          (data.items ?? []).map((r) => toNotification(r, en)).filter(Boolean),
        ),
      )
      .catch(() => setNotifications([]));
  }, []);

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
