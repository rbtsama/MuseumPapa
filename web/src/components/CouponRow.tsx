import type { Pass, Library } from '../data/types';
import { PassTypeLabel } from './PassTypeLabel';
import { CouponLine, formatCapacity } from './CouponLine';
import { getBranchesForPass } from '../data/load';

interface CouponRowProps {
  pass: Pass;
  library: Library;
  distanceMi: number | null;
  userHasCard: boolean;
  /** Render a top border between rows; pass `false` on the first row in a list. */
  showTopBorder?: boolean;
  onBook: (pass: Pass) => void;
}

/**
 * Single coupon row. Visual format matches `AttractionCard`'s per-pass row so
 * the detail page and list page read identically. Kept as a focused component
 * so it can also slot back into the list card in the future.
 *
 * No-card sub-label is preserved for future list-page reuse. On the detail
 * page no-card rows are filtered out upstream, so `userHasCard` is always true
 * there.
 */
export function CouponRow({
  pass, library, distanceMi, userHasCard, showTopBorder = true, onBook,
}: CouponRowProps) {
  const isDigital = pass.pickup_method === 'digital';
  const branches = isDigital ? [] : getBranchesForPass(pass);
  const showBranchLabel =
    !isDigital && branches.length === 1 && branches[0].id !== `${pass.library_id}--main`;
  const branchSummary = !isDigital && branches.length > 1
    ? `${library.town} · ${branches.length} branches`
    : null;

  const locationText = isDigital ? library.name
    : branchSummary ? branchSummary
    : showBranchLabel ? `${branches[0].name} · ${branches[0].address.street}`
    : library.town;

  const capacityText = formatCapacity(pass.coupon.capacity);

  const handleBook = (e: React.SyntheticEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onBook(pass);
  };

  const handleBookKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      handleBook(e);
    }
  };

  return (
    <div
      className="flex items-center gap-3 px-3 py-2"
      style={{ borderTop: showTopBorder ? '1px solid var(--rule)' : 'none' }}
    >
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
          <PassTypeLabel type={pass.pass_type} />
          <CouponLine coupon={pass.coupon} align="left" />
          {capacityText && (
            <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>
              ({capacityText})
            </span>
          )}
        </div>
      </div>

      <span
        role="button"
        tabIndex={0}
        onClick={handleBook}
        onKeyDown={handleBookKeyDown}
        className="flex-shrink-0 rounded-md inline-flex flex-col items-center"
        style={{
          background: userHasCard ? 'var(--g)' : 'var(--paper)',
          color: userHasCard ? 'var(--white)' : 'var(--ink-3)',
          fontSize: 12,
          fontWeight: 600,
          padding: '6px 12px',
          border: 'none',
          cursor: 'pointer',
          userSelect: 'none',
          lineHeight: 1.1,
        }}
        title={userHasCard ? undefined : 'You don\'t have a card from this library'}
      >
        <span>Book</span>
        {!userHasCard && (
          <span style={{
            fontSize: 9, fontWeight: 400, fontStyle: 'italic',
            color: 'var(--ink-3)', marginTop: 1,
          }}>no card</span>
        )}
      </span>
    </div>
  );
}
