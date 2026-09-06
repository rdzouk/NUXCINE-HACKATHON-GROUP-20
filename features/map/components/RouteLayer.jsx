import { useEffect, useRef } from 'react';

export default function RouteLayer({ map, geometry }) {
  const layerId = useRef('route-layer');

  useEffect(() => {
    if (!map || !geometry) return;

    const sourceId = 'route-source';
    if (map.getSource(sourceId)) {
      map.getSource(sourceId).setData({ type: 'Feature', geometry });
    } else {
      map.addSource(sourceId, { type: 'geojson', data: { type: 'Feature', geometry } });
      map.addLayer({
        id: layerId.current,
        type: 'line',
        source: sourceId,
        paint: { 'line-color': '#1d4ed8', 'line-width': 4 },
      });
    }
  }, [map, geometry]);

  return null; // this component only draws on the map instance, no DOM output
}