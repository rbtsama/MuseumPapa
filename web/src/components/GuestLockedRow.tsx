import type { Library, Pass } from '../data/types';
import { PassTypeLabel } from './PassTypeLabel';
import { CouponLine } from './CouponLine';

interface Props {
  pass: Pass;
  library: Library | null;
  onSignInRequest: () => void;
}

/**
 * Guest-mode option row: same shape as a real row but with a 🔒 lock icon
 * instead of the Book button. Clicking opens the sign-in flow.
 */
export function GuestLockedRow({ pass, library, onSignInRequest }: Props) {
  return (
    <button
      type="button"
      onClick={onSignInRequest}
      className="flex items-center gap-2 rounded-md text-left w-full"
      style={{
        background: 'var(--white)',
        border: '1px solid var(--rule)',
        padding: '8px 12px',
        cursor: 'pointer',
      }}
      aria-label={`Sign in to use ${library?.name ?? pass.library_id} pass`}
    >
      <PassTypeLabel type={pass.pass_type} />
      <span style={{ fontSize: 13, color: 'var(--ink-2)', fontWeight: 500 }}>
        {library?.name ?? pass.library_id}
      </span>
      <span className="ml-auto flex items-center gap-2">
        <CouponLine coupon={pass.coupon} />
        <span aria-hidden style={{ fontSize: 14, color: 'var(--ink-3)' }}>🔒</span>
      </span>
    </button>
  );
}
