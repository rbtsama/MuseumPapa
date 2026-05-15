import {
  Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button,
} from '@heroui/react';
import type { Pass } from '../data/types';
import type { CardPack } from '../stores/cardpack';

interface Props {
  pass: Pass | null;
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

export function BookingConfirmModal({ pass, cardpack, onClose }: Props) {
  if (!pass) return null;
  const card = cardpack.cards[pass.library_id];
  const hasCard = !!card?.barcode;

  const handleOpen = async () => {
    if (hasCard) {
      await copyToClipboard(card.barcode);
    }
    if (pass.source_url) {
      window.open(pass.source_url, '_blank', 'noopener,noreferrer');
    }
    onClose();
  };

  return (
    <Modal isOpen={!!pass} onClose={onClose}>
      <ModalContent>
        <ModalHeader>Open booking page</ModalHeader>
        <ModalBody>
          {hasCard ? (
            <>
              <p>Your barcode for <b>{pass.library_id}</b> will be copied to clipboard.</p>
              <p style={{ fontSize: 12, color: 'var(--ink-3)' }}>
                On the next page, paste it into the library&apos;s reservation form.
              </p>
            </>
          ) : (
            <>
              <p style={{ color: 'var(--rd)' }}>
                You don&apos;t have a card for this library yet.
              </p>
              <p style={{ fontSize: 12, color: 'var(--ink-3)' }}>
                Add one in <a href="/settings/passes" style={{ color: 'var(--g)' }}>My passes</a> first.
              </p>
            </>
          )}
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onClick={onClose}>Cancel</Button>
          {hasCard && (
            <Button color="primary" onClick={handleOpen}>
              Open booking page →
            </Button>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
