import { Modal, ModalContent, ModalBody } from '@heroui/react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onGetStarted: () => void;
  /** Optional secondary CTA at the bottom for returning users. When omitted
   *  the "Already a member? Sign in" link is hidden. */
  onSignIn?: () => void;
}

/**
 * Marketing landing modal shown to first-time guests. Primary CTA "Get
 * started" → SignUpModal (new account). Secondary link "Already a member?
 * Sign in" → SignInModal. Close button dismisses for a week.
 *
 * Designed brand-first: forest-green hero band carrying the headline, a
 * subtitle on the off-white body, and a single high-contrast CTA.
 */
export function LandingPromoModal({ isOpen, onClose, onGetStarted, onSignIn }: Props) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      hideCloseButton
      placement="center"
      backdrop="opaque"
      classNames={{
        base: 'rounded-2xl overflow-hidden',
        body: 'p-0',
      }}
    >
      <ModalContent>
        <ModalBody>
          {/* Close button — small ✕ in the top-right corner over the green band. */}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              position: 'absolute', top: 12, right: 12, zIndex: 10,
              width: 28, height: 28, borderRadius: '50%',
              border: 0, cursor: 'pointer',
              background: 'rgba(255, 255, 255, 0.18)',
              color: 'rgba(255, 255, 255, 0.9)',
              fontSize: 16, lineHeight: 1,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            ✕
          </button>

          {/* Hero band — forest green, carries the headline. */}
          <div style={{
            background: 'var(--g)',
            color: 'var(--white)',
            padding: '32px 28px 28px',
            position: 'relative',
          }}>
            {/* Subtle decorative dots — adds the marketing feel without being noisy. */}
            <div aria-hidden style={{
              position: 'absolute', top: 0, right: 0,
              width: 140, height: 140,
              background: 'radial-gradient(circle at 70% 30%, rgba(255,255,255,0.10) 0%, transparent 60%)',
              pointerEvents: 'none',
            }} />
            <p style={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              opacity: 0.78,
              margin: '0 0 12px',
            }}>
              MuseumPapa
            </p>
            <h2 style={{
              fontSize: 26,
              lineHeight: 1.18,
              fontWeight: 700,
              margin: 0,
              maxWidth: 340,
            }}>
              Free museum visits with&nbsp;your library&nbsp;card
            </h2>
          </div>

          {/* Body — subtitle + CTA. */}
          <div style={{
            background: 'var(--white)',
            padding: '22px 28px 26px',
          }}>
            <p style={{
              fontSize: 14,
              lineHeight: 1.55,
              color: 'var(--ink-2)',
              margin: '0 0 6px',
              fontWeight: 500,
            }}>
              Covers 100+ museums across Massachusetts
            </p>
            <p style={{
              fontSize: 12,
              lineHeight: 1.55,
              color: 'var(--ink-3)',
              margin: '0 0 20px',
            }}>
              Link the library cards you already hold, pick a date, and see which museums are free or discounted that day.
            </p>
            <button
              type="button"
              onClick={onGetStarted}
              style={{
                width: '100%',
                padding: '12px 16px',
                border: 0,
                borderRadius: 8,
                background: 'var(--g)',
                color: 'var(--white)',
                fontSize: 14,
                fontWeight: 600,
                cursor: 'pointer',
                letterSpacing: '0.01em',
                boxShadow: '0 1px 2px rgba(0,0,0,0.08)',
              }}
            >
              Get started
            </button>
            <p style={{
              fontSize: 11,
              color: 'var(--ink-3)',
              textAlign: 'center',
              margin: '12px 0 0',
            }}>
              Already a member? <button
                type="button"
                onClick={onSignIn ?? onGetStarted}
                style={{
                  background: 'transparent', border: 0, padding: 0, cursor: 'pointer',
                  color: 'var(--g)', fontWeight: 600, textDecoration: 'none',
                  fontSize: 11,
                }}
              >Sign in →</button>
            </p>
          </div>
        </ModalBody>
      </ModalContent>
    </Modal>
  );
}
