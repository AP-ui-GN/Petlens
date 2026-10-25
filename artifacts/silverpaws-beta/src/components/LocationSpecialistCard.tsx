import { useState, type FormEvent } from 'react';
import { MapPin, Search } from 'lucide-react';

const MAPS_SEARCH_URL = 'https://www.google.com/maps/search/';
const SEARCH_TERM = 'Veterinary Physical Therapy';

function openMapsSearch(query: string) {
  const url = new URL(MAPS_SEARCH_URL);
  url.searchParams.set('api', '1');
  url.searchParams.set('query', query);
  window.open(url.toString(), '_blank', 'noopener,noreferrer');
}

export default function LocationSpecialistCard() {
  const [location, setLocation] = useState('');
  const [error, setError] = useState('');

  function searchNearby(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const place = location.trim();
    if (!place) {
      setError('Enter a ZIP code or city to search nearby.');
      return;
    }

    setError('');
    openMapsSearch(`${SEARCH_TERM} near ${place}`);
  }

  function searchCurrentLocation() {
    setError('');
    if (!navigator.geolocation) {
      setError('Location services are not available in this browser. Enter a ZIP code or city instead.');
      return;
    }

    const mapWindow = window.open('about:blank', '_blank');
    if (!mapWindow) {
      setError('Your browser blocked the map window. Allow pop-ups and try again.');
      return;
    }
    mapWindow.opener = null;
    mapWindow.document.title = 'Finding nearby veterinary physical therapy…';

    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const url = new URL(MAPS_SEARCH_URL);
        url.searchParams.set('api', '1');
        url.searchParams.set('query', `${SEARCH_TERM} near ${coords.latitude},${coords.longitude}`);
        mapWindow.location.replace(url.toString());
      },
      (geolocationError) => {
        mapWindow.close();
        setError(
          geolocationError.code === geolocationError.PERMISSION_DENIED
            ? 'Location permission was denied. Enter a ZIP code or city to search instead.'
            : 'Could not determine your location. Enter a ZIP code or city to search instead.',
        );
      },
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 60_000 },
    );
  }

  return (
    <section aria-labelledby="nearby-care-title" className="rounded-2xl border border-[#1669aa]/50 border-t-[#3794a4]/40 bg-[#0a2b3e] p-6 text-white shadow-2xl backdrop-blur-md">
      <div className="flex items-center gap-2">
        <MapPin aria-hidden="true" className="h-5 w-5 text-[#3eb49c]" />
        <h2 className="text-lg font-bold text-white" id="nearby-care-title">
          Find Care Nearby
        </h2>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-slate-300">
        Search Google Maps for veterinary physical therapy specialists near you.
      </p>

      <form className="mt-4 flex flex-col gap-2 sm:flex-row" onSubmit={searchNearby}>
        <label className="sr-only" htmlFor="specialist-location">
          ZIP code or city
        </label>
        <input
          autoComplete="postal-code"
          className="min-w-0 flex-1 rounded-xl border border-[#1669aa]/60 bg-slate-900/80 px-3 py-2 text-sm text-white placeholder:text-slate-400 focus:border-[#3794a4] focus:outline-none focus:ring-1 focus:ring-[#5e17eb]"
          id="specialist-location"
          onChange={(event) => setLocation(event.target.value)}
          placeholder="ZIP code or city"
          type="text"
          value={location}
        />
        <button
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#3eb49c] px-5 py-2.5 text-sm font-bold text-slate-950 transition-all hover:bg-[#3794a4] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#5e17eb]"
          type="submit"
        >
          <Search aria-hidden="true" className="h-4 w-4" />
          Search
        </button>
      </form>

      <button
        className="mt-3 w-full rounded-xl border border-slate-700 bg-slate-900/60 py-2.5 text-sm font-medium text-slate-300 transition-all hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#5e17eb]"
        onClick={searchCurrentLocation}
        type="button"
      >
        Use Current Location
      </button>
      {error && (
        <p className="mt-3 text-sm text-rose-300" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
