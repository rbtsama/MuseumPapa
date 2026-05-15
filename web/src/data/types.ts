export interface LibraryAddress {
  street: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
}

export interface Geo {
  lat: number;
  lon: number;
}

export interface Library {
  id: string;
  name: string;
  town: string;
  network: string;
  platform: string;
  card_page: string;
  eligibility: string;
  supports_availability: boolean;
  address: LibraryAddress | null;
  geo: Geo | null;
}

export interface OriginalPrice {
  adult: number | null;
  child: number | null;
  senior: number | null;
  student: number | null;
  family: number | null;
  free_under_age: number | null;
  notes: string | null;
  source_url: string | null;
}

export interface HeroImage {
  og_image_url: string | null;
  local_path: string | null;
}

export type DayKey = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun';

export interface Hours {
  status?: 'ok' | 'varies';
  regular_hours: Record<DayKey, string> | null;  // "Closed" or e.g. "9:00 AM – 5:00 PM"; null when status='varies'
  notes: string | null;
  source_url: string | null;
}

export interface Attraction {
  slug: string;
  museum_name: string;
  address: string;
  website: string;
  categories: string[];
  sources: string[];
  original_price: OriginalPrice | null;
  hero_image: HeroImage | null;
  geo: Geo | null;
  hours: Hours | null;
}

export type PassTypeKind = 'digital' | 'physical-coupon' | 'loan-card' | 'unknown';
export type DiscountClass = 'free' | 'half' | 'percent-off' | 'dollar-off' | 'price' | 'discount' | 'unknown';

export interface Discount {
  class: DiscountClass;
  label: string;
  raw: string;
}

export interface Pass {
  library_id: string;
  attraction_slug: string;
  pass_type: PassTypeKind;
  pass_type_raw: string;
  discount: Discount;
  source_url: string;
  availability: Record<string, string> | null;
}

export interface LibrariesJson {
  _meta: { built_at: string; n_libraries: number; n_with_address: number; n_with_geo: number };
  libraries: Library[];
}

export interface AttractionsJson {
  _meta: {
    built_at: string;
    n_attractions: number;
    n_with_price: number;
    n_with_image: number;
    n_with_geo: number;
  };
  attractions: Attraction[];
}

export interface PassesJson {
  _meta: { built_at: string; n_passes: number; n_with_availability: number };
  passes: Pass[];
}
