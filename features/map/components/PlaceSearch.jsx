import { useState } from 'react';
import { searchPlaces } from '../services/geocoding';
import { haversineKm } from '../utils/distance';
import { getLocale } from '../../shared/services/locale';
import { t } from '../../shared/services/strings';

/**
 * How the match was made, in words a passenger would use.
 *
 * This is the demo's opening moment and the point of the gazetteer, so the
 * result says *why* it matched rather than just listing names. "Exact match"
 * on a carrefour somebody typed from memory is the whole argument for Bet 1:
 * people here navigate by landmark, and a street-address geocoder cannot.
 */
const MATCH_LABELS = {
  en: {
    exact_alias: 'Exact match',
    fuzzy_landmark: 'Close match',
    quartier: 'Quartier',
    street_fallback: 'Street',
  },
  fr: {
    exact_alias: 'Correspondance exacte',
    fuzzy_landmark: 'Correspondance approchee',
    quartier: 'Quartier',
    street_fallback: 'Rue',
  },
};

export default function PlaceSearch({ label, defaultValue, near, onSelect, hint }) {
  const [query, setQuery] = useState(defaultValue?.name ?? '');
  const [results, setResults] = useState([]);
  const [errorMessage, setErrorMessage] = useState('');
  const [searching, setSearching] = useState(false);
  // A picked place and a search that found nothing both leave the results
  // list empty, so without this the screen says "Nothing found" directly
  // underneath the name the user just chose.
  const [picked, setPicked] = useState(Boolean(defaultValue));

  const handleChange = async (e) => {
    const value = e.target.value;
    setQuery(value);
    setErrorMessage('');
    setPicked(false);

    // Two characters is too little to be a landmark and matches most of the
    // gazetteer, so the search waits rather than sending noise per keystroke.
    if (value.length < 3) {
      setResults([]);
      return;
    }

    setSearching(true);
    try {
      setResults(await searchPlaces(value, near));
    } catch (error) {
      setResults([]);
      setErrorMessage(error.message);
    } finally {
      setSearching(false);
    }
  };

  const handlePick = (place) => {
    setQuery(place.name);
    setResults([]);
    setPicked(true);
    onSelect({ lat: place.lat, lng: place.lng, name: place.name });
  };

  return (
    <div className="place-search">
      <label htmlFor={`search-${label}`}>{label}</label>
      <input
        id={`search-${label}`}
        value={query}
        onChange={handleChange}
        placeholder={hint ?? label}
        autoComplete="off"
      />

      {searching ? (
        <p className="place-search__hint">{t('book.searching')}</p>
      ) : null}

      {results.length > 0 && (
        <ul className="place-results">
          {results.map((r) => {
            const away = near ? haversineKm(near, r) : null;

            return (
              <li key={r.id}>
                <button type="button" onClick={() => handlePick(r)}>
                  <span className="place-results__name">{r.name}</span>
                  <span className="place-results__meta">
                    {r.quartier ? <span>{r.quartier}</span> : null}
                    {away != null ? <span>{away.toFixed(1)} km</span> : null}
                    {/* Named, not colour-coded: a badge that only differs by
                        colour says nothing to a screen reader or to anyone who
                        cannot distinguish the two. */}
                    <span className="place-results__match">
                      {MATCH_LABELS[getLocale()]?.[r.matchType] ?? r.matchType}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {!searching && !picked && query.length >= 3 && results.length === 0 && !errorMessage ? (
        <p className="place-search__hint">
          Nothing found. Try the carrefour or quartier name.
        </p>
      ) : null}

      {errorMessage ? <p className="place-search__hint">{errorMessage}</p> : null}
    </div>
  );
}
