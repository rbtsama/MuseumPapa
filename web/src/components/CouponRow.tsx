import type { Pass, Library, Geo } from '../data/types';
import type { PassVerdict } from '../lib/eligibility';
import { PassTypeLabel } from './PassTypeLabel';
import { CouponLine, formatCapacity } from './CouponLine';
import { couponSummary } from '../lib/couponSummary';
import { PickupBranches } from './PickupBranches';

interface CouponRowProps {
  pass: Pass;
  library: Library;
  verdict: PassVerdict;
  distanceMi: number | null;
  /** User home centroid, for the multi-branch pickup distances. */
  userGeo?: Geo | null;
  /** Render a top border between rows; pass `false` on the first row in a list. */
  showTopBorder?: boolean;
  onBook: (pass: Pass) => void;
}

/** Shared coupon row used by the detail page and the list card. */
export function CouponRow({
  pass, library, verdict, distanceMi, userGeo = null, showTopBorder = true, onBook,
}: CouponRowProps) {
  // Physical passes are collected in person; digital (email) ones are not, so
  // only the physical forms get the "which branch do I pick it up at" affordance.
  const isPhysical = pass.pass_form === 'physical_coupon' || pass.pass_form === 'physical_circ';
  const isDigital = pass.pass_form === 'digital_email';

  const locationText = isDigital ? library.name : library.town;

  const capacityText = pass.coupon ? formatCapacity(pass.coupon.capacity) : null;

  const handleBook = (e: React.SyntheticEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (verdict.eligible) onBook(pass);
  };

  // Eligibility chip
  let chip: React.ReactNode = null;
  if (!verdict.eligible) {
    chip = (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        background: 'var(--paper)', color: 'var(--ink-3)',
        border: '1px solid var(--rule)',
        fontSize: 11, fontWeight: 500, padding: '1px 7px', borderRadius: 10,
      }}>
        Not eligible
        {verdict.reasons[0] && (
          <span style={{ fontWeight: 400 }}> · {verdict.reasons[0]}</span>
        )}
      </span>
    );
  } else if (verdict.warnings.length > 0) {
    chip = (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        background: 'var(--or-pale)', color: 'var(--or)',
        border: '1px solid var(--or)',
        fontSize: 11, fontWeight: 500, padding: '1px 7px', borderRadius: 10,
      }}>
        ⚠ {verdict.warnings[0]}
      </span>
    );
  }

  const bookBg = verdict.eligible
    ? (verdict.warnings.length > 0 ? 'var(--or)' : 'var(--g)')
    : 'var(--paper)';
  const bookColor = verdict.eligible ? 'var(--white)' : 'var(--ink-3)';

  return (
    <div
      style={{ borderTop: showTopBorder ? '1px solid var(--rule)' : 'none' }}
    >
      <div className="flex items-center gap-3 px-3 py-2">
        <div className="flex-grow min-w-0 flex flex-col gap-0.5">
          <div className="flex items-center gap-1.5 min-w-0" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
            <span style={{ color: 'var(--ink-2)', fontWeight: 500, fontSize: 13,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {locationText}
            </span>
            {!isDigital && distanceMi != null && (
              <span className="flex-shrink-0" style={{ fontSize: 11 }}>
                · {Math.round(distanceMi)} mi
              </span>
            )}
          </div>
          <div className="flex items-center flex-wrap gap-x-1.5 gap-y-0.5 min-w-0">
            <PassTypeLabel type={pass.pass_form} />
            {pass.coupon && <CouponLine coupon={pass.coupon} align="left" />}
            {!pass.coupon && (
              <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>{couponSummary(null)}</span>
            )}
            {capacityText && (
              <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>
                ({capacityText})
              </span>
            )}
          </div>
          {chip && <div style={{ marginTop: 2 }}>{chip}</div>}
        </div>

        <button
          type="button"
          onClick={handleBook}
          disabled={!verdict.eligible}
          className="flex-shrink-0 rounded-md inline-flex flex-col items-center"
          style={{
            background: bookBg,
            color: bookColor,
            fontSize: 12,
            fontWeight: 600,
            padding: '6px 12px',
            border: 'none',
            cursor: verdict.eligible ? 'pointer' : 'not-allowed',
            userSelect: 'none',
            lineHeight: 1.1,
            opacity: verdict.eligible ? 1 : 0.6,
          }}
          title={!verdict.eligible ? (verdict.reasons[0] ?? 'Not eligible') : undefined}
        >
          <span>Book</span>
        </button>
      </div>

      {/* Restriction notes */}
      {(pass.pass_form === 'physical_circ' ||
        pass.restrictions?.late_return_penalty ||
        pass.restrictions?.booking_frequency_limit) && (
        <div style={{ padding: '0 12px 8px', fontSize: 11, color: 'var(--ink-3)', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {pass.pass_form === 'physical_circ' && (
            <span>Pick up and return at the library — note late-return fees</span>
          )}
          {pass.restrictions?.late_return_penalty && (
            <span>{pass.restrictions.late_return_penalty}</span>
          )}
          {pass.restrictions?.booking_frequency_limit && (
            <span>Booking limit: {pass.restrictions.booking_frequency_limit}</span>
          )}
        </div>
      )}

      {/* Where to pick up — only for physical passes at multi-branch libraries.
          Renders nothing for single-branch libraries / digital passes. */}
      {isPhysical && (
        <div style={{ padding: '0 12px 8px' }}>
          <PickupBranches libraryId={library.id} userGeo={userGeo} />
        </div>
      )}
    </div>
  );
}
