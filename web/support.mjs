import {applicationState} from './support-state.mjs?v=hwaseong-2';
import {createPlacement} from './placements.mjs';
const $ = id => document.getElementById(id);
const regionNames = {seoul:'서울시',hwaseong:'화성시',yongin:'용인시',busan:'부산시',buan:'부안군'};
let items = [], report = {}, region = 'all', visible = 12;
const initialRegion = new URLSearchParams(location.search).get('region');
if (Object.hasOwn(regionNames, initialRegion)) {
  region = initialRegion;
  for (const tab of document.querySelectorAll('[data-region]')) {
    tab.classList.toggle('active', tab.dataset.region === region);
    tab.setAttribute('aria-pressed', String(tab.dataset.region === region));
  }
}
const date = value => value ? new Date(value).toLocaleString('ko-KR', {timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}) : '확인 기록 없음';
function node(tag, cls, value) { const n = document.createElement(tag); if(cls)n.className=cls; if(value!==undefined)n.textContent=value;return n; }
function link(label, url) {
  try { const u = new URL(url); if(!['https:','http:'].includes(u.protocol)||u.username||u.password)throw new Error(); const a=node('a','',label);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a; }
  catch { return node('span','','공식 링크 확인 필요'); }
}
const rail=createPlacement('support-rail','rail');
rail.querySelector('.placement-title').textContent='신청하기 전, 세 가지만 확인하세요.';
rail.querySelector('ol').replaceChildren(...['시·군·구와 실제 거주기간','나이·소득·중복수급 조건','접수기간과 예산 소진 여부'].map(t=>node('li','',t)));
$('railPlacement').append(rail);
function filtered() {
  const query=$('search').value.trim().toLowerCase();
  return items.map(item=>({item,state:applicationState(item)})).filter(({item,state})=>
    (region==='all'||item.region===region)&&($('category').value==='all'||item.category===$('category').value)&&
    (!query||[item.title,item.region_name,item.support_text,item.target_text].join(' ').toLowerCase().includes(query))&&
    ($('applicationStatus').value==='all'||($('applicationStatus').value==='available'?state.key!=='closed':state.key===$('applicationStatus').value))
  ).sort((a,b)=>{
    if($('sort').value==='recent')return (b.item.last_checked_at||'').localeCompare(a.item.last_checked_at||'') || b.item.title.localeCompare(a.item.title);
    if($('sort').value==='deadline')return (Date.parse(a.item.application_end)||Infinity)-(Date.parse(b.item.application_end)||Infinity)||a.item.title.localeCompare(b.item.title);
    const order={open:0,upcoming:1,unknown:2,closed:3};return order[a.state.key]-order[b.state.key] || (Date.parse(a.item.application_end)||Infinity)-(Date.parse(b.item.application_end)||Infinity)||a.item.title.localeCompare(b.item.title);
  });
}
function render() {
  const data=filtered();$('resultCount').textContent=data.length+'개';$('allCount').textContent=items.length;
  $('regionLabel').textContent=region==='all'?'5개 지역의 공식 지원 공고':regionNames[region]+'의 공식 지원 공고';
  $('supportNotice').textContent='신청 자격을 판정한 결과가 아닙니다. 금액은 공고 원문 표현이며, 기간·금액이 불명확한 항목은 원문 확인이 필요해요.';
  $('listArea').replaceChildren();
  for(const {item,state} of data.slice(0,visible)) {
    const card=node('article','card support-card'),top=node('div','card-top');
    top.append(node('span','',(item.coverage_label||item.region_name)+' · '+item.category),node('span','badge'+(state.key==='unknown'?' warning':''),state.label));
    const title=node('button','product-button',item.title);title.type='button';title.addEventListener('click',()=>openDetail(item));
    const support=item.support_text?item.support_text:'지원금액·세부 조건은 공식 공고에서 확인하세요.';
    const desc=node('p','support-summary',support.length>150?support.slice(0,150)+'…':support);
    const periodTitle=item.period_kind==='coverage'?'보장·청구 안내':item.period_kind==='usage'?'이용 안내':'신청기간';
    const period=node('p','condition',item.application_period_text?periodTitle+': '+item.application_period_text:periodTitle+': 공식 원문 확인 필요');
    const bottom=node('div','card-bottom');bottom.append(node('span','',item.source_name),node('span','',`확인 ${date(item.last_checked_at)}${state.stale?' · 확인 지연':''}`));
    card.append(top,title,desc,period,bottom);$('listArea').append(card);
  }
  if(!data.length)$('listArea').append(node('div','empty','조건에 맞는 공고가 없어요. 기간 확인 필요·마감 포함 전체 또는 다른 지역을 선택해 보세요.'));
  $('loadMore').hidden=data.length<=visible;$('loadMore').textContent=`공고 ${Math.min(12,Math.max(0,data.length-visible))}개 더 보기 · ${Math.min(visible,data.length)} / ${data.length}`;
}
function section(title,text) {const s=node('section','detail-section');s.append(node('h3','',title));if(text)s.append(node('p','',text));return s;}
function openDetail(item) {
  const content=$('detailContent'),state=applicationState(item);content.replaceChildren();
  content.append(node('div','detail-bank',item.region_name+' · '+item.source_name));const title=node('h2','',item.title);title.id='detailName';content.append(title,node('span','badge'+(state.key==='unknown'?' warning':''),state.label));
  content.append(section('지원 안내',item.support_text||'HTML에서 지원금액을 확정하지 못했어요. 이미지·첨부파일을 포함한 공식 공고를 확인하세요.'));
  content.append(section(item.period_kind==='coverage'?'보장·청구 안내':item.period_kind==='usage'?'이용 안내':'신청기간',item.application_period_text||'신청기간을 확인하지 못했어요. 게시일을 신청일이나 마감일로 대체하지 않습니다.'));
  content.append(section('지원 대상',item.target_text||'지역·나이·소득·거주기간·중복수급 기준은 공식 공고에서 확인하세요.'));
  content.append(section('신청 전 확인',item.notice));
  const source=section('공식 원문');source.append(link('공식 안내 확인 ↗',item.source_url));
  if(item.detail_url!==item.source_url)source.append(document.createTextNode(' · '),link('개별 사업 안내 ↗',item.detail_url));
  source.append(node('p','detail-meta',`마지막 조회 ${date(item.last_checked_at)}${item.published_on?' · 게시일 '+item.published_on:''}`));content.append(source);
  if(item.attachments?.length) {const a=section('공식 첨부파일');for(const file of item.attachments){const p=node('p');p.append(link(file.name||'공고 첨부파일',file.url));a.append(p)}content.append(a)}
  const raw=section('수집한 공고 내용');raw.append(node('p','support-excerpt',item.excerpt));content.append(raw);
  $('detailDialog').showModal();$('detailDialog').scrollTop=0;document.body.style.overflow='hidden';
}
function renderSources() {
  $('sourceStatus').replaceChildren();
  for(const [key,name] of Object.entries(regionNames)) {
    const source=report.sources?.[key],row=node('div','source-row');row.append(node('strong','',name),node('span','',source?({ok:'수집 완료',partial:'일부 확인 지연',failed:'확인 실패'}[source.status]||'미확인'):'확인 기록 없음'));
    const detail=node('div','support-source');detail.append(row);
    if(source){detail.append(node('p','',source.scope||''),node('p','',date(source.last_success_at)));detail.append(link('수집 출처 ↗',source.url))}
    $('sourceStatus').append(detail);
  }
}
for(const button of document.querySelectorAll('[data-region]'))button.addEventListener('click',()=>{region=button.dataset.region;visible=12;for(const tab of document.querySelectorAll('[data-region]')){tab.classList.toggle('active',tab===button);tab.setAttribute('aria-pressed',String(tab===button))}render();});
for(const id of ['category','applicationStatus','search','sort'])$(id).addEventListener('input',()=>{visible=12;render()});
$('loadMore').addEventListener('click',()=>{visible+=12;render()});
$('closeDetail').addEventListener('click',()=>$('detailDialog').close());$('detailDialog').addEventListener('close',()=>{document.body.style.overflow=''});
try {
  const results=await Promise.allSettled(['support.json','support_status.json'].map(async url=>{const r=await fetch(url,{cache:'no-cache'});if(!r.ok)throw new Error('fetch');return r.json()}));
  if(results[0].status!=='fulfilled'||!Array.isArray(results[0].value))throw new Error('data');items=results[0].value;report=results[1].status==='fulfilled'?results[1].value:{};render();renderSources();
} catch { $('listArea').replaceChildren(node('div','empty error','공고를 불러오지 못했어요. 잠시 후 새로고침해 주세요.'));$('supportNotice').textContent='지원 공고 조회 실패'; }
