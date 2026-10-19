"use client";

export function ConnectionFields({
  gsc,
  ga4,
  setGsc,
  setGa4,
  disabled = false,
}: {
  gsc: string;
  ga4: string;
  setGsc: (value: string) => void;
  setGa4: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <div>
        <label htmlFor="gsc-property" className="mb-1.5 block font-medium">
          Search Console property
        </label>
        <input
          id="gsc-property"
          className="w-full"
          value={gsc}
          onChange={(event) => setGsc(event.target.value)}
          placeholder="sc-domain:example.com"
          maxLength={2048}
          disabled={disabled}
          aria-describedby="gsc-help"
        />
        <p id="gsc-help" className="mt-2 text-xs text-muted">
          Use the exact property from Search Console: sc-domain:example.com for
          a domain property, or https://example.com/ for a URL-prefix property.
          Optional.
        </p>
      </div>
      <div>
        <label htmlFor="ga4-property" className="mb-1.5 block font-medium">
          GA4 property ID
        </label>
        <input
          id="ga4-property"
          className="w-full"
          value={ga4}
          onChange={(event) => setGa4(event.target.value)}
          placeholder="123456789"
          inputMode="numeric"
          pattern="[1-9][0-9]{0,29}"
          maxLength={30}
          disabled={disabled}
          aria-describedby="ga4-help"
        />
        <p id="ga4-help" className="mt-2 text-xs text-muted">
          Find the numeric ID in Google Analytics → Admin → Property details.
          This is not the G- measurement ID. Optional.
        </p>
      </div>
    </div>
  );
}
