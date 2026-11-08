import {shortTerm, selectedOption, displayRate, estimate, freshness} from './rates.mjs';

const $ = id => document.getElementById(id);
const labels = {parking: '파킹통장', cma: 'CMA', deposit: '예금', savings: '적금'};
const subtitles = {parking: '자유롭게 넣고 빼는', cma: '잠깐 머무는 자금도', deposit: '목돈을 차곡차곡', savings: '매달 쌓아가는'};
const sourceLabels = {fsb_parking: '저축은행 입출금자유예금', kb_cma: 'KB증권 CMA', kakao_parking: '카카오뱅크 세이프박스', kfb_parking: '시중은행 통합 목록',
  fss_deposit_020000: '은행 예금', fss_deposit_030300: '저축은행 예금', fss_savings_020000: '은행 적금', fss_savings_030300: '저축은행 적금'};
let allData = [], status = {}, type = 'parking', currentItem = null;
const money = value => Math.floor(value).toLocaleString('ko-KR') + '원';
const percent = value => Number(value).toFixed(2) + '%';
function dateText(value) {
  if (!value) return '확인 기록 없음';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString('ko-KR', {timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'});
}
function node(tag, className, text) {
  const result = document.createElement(tag);
  if (className) result.className = className;
  if (text !== undefined) result.textContent = text;
  return result;
}
function link(label, url) {
  const a = node('a', '', label);
  try {
    const parsed = new URL(url);
    if (!['https:', 'http:'].includes(parsed.protocol)) return node('span', '', '공식 링크 확인 필요');
    a.href = parsed.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
  } catch { return node('span', '', '공식 링크 확인 필요'); }
  return a;
}
function settings(index = null) {
  return {amount: Number($('amount').value), days: Number($('days').value), baseOnly: $('baseOnly').checked,
    term: $('term').value, index};
}
function limitText(item) {
  if (item.deposit_limit) return `입금한도: ${money(item.deposit_limit)} (한도 증액 기준)`;
  const limit = item.max_rate_amount;
  if (!limit) return '';
  if (limit.relation === '제한없음') return '최고금리 적용 금액: 공시상 제한 없음 · 우대조건 별도 확인';
  return limit.amount > 0 ? `최고금리 적용 금액: ${money(limit.amount)} ${limit.relation}` : '최고금리 적용 금액: 상세 조건 확인';
}
function badge(item) {
  const fresh = freshness(item);
  return node('span', `badge${fresh === '확인 완료' ? '' : ' warning'}`, fresh);
}
function render() {
  const short = ['parking', 'cma'].includes(type);
  $('daysField').hidden = !short; $('termField').hidden = short;
  $('amountLabel').textContent = type === 'savings' ? '매월 납입 금액' : '예치 금액';
  $('categoryNote').textContent = subtitles[type];
  $('resultsTitle').replaceChildren(document.createTextNode(labels[type] + ' '), $('resultCount'));
  $('coverage').textContent = type === 'parking' ? '저축은행 입출금자유예금 · 카카오뱅크 세이프박스' : type === 'cma' ? 'KB증권 개인 RP·발행어음형' : '금융감독원 은행·저축은행 공시';
  const config = settings(), search = $('search').value.trim().toLowerCase();
  let items = allData.filter(item => item.type === type && (item.bank + ' ' + item.name).toLowerCase().includes(search));
  if (!short && config.term !== 'all') items = items.filter(item => (item.options || []).some(o => String(o.save_trm) === config.term));
  items.sort((a, b) => {
    if ($('sort').value === 'interest') {
      const ea = estimate(a, config), eb = estimate(b, config);
      if (Boolean(ea) !== Boolean(eb)) return ea ? -1 : 1;
      if (ea && eb) return eb.interest - ea.interest;
    }
    return displayRate(b, config.term, config.baseOnly) - displayRate(a, config.term, config.baseOnly);
  });
  $('resultCount').textContent = `${items.length}개`;
  $('comparisonNote').textContent = type === 'parking' ? '최고금리는 잔액 일부에만 적용될 수 있어요. 금액 구간 검증 전에는 예상 이자를 계산하지 않아요.' :
    type === 'cma' ? '약정수익률 기준 · 예금자보호 대상 아님 · 재투자 효과 미반영' : '선택한 기간의 금리로 정렬해요. 우대금리 적용에는 각 상품의 조건 충족이 필요해요.';
  if ($('sort').value === 'interest') $('comparisonNote').textContent += ' 계산 가능한 상품부터 표시하며, 계산 불가 상품은 표시 금리순이에요.';
  $('listArea').replaceChildren();
  for (const item of items) {
    const card = node('article', 'card'), top = node('div', 'card-top');
    const option = selectedOption(item, config.term);
    top.append(node('span', '', item.bank + (short ? (item.subtype ? ` · ${item.subtype}형` : '') : ` · ${option.save_trm}개월`)), badge(item));
    const main = node('div', 'card-main'), title = node('button', 'product-button', item.name);
    title.type = 'button'; title.addEventListener('click', () => openDetail(item));
    const rates = node('div'), rate = node('div', 'rate');
    rate.append(node('small', '', config.baseOnly || item.rate_scope === 'base_excluding_coupons' ? '기본' : '최고'), document.createTextNode(percent(displayRate(item, config.term, config.baseOnly))));
    rates.append(rate, node('div', 'basic-rate', `기본 ${percent(displayRate(item, config.term, true))}`));
    main.append(title, rates); card.append(top, main);
    if (limitText(item)) card.append(node('div', 'amount-limit', limitText(item)));
    const condition = item.spcl_cnd || '공시된 우대조건 정보 없음';
    card.append(node('div', 'condition', condition.length > 100 ? condition.slice(0, 100) + '…' : condition));
    const bottom = node('div', 'card-bottom'), calculated = estimate(item, config);
    const result = node('span');
    if (calculated) result.append(document.createTextNode('예상 세전 이자 '), node('strong', '', money(calculated.interest)));
    else result.textContent = item.deposit_limit && config.amount > item.deposit_limit ? '입금한도 초과 · 계산 불가' : short ? '금액 구간 확인 후 계산' : '이 계산 방식은 상세 조건 확인 필요';
    bottom.append(result, node('span', '', item.last_checked_at ? `확인 ${dateText(item.last_checked_at)}` : '마지막 확인 기록 없음'));
    card.append(bottom); $('listArea').append(card);
  }
  if (!items.length) $('listArea').append(node('div', 'empty', '조건에 맞는 상품이 없어요. 검색어나 기간을 바꿔보세요.'));
  for (const key of Object.keys(labels)) document.querySelector(`[data-count="${key}"]`).textContent = allData.filter(x => x.type === key).length;
}
function section(title) {
  const result = node('section', 'detail-section'); result.append(node('h3', '', title)); return result;
}
function openDetail(item) {
  currentItem = item;
  const content = $('detailContent'); content.replaceChildren();
  const bank = node('div', 'detail-bank', item.bank); bank.append(document.createTextNode(' · '), badge(item));
  const heading = node('h2', '', item.name); heading.id = 'detailName';
  const rate = node('div', 'detail-rate', percent(displayRate(item, $('term').value, $('baseOnly').checked)));
  rate.append(node('small', '', ' 연 · 세전'));
  content.append(bank, heading, rate, node('p', 'detail-meta', `기본 ${percent(displayRate(item, $('term').value, true))} · ${item.intr_type || '공시 기준'}`));
  const conditions = section('적용 조건을 먼저 확인하세요');
  const dl = node('dl', 'detail-grid');
  const entries = [['우대조건', item.spcl_cnd || '공시된 조건 정보 없음'], ['적용 금액', limitText(item)],
    ['금액별 안내', item.rate_notes], ['가입 대상', item.join_target], ['이자 지급', item.payment_cycle],
    ['재투자', item.reinvestment], ['예금자보호', item.deposit_protection === false ? '보호 대상 아님' : null],
    ['금리 적용일', item.effective_from], ['공시일', item.disclosed_on], ['조회기준일', item.reference_date], ['최종 확인', dateText(item.last_checked_at)]];
  for (const [key, value] of entries) if (value) dl.append(node('dt', '', key), node('dd', '', value));
  conditions.append(dl); content.append(conditions);
  const calc = section('내 금액으로 예상 이자 확인');
  const panel = node('div', 'calc-panel');
  panel.append(node('p', 'calc-caption', `${type === 'savings' ? '월 납입액' : '예치액'} ${money(settings().amount)} · 목록의 비교 조건 기준`));
  let optionSelect = null;
  if (!shortTerm(item) && item.options?.length) {
    optionSelect = node('select'); optionSelect.setAttribute('aria-label', '계산 기간 및 이자 방식');
    const preferred = selectedOption(item, $('term').value);
    item.options.forEach((o, index) => {
      const opt = node('option', '', `${o.save_trm}개월 · ${o.intr_type}${o.rsrv_type ? ' · ' + o.rsrv_type : ''} · 기본 ${percent(o.intr_rate)} / 최고 ${percent(o.intr_rate2)}`);
      opt.value = index; opt.selected = o === preferred; optionSelect.append(opt);
    });
    panel.append(optionSelect);
  }
  const value = node('div', 'calc-amount'), caption = node('p', 'calc-caption');
  function calculate() {
    const result = estimate(item, settings(optionSelect ? Number(optionSelect.value) : null));
    value.textContent = result ? money(result.interest) : '상세 조건 확인 필요';
    caption.textContent = result ? `${result.label} · 일반과세 15.4% 가정 시 세후 이자 ${money(result.interest * .846)}. 실제 과세·일수·재투자에 따라 달라집니다.` :
      item.deposit_limit && settings().amount > item.deposit_limit ? '입금한도를 초과했어요. 목록의 예치 금액을 한도 안으로 조정해 주세요.' :
      '잔액 구간별 금리, 자유적립식 납입 일정 또는 복리 방식이 검증되지 않아 계산을 제공하지 않아요. 위의 공시 조건과 공식 안내를 확인하세요.';
  }
  optionSelect?.addEventListener('change', calculate); calculate(); panel.append(value, caption); calc.append(panel); content.append(calc);
  const history = section('표시 금리 변동 기록');
  const table = node('table', 'history'), head = node('tr'); head.append(node('th', '', '확인일'), node('th', '', '연 · 세전')); table.append(head);
  for (const h of [...(item.history || [])].reverse().slice(0, 10)) { const tr = node('tr'); tr.append(node('td', '', h.date), node('td', '', percent(h.rate))); table.append(tr); }
  history.append(item.history?.length ? table : node('p', '', '저장된 변동 기록이 없어요.'));
  history.append(node('p', 'calc-caption', '과거 기록은 상품의 대표 표시 금리 기준이며, 위에서 선택한 기간의 금리 추이와 다를 수 있어요. 쿠폰 제외 상품은 공시 기본금리를 기록해요.'));
  content.append(history);
  const sources = section('공식 출처');
  sources.append(link('공식 공시 확인 ↗', item.source_url || 'https://finlife.fss.or.kr/'));
  if (item.product_url) { sources.append(document.createTextNode(' · '), link('금융기관 상품 안내 ↗', item.product_url)); }
  content.append(sources);
  $('detailDialog').showModal(); $('detailDialog').scrollTop = 0; document.body.style.overflow = 'hidden';
}
function renderStatus() {
  $('sourceStatus').replaceChildren();
  for (const [key, source] of Object.entries(status.sources || {})) {
    const row = node('div', 'source-row');
    const state = {ok: '확인 완료', partial: '목록 일부 확인 필요', failed: '확인 지연', unavailable: '수집 미지원'}[source.status] || '미확인';
    row.append(node('span', '', sourceLabels[key] || '공식 출처'), node('span', '', `${state}${source.last_success_at ? ' · ' + dateText(source.last_success_at) : ''}`));
    $('sourceStatus').append(row);
  }
  if (!Object.keys(status.sources || {}).length) $('sourceStatus').textContent = '수집 상태 정보를 가져오지 못했어요. 상품별 확인 시각을 확인하세요.';
}
for (const button of document.querySelectorAll('[data-type]')) button.addEventListener('click', () => {
  type = button.dataset.type;
  for (const tab of document.querySelectorAll('[data-type]')) { tab.classList.toggle('active', tab === button); tab.setAttribute('aria-pressed', String(tab === button)); }
  render();
});
for (const button of document.querySelectorAll('[data-amount]')) button.addEventListener('click', () => { $('amount').value = button.dataset.amount; render(); });
for (const id of ['amount', 'days', 'term', 'baseOnly', 'search', 'sort']) $(id).addEventListener('input', render);
$('closeDetail').addEventListener('click', () => $('detailDialog').close());
$('detailDialog').addEventListener('close', () => { document.body.style.overflow = ''; currentItem = null; });
$('detailDialog').addEventListener('click', event => { if (event.target === $('detailDialog')) { const r = event.target.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) event.target.close(); } });
try {
  const [dataResult, statusResult] = await Promise.allSettled([
    fetch('data.json', {cache: 'no-cache'}).then(r => { if (!r.ok) throw new Error('data'); return r.json(); }),
    fetch('update_status.json', {cache: 'no-cache'}).then(r => { if (!r.ok) throw new Error('status'); return r.json(); })
  ]);
  if (dataResult.status !== 'fulfilled' || !Array.isArray(dataResult.value)) throw new Error('data');
  allData = dataResult.value; status = statusResult.status === 'fulfilled' ? statusResult.value : {};
  render(); renderStatus();
} catch {
  $('listArea').replaceChildren(node('div', 'empty error', '데이터를 불러오지 못했어요. 잠시 후 새로고침해 주세요.'));
  $('sourceStatus').textContent = '데이터 조회 실패';
}
