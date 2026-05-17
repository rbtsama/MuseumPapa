import {
  Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button,
} from '@heroui/react';
import type { Pass, Library } from '../data/types';
import type { CardPack } from '../stores/cardpack';

interface Props {
  pass: Pass | null;
  library: Library | null;
  cardpack: CardPack;
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

export function BookingConfirmModal({ pass, library, cardpack, onClose }: Props) {
  if (!pass) return null;
  const card = cardpack.cards[pass.library_id];
  const hasCard = !!card?.barcode;
  const libraryName = library?.name ?? pass.library_id;

  const handleCopyAndGo = async () => {
    if (card?.barcode) {
      await copyToClipboard(card.barcode);
    }
    if (pass.source_url) {
      window.open(pass.source_url, '_blank', 'noopener,noreferrer');
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
          <span className="font-serif" style={{ fontSize: 16, color: 'var(--ink-2)' }}>
            {libraryName}
          </span>
        </ModalHeader>
        <ModalBody>
          {hasCard ? (
            <>
              <p style={{ fontSize: 13, color: 'var(--ink-3)', marginBottom: 12 }}>
                Use these credentials when the library's pickup page asks for them.
              </p>
              <CredentialBox label="Card number" value={card.barcode} />
              {card.pin && <CredentialBox label="PIN" value={card.pin} />}
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
              style={{ background: 'var(--g)', color: 'var(--white)' }}
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
