export function applicationState(item, now = new Date()) {
  const stamp = item.last_checked_at && Date.parse(item.last_checked_at);
  // A stale collection cannot establish that an application is currently open.
  const stale = !Number.isFinite(stamp) || now - stamp > 48 * 3600e3 || item.verification_status === 'stale';
  if (/마감|종료|접수완료/.test(item.source_state || '')) return {key: 'closed', label: '마감', stale};
  const start = Date.parse(item.application_start || ''), end = Date.parse(item.application_end || '');
  if (Number.isFinite(end) && now > end) return {key: 'closed', label: '마감', stale};
  if (stale) return {key: 'unknown', label: '확인 지연 · 기간 재확인', stale};
  if (Number.isFinite(start) && Number.isFinite(end) && start <= end) {
    if (now < start) return {key: 'upcoming', label: '접수 예정', stale};
    if (now <= end) return {key: 'open', label: '접수 기간 내', stale};
  }
  if (/마감|종료|접수완료/.test(item.source_state || '')) return {key: 'closed', label: '마감', stale};
  if (item.source_state === '모집중') return {key: 'open', label: '원문 모집중 · 기간 확인', stale};
  if (item.source_state === '모집예정') return {key: 'upcoming', label: '원문 모집 예정', stale};
  if (item.source_state === '상시') return {key: 'open', label: '원문 상시 · 예산 확인', stale};
  return {key: 'unknown', label: '기간 확인 필요', stale};
}
