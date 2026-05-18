import { Link } from 'react-router';
import type { Attraction, Pass } from '../data/types';
import type { PickedTag } from '../lib/tag-algorithm';
import { FavoriteButton } from './FavoriteButton';
import { PassTypeLabel } from './PassTypeLabel';
import { CouponLine, formatCapacity } from './CouponLine';
import { AttractionInfoRows } from './AttractionInfoRows';
import { heroSrc } from '../lib/hero';
import { getBranchesForPass } from '../data/load';

/**
 * 'guest'     — not signed in. Show CTA to open SignInModal.
 * 'no_cards'  — signed in but no library cards entered. Show CTA → /settings/passes.
 * 'has_cards' — signed in with ≥1 card. Show real coupons, or a "no match for
 *               this attraction" hint when pickedTags is empty.
 */
export type CardpackState = 'guest' | 'no_cards' | 'has_cards';

interface Props {
  attraction: Attraction;
  pickedTags: PickedTag[];
  cardpackState?: CardpackState;
  closedToday?: boolean;
  /** Selected date (ISO) — used to look up today's hours. */
  date?: string;
  /** Called when user taps a per-pass "Book" button. List page opens the modal. */
  onBookPass?: (pass: Pass) => void;
  /** Called when the guest empty-state CTA is clicked. List page opens sign-in. */
  onSignInClick?: () => void;
}

const MAX_ROWS_VISIBLE = 3;

export function AttractionCard({
  attraction, pickedTags, cardpackState = 'has_cards',
  closedToday = false, date, onBookPass, onSignInClick,
}: Props) {
  const total = pickedTags.length;
  const dim = closedToday ? { filter: 'grayscale(0.7)', opacity: 0.55 } : {};

  const handleBook = (e: React.SyntheticEvent, pass: Pass) => {
    e.preventDefault();
    e.stopPropagation();
    onBookPass?.(pass);
  };

  const handleBookKeyDown = (e: React.KeyboardEvent, pass: Pass) => {
    if (e.key === 'Enter' || e.key === ' ') {
      handleBook(e, pass);
    }
  };

  return (
    <Link
      to={`/attractions/${attraction.slug}`}
      className="block rounded-lg overflow-hidden mb-3 transition-colors active:bg-[color:var(--paper)]"
      style={{
        position: 'relative',
        background: 'var(--white)',
        color: 'inherit',
        textDecoration: 'none',
        border: '1px solid var(--rule)',
      }}
    >
      <div className="absolute" style={{ top: 6, right: 6, zIndex: 1 }}>
        <FavoriteButton slug={attraction.slug} variant="overlay" />
      </div>

      {/* Header: square 70×70 hero with rounded corners; standard p-3 padding
          around the whole header so the image and meta both sit inside the
          card's content gutters. */}
      <div className="flex gap-3 p-3" style={dim}>
        <img
          src={heroSrc(attraction)}
          alt=""
          loading="lazy"
          className="rounded-md object-cover bg-[color:var(--paper)] flex-shrink-0"
          style={{ width: 70, height: 70 }}
        />

        <div className="flex-grow min-w-0 pr-9">
          <h3 className="font-serif" style={{
            fontSize: 16, lineHeight: 1.25, color: 'var(--ink-2)', fontWeight: 700,
          }}>
            {attraction.museum_name}
          </h3>

          <AttractionInfoRows
            attraction={attraction}
            date={date}
            closedToday={closedToday}
          />

          {closedToday && (
            <span className="inline-block mt-2 px-2 py-0.5 rounded-md" style={{
              fontSize: 11, fontWeight: 500,
              background: 'var(--rd-pale)', color: 'var(--rd)',
            }}>
              Closed
            </span>
          )}
        </div>
      </div>

      {/* Body: pass options, or one of three empty-state CTAs */}
      {closedToday ? null : (
        <div className="border-t" style={{ borderColor: 'var(--rule)' }}>
          {cardpackState === 'guest' ? (
            <button
              type="button"
              className="block w-full text-left px-3 py-3"
              style={{ fontSize: 12, color: 'var(--g)', background: 'transparent', border: 0, cursor: 'pointer' }}
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); onSignInClick?.(); }}
            >
              Sign in to see the discounts available to your library cards →
            </button>
          ) : cardpackState === 'no_cards' ? (
            <Link
              to="/settings/passes"
              onClick={(e) => e.stopPropagation()}
              className="block px-3 py-3"
              style={{ fontSize: 12, color: 'var(--g)', textDecoration: 'none' }}
            >
              Add a library card or Library Pass to see your discounts →
            </Link>
          ) : total === 0 ? (
            <div className="px-3 py-3 text-center" style={{ fontSize: 11, color: 'var(--ink-3)', fontStyle: 'italic' }}>
              None of your library cards cover this attraction
            </div>
          ) : (
            <>
          {pickedTags.slice(0, MAX_ROWS_VISIBLE).map((t, i) => {
            const isDigital = t.pass.pickup_method === 'digital';
            // For physical, prefer the actual pickup branch(es). Single-branch
            // libs synthesize `<lib_id>--main`, so this still resolves cleanly.
            const branches = isDigital ? [] : getBranchesForPass(t.pass);
            const showBranchLabel =
              !isDigital && branches.length === 1 && branches[0].id !== `${t.pass.library_id}--main`;
            const branchSummary = !isDigital && branches.length > 1
              ? `${t.library.town} · ${branches.length} branches`
              : null;

            const locationText = isDigital ? t.library.name
              : branchSummary ? branchSummary
              : showBranchLabel ? `${branches[0].name} · ${branches[0].address.street}`
              : t.library.town;

            const capacityText = formatCapacity(t.pass.coupon.capacity);

            return (
              <div
                key={`${t.pass.library_id}-${i}`}
                className="flex items-center gap-3 px-3 py-2"
                style={{ borderTop: i === 0 ? 'none' : '1px solid var(--rule)' }}
              >
                <div className="flex-grow min-w-0 flex flex-col gap-0.5">
                  {/* Row 1: location + distance only — the type label moved
                      down to the coupon row where it sits naturally with the
                      pricing details. */}
                  <div className="flex items-center gap-1.5 min-w-0" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
                    <span style={{ color: 'var(--ink-2)', fontWeight: 500, fontSize: 13,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {locationText}
                    </span>
                    {!isDigital && t.distanceMi != null && (
                      <span className="flex-shrink-0" style={{ fontSize: 11 }}>
                        · {Math.round(t.distanceMi)} mi
                      </span>
                    )}
                  </div>
                  {/* Row 2: [Type label] price1 · price2 · ... (up to N).
                      Capacity now lives in a small trailing parenthetical
                      instead of a leading person-icon group, so the eye
                      scans prices first. */}
                  {/* Center alignment, not baseline: the type pill has a
                      border/padding that makes it taller than the plain price
                      text, and the row mixes 11/12/13px tokens. items-center
                      gives all three (pill, prices, "(up to N)") a single
                      shared vertical midline. */}
                  <div className="flex items-center flex-wrap gap-x-1.5 gap-y-0.5 min-w-0">
                    <PassTypeLabel type={t.pass.pass_type} />
                    <CouponLine coupon={t.pass.coupon} align="left" />
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
                  onClick={(e) => handleBook(e, t.pass)}
                  onKeyDown={(e) => handleBookKeyDown(e, t.pass)}
                  className="flex-shrink-0 rounded-md inline-flex flex-col items-center"
                  style={{
                    background: t.userHasCard ? 'var(--g)' : 'var(--paper)',
                    color: t.userHasCard ? 'var(--white)' : 'var(--ink-3)',
                    fontSize: 12,
                    fontWeight: 600,
                    padding: '6px 12px',
                    border: 'none',
                    cursor: 'pointer',
                    userSelect: 'none',
                    lineHeight: 1.1,
                  }}
                  title={t.userHasCard ? undefined : 'You don\'t have a card from this library'}
                >
                  <span>Book</span>
                  {!t.userHasCard && (
                    <span style={{
                      fontSize: 9, fontWeight: 400, fontStyle: 'italic',
                      color: 'var(--ink-3)', marginTop: 1,
                    }}>no card</span>
                  )}
                </span>
              </div>
            );
          })}

          {total > MAX_ROWS_VISIBLE && (
            <div className="px-3 py-2 text-center" style={{
              borderTop: '1px solid var(--rule)', background: 'var(--bg)',
              fontSize: 12, color: 'var(--g)', fontWeight: 500,
            }}>
              + {total - MAX_ROWS_VISIBLE} more coupon{total - MAX_ROWS_VISIBLE === 1 ? '' : 's'} →
            </div>
          )}
            </>
          )}
        </div>
      )}
    </Link>
  );
}
