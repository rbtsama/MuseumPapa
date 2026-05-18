import type { Pass, Library } from '../data/types';
import { PassDeliveryChip } from './PassDeliveryChip';
import { AudienceValueLine } from './AudienceValueLine';

interface Props {
  pass: Pass;
  library: Library;
  distanceMi: number | null;
  onBook: (pass: Pass) => void;
}

export function PassRow({ pass, library, distanceMi, onBook }: Props) {
  // No loan-duration field exists on Pass (confirmed in types.ts) — omit suffix.
  const loanSuffix = '';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
        padding: '10px 0',
        borderBottom: '1px solid var(--rule)',
      }}
    >
      <div style={{ flexGrow: 1, minWidth: 0 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          marginBottom: 2, flexWrap: 'wrap',
        }}>
          <PassDeliveryChip passType={pass.pass_type} distanceMi={distanceMi} />
          <AudienceValueLine coupon={pass.coupon} />
        </div>
        <div style={{ fontSize: 11, color: 'var(--ink-3)' }}>
          {library.name}{loanSuffix}
        </div>
      </div>
      <button
        type="button"
        onClick={() => onBook(pass)}
        style={{
          background: 'var(--g)', color: 'var(--white)', border: 'none',
          borderRadius: 5, padding: '7px 14px',
          font: '600 12px sans-serif', cursor: 'pointer', alignSelf: 'center',
        }}
      >
        Book
      </button>
    </div>
  );
}
