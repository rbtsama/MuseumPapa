import { Link, useNavigate } from 'react-router';
import type { Attraction, Pass } from '../data/types';
import type { RecommendedPass } from '../lib/recommend';
import { FavoriteButton } from './FavoriteButton';
import { PassTypeLabel } from './PassTypeLabel';
import { AttractionInfoRows } from './AttractionInfoRows';
import { heroSrc } from '../lib/hero';
import { getLibrary } from '../data/load';
import { couponSummary } from '../lib/couponSummary';

/**
 * 'guest'     — not signed in. Show CTA to open SignInModal.
 * 'no_cards'  — signed in but no library cards entered. Show CTA → /settings/passes.
 * 'has_cards' — signed in with ≥1 card. Show real recommendations, or a "no match for
 *               this attraction" hint when recommendations is empty.
 */
export type CardpackState = 'guest' | 'no_cards' | 'has_cards';

interface Props {
  attraction: Attraction;
  recommendations: RecommendedPass[];
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
  attraction, recommendations, cardpackState = 'has_cards',
  closedToday = false, date, onBookPass, onSignInClick,
}: Props) {
  const navigate = useNavigate();
  // On the compact card we only surface eligible recommendations (incl. warn) so
  // usable options aren't crowded out by gray ineligible rows. The DETAIL page
  // still shows every rec (including ineligible-with-reason) for transparency.
  const eligibleRecs = recommendations.filter(rec => rec.verdict.eligible);
  const total = recommendations.length;
  const eligibleTotal = eligibleRecs.length;
  const dim = closedToday ? { filter: 'grayscale(0.7)', opacity: 0.55 } : {};

  const handleBook = (e: React.SyntheticEvent, pass: Pass) => {
    e.preventDefault();
    e.stopPropagation();
    onBookPass?.(pass);
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

      <div className="flex gap-3 p-3" style={dim}>
        <img
          src={heroSrc(attraction)}
          alt={attraction.name}
          loading="lazy"
          className="rounded-md object-cover bg-[color:var(--paper)] flex-shrink-0"
          style={{ width: 70, height: 70 }}
        />

        <div className="flex-grow min-w-0 pr-9">
          <h3 className="font-serif" style={{
            fontSize: 16, lineHeight: 1.25, color: 'var(--ink-2)', fontWeight: 700,
          }}>
            {attraction.name}
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

      {/* Body: recommendation rows, or one of three empty-state CTAs */}
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
            <button
              type="button"
              className="block w-full text-left px-3 py-3"
              style={{ fontSize: 12, color: 'var(--g)', background: 'transparent', border: 0, cursor: 'pointer' }}
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); navigate('/settings/passes'); }}
            >
              Add a library card or Library Pass to see your discounts →
            </button>
          ) : total === 0 ? (
            <div className="px-3 py-3 text-center" style={{ fontSize: 11, color: 'var(--ink-3)', fontStyle: 'italic' }}>
              None of your library cards cover this attraction
            </div>
          ) : eligibleTotal === 0 ? (
            // Had recommendations, but none eligible for this user's cards.
            // Keep the card uncrowded — point them to the detail page (the whole
            // tile is a Link) where every option + reason is shown.
            <div className="px-3 py-3 text-center" style={{ fontSize: 11, color: 'var(--ink-3)', fontStyle: 'italic' }}>
              No eligible pass for your cards — see details
            </div>
          ) : (
            <>
              {eligibleRecs.slice(0, MAX_ROWS_VISIBLE).map((rec, i) => {
                const lib = getLibrary(rec.pass.library_id);
                // For digital_email passes show library name; for physical show town.
                const locationText = rec.pass.pass_form === 'digital_email'
                  ? (lib?.name ?? rec.pass.library_id)
                  : (lib?.town ?? rec.pass.library_id);

                const discountLabel = couponSummary(rec.pass.coupon);
                const { eligible, warnings, reasons } = rec.verdict;
                const isBookable = eligible;  // blocked passes are NOT bookable

                return (
                  <div
                    key={`${rec.pass.library_id}-${rec.pass.pass_form}-${i}`}
                    className="flex items-center gap-3 px-3 py-2"
                    style={{ borderTop: i === 0 ? 'none' : '1px solid var(--rule)' }}
                  >
                    <div className="flex-grow min-w-0 flex flex-col gap-0.5">
                      {/* Location + pass type row */}
                      <div className="flex items-center gap-1.5 min-w-0" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
                        <span style={{
                          color: 'var(--ink-2)', fontWeight: 500, fontSize: 13,
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                          {locationText}
                        </span>
                      </div>

                      {/* Pass type + discount label + eligibility badge */}
                      <div className="flex items-center flex-wrap gap-x-1.5 gap-y-0.5 min-w-0">
                        <PassTypeLabel type={rec.pass.pass_form} />
                        <span style={{ fontSize: 12, color: 'var(--ink-2)', fontWeight: 600 }}>
                          {discountLabel}
                        </span>

                        {/* Eligibility badge — driven strictly from verdict */}
                        {!eligible ? (
                          <span
                            className="inline-block whitespace-nowrap"
                            style={{
                              fontSize: 11, fontWeight: 500,
                              background: 'var(--paper)', color: 'var(--ink-3)',
                              border: '1px solid var(--rule)',
                              padding: '1px 5px', borderRadius: 3,
                            }}
                            title={reasons[0]}
                          >
                            Not eligible
                          </span>
                        ) : warnings.length > 0 ? (
                          <span
                            className="inline-block whitespace-nowrap"
                            style={{
                              fontSize: 11, fontWeight: 500,
                              background: 'var(--or-pale)', color: 'var(--or)',
                              border: '1px solid var(--or)',
                              padding: '1px 5px', borderRadius: 3,
                            }}
                            title={warnings[0]}
                          >
                            Eligibility unconfirmed
                          </span>
                        ) : null}
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={(e) => {
                        if (!isBookable) { e.preventDefault(); e.stopPropagation(); return; }
                        handleBook(e, rec.pass);
                      }}
                      disabled={!isBookable}
                      className="flex-shrink-0 rounded-md inline-flex flex-col items-center"
                      style={{
                        background: isBookable ? 'var(--g)' : 'var(--paper)',
                        color: isBookable ? 'var(--white)' : 'var(--ink-3)',
                        fontSize: 12,
                        fontWeight: 600,
                        padding: '6px 12px',
                        border: isBookable ? 'none' : '1px solid var(--rule)',
                        cursor: isBookable ? 'pointer' : 'not-allowed',
                        userSelect: 'none',
                        lineHeight: 1.1,
                        opacity: isBookable ? 1 : 0.6,
                      }}
                      title={!isBookable ? (reasons[0] ?? 'Not eligible') : undefined}
                    >
                      <span>Book</span>
                      {!isBookable && (
                        <span style={{
                          fontSize: 9, fontWeight: 400, fontStyle: 'italic',
                          color: 'var(--ink-3)', marginTop: 1,
                        }}>Not eligible</span>
                      )}
                    </button>
                  </div>
                );
              })}

              {eligibleTotal > MAX_ROWS_VISIBLE && (
                <div className="px-3 py-2 text-center" style={{
                  borderTop: '1px solid var(--rule)', background: 'var(--bg)',
                  fontSize: 12, color: 'var(--g)', fontWeight: 500,
                }}>
                  + {eligibleTotal - MAX_ROWS_VISIBLE} more option{eligibleTotal - MAX_ROWS_VISIBLE === 1 ? '' : 's'} →
                </div>
              )}
            </>
          )}
        </div>
      )}
    </Link>
  );
}
