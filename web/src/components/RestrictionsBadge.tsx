import type { PassRestrictions } from '../data/types';

interface Props {
  restrictions: PassRestrictions | null;
}

function summarize(r: PassRestrictions): string {
  const parts: string[] = [];
  if (r.blackout_dates) parts.push('blackout dates apply');
  if (r.weekdays_only) parts.push('weekdays only');
  if (r.seasonal) parts.push(`open ${r.seasonal}`);
  if (r.reservation_required) parts.push('reservation required');
  return parts.join(' · ');
}

export function RestrictionsBadge({ restrictions }: Props) {
  if (!restrictions) return null;
  const tip = summarize(restrictions);
  if (!tip) return null;
  return (
    <span
      title={tip}
      aria-label={`Restrictions: ${tip}`}
      className="inline-flex items-center flex-shrink-0"
      style={{
        fontSize: 13,
        color: 'var(--or)',
        cursor: 'help',
        userSelect: 'none',
      }}
    >
      ⚠
    </span>
  );
}
