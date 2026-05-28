// Types mirror the structured JSON from data/structured/.
// Kept loose where upstream schema is loose; tight where the matrix joins/renders.

export type PassForm = "digital_email" | "physical_coupon" | "physical_circ";
export type Verdict = "network_open" | "own_card_only" | "not_verified" | "ambiguous";
export type Residency = "no" | "yes" | "unknown";
export type Eligibility =
  | "ma_resident"
  | "town_resident"
  | "town_or_works"
  | "network"
  | "unknown";

export interface Library {
  id: string;
  name: string;
  town: string;
  network: string;
  platform: string;
  consortium_label?: string;
  card_issuance_group?: string;
  card_issuance_groups?: string[];
  card_auth_groups?: string[];
  card_page?: string;
  pass_page?: string;
  address?: { street?: string; city?: string; state?: string; zip?: string };
  geo?: { lat: number; lon: number };
  card_eligibility: Eligibility;
  pass_pickup_default?: string;
  resident_zips?: string[];
  hours?: Record<string, string> | null;
  hours_note?: string | null;
}

export interface Attraction {
  slug: string;
  name: string;
  website?: string;
  phone?: string;
  address?: { street?: string; city?: string; state?: string; zip?: string };
  geo?: { lat: number; lon: number };
  description?: string;
  categories?: string[];
  hero_image?: string;
  prices?: Array<{
    audience: string;
    price: number | null;
    age_range?: { min: number | null; max: number | null } | null;
    source_phrase?: string | null;
  }>;
  booking_model?: string | null;
  booking_note?: string | null;
  closed_days?: string[] | null;
  visitor_eligibility?: unknown;
  reservation?: {
    required?: string;
    booking_url?: string | null;
    lead_time_hours?: number | null;
    pass_holder_path?: string | null;
    pass_holder_url?: string | null;
    notes?: string | null;
    source_phrase?: string | null;
  };
  hours?: Record<string, string> | null;
  hours_note?: string | null;
  sources?: unknown;
}

export interface Pass {
  library_id: string;
  attraction_slug: string;
  attraction_rawslug: string;
  pass_form: PassForm;
  available_at_branches: string | string[];
  source_url: string;
  coupon: {
    capacity?: { kind?: string; n?: number | null };
    audience_policies?: Array<{
      audience: string;
      age_range?: { min: number | null; max: number | null } | null;
      count?: number | null;
      form?: string;
      value?: number | null;
      source_phrase?: string | null;
    }>;
    summary: string;
    source_phrase_block?: string;
  };
  restrictions?: {
    blackout?: unknown[];
    blackout_recurring?: unknown[];
    weekdays_only?: boolean;
    seasonal?: unknown;
    advance_booking_required?: boolean;
    advance_booking_hours?: number | null;
    booking_frequency_limit?: string | null;
    late_return_penalty?: string | null;
  };
  residency_restriction?: {
    restricted: Residency;
    scope?: string | null;
    source?: string | null;
    evidence?: string | null;
  };
  requires_own_card?: boolean;
  own_card_evidence?: string | null;
  booking_access_probe?: {
    verdict: Verdict;
    source?: string | null;
    evidence?: string | null;
    prober_card?: string | null;
    probed_date?: string | null;
  };
  availability?: Record<string, "available" | "booked" | "closed" | string>;
}

export interface Branch {
  id: string;
  library_id: string;
  name: string;
  code?: string;
  geo?: { lat: number; lon: number };
}

export interface DataBundle {
  libraries: Library[];
  attractions: Attraction[];
  passes: Pass[];
  branches: Branch[];
  // Indices (built at load time, validated against pass count).
  passByPair: Map<string, Pass>; // key = `${attraction_slug}::${library_id}`
  libById: Map<string, Library>;
  attrBySlug: Map<string, Attraction>;
  // Branch index: multi-branch libs (BPL 24 / Cambridge 7 / Brookline 3) can
  // expand to per-branch sub-columns. Policy is institution-level so sub-cells
  // are pickup-location annotations, not separate facts.
  branchesByLib: Map<string, Branch[]>;
  // Column layout: networks in user-friendly order, each with its libraries by town.
  networks: Array<{ network: string; libraries: Library[] }>;
}
