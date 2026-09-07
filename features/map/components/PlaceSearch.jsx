import { useState } from 'react';
import { searchPlaces } from '../services/geocoding';

export default function PlaceSearch({ label, defaultValue, onSelect }) {
  const [query, setQuery] = useState(defaultValue?.name ?? '');
  const [results, setResults] = useState([]);
  const [errorMessage, setErrorMessage] = useState('');

  const handleChange = async (e) => {
    const value = e.target.value;
    setQuery(value);
    setErrorMessage('');

    if (value.length < 3) {
      setResults([]);
      return;
    }

    try {
      setResults(await searchPlaces(value));
    } catch (error) {
      setResults([]);
      setErrorMessage(error.message);
    }
  };

  const handlePick = (place) => {
    setQuery(place.name);
    setResults([]);
    onSelect({ lat: place.lat, lng: place.lng, name: place.name });
  };

  return (
    <div className="place-search">
      <label>{label}</label>
      <input value={query} onChange={handleChange} placeholder={label} />
      {results.length > 0 && (
        <ul>
          {results.map((r) => (
            <li key={r.id} onClick={() => handlePick(r)}>{r.name}</li>
          ))}
        </ul>
      )}
      {errorMessage ? <p>{errorMessage}</p> : null}
    </div>
  );
}