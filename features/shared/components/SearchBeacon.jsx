/**
 * The radar that runs while a driver is being found.
 *
 * Matching fires in widening rings, 2 km then 4 km then 6 km, and this draws
 * exactly that: three rings expanding outward on a stagger, a sweep arm, and
 * drivers appearing as the search reaches them. It is not a spinner dressed
 * up. A passenger watching it can see that the search is widening rather than
 * stalled, which is the difference between waiting and wondering.
 *
 * SVG and CSS, no library and no WebGL. It is a couple of kilobytes, paints on
 * the first frame, and costs nothing on a phone that is already struggling
 * with the network. Shipping a 3D runtime to draw a pulsing circle would
 * contradict the entire premise of the product.
 */
export default function SearchBeacon({ label = 'Finding you a driver', detail }) {
  return (
    <div className="beacon" role="status" aria-live="polite">
      <div className="beacon__stage">
        <span className="beacon__ring" />
        <span className="beacon__ring beacon__ring--2" />
        <span className="beacon__ring beacon__ring--3" />

        <svg className="beacon__sweep" viewBox="0 0 200 200" aria-hidden="true">
          <defs>
            <linearGradient id="beacon-sweep" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity="0" />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.55" />
            </linearGradient>
          </defs>
          <path d="M100 100 L100 6 A94 94 0 0 1 187 62 Z" fill="url(#beacon-sweep)" />
        </svg>

        {/* Drivers found so far, placed off-centre so the ring passes over
            them rather than through the middle. */}
        <span className="beacon__blip beacon__blip--a" />
        <span className="beacon__blip beacon__blip--b" />
        <span className="beacon__blip beacon__blip--c" />

        <span className="beacon__core" />
      </div>

      <p className="beacon__label">{label}</p>
      {detail ? <p className="beacon__detail">{detail}</p> : null}
    </div>
  );
}
