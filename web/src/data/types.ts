export interface Geo { lat: number; lon: number; }
export interface Address { street: string | null; city: string | null; state: string | null; zip: string | null; }

export type CardEligibility = 'ma_resident' | 'town_resident' | 'town_or_works' | 'network' | 'none' | 'unknown';
export type PassPickup = 'same_as_card' | 'ma_resident' | 'town_resident' | 'town_cardholder_only' | 'network' | 'walkin_for_nonresidents' | 'none' | 'unknown';

export interface Library {
  id: string; name: string; town: string; network: string; platform: string;
  card_page: string | null; address: Address | null; geo: Geo | null;
  card_eligibility: CardEligibility; pass_pickup_default: PassPickup;
  eligibility_source_phrase?: string | null; pickup_source_phrase?: string | null;
  resident_zips: string[];
}

export type CouponForm = 'free' | 'percent-off' | 'dollar-off' | 'per-person-price' | 'bogo' | 'discount';
export type CapacityKind = 'people' | 'vehicle' | 'ticket' | 'unspecified';
export interface AudiencePrice { audience: string; price: number | null; age_range?: { min: number | null; max: number | null } | null; source_phrase?: string | null; }
export interface AudiencePolicy { audience: string; form: CouponForm; value?: number | null; age_range?: { min: number | null; max: number | null } | null; count?: number | null; source_phrase?: string | null; }
export interface Capacity { kind: CapacityKind; n: number | null; }
export interface Coupon { capacity: Capacity; audience_policies: AudiencePolicy[]; summary?: string | null; source_phrase_block?: string | null; }

export type DayKey = 'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday' | 'saturday' | 'sunday';
export type Hours = Record<DayKey, string>; // "HH:MM-HH:MM" | "closed" | "unknown"

export interface VisitorEligibility { residency: 'ma_resident' | 'town_resident' | 'none' | 'unknown'; scope?: string | null; locals_free?: boolean; note?: string | null; source_phrase?: string | null; }
export interface Reservation { required: 'none' | 'timed_entry' | 'walk_in_ok'; booking_url?: string | null; lead_time_hours?: number | null; pass_holder_path?: string; pass_holder_url?: string | null; notes?: string | null; source_phrase?: string | null; }

export interface Attraction {
  slug: string; name: string; website?: string | null; phone?: string | null;
  address?: Address | null; geo?: Geo | null; description?: string | null;
  categories: string[]; hero_image?: string | null; hours?: Hours | null;
  prices: AudiencePrice[]; visitor_eligibility?: VisitorEligibility | null;
  reservation?: Reservation | null; sources: string[];
}

export type PassForm = 'digital_email' | 'physical_circ' | 'physical_coupon';
export interface Restrictions {
  blackout: { month: number; day: number | null }[]; blackout_recurring: string[];
  weekdays_only: boolean; seasonal: { start_month: number; end_month: number } | null;
  advance_booking_required: boolean; advance_booking_hours: number | null;
  booking_frequency_limit?: string | null; late_return_penalty?: string | null;
}
export interface ResidencyRestriction { restricted: 'yes' | 'no' | 'unknown'; scope: 'town' | 'ma' | null; source?: string | null; evidence?: string | null; }
export interface Pass {
  library_id: string; attraction_slug: string; pass_form: PassForm;
  available_at_branches: 'all' | string[]; source_url?: string | null;
  coupon: Coupon | null; restrictions: Restrictions | null;
  residency_restriction: ResidencyRestriction; availability: Record<string, string>;
  eligibility_override?: unknown;
}
export interface Branch { id: string; library_id: string; name: string; code?: string | null; geo?: Geo | null; }

export interface LibrariesJson { _meta: unknown; libraries: Library[]; }
export interface AttractionsJson { _meta: unknown; attractions: Attraction[]; }
export interface PassesJson { _meta: unknown; passes: Pass[]; }
export interface BranchesJson { _meta: unknown; branches: Branch[]; }
