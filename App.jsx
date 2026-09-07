import MapView from './features/map/components/MapView';

const defaultCenter = {
  lat: 3.8480,
  lng: 11.5021,
};

export default function App() {
  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">VORA mobility</p>
          <h1>Map preview</h1>
        </div>
        <span className="status">Mapbox ready</span>
      </header>
      <section className="map-panel" aria-label="Map preview">
        <MapView center={defaultCenter} />
      </section>
    </main>
  );
}