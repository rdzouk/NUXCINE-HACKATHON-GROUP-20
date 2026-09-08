import { getLocale } from './locale';

/**
 * Interface strings, in both languages.
 *
 * Deliberately a flat object and not an i18n library. There are a few dozen
 * strings, they all live here, and a library would add a bundle, a loader and
 * a plural-rules engine to solve a problem this size does not have.
 *
 * **Server messages are not in here.** Errors, ride announcements and the
 * needs vocabulary are all returned by the API already translated, because
 * they have to be correctable without shipping an app. This file covers only
 * what the client itself writes.
 */
const STRINGS = {
  // Auth
  'auth.login.title': { fr: 'Connexion', en: 'Log in' },
  'auth.login.hint': {
    fr: 'Utilisez votre numero au format international, par exemple +237600000001.',
    en: 'Use your phone number in international format, for example +237600000001.',
  },
  'auth.phone': { fr: 'Numero de telephone', en: 'Phone number' },
  'auth.code': { fr: 'Code recu par SMS', en: 'Code from the SMS' },
  'auth.send': { fr: 'Envoyer le code', en: 'Send code' },
  'auth.sending': { fr: 'Envoi du code...', en: 'Sending code...' },
  'auth.verify': { fr: 'Verifier le code', en: 'Verify code' },
  'auth.verifying': { fr: 'Verification...', en: 'Verifying...' },
  'auth.resend': { fr: 'Renvoyer un code', en: 'Send a new code' },
  'auth.resendIn': { fr: 'Renvoyer dans', en: 'Send a new code in' },
  'auth.expires': { fr: 'Le code expire a', en: 'Code expires at' },
  'auth.enterCode': {
    fr: 'Entrez le code envoye a votre telephone.',
    en: 'Enter the code that was sent to your phone.',
  },
  'auth.noAccount': { fr: 'Pas de compte ?', en: 'No account?' },
  'auth.haveAccount': { fr: 'Vous avez deja un compte ?', en: 'Already have an account?' },
  'auth.signup': { fr: 'Creer un compte', en: 'Sign up' },
  'auth.signupTitle': { fr: 'Creer un compte', en: 'Create account' },
  'auth.signupHint': {
    fr: 'Le compte est cree apres verification du numero. Format international, par exemple +237600000001.',
    en: 'Accounts are created after phone verification. Use international format, for example +237600000001.',
  },
  'auth.login': { fr: 'Se connecter', en: 'Log in' },
  'auth.devCode': { fr: 'Code de developpement :', en: 'Development code:' },
  'auth.devNote': {
    fr: "Aucune passerelle SMS n'est configuree, le serveur affiche donc le code qu'il aurait envoye. Ceci n'existe pas en production.",
    en: 'No SMS gateway is wired, so the server is showing you the code it would have sent. This does not exist outside development.',
  },

  // Splash
  'splash.eyebrow': { fr: 'Mobilite intelligente\npour le Cameroun', en: 'Smart mobility\nfor Cameroon' },
  'splash.line1': { fr: 'Votre ville.', en: 'Your city.' },
  'splash.line2': { fr: 'Votre trajet.', en: 'Your ride.' },
  'splash.sub': {
    fr: 'Sur. Fiable. Abordable.\nPense pour vos deplacements.',
    en: 'Safe. Reliable. Affordable.\nBuilt for how you move.',
  },
  'splash.start': { fr: 'Commencer', en: 'Get started' },
  'splash.bet1': { fr: 'Carrefour Warda, pas 12 Rue X', en: 'Carrefour Warda, not 12 Rue X' },
  'splash.bet1sub': {
    fr: "5454 lieux reels. L'orthographe importe peu.",
    en: '5454 real landmarks. Spelling optional.',
  },
  'splash.bet2': { fr: 'Partagez la route, payez votre place', en: 'Share a corridor, pay for your seat' },
  'splash.bet2sub': {
    fr: 'Vous payez moins. Le chauffeur gagne plus.',
    en: 'You pay less. The driver earns more.',
  },
  'splash.bet3': { fr: 'Un code PIN a chaque prise en charge', en: 'A PIN at every pickup' },
  'splash.bet3sub': {
    fr: "La seule chose qu'un inconnu ne peut pas savoir.",
    en: 'The one thing a stranger cannot know.',
  },

  // Booking
  'book.pickup': { fr: 'Depart', en: 'Pickup' },
  'book.destination': { fr: 'Destination', en: 'Destination' },
  'book.tryWarda': { fr: 'Essayez warda, ou mokolo', en: 'Try warda, or mokolo' },
  'book.searching': { fr: 'Recherche...', en: 'Searching...' },
  'book.nothingFound': {
    fr: 'Aucun resultat. Essayez le nom du carrefour ou du quartier.',
    en: 'Nothing found. Try the carrefour or quartier name.',
  },
  'book.setPickup': {
    fr: "Choisissez d'abord un point de depart. Nous n'avons pas pu lire votre position.",
    en: 'Set a pickup point first. We could not read your location.',
  },
  'book.exclusive': { fr: 'Prive', en: 'Exclusive' },
  'book.exclusiveNote': { fr: 'Tout le vehicule', en: 'The whole vehicle' },
  'book.shared': { fr: 'Partage', en: 'Shared' },
  'book.sharedNote': { fr: 'Payez votre place', en: 'Pay for your seat' },
  'book.seats': { fr: 'Places', en: 'Seats' },
  'book.confirm': { fr: 'Confirmer la course', en: 'Confirm ride' },
  'book.needs': { fr: 'Ce dont vous avez besoin', en: 'What you need' },
  'book.needsNote': {
    fr: "Ces demandes decrivent ce que le chauffeur fait, jamais qui vous etes. Nous n'enregistrons aucune information de sante.",
    en: 'These describe what the driver does, never anything about you. We store no health information.',
  },
  'book.needsOther': { fr: 'Precisez (140 caracteres)', en: 'Tell the driver (140 characters)' },

  // Ride
  'ride.pinTitle': { fr: 'Votre code de prise en charge', en: 'Your pickup PIN' },
  'ride.pinNote': {
    fr: "Dites ce code a voix haute a votre chauffeur. Ne l'envoyez pas.",
    en: 'Read this code aloud to your driver. Do not send it.',
  },
  'ride.finding': { fr: "Recherche d'un chauffeur", en: 'Finding you a driver' },
  'ride.findingNote': {
    fr: 'Nous demandons aux chauffeurs les plus proches, puis nous elargissons.',
    en: 'Asking the nearest drivers first, then widening the search.',
  },
  'ride.cancel': { fr: 'Annuler la course', en: 'Cancel ride' },
  'ride.emergency': { fr: 'Urgence', en: 'Emergency' },
  'ride.speak': { fr: 'Annoncer les etapes', en: 'Speak ride updates' },
  'ride.speaking': { fr: 'Annonces activees', en: 'Spoken updates on' },

  // Common
  'common.home': { fr: 'Accueil', en: 'Home' },
  'common.history': { fr: 'Historique', en: 'History' },
  'common.profile': { fr: 'Profil', en: 'Profile' },
  'common.done': { fr: 'Termine', en: 'Done' },
  'common.loading': { fr: 'Chargement...', en: 'Loading...' },
  'common.logout': { fr: 'Se deconnecter', en: 'Log out' },
  'common.language': { fr: 'Langue', en: 'Language' },
};

/** One string, in the current language. Falls back to the key so a missing
 *  entry is visible in development rather than rendering as blank. */
export function t(key) {
  const entry = STRINGS[key];
  if (!entry) return key;
  return entry[getLocale()] ?? entry.fr ?? key;
}
