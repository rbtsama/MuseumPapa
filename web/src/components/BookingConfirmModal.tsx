import {
  Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button,
} from '@heroui/react';
import type { Pass, Library } from '../data/types';
import type { CardPack } from '../stores/cardpack';
import { passUrlForDate } from '../lib/reserveUrl';
import { todayIso } from '../lib/dates';

interface Props {
  pass: Pass | null;
  library: Library | null;
  cardpack: CardPack;
  /** ISO date the user picked. For Assabet passes the modal deep-links straight
   *  to the per-date reservation form so the user lands on the right calendar
   *  slot, not the per-museum page's top. Falls back to today when unset. */
  selectedDate?: string;
  /** When provided (non-null), renders a timed-entry reminder line with a link
   *  to the attraction's reservation page so the user knows to book a slot after
   *  picking up the pass. When omitted / null, no reminder is shown. */
  timedEntryUrl?: string | null;
  onClose: () => void;
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function CredentialBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-2">
      <div style={{
        fontSize: 11, color: 'var(--ink-3)', marginBottom: 4,
        textTransform: 'uppercase', letterSpacing: '0.04em',
      }}>
        {label}
      </div>
      <div
        className="rounded-md"
        style={{
          border: '1px solid var(--rule)',
          background: 'var(--white)',
          padding: '8px 12px',
        }}
      >
        <span style={{
          fontFamily: '"DM Mono", "Courier New", monospace',
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--ink-2)',
          letterSpacing: '0.02em',
          userSelect: 'all',
        }}>
          {value}
        </span>
      </div>
    </div>
  );
}

export function BookingConfirmModal({ pass, library, cardpack, selectedDate, timedEntryUrl, onClose }: Props) {
  if (!pass) return null;
  const card = cardpack.cards[pass.library_id];
  const hasCard = !!card?.barcode;
  const libraryName = library?.name ?? pass.library_id;

  const handleCopyAndGo = async () => {
    if (card?.barcode) {
      await copyToClipboard(card.barcode);
    }
    if (pass.source_url) {
      // Deep-link to the per-date Assabet reservation form when possible
      // so the user lands on the right calendar slot, not the museum page top.
      const target = passUrlForDate(pass.source_url, selectedDate || todayIso());
      window.open(target, '_blank', 'noopener,noreferrer');
    }
    onClose();
  };

  const handleApplyForCard = () => {
    const url = library?.card_page || library?.platform || '';
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
    onClose();
  };

  return (
    <Modal isOpen={!!pass} onClose={onClose} placement="center" size="sm">
      <ModalContent>
        <ModalHeader className="flex flex-col gap-1">
          <span style={{
            fontSize: 11, color: 'var(--ink-3)',
            textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 500,
          }}>
            Get pass from
          </span>
          <span style={{ fontSize: 16, color: 'var(--ink-2)', fontWeight: 600 }}>
            {libraryName}
          </span>
        </ModalHeader>
        <ModalBody>
          {hasCard ? (
            <>
              <p style={{ fontSize: 13, color: 'var(--ink-3)', marginBottom: 12 }}>
                Copy this card number, then enter your name on the pickup page.
              </p>
              <CredentialBox label="Card number" value={card.barcode} />
            </>
          ) : (
            <div style={{
              padding: 12,
              background: 'var(--au-pale)',
              borderRadius: 6,
              fontSize: 13,
              color: 'var(--au)',
            }}>
              <p style={{ fontWeight: 600 }}>
                You don't have a card from {libraryName} yet.
              </p>
            </div>
          )}
          {timedEntryUrl && (
            <div style={{
              marginTop: 10,
              padding: '8px 12px',
              background: 'var(--g-pale)',
              borderRadius: 6,
              fontSize: 12,
              color: 'var(--ink-2)',
            }}>
              <span>此景点需到官网预约入场时段</span>
              {' · '}
              <a
                href={timedEntryUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'var(--g)', fontWeight: 600, textDecoration: 'none' }}
              >
                预约 →
              </a>
            </div>
          )}
        </ModalBody>
        <ModalFooter>
          <Button variant="light" size="sm" onClick={onClose}>Cancel</Button>
          {hasCard ? (
            <Button
              size="sm"
              style={{ background: 'var(--g)', color: 'var(--white)' }}
              onClick={handleCopyAndGo}
            >
              {pass.source_url ? 'Copy card # and go →' : 'Copy card # ✓'}
            </Button>
          ) : (
            <Button
              size="sm"
              style={{
                background: 'var(--g)', color: 'var(--white)',
                whiteSpace: 'normal', lineHeight: 1.25,
              }}
              onClick={handleApplyForCard}
            >
              Apply for a card at {libraryName} →
            </Button>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
