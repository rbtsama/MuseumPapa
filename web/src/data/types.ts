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

/** Age-based pricing tier — applies to anyone matching the age range. */
export interface AgeTier {
  price: number;
  min_age?: number | null;   // e.g. Senior 65+
  max_age?: number | null;   // e.g. Child <=12, Youth 11-17
}

/** Identity-based pricing tier — requires status proof (student ID, military ID, educator badge). */
export interface IdentityTier {
  price: number;
  requires?: string | null;   // free-text human description, e.g. "valid student ID"
}

/**
 * Original (non-discounted) admission price for an attraction.
 *
 * Two conceptual layers:
 *   - age_pricing: tiers by age (adult/youth/child/senior + free_under_age threshold)
 *   - identity_pricing: tiers by status proof (student/educator/military)
 *
 * 两层定价模型:age_pricing 按年龄(任何人都适用),identity_pricing 按身份(需出示证件)。
 */
export interface OriginalPrice {
  age_pricing: {
    adult:  AgeTier | null;
    youth:  AgeTier | null;
    child:  AgeTier | null;
    senior: AgeTier | null;
    free_under_age: number | null;   // age threshold, NOT a price
  };
  identity_pricing: {
    student:  IdentityTier | null;
    educator: IdentityTier | null;
    military: IdentityTier | null;
  };
  family:    number | null;
  notes:     string | null;
  source_url: string | null;
}

export type CouponCapacityKind = 'people' | 'vehicle' | 'ticket' | 'unspecified';

export interface CouponCapacity {
  kind: CouponCapacityKind;
  n: number | null;
}

export type CouponAudience =
  | 'Everyone'
  | 'Adult'
  | 'Child'
  | 'Youth'
  | 'Senior'
  | 'Vehicle'
  | 'Single ticket';

export interface AgeRange {
  min: number | null;
  max: number | null;
}

export type CouponForm =
  | 'free'
  | 'percent-off'
  | 'dollar-off'
  | 'per-person-price'
  | 'discount';

export interface AudiencePolicy {
  audience: CouponAudience;
  age_range: AgeRange | null;
  count: number | null;
  form: CouponForm;
  value: number | null;
}

export interface Coupon {
  capacity: CouponCapacity;
  audience_policies: AudiencePolicy[];
}

export interface PassRestrictions {
  blackout_dates: string[];
  weekdays_only: boolean;
  seasonal: string | null;
}

export interface MuseumReservation {
  required: true;
  url: string | null;
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
  legacy_slugs?: string[];       // alternate slugs that map to this canonical attraction
  sources: string[];
  original_price: OriginalPrice | null;
  hero_image: HeroImage | null;
  geo: Geo | null;
  hours: Hours | null;
  museum_reservation: MuseumReservation | null;
}

export type PassTypeKind = 'digital' | 'physical-coupon' | 'physical-circ' | 'unknown';
export type PickupMethod = 'digital' | 'physical_at_branch';

export interface Pass {
  library_id: string;
  attraction_slug: string;
  pass_type: PassTypeKind;
  pass_type_raw: string;
  pickup_method: PickupMethod;
  pickup_branches: string[];
  coupon: Coupon;
  restrictions: PassRestrictions | null;
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
  branches: Branch[];
}

export interface LibrariesJson {
  libraries: Library[];
}

export interface AttractionsJson {
  attractions: Attraction[];
}

export interface PassesJson {
  passes: Pass[];
}
