import { useState } from 'react';
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
  const [copied, setCopied] = useState(false);
  const handleCopy = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (await copyToClipboard(value)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  return (
    <div className="mb-2">
      <div style={{
        fontSize: 11, color: 'var(--ink-3)', marginBottom: 4,
        textTransform: 'uppercase', letterSpacing: '0.04em',
      }}>
        {label}
      </div>
      <div
        className="flex items-center justify-between gap-2 rounded-md"
        style={{
          border: '1px solid var(--rule)',
          background: 'var(--white)',
          padding: '8px 12px',
        }}
      >
        <span style={{
          fontFamily: '"DM Mono", "Courier New", monospace',
          fontSize: 14,
          fontWeight: 600,
          color: 'var(--ink-2)',
          letterSpacing: '0.02em',
          userSelect: 'all',
        }}>
          {value}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          style={{
            background: 'transparent',
            border: 'none',
            padding: '4px 6px',
            cursor: 'pointer',
            fontSize: 11,
            fontWeight: 600,
            color: copied ? 'var(--g)' : 'var(--g-2)',
            letterSpacing: '0.06em',
          }}
        >
          {copied ? 'COPIED ✓' : 'COPY'}
        </button>
      </div>
    </div>
  );
}

export function BookingConfirmModal({ pass, library, cardpack, onClose }: Props) {
  if (!pass) return null;
  const card = cardpack.cards[pass.library_id];
  const hasCard = !!card?.barcode;
  const libraryName = library?.name ?? pass.library_id;

  const goToBooking = () => {
    if (pass.source_url) {
      window.open(pass.source_url, '_blank', 'noopener,noreferrer');
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
          <span className="font-serif" style={{ fontSize: 17, color: 'var(--ink-2)' }}>
            {libraryName}
          </span>
        </ModalHeader>
        <ModalBody>
          {hasCard ? (
            <>
              <p style={{ fontSize: 13, color: 'var(--ink-3)', marginBottom: 12 }}>
                Use these credentials when the library's reservation page asks for them.
              </p>
              <CredentialBox label="Card number" value={card.barcode} />
              {card.pin && <CredentialBox label="PIN" value={card.pin} />}
              <p style={{ fontSize: 11, color: 'var(--ink-3)', fontStyle: 'italic', marginTop: 8 }}>
                Tap COPY to copy a value, then paste it into the form on the next page.
              </p>
            </>
          ) : (
            <div style={{
              padding: 12,
              background: 'var(--rd-pale)',
              borderRadius: 6,
              fontSize: 13,
              color: 'var(--rd)',
            }}>
              <p style={{ fontWeight: 600, marginBottom: 4 }}>
                You don't have a card for this library yet.
              </p>
              <p style={{ fontSize: 12 }}>
                Add one in <a href="/settings/passes" style={{ color: 'var(--rd)', textDecoration: 'underline' }}>
                My passes</a> to use this offer.
              </p>
            </div>
          )}
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onClick={onClose}>Cancel</Button>
          {hasCard && (
            <Button color="primary" onClick={goToBooking}>
              Go to library website →
            </Button>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
