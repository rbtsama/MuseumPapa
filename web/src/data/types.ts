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
  youth: number | null;
  senior: number | null;
  student: number | null;
  military: number | null;
  educator: number | null;
  family: number | null;
  free_under_age: number | null;
  notes: string | null;
  source_url: string | null;
}

export type EligibilityTag =
  | 'all'
  | 'adults_only'
  | 'children_only'
  | 'vehicle'
  | 'single_ticket'
  | 'members_free'
  | 'seniors_free'
  | 'students_only'
  | 'military_free'
  | 'educator_free'
  | 'family'
  | 'groups'
  | 'residents_only';

export type ExclusionTag =
  | 'weekdays_only'
  | 'weekends_only'
  | 'blackout_dates'
  | 'reservation_required'
  | 'id_required'
  | string;  // allow `seasonal:May-Oct` style

export type BoostTag =
  | 'ebt_discount'
  | 'snap_free'
  | 'library_card_required'
  | 'members_discount'
  | 'gift_shop_discount';

export interface Policy {
  max_people: number | null;
  max_adults: number | null;
  max_children: number | null;
  free_under_age: number | null;
  savings_per_person_usd: number | null;
  discount_percent: number | null;
  discount_dollar_off: number | null;
  eligibility_tags: EligibilityTag[];
  exclusions: ExclusionTag[];
  boosts: BoostTag[];
  notes: string | null;
  raw: string | null;
}

export interface HeroImage {
  og_image_url: string | null;
  local_path: string | null;
}

export type DayKey = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun';

export interface Hours {
  status?: 'ok' | 'varies' | 'seasonal';
  regular_hours: Record<DayKey, string> | null;  // "Closed" or e.g. "9:00 AM – 5:00 PM"; null when status='varies'
  notes: string | null;
  source_url: string | null;
}

export interface Attraction {
  slug: string;
  museum_name: string;
  address: string;
  website: string;
  phone: string | null;
  description: string | null;
  categories: string[];          // canonical 7-class set: Children | History | Nature | Science | Art | Performance | Sports
  categories_raw?: string[];     // original Assabet labels (audit / debug only)
  sources: string[];
  original_price: OriginalPrice | null;
  hero_image: HeroImage | null;
  geo: Geo | null;
  hours: Hours | null;
}

export type PassTypeKind = 'digital' | 'physical-coupon' | 'physical-circ' | 'unknown';
export type DiscountClass = 'free' | 'half' | 'percent-off' | 'dollar-off' | 'price' | 'discount' | 'unknown';

export interface Discount {
  class: DiscountClass;
  label: string;
  raw: string;
}

export type PickupMethod = 'digital' | 'physical_at_branch';

export interface Pass {
  library_id: string;
  attraction_slug: string;
  pass_type: PassTypeKind;
  pass_type_raw: string;
  pickup_method: PickupMethod;
  pickup_branches: string[];   // branch ids; empty for digital
  discount: Discount;
  policy: Policy | null;
  source_url: string;
  availability: Record<string, string> | null;
}

export interface Branch {
  id: string;
  name: string;
  parent_lib_id: string;
  address: { street: string; city: string; state: string; zip: string | null };
  geo: Geo;
  hours_raw: string | null;
}

export interface BranchesJson {
  _meta: { built_at: string; n_branches: number; n_multi_branch_libs: number };
  branches: Branch[];
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
