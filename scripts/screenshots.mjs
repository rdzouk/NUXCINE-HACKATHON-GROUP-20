/**
 * Capture the app, screen by screen, into docs/screenshots/.
 *
 *   node scripts/screenshots.mjs
 *
 * The README makes claims about screens a reader cannot open. Pictures settle
 * that in a way prose cannot, and a jury reading on a phone will look at them
 * before reading a word.
 *
 * **Real data, real sessions, no mockups.** Every shot is the running stack
 * against the seeded database, so a screen that is broken photographs broken.
 * That is the point: a screenshot of a mocked screen is the same lie as a
 * table of invented rows, one layer further out.
 *
 * A live ride is driven through the API between shots, because the screens
 * worth showing are the ones that only exist mid-journey: an offer on the
 * driver's phone, the PIN on the passenger's.
 *
 * The passenger and driver shots are taken at phone size because that is what
 * the product is. Admin is taken at desktop width because that is where it
 * lives.
 *
 * Requires the stack up and seeded:
 *   docker compose up -d && ./scripts/seed.sh
 *
 * Chromium comes from puppeteer. On a machine without the system libraries it
 * needs, and without root to install them, the packages can be unpacked into a
 * directory and pointed at with LD_LIBRARY_PATH. See docs/screenshots/README.
 */

import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import puppeteer from 'puppeteer';

const WEB = process.env.WEB_BASE ?? 'http://localhost:8090';
const API = process.env.API_BASE ?? 'http://localhost:8080/api/v1';
const OUT = 'docs/screenshots';

const PASSENGER = '+237600000008000';
const DRIVER = '+237600000009000';
const ADMIN = '+237600000007000';

// Carrefour Warda to Marche Central. A corridor people actually travel.
const PICKUP = { lat: 3.87664, lng: 11.51303, label: 'Carrefour Warda' };
const DROPOFF = { lat: 3.866, lng: 11.517, label: 'Marche Central' };

const PHONE = { width: 430, height: 800, deviceScaleFactor: 2 };
const DESKTOP = { width: 1240, height: 800, deviceScaleFactor: 2 };

const LIVE = new Set([
  'requested', 'matching', 'accepted', 'arriving', 'arrived', 'in_progress',
]);

const captions = [];
const settle = (ms) => new Promise((r) => setTimeout(r, ms));

async function api(method, urlPath, body, token) {
  const res = await fetch(`${API}${urlPath}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Accept-Language': 'fr',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(method === 'POST' && urlPath === '/rides'
        ? { 'Idempotency-Key': randomUUID() }
        : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  return { status: res.status, body: text ? JSON.parse(text) : null };
}

/**
 * Sign in out of band and plant the session.
 *
 * The login screen is photographed separately, through the real form. Driving
 * the four PIN boxes for every subsequent shot would make this script a test
 * of the OTP widget rather than a camera.
 */
async function session(phone) {
  const challenge = await api('POST', '/auth/otp/request', { phone });
  if (!challenge.body?.challenge_id) {
    throw new Error(`OTP refused for ${phone}: ${JSON.stringify(challenge.body)}`);
  }
  const peek = await api('GET', `/dev/otp/${encodeURIComponent(phone)}`);
  const verified = await api('POST', '/auth/otp/verify', {
    challenge_id: challenge.body.challenge_id,
    code: peek.body.code,
  });
  if (!verified.body?.access_token) {
    throw new Error(`verify failed for ${phone}: ${JSON.stringify(verified.body)}`);
  }
  return verified.body;
}

async function shot(page, name, caption) {
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file });
  captions.push({ file: `${name}.png`, caption });
  console.log(`  ${String(captions.length).padStart(2)}. ${name.padEnd(26)} ${caption}`);
}

async function open(browser, viewport, tokens, activeRide) {
  const page = await browser.newPage();
  await page.setViewport(viewport);
  await page.evaluateOnNewDocument((s, ride) => {
    // French, because that is the product's default and the jury's language.
    localStorage.setItem('vora.locale', 'fr');
    if (s) {
      localStorage.setItem('access_token', s.access_token);
      localStorage.setItem('refresh_token', s.refresh_token);
      localStorage.setItem('session_user', JSON.stringify(s.user));
    }
    if (ride) {
      // The mid-journey screens read the ride from here and bounce to the
      // booking screen without it. This ride was created through the API, so
      // it is planted the way the app itself would have left it.
      sessionStorage.setItem('active_ride', JSON.stringify(ride));
    }
  }, tokens ?? null, activeRide ?? null);
  return page;
}

async function go(page, route, wait = 2200) {
  await page.goto(`${WEB}${route}`, { waitUntil: 'networkidle2' });
  await settle(wait);
  await waitForMap(page);
}

/**
 * Wait for the map to actually draw.
 *
 * A Mapbox canvas that has not finished loading photographs as a black
 * rectangle, which reads as a broken screen rather than a slow one. Software
 * rendering makes that slower still, so the wait is generous and gives up
 * quietly on screens that have no map at all.
 */
async function waitForMap(page) {
  const hasCanvas = await page.evaluate(
    () => Boolean(document.querySelector('.mapboxgl-canvas')),
  );
  if (!hasCanvas) return;

  await page
    .waitForFunction(
      () => {
        const c = document.querySelector('.mapboxgl-canvas');
        return c && c.width > 0 && document.querySelectorAll('.mapboxgl-marker, .mapboxgl-ctrl-attrib').length > 0;
      },
      { timeout: 20000 },
    )
    .catch(() => {});
  await settle(5000);
  await freezeMap(page);
}

/**
 * Copy the drawn map onto a plain canvas laid over it.
 *
 * Software-rendered WebGL draws correctly but composites black into a headless
 * screenshot, so the map photographs as a void even though the browser is
 * showing it. Reading the pixels back through a 2D context and painting them
 * into an ordinary canvas gets the real map into the capture.
 *
 * This copies what Mapbox actually drew. It is not a substitute image, and if
 * the map had failed to load this would photograph the failure.
 */
async function freezeMap(page) {
  await page.evaluate(() => {
    const gl = document.querySelector('.mapboxgl-canvas');
    if (!gl || document.querySelector('[data-map-freeze]')) return;

    const flat = document.createElement('canvas');
    flat.width = gl.width;
    flat.height = gl.height;
    flat.setAttribute('data-map-freeze', '');
    const box = gl.getBoundingClientRect();
    Object.assign(flat.style, {
      position: 'absolute',
      left: `${gl.offsetLeft}px`,
      top: `${gl.offsetTop}px`,
      width: `${box.width}px`,
      height: `${box.height}px`,
      zIndex: '0',
      pointerEvents: 'none',
    });
    flat.getContext('2d').drawImage(gl, 0, 0);
    gl.parentElement.appendChild(flat);
    gl.style.visibility = 'hidden';
  });
  await settle(400);
}

/** Type into a React-controlled input the way React will notice. */
async function setInput(page, selector, value, index = 0) {
  await page.evaluate(
    (sel, val, i) => {
      const el = document.querySelectorAll(sel)[i];
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value',
      ).set;
      setter.call(el, val);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    },
    selector,
    value,
    index,
  );
}

async function clickText(page, selector, text) {
  return page.evaluate(
    (sel, t) => {
      const el = [...document.querySelectorAll(sel)].find((n) =>
        n.innerText.trim().startsWith(t),
      );
      if (el) el.click();
      return Boolean(el);
    },
    selector,
    text,
  );
}

/** Put a ride in front of the driver, so the offer screens have something on them. */
async function stageLiveRide(driverToken) {
  await api('POST', '/driver/online',
    { lat: PICKUP.lat, lng: PICKUP.lng, seats_free: 4 }, driverToken);

  // A fresh passenger each run: the seeded one may be mid-ride, and clearing
  // that by cancelling would charge a fee and then block the booking.
  const phone = `+23760000000${String(Math.floor(Math.random() * 10000)).padStart(4, '0')}`;
  const rider = await session(phone);

  const quote = await api('POST', '/rides/quote', {
    pickup: PICKUP, dropoff: DROPOFF, mode: 'exclusive', seats: 1,
  }, rider.access_token);

  const ride = await api('POST', '/rides', {
    quote_id: quote.body.quote_id,
    seats: 1,
    ride_needs: ['extra_legroom', 'spoken_itinerary'],
  }, rider.access_token);

  return { rider, rideId: ride.body?.ride?.id ?? null };
}

async function clearDriverRides(driverToken) {
  const mine = await api('GET', '/rides?limit=10', undefined, driverToken);
  for (const ride of mine.body?.items ?? []) {
    if (LIVE.has(ride.status)) {
      await api('POST', `/rides/${ride.id}/cancel`, { reason: 'other' }, driverToken);
    }
  }
}

async function main() {
  await mkdir(OUT, { recursive: true });

  const browser = await puppeteer.launch({
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-dev-shm-usage',
      // Without a GPU the map canvas renders as a black hole, which makes the
      // booking screen photograph as if it were broken. SwiftShader draws it
      // in software instead.
      '--use-gl=angle',
      '--use-angle=swiftshader',
      '--enable-unsafe-swiftshader',
      '--enable-webgl',
      '--ignore-gpu-blocklist',
      '--disable-gpu-sandbox',
      '--in-process-gpu',
    ],
  });

  const context = browser.defaultBrowserContext();
  await context.overridePermissions(WEB, ['geolocation']);

  console.log(`capturing ${WEB} into ${OUT}/\n`);

  // ------------------------------------------------ signed out, phone --
  {
    const page = await open(browser, PHONE);
    await go(page, '/');
    await shot(page, '01-splash',
      "L'ecran d'ouverture: les deux paris du produit et le code PIN.");

    await go(page, '/login');
    await shot(page, '02-login',
      'Connexion par numero de telephone. Aucun mot de passe nulle part.');

    // The real form, so the OTP boxes and the development code are genuine.
    await setInput(page, 'input', PASSENGER);
    await clickText(page, 'button.primary-button', '');
    await settle(3200);
    await shot(page, '03-otp',
      "Quatre cases, et le code affiche a l'ecran pour les numeros de test.");
    await page.close();
  }

  // ---------------------------------------------------------- passenger --
  const passenger = await session(PASSENGER);
  {
    const page = await open(browser, PHONE, passenger);
    await page.setGeolocation({ latitude: PICKUP.lat, longitude: PICKUP.lng });

    await go(page, '/passenger/home');
    await shot(page, '04-home',
      'Destinations recentes, tirees des courses reelles du passager.');

    await go(page, '/passenger/book', 3200);
    await setInput(page, '.place-search input', 'warda carefour', 0);
    await settle(2600);
    await shot(page, '05-landmark-search',
      'Pari 1: un carrefour mal orthographie et dans le desordre, retrouve, avec la raison du match.');

    await clickText(page, '.place-results button', 'Carrefour Warda');
    await settle(1000);
    await setInput(page, '.place-search input', 'marche central', 1);
    await settle(2600);
    await clickText(page, '.place-results button', 'Marche Central');
    await settle(4000);
    await shot(page, '06-quote',
      'Les deux tarifs cote a cote: prive et partage, calcules par le serveur.');

    await clickText(page, '.mode-toggle__option', 'Partage');
    await settle(3000);
    await shot(page, '07-corridor-mode',
      'Pari 2: payez votre place, avec le selecteur de places.');

    await page.evaluate(() => {
      document.querySelector('.needs-picker__summary')?.click();
    });
    await settle(1400);
    await shot(page, '08-ride-needs',
      "Sept besoins. Chacun decrit ce que le chauffeur fait, aucun n'enregistre quoi que ce soit sur la personne.");

    await go(page, '/passenger/history');
    await shot(page, '09-history',
      'Les trajets du passager, servis par GET /rides.');

    await go(page, '/passenger/profile');
    await shot(page, '10-profile',
      'Profil et bascule de langue.');

    await go(page, '/notifications');
    await shot(page, '11-notifications',
      "Construites a partir des courses reelles, et l'ecran le dit.");

    await go(page, '/legal/privacy');
    await shot(page, '12-privacy',
      'Ce qui est collecte, et ce qui est refuse.');

    await page.close();
  }

  // ------------------------------------------------------------- driver --
  const driver = await session(DRIVER);
  await clearDriverRides(driver.access_token);
  {
    const page = await open(browser, PHONE, driver);
    await page.setGeolocation({ latitude: PICKUP.lat, longitude: PICKUP.lng });

    await api('POST', '/driver/offline', {}, driver.access_token);
    await go(page, '/driver/dashboard');
    await shot(page, '13-driver-offduty',
      "Hors service, avec la raison pour laquelle rien n'arrive.");

    // Through the real toggle, not the API. Driving it from outside left the
    // header reading "off duty" above a list of incoming requests, which is
    // the screen contradicting itself in a screenshot.
    await page.evaluate(() => document.querySelector('.duty-toggle')?.click());
    await settle(4000);

    const staged = await stageLiveRide(driver.access_token);
    await settle(2500);
    await go(page, '/driver/dashboard', 3500);
    await shot(page, '14-driver-offer',
      'En service: la demande arrive avec le tarif et les deux etapes.');

    const opened = await clickText(page, '.offer-list button', '');
    if (opened) {
      await settle(2600);
      await shot(page, '15-driver-request',
        "La demande en detail, avec ce que le passager a demande, avant d'accepter.");
    }

    // Accept through the API so the next shots have a live ride behind them.
    const offers = await api('GET', '/driver/offers', undefined, driver.access_token);
    const mine = (offers.body?.offers ?? []).find((o) => o.ride_id === staged.rideId);
    if (mine) {
      await api('POST', `/driver/offers/${mine.id}/accept`, {}, driver.access_token);
    }

    await go(page, '/driver/earnings');
    await shot(page, '16-driver-earnings',
      'Gains, sommes sur les courses terminees, honnete sur sa propre portee.');

    await go(page, '/driver/safety');
    await shot(page, '17-driver-safety',
      'Ecran de securite du chauffeur.');

    await page.close();

    // ------------------------------------------ the PIN, on the passenger --
    if (staged.rideId && staged.rider) {
      const rider = await open(browser, PHONE, staged.rider, { id: staged.rideId });
      await rider.setGeolocation({ latitude: PICKUP.lat, longitude: PICKUP.lng });
      await go(rider, '/passenger/driver-enroute', 3600);
      await rider.evaluate(() => {
        document.querySelector('.ride-panel')?.scrollIntoView({ block: 'start' });
      });
      await settle(900);
      await shot(rider, '18-pickup-pin',
        "Le code de prise en charge, chez le passager uniquement. Le chauffeur ne le recoit jamais.");
      await rider.close();
    }

    await clearDriverRides(driver.access_token);
  }

  // -------------------------------------------------------------- admin --
  const admin = await session(ADMIN);
  {
    const page = await open(browser, DESKTOP, admin);

    await go(page, '/admin/dashboard', 3000);
    await shot(page, '19-admin-overview',
      'Chiffres reels, derives de la liste des chauffeurs. Rien de fabrique.');

    await go(page, '/admin/drivers', 3000);
    await clickText(page, '.admin-tabs button', 'Verifies');
    await settle(2400);
    await shot(page, '20-admin-kyc',
      'La file KYC, avec la decision reellement branchee.');

    await go(page, '/admin/rides', 2200);
    await shot(page, '21-admin-notbuilt',
      "Un ecran non construit le dit, au lieu d'afficher des lignes inventees.");

    await page.close();
  }

  await browser.close();

  const manifest = [
    '# Captures d\'ecran',
    '',
    'Produites par `node scripts/screenshots.mjs` contre la pile en marche et',
    'la base de donnees chargee. Rien ici n\'est une maquette: une course est',
    'creee par l\'API entre deux captures pour que les ecrans de course',
    'existent vraiment.',
    '',
    '| Fichier | Ce que cela montre |',
    '|---|---|',
    ...captions.map((c) => `| \`${c.file}\` | ${c.caption} |`),
    '',
    '## Regenerer',
    '',
    '```bash',
    'docker compose up -d && ./scripts/seed.sh',
    'npm i --no-save puppeteer@22.15.0',
    'node scripts/screenshots.mjs',
    '```',
    '',
    'Sur une machine sans les bibliotheques systeme que Chromium exige et sans',
    'droits root, elles peuvent etre depaquetees a cote:',
    '',
    '```bash',
    'mkdir -p /tmp/chromedeps && cd /tmp/chromedeps',
    'apt-get download libnss3 libnspr4 libasound2t64',
    'for d in *.deb; do dpkg -x "$d" root; done',
    'export LD_LIBRARY_PATH=/tmp/chromedeps/root/usr/lib/x86_64-linux-gnu',
    '```',
    '',
  ].join('\n');
  await writeFile(path.join(OUT, 'README.md'), manifest, 'utf8');

  console.log(`\n${captions.length} captures ecrites dans ${OUT}/`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
