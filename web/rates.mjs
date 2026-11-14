export const shortTerm = item => ['parking', 'cma'].includes(item.type);

export function isComparable(item, now = new Date()) {
  const age = now - new Date(item.last_checked_at);
  return item.verification_status === 'verified' && Number.isFinite(age) && age >= 0 && age <= 48 * 3600e3;
}

export function selectedOption(item, term = 'all', index = null) {
  const options = item.options || [];
  if (index !== null && options[index]) return options[index];
  const matches = options.filter(o => term === 'all' ? o.save_trm === item.save_trm : String(o.save_trm) === String(term));
  return matches.find(o => o.intr_type === '단리' && o.rsrv_type !== '자유적립식') || matches[0] ||
    {save_trm: item.save_trm, intr_rate: item.base, intr_rate2: item.max, intr_type: item.intr_type};
}

export function displayRate(item, term, baseOnly) {
  const option = selectedOption(item, term);
  return Number(shortTerm(item) ? item[baseOnly ? 'base' : 'max'] : option[baseOnly ? 'intr_rate' : 'intr_rate2']);
}

export function estimate(item, {amount, days = 30, baseOnly = false, term = 'all', index = null}) {
  if (!isComparable(item)) return null;
  if (!Number.isFinite(amount) || amount <= 0) return null;
  if (shortTerm(item)) {
    if (!Number.isFinite(days) || days <= 0 || !['flat', 'verified_tiers'].includes(item.rate_model)) return null;
    const tiers = item.rate_tiers || [];
    if (!tiers.length) return null;
    let annual = 0, end = 0;
    for (const tier of tiers) {
      if (tier.from !== end || (tier.to !== null && tier.to <= tier.from)) return null;
      const rate = tier[baseOnly ? 'base' : 'max'];
      if (!Number.isFinite(rate) || rate < 0) return null;
      const to = tier.to === null ? Infinity : tier.to;
      annual += Math.max(0, Math.min(amount, to) - tier.from) * rate / 100;
      end = to;
      if (amount <= end) break;
    }
    if (amount > end) return null; // Never guess a rate for uncovered balances.
    return {interest: annual * days / 365, principal: amount, label: `${days}일 · 세전 단리 추정`};
  }
  const option = selectedOption(item, term, index);
  const months = Number(option.save_trm), rate = Number(option[baseOnly ? 'intr_rate' : 'intr_rate2']) / 100;
  if (!Number.isFinite(months) || months <= 0 || !Number.isFinite(rate) || option.intr_type !== '단리') return null;
  // Free-installment cash flows and compound products need separate assumptions.
  if (item.type === 'savings' && option.rsrv_type === '자유적립식') return null;
  const savings = item.type === 'savings';
  return {interest: savings ? amount * rate * months * (months + 1) / 24 : amount * rate * months / 12,
    principal: savings ? amount * months : amount, label: `${months}개월 · ${savings ? '매월 같은 금액 납입 · ' : ''}세전 단리 추정`};
}

export function freshness(item, now = new Date()) {
  if (!item.last_checked_at) return '미확인';
  if (item.verification_status === 'missing') return '목록 누락 · 확인 필요';
  if (!isComparable(item, now)) return '확인 지연';
  return '확인 완료';
}
