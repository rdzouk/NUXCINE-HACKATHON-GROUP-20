import mapboxgl from 'mapbox-gl';

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN;

export const MAP_DEFAULTS = {
  style: 'mapbox://styles/mapbox/streets-v12',
  zoom: 14,
};

export default mapboxgl;