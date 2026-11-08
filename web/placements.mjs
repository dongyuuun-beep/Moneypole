// Editorial content occupies future ad space. No ad requests or publisher IDs yet.
// Keep these containers mounted across filtering; never request ads on each render.
export function createPlacement(id, variant = 'inline') {
  const slot = document.createElement('section');
  slot.className = `placement placement--${variant}`;
  slot.dataset.placement = id;
  slot.dataset.state = 'editorial';
  slot.setAttribute('aria-label', '금리 비교 참고');
  const editorial = document.createElement('div');
  editorial.className = 'placement-editorial';
  const kicker = document.createElement('p');
  kicker.className = 'placement-kicker'; kicker.textContent = 'COMPARISON NOTE';
  const title = document.createElement('h3'); title.className = 'placement-title';
  title.textContent = variant === 'rail' ? '금리보다 먼저,\n세 가지를 확인해요.' : '같은 금리라도, 내 돈에 붙는 이자는 달라요.';
  editorial.append(kicker, title);
  if (variant === 'rail') {
    const list = document.createElement('ol');
    for (const text of ['최고금리가 적용되는 금액', '내가 충족하는 우대조건', '돈을 꺼낼 시점과 지급일']) {
      const item = document.createElement('li'); item.textContent = text; list.append(item);
    }
    editorial.append(list);
  } else {
    const text = document.createElement('p');
    text.textContent = '잔액 일부에만 높은 금리가 적용되는지 확인해 보세요. 조건을 충족하지 못한 우대금리와 개인별 쿠폰은 실제 이자와 차이가 날 수 있어요.';
    editorial.append(text);
  }
  const label = document.createElement('span');
  label.className = 'placement-label'; label.textContent = '광고'; label.hidden = true;
  const host = document.createElement('div'); host.className = 'placement-host'; host.hidden = true;
  slot.append(editorial, label, host);
  return slot;
}

// Call once, BEFORE requesting an approved ad unit. A visible host is required
// for responsive AdSense sizing. Do not hide loaded ads or disguise them as notes.
export function activatePlacement(slot) {
  if (!slot?.matches('.placement')) throw new TypeError('Unknown placement');
  slot.dataset.state = 'advertisement';
  slot.setAttribute('aria-label', '광고');
  slot.querySelector('.placement-editorial').hidden = true;
  slot.querySelector('.placement-label').hidden = false;
  const host = slot.querySelector('.placement-host'); host.hidden = false;
  return host;
}
