const $ = id => document.getElementById(id);
let projects = [];
let swaggerInfo = null;
let currentDiagramModel = null;
let lastAnalysis = null;
let analysisEngines = null;
const loadContextKey='expert-code-flow:load-context';
const projectSourceKey='expert-code-flow:project-source';
const positiveNumber=id=>{const value=Number($(id).value);return Number.isFinite(value)&&value>0?value:null;};
try{const savedLoad=JSON.parse(localStorage.getItem(loadContextKey)||'{}');$('average-tps').value=savedLoad.average_tps??'';$('target-p95-ms').value=savedLoad.target_p95_ms??'';}catch{}
['average-tps','target-p95-ms'].forEach(id=>$(id).addEventListener('input',()=>localStorage.setItem(loadContextKey,JSON.stringify({average_tps:positiveNumber('average-tps'),target_p95_ms:positiveNumber('target-p95-ms')}))));
const status = (message, error=false) => { $('status').textContent = message; $('status').className = error ? 'error' : ''; };
async function loadAnalysisEngines(){try{analysisEngines=await json('/api/analysis/engines');const spoon=analysisEngines.engines.find(item=>item.id==='spoon'),option=$('spoon-engine-option');if(option)option.disabled=!spoon?.available||!spoon?.enabled;if($('analysis-engine'))$('analysis-engine').title=option?.disabled?'Spoon + SootUp indisponível neste ambiente':'Selecione Python leve ou Spoon + SootUp estrutural antes de analisar';}catch{const option=$('spoon-engine-option');if(option)option.disabled=true;}}
const escapeXml = value => String(value).replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[c]));
const formatNumber=value=>new Intl.NumberFormat('pt-BR').format(value??0);
const formatBytes=value=>{const bytes=Number(value)||0;if(bytes<1024)return `${bytes} B`;const units=['KB','MB','GB'];let amount=bytes/1024,index=0;while(amount>=1024&&index<units.length-1){amount/=1024;index++;}return `${amount.toLocaleString('pt-BR',{maximumFractionDigits:1})} ${units[index]}`;};
function xrayStat(label,value,wide=false){return `<div class="xray-stat${wide?' wide':''}"><span>${escapeXml(label)}</span><strong>${escapeXml(value)}</strong></div>`;}
function auditGroup(label,count,items,reason,excluded=[]){return `<div class="audit-box"><header><h4>${escapeXml(label)}</h4><strong>${formatNumber(count)}</strong></header><p class="audit-reason">${escapeXml(reason)}</p>${items?.length?`<ul>${items.map(item=>`<li><b>${escapeXml(item.name||item)}</b>${item.endpoints!=null?`<small>${formatNumber(item.endpoints)} endpoint(s)</small>`:item.owner?`<small>${escapeXml(item.owner)}</small>`:''}</li>`).join('')}</ul>`:'<p>Nenhum item contabilizado.</p>'}${excluded.length?`<p class="audit-excluded">Não contabilizados: ${excluded.map(escapeXml).join(', ')}.</p>`:''}</div>`;}
function renderStructuralAudit(architecture,details){return `<details class="xray-audit"><summary><span>Auditar classificação estrutural</span><small>Clique para detalhar as quantidades do Spring + Hexagonal</small></summary><div class="xray-audit-grid">${auditGroup('Controllers',architecture.rest_controllers,details.controllers,'Classes de produção com @RestController.',details.excluded_from_controllers)}${auditGroup('Endpoints',architecture.rest_endpoints,details.endpoints,'Métodos REST mapeados nos Controllers contabilizados.')}${auditGroup('Services',architecture.services,details.services,'Classes de produção da camada de serviço.')}${auditGroup('Ports IN',architecture.ports_in,details.ports_in,'Interfaces que expõem casos de uso de entrada.')}${auditGroup('Ports OUT',architecture.ports_out,details.ports_out,'Interfaces de saída usadas pelo núcleo da aplicação.')}${auditGroup('Adapters OUT',architecture.adapters_out,details.adapters_out,'Implementações concretas de uma Port OUT.')}${auditGroup('Repositories',architecture.repositories,details.repositories,'Interfaces Spring Data de persistência.')}${auditGroup('Entidades JPA',architecture.jpa_entities,details.jpa_entities,'Classes de produção declaradas com @Entity.')}</div></details>`;}
function renderXray(data){const code=data.code,architecture=data.architecture,details=architecture.details||{},integrations=data.integrations,versions=Object.entries(data.versions||{}),rows=(data.dependencies||[]).map(item=>`<li><span><b>${escapeXml(item.name)}</b><small>${escapeXml(item.group||'dependência local')}</small></span><code>${escapeXml(item.version)}</code><em>${escapeXml(item.scope)}</em></li>`).join('');$('xray-project').textContent=`Microsserviço: ${data.microservice}`;$('xray-content').innerHTML=`<div class="xray-cards"><section class="xray-group"><h3>Dimensão do código</h3>${xrayStat('Arquivos Java',formatNumber(code.java_files))}${xrayStat('Classes',formatNumber(code.classes))}${xrayStat('Interfaces',formatNumber(code.interfaces))}${xrayStat('Métodos',formatNumber(code.methods))}${xrayStat('Linhas de código',formatNumber(code.lines_of_code))}${xrayStat('Dependências',formatNumber(code.dependencies))}</section><section class="xray-group version-group"><h3>Dimensão de versões</h3>${versions.length?versions.map(([name,version])=>xrayStat(name,version)).join(''):'<p class="xray-empty">Nenhuma versão explícita encontrada.</p>'}</section><section class="xray-group"><h3>Spring + Hexagonal</h3>${xrayStat('Controllers',formatNumber(architecture.rest_controllers))}${xrayStat('Endpoints',formatNumber(architecture.rest_endpoints))}${xrayStat('Services',formatNumber(architecture.services))}${xrayStat('Ports IN',formatNumber(architecture.ports_in))}${xrayStat('Ports OUT',formatNumber(architecture.ports_out))}${xrayStat('Adapters OUT',formatNumber(architecture.adapters_out))}${xrayStat('Repositories',formatNumber(architecture.repositories))}${xrayStat('Entidades JPA',formatNumber(architecture.jpa_entities))}</section><section class="xray-group"><h3>Integrações</h3>${xrayStat('Chamadas externas',formatNumber(integrations.external_calls))}${xrayStat('Bancos acessados',formatNumber(integrations.databases))}${xrayStat('Produtores de eventos',formatNumber(integrations.event_producers))}${xrayStat('Consumidores de eventos',formatNumber(integrations.event_consumers))}</section></div>${renderStructuralAudit(architecture,details)}<details class="xray-dependencies"><summary><span>Inventário de dependências</span><b>${formatNumber(code.dependencies)}</b><small>Clique para listar</small></summary>${rows?`<ul>${rows}</ul>`:'<p>Nenhuma dependência declarada encontrada.</p>'}</details>`;}
async function openXray(){const project=projects[+$('project').value];if(!project)return;$('xray-project').textContent=`Microsserviço: ${project.name}`;$('xray-content').innerHTML='<div class="xray-loading">Mapeando código, arquitetura e integrações…</div>';$('xray-modal').showModal();try{renderXray(await json('/api/microservice-xray?project='+encodeURIComponent(project.path)));}catch(error){$('xray-content').innerHTML=`<div class="xray-loading">${escapeXml(error.message)}</div>`;}}
function setXrayMaximized(maximized){$('xray-modal').classList.toggle('maximized',maximized);$('xray-maximize').textContent=maximized?'❐':'□';$('xray-maximize').setAttribute('aria-label',maximized?'Restaurar':'Maximizar');$('xray-maximize').title=maximized?'Restaurar tamanho':'Maximizar';}
let diagramZoom = 1;
function applyZoom() { const svg=$('sequence-diagram').querySelector('svg'); if(svg) svg.style.width=`${diagramZoom*100}%`; $('zoom-reset').textContent=`${Math.round(diagramZoom*100)}%`; }
function renderSequence(model) {
  const target = $('sequence-diagram');
  if (!model?.events?.length) { currentDiagramModel=null;$('download-png').disabled=true;$('download-pdf').disabled=true;target.className='diagram-empty'; target.textContent='Nenhuma etapa disponível.'; return; }
  currentDiagramModel=model;
  const participants=model.participants, events=model.events, gap=270, margin=140, top=195, row=50;
  const width=Math.max(820,margin*2+(participants.length-1)*gap), height=top+events.length*row+95;
  const x=Object.fromEntries(participants.map((p,index)=>[p.id,margin+index*gap]));
  const y=index=>top+index*row;
  let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Diagrama de sequência UML para ${escapeXml(model.interaction)}"><defs><marker id="sync-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z"/></marker><marker id="return-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none"/></marker><marker id="error-arrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="8" markerHeight="8" orient="auto"><path d="M2 2L10 10M10 2L2 10"/></marker></defs>`;
  svg+=`<rect class="uml-frame" x="8" y="8" width="${width-16}" height="${height-16}"/><path class="frame-tab" d="M8 8h255v30h-22l-13 12H8z"/><text class="frame-label" x="22" y="29">sd ${escapeXml(model.interaction)}</text>`;
  participants.forEach(p=>{const px=x[p.id],actor=p.type==='actor';if(actor){svg+=`<circle class="actor-symbol" cx="${px}" cy="65" r="10"/><path class="actor-symbol" d="M${px} 75v24m-16-14h32m-25 31l9-17 9 17"/><text class="actor-label" x="${px}" y="142">${escapeXml(p.display)}</text>`;}else{svg+=`<rect class="actor" x="${px-115}" y="45" width="230" height="66" rx="4"/><text class="instance-label" x="${px}" y="65">${escapeXml(p.instance)}</text><text class="classifier-label" x="${px}" y="83">:${escapeXml(p.classifier)}</text><text class="stereotype" x="${px}" y="102">«${escapeXml(p.layer)}»</text>`;}svg+=`<line class="lifeline" x1="${px}" y1="${actor?154:111}" x2="${px}" y2="${height-35}"/>`;});
  const returns=new Map();events.forEach((e,i)=>{if(e.type==='return')returns.set(e.call_id,i);});
  events.forEach((e,i)=>{if(e.type!=='call')return;const end=returns.get(e.id)??i+1,px=x[e.callee],offset=Math.max(0,e.depth-1)*5;svg+=`<rect class="activation" x="${px-6+offset}" y="${y(i)-4}" width="12" height="${Math.max(24,y(end)-y(i)+8)}"/>`;});
  const groupMap=new Map();events.forEach((e,i)=>{if(!e.fragment)return;const key=e.fragment.group_id||`${e.fragment.operator}:${e.fragment.condition}`;if(!groupMap.has(key))groupMap.set(key,{start:i,end:i,operator:e.fragment.operator,condition:e.fragment.condition,elseAt:null});const g=groupMap.get(key);g.end=i;if(e.fragment.branch==='else'&&g.elseAt===null)g.elseAt=i;});[...groupMap.values()].forEach(g=>{const gy=y(g.start)-24,gh=y(g.end)-y(g.start)+42;svg+=`<rect class="fragment" x="18" y="${gy}" width="${width-36}" height="${gh}"/><path class="fragment-tab" d="M18 ${gy}h165v22h-16l-10 10H18z"/><text class="fragment-label" x="28" y="${gy+16}">${escapeXml(g.operator)} [${escapeXml(g.condition)}]</text>`;if(g.elseAt!==null){const ey=y(g.elseAt)-24;svg+=`<line class="fragment-divider" x1="18" y1="${ey}" x2="${width-18}" y2="${ey}"/><text class="fragment-label" x="28" y="${ey+16}">else</text>`;}});
  events.forEach((e,i)=>{const yy=y(i),from=x[e.caller??e.from],to=x[e.callee??e.to],same=from===to,label=e.signature??e.exception??e.value,details=e.type==='call'?[`Chamada: ${label}`,e.object_reference&&`Referência: ${e.object_reference}`,e.object_type&&`Tipo: ${e.object_type}`,e.call_return_type&&`Retorno da chamada: ${e.call_return_type}`,e.method_return_type&&`Retorno do método: ${e.method_return_type}`].filter(Boolean).join('\n'):label;svg+=`<g class="sequence-event"><title>${escapeXml(details)}</title>`;if(e.type==='call'){if(same)svg+=`<path class="message" d="M${from+6} ${yy}h54v26h-49" marker-end="url(#sync-arrow)"/>`;else svg+=`<line class="message" x1="${from}" y1="${yy}" x2="${to}" y2="${yy}" marker-end="url(#sync-arrow)"/>`;}else if(e.type==='return'){svg+=`<line class="return-message" x1="${from}" y1="${yy}" x2="${to}" y2="${yy}" marker-end="url(#return-arrow)"/>`;}else{svg+=`<line class="error-message" x1="${from}" y1="${yy}" x2="${to}" y2="${yy}" marker-end="url(#error-arrow)"/>`;}const lx=same?from+66:(from+to)/2;svg+=`<text class="message-label ${e.type}" x="${lx}" y="${yy-8}">${escapeXml(label)}</text></g>`;});
  const contracted=participants.filter(p=>p.contracts?.length);if(contracted.length){const legend=contracted.map(p=>`${p.classifier} implements ${p.contracts.join(', ')}`).join(' · ');svg+=`<text class="legend" x="22" y="${height-27}">${escapeXml(legend)}</text>`;}
  target.className='sequence-canvas';target.innerHTML=svg+'</svg>';diagramZoom=1;applyZoom();$('download-png').disabled=false;$('download-pdf').disabled=false;
}
const isCollapsibleTechnicalStep=step=>/^(get|set|is|has|with)[A-Z_]|^(toString|hashCode|equals)$/i.test(step.method||'');
const isFlowObjective=step=>step.order===1||step.contract_dispatch||/(Controller|UseCase|Service|Port|PersistenceAdapter|Repository)$/.test(step.class_name||'');
const BACKBONE_LAYERS=['Adapter IN','Port IN','Service','Port OUT','Adapter OUT','Repository','Framework/Database'];
function selectBackboneSteps(steps){
  const selected=[],usedLayers=new Set();
  for(const layer of BACKBONE_LAYERS){
    if(usedLayers.has(layer))continue;
    const step=steps.find(candidate=>candidate.layer===layer&&isFlowObjective(candidate));
    if(step){selected.push(step);usedLayers.add(layer);}
  }
  return selected.length>=3?selected:steps.filter(isFlowObjective);
}
function buildObjectiveFlow(steps){
  const byId=new Map(steps.map(step=>[step.call_id,step])),objectives=[],objectiveById=new Map();
  for(const step of steps){
    if(isFlowObjective(step)){
      const item={step,details:[]};objectives.push(item);objectiveById.set(step.call_id,item);continue;
    }
    let parent=step.parent_call_id,objective=null;
    while(parent&&!objective){objective=objectiveById.get(parent);parent=byId.get(parent)?.parent_call_id;}
    if(objective)objective.details.push(step);else objectives.push({step,details:[]});
  }
  return objectives;
}
function groupTechnicalSteps(steps){
  const groups=[];
  for(let index=0;index<steps.length;){
    const first=steps[index],same=[];
    while(index<steps.length&&steps[index].class_name===first.class_name&&isCollapsibleTechnicalStep(steps[index]))same.push(steps[index++]);
    if(same.length>=3){groups.push({kind:'group',className:first.class_name,steps:same});continue;}
    if(same.length){same.forEach(step=>groups.push({kind:'step',step}));continue;}
    groups.push({kind:'step',step:first});index++;
  }
  return groups;
}
function renderTechnicalStep(s,nested=false,outgoing=null){
  const source=s.relative_file||s.file,fileName=source.split(/[\\/]/).pop();
  // Call metadata belongs to its caller. In the timeline the edge is stored on
  // the destination step, so use the next step when detailing the current one.
  const call=outgoing;
  const parameters=(call?.method_parameters?.length?call.method_parameters:s.method_parameters)||[];
  const argumentsList=call?.argument_details||[];
  const methodReturn=call?.method_return_type||s.method_return_type||(!call?s.call_return_type:null);
  const hasMetadata=parameters.length||argumentsList.length||call?.object_reference||call?.object_type||call?.call_return_type||methodReturn;
  // Every invocation after the entry point is expandable. Engines with less
  // semantic resolution still expose the source and call without inventing types.
  const expandable=hasMetadata||s.order>1;
  const parameterRows=parameters.length?parameters.map(item=>`<li><code>${escapeXml(item.name)} : ${escapeXml(item.type||'Não resolvido')}</code></li>`).join(''):'<li><em>Sem parâmetros</em></li>';
  const origins=[...new Set(parameters.flatMap(item=>item.annotations||[]))];
  const originValue=origins.length?origins.map(item=>`@${escapeXml(item)}`).join(', '):'Não se aplica';
  const argumentRows=argumentsList.length?argumentsList.map(item=>`<li><code>${escapeXml(item.expression)} : ${escapeXml(item.type||'Não resolvido')}</code></li>`).join(''):'<li><em>Sem argumentos</em></li>';
  const callValue=call?(call.object_reference?`${call.object_reference}.${call.method}(${call.arguments||''})`:call.label):'Nenhuma chamada principal';
  const referenceValue=call?(call.object_reference||'Não identificada'):'Não se aplica';
  const referenceType=call?(call.object_type||'Não resolvido'):'Não se aplica';
  const callReturn=call?(call.call_return_type||call.return_type||'Não resolvido'):'Não se aplica';
  const content=`<div class="flow-marker"><span>${String(s.order).padStart(2,'0')}</span></div>
    <div class="flow-content"><div class="compact-title"><strong>${escapeXml(s.label)}</strong><span class="layer-chip">${escapeXml(s.layer)}</span></div>
    <div class="compact-meta"><span class="compact-file">${escapeXml(fileName)}:${s.line}</span><i></i><span class="compact-relation">${escapeXml(s.architecture_relation)}</span></div></div>`;
  if(!expandable)return `<article class="${nested?'nested-step':''}" style="--depth:${Math.min(s.depth,4)}" title="${escapeXml(source)} — ${escapeXml(s.hexagonal_role)}">${content}</article>`;
  return `<details class="call-detail-step ${nested?'nested-step':''}" style="--depth:${Math.min(s.depth,4)}"><summary title="${escapeXml(source)} — ${escapeXml(s.hexagonal_role)}">${content}<span class="group-toggle" aria-label="Expandir detalhes"></span></summary><div class="call-detail-panel"><section><b>Entrada</b><ul>${parameterRows}</ul></section><section><b>Origem da entrada</b><code>${originValue}</code></section><section><b>Chamada</b><code>${escapeXml(callValue)}</code></section><section><b>Referência</b><code>${escapeXml(referenceValue)}</code></section><section><b>Tipo da referência</b><code>${escapeXml(referenceType)}</code></section><section><b>Argumentos enviados</b><ul>${argumentRows}</ul></section><section><b>Retorno da chamada</b><code>${escapeXml(callReturn)}</code></section><section><b>Retorno do método</b><code>${escapeXml(methodReturn||'Não resolvido')}</code></section></div></details>`;
}
function renderTechnicalGroup(group){
  const first=group.steps[0],last=group.steps[group.steps.length-1],methods=group.steps.map(step=>step.method).join(', ');
  return `<details class="flow-group"><summary title="${escapeXml(methods)}">
    <div class="flow-marker group-marker"><span>${String(first.order).padStart(2,'0')}–${String(last.order).padStart(2,'0')}</span></div>
    <div class="flow-content"><div class="compact-title"><strong>${escapeXml(group.className)} · leitura de atributos</strong><span class="layer-chip">${escapeXml(first.layer)}</span></div>
    <div class="compact-meta"><span>${group.steps.length} chamadas técnicas agrupadas</span><i></i><span>Clique para detalhar</span></div></div><span class="group-toggle" aria-hidden="true"></span>
    </summary><div class="flow-group-children">${group.steps.map(step=>renderTechnicalStep(step,true)).join('')}</div></details>`;
}
function objectiveDescription(step){
  if(step.layer==='Adapter IN')return 'Recebe e traduz a requisição HTTP';
  if(step.layer==='Port IN')return 'Aciona o contrato do caso de uso';
  if(step.layer==='Service')return 'Executa as regras da aplicação';
  if(step.layer==='Port OUT')return 'Aciona o contrato de saída';
  if(/PersistenceAdapter$/.test(step.class_name||''))return 'Implementa a porta e acessa a infraestrutura';
  if(step.layer==='Framework/Database')return 'Consulta o mecanismo de persistência';
  if(/Mapper$/.test(step.class_name||''))return 'Converte persistência para domínio';
  if(/Response$/.test(step.class_name||''))return 'Monta a resposta da API';
  return step.hexagonal_role||'Executa etapa técnica';
}
function renderObjective(item){
  const step=item.step,source=step.relative_file||step.file,fileName=source.split(/[\\/]/).pop();
  if(!item.details.length)return renderTechnicalStep(step);
  return `<details class="flow-group objective-group"><summary title="${escapeXml(step.label)}">
    <div class="flow-marker"><span>${String(step.order).padStart(2,'0')}</span></div>
    <div class="flow-content"><div class="compact-title"><strong>${escapeXml(step.label)}</strong><span class="layer-chip">${escapeXml(step.layer)}</span></div>
    <div class="objective-description">${escapeXml(objectiveDescription(step))}</div><div class="compact-meta"><span class="compact-file">${escapeXml(fileName)}:${step.line}</span><i></i><span>${item.details.length} detalhes internos</span></div></div><span class="group-toggle" aria-hidden="true"></span>
    </summary><div class="flow-group-children">${item.details.map(detail=>renderTechnicalStep(detail,true)).join('')}</div></details>`;
}
function renderFlow(steps) {
  const target=$('flow');
  if(!steps.length){target.className='empty';target.textContent='Nenhuma chamada resolvida.';return;}
  target.className='timeline compact';
  const backbone=selectBackboneSteps(steps);
  target.innerHTML=backbone.map((step,index)=>renderTechnicalStep(step,false,backbone[index+1]||null)).join('');
}
function semanticDiagramModel(flow) {
  const participants=flow.participants.map((p,index)=>({id:p.id,instance:p.display_name,classifier:p.technical_name,display:p.display_name,type:p.type,layer:p.role,order:index}));
  const events=[],depths=new Map();let depth=0;
  (flow.events||[]).forEach(item=>{if(item.type==='call'){depths.set(item.id,depth);events.push({...item,type:'call',id:item.id,parent_call_id:item.parent_call_id,caller:item.source,callee:item.target,method:item.functional_description,signature:item.signature||item.functional_description,depth});depth++;}else if(item.type==='return'){depth=Math.max(0,depth-1);events.push({type:'return',call_id:item.call_id,from:item.source,to:item.target,value:item.functional_description,depth:depths.get(item.call_id)||0});}else{events.push({type:'exception',call_id:item.call_id,from:item.source,to:item.target,exception:item.functional_description,depth});}});
  return {interaction:flow.interaction,participants,events,calls:events.filter(e=>e.type==='call')};
}
function semanticBackboneFlow(flow){
  const transitionOrder=['ACTOR>HTTP_ENTRYPOINT','HTTP_ENTRYPOINT>APPLICATION_SERVICE','APPLICATION_SERVICE>PERSISTENCE_ADAPTER','PERSISTENCE_ADAPTER>DATABASE_REPOSITORY'];
  const selected=[];
  transitionOrder.forEach(transition=>{const item=flow.interactions.find(candidate=>`${candidate.source_role}>${candidate.target_role}`===transition);if(item)selected.push(item);});
  if(!selected.length)return flow;
  const callIds=new Set(selected.map(item=>item.id)),participantIds=new Set(['client']);
  selected.forEach(item=>{participantIds.add(item.source);participantIds.add(item.target);});
  return {...flow,participants:flow.participants.filter(participant=>participantIds.has(participant.id)),interactions:selected,events:flow.events.filter(event=>callIds.has(event.id||event.call_id)),detail_mode:'BACKBONE'};
}
function objectiveDiagramModel(model,steps){
  const objectiveIds=new Set(selectBackboneSteps(steps).map(step=>step.call_id));
  const events=model.events.filter(event=>objectiveIds.has(event.id||event.call_id));
  const participantIds=new Set(['client']);
  events.forEach(event=>{if(event.caller)participantIds.add(event.caller);if(event.callee)participantIds.add(event.callee);if(event.from)participantIds.add(event.from);if(event.to)participantIds.add(event.to);});
  return {...model,participants:model.participants.filter(participant=>participantIds.has(participant.id)),events,calls:model.calls.filter(call=>objectiveIds.has(call.id)),detail_mode:'OBJECTIVES'};
}
function renderSemanticFlow(flow) {
  const names=Object.fromEntries(flow.participants.map(p=>[p.id,p.display_name]));
  const target=$('flow');
  if(!flow.interactions.length){target.className='empty';target.textContent='Nenhuma interação arquitetural encontrada.';return;}
  target.className='semantic-path';
  target.innerHTML=flow.interactions.map((item,index)=>`<article><span>${String(index+1).padStart(2,'0')}</span><div><strong>${escapeXml(names[item.source])} → ${escapeXml(names[item.target])}</strong><small>${escapeXml(item.functional_description)}</small></div></article>`).join('');
}
function renderArchitecture(architecture) {
  const target=$('architecture');
  if(!architecture){target.className='architecture-detection empty';target.textContent='Arquitetura não determinada.';return;}
  const tone=architecture.type.toLowerCase();
  target.className=`architecture-detection ${tone}`;
  const hexRole=item=>item.startsWith('Adapter')?'spring-edge':item.startsWith('Port')?'domain-port':item.includes('Use Case')?'domain-core':item==='Database'?'database-edge':'infrastructure-edge';
  const hexHint=item=>({
    'Adapter IN':'Controller · entrada HTTP',
    'Port IN':'Interface do caso de uso',
    'Use Case/Service':'Implementação · regras da aplicação',
    'Port OUT':'Interface de persistência/integração',
    'Adapter OUT':'Persistence Adapter · implementa a porta',
    'Repository':'Spring Data Repository',
    'Database':'Banco de dados · recurso externo'
  }[item]||'Componente arquitetural');
  target.innerHTML=`<div><span class="architecture-kicker">Arquitetura detectada</span><strong>${escapeXml(architecture.label)}</strong><small>confiança estrutural ${architecture.confidence}%</small></div><div class="architecture-chain">${architecture.expected_flow.map((item,index)=>`${index?'<i>→</i>':''}<span class="${hexRole(item)}" title="${hexHint(item)}">${escapeXml(item)}<small>${hexHint(item)}</small></span>`).join('')}</div><details><summary>Por que foi classificada assim?</summary><ul>${architecture.evidence.map(item=>`<li>${escapeXml(item)}</li>`).join('')}</ul><code>Hexagonal ${architecture.scores.hexagonal}% · Layered ${architecture.scores.layered}%</code></details>`;
}
function resetProjectAnalysis(){lastAnalysis=null;currentDiagramModel=null;swaggerInfo=null;$('endpoint-badge').textContent='';$('architecture').className='architecture-detection empty';$('architecture').textContent='Detectando arquitetura do microsserviço…';$('flow').className='empty';$('flow').textContent='Selecione um endpoint e analise o fluxo.';$('sequence-diagram').className='diagram-empty';$('sequence-diagram').textContent='Analise um endpoint para gerar o diagrama.';$('mermaid').textContent='sequenceDiagram';$('maturity').disabled=true;$('swagger').disabled=true;$('download-png').disabled=true;$('download-pdf').disabled=true;}
async function json(url) { const response = await fetch(url); const body = await response.json(); if (!response.ok) throw new Error(body.detail || 'Falha na requisição'); return body; }
$('load').onclick = async () => { try { resetProjectAnalysis();$('project').innerHTML='<option>Carregando projetos…</option>';$('endpoint').innerHTML='<option>Aguardando projeto…</option>';status('Procurando projetos Spring Boot…'); const data = await json('/api/projects?root='+encodeURIComponent($('root').value.trim())); projects=data.projects; $('project').innerHTML=projects.length?projects.map((p,i)=>`<option value="${i}">${p.name}</option>`).join(''):'<option>Nenhum projeto Spring Boot</option>'; status(`${projects.length} projeto(s) encontrado(s).`); if(projects.length) await loadEndpoints();else{$('architecture').textContent='Nenhum microsserviço Spring Boot encontrado.';$('endpoint').innerHTML='<option>Nenhum endpoint</option>';} } catch(e){projects=[];$('project').innerHTML='<option>Diretório inválido</option>';$('endpoint').innerHTML='<option>Nenhum endpoint</option>';$('architecture').textContent='Não foi possível detectar a arquitetura.';status(e.message,true);} };
async function loadEndpoints(){ try { resetProjectAnalysis();const project=projects[+$('project').value]; if(!project)return;status(`Carregando ${project.name}…`);const [data,swagger]=await Promise.all([json('/api/endpoints?project='+encodeURIComponent(project.path)),json('/api/swagger-info?project='+encodeURIComponent(project.path))]);swaggerInfo=swagger;$('endpoint').innerHTML=data.endpoints.length?data.endpoints.map(e=>`<option value="${e.id}">${e.http_method} ${e.path}</option>`).join(''):'<option>Nenhum endpoint</option>';renderArchitecture(data.architecture);$('swagger').disabled=!swagger.detected;$('swagger').title=swagger.detected?`Abrir ${swagger.swagger_url}`:'Springdoc/Swagger não identificado no build';status(`${project.name}: ${data.endpoints.length} endpoint(s). Arquitetura ${data.architecture.label}.${swagger.detected?' Swagger: '+swagger.swagger_url:' Swagger não identificado.'}`);rememberSelectedProject(); }catch(e){swaggerInfo=null;$('swagger').disabled=true;$('architecture').textContent='Não foi possível detectar a arquitetura.';status(e.message,true);} }
$('project').onchange=loadEndpoints;
$('swagger').onclick=()=>{if(!swaggerInfo)return;const selected=$('endpoint').selectedOptions[0]?.textContent||'endpoint selecionado';const popup=window.open(swaggerInfo.swagger_url,'_blank','noopener,noreferrer');if(popup)status(`Swagger aberto para consultar ${selected}.`);else status(`O navegador bloqueou a nova aba. Abra: ${swaggerInfo.swagger_url}`,true);};
function currentMaturityContext(project,analysis=lastAnalysis){if(!project||!analysis)return null;return {project_name:project.name,project_path:project.path,endpoint:`${analysis.endpoint.http_method} ${analysis.endpoint.path}`,endpoint_id:$('endpoint').value,architecture:analysis.architecture?.label||'Não determinada',average_tps:positiveNumber('average-tps'),target_p95_ms:positiveNumber('target-p95-ms')};}
function syncMaturityContext(project,analysis=lastAnalysis){const next=currentMaturityContext(project,analysis);if(next){const serialized=JSON.stringify(next);sessionStorage.setItem('expert-code-flow:maturity-context',serialized);localStorage.setItem('expert-code-flow:maturity-context',serialized);}return next;}
$('analyze').onclick=async()=>{try{$('maturity').disabled=true;const project=projects[+$('project').value];if(!project)throw new Error('Carregue um projeto primeiro.');const detailLevel=$('detail-level').value,diagramType=$('diagram-type').value,analysisEngine=$('analysis-engine').value;status(analysisEngine==='spoon-hybrid'?'Executando análise Spoon + SootUp…':'Detectando arquitetura com o motor Python…');const response=await fetch('/api/flow',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_path:project.path,endpoint:$('endpoint').value,http_method:$('endpoint').selectedOptions[0]?.textContent.split(' ')[0],diagram_type:diagramType,detail_level:detailLevel,analysis_engine:analysisEngine})});const data=await response.json();if(!response.ok)throw new Error(data.detail||'Falha na análise');lastAnalysis=data;syncMaturityContext(project,data);sessionStorage.setItem('expert-code-flow:last-semantic-analysis',JSON.stringify({endpoint:data.endpoint,semantic_flow:data.semantic_flow}));const spoonActive=data.analysis_engine?.active==='spoon',engine=spoonActive?'SPOON+SOOTUP':'PYTHON';$('endpoint-badge').textContent=`${data.endpoint.http_method} ${data.endpoint.path} · ${engine}`;renderArchitecture(data.architecture);if(detailLevel==='ARCHITECTURAL'){const backbone=semanticBackboneFlow(data.semantic_flow);renderSemanticFlow(backbone);renderSequence(semanticDiagramModel(backbone));}else{renderFlow(data.steps);renderSequence(objectiveDiagramModel(data.model,data.steps));}$('mermaid').textContent=data.mermaid;$('maturity').disabled=false;const engineLabel=spoonActive?'Spoon + SootUp estrutural':'Python leve',fallback=data.analysis_engine?.fallback_used?' Analisador Java indisponível; fallback aplicado.':'',backboneCount=selectBackboneSteps(data.steps).length,omittedCount=data.steps.length-backboneCount,detailSummary=detailLevel==='TECHNICAL'?` Backbone principal com ${backboneCount} etapas; ${omittedCount} chamadas internas omitidas.`:' Backbone arquitetural sem interações repetidas.';status(`Motor ${engineLabel}. Fonte: ${data.analysis_engine?.flow_source}. Arquitetura ${data.architecture.label}.${fallback}${detailSummary}`);}catch(e){status(e.message,true);}};
$('maturity').onclick=()=>{const project=projects[+$('project').value];if(!syncMaturityContext(project))return;location.href='/avaliacao-maturidade';};
const originalLoadProjects=$('load').onclick;
function rememberSelectedProject(){const project=projects[+$('project').value];if(project)localStorage.setItem('expert-code-flow:selected-project',JSON.stringify({project_name:project.name,project_path:project.path,endpoint:$('endpoint').selectedOptions[0]?.textContent||'',endpoint_id:$('endpoint').value}));}
$('load').onclick=async()=>{ $('capacity').disabled=true;$('xray').disabled=true;await originalLoadProjects();$('capacity').disabled=!projects.length;$('xray').disabled=!projects.length;if(projects.length)localStorage.setItem(projectSourceKey,JSON.stringify({source:'directory',root:$('root').value.trim()}));rememberSelectedProject(); };
$('project').addEventListener('change',()=>{$('capacity').disabled=!projects[+$('project').value];$('xray').disabled=!projects[+$('project').value];setTimeout(rememberSelectedProject,0);});
$('endpoint').addEventListener('change',()=>{lastAnalysis=null;currentDiagramModel=null;$('endpoint-badge').textContent='';$('flow').className='empty';$('flow').textContent='Analise o endpoint selecionado para revelar o fluxo.';$('sequence-diagram').className='diagram-empty';$('sequence-diagram').textContent='Analise o endpoint selecionado para gerar o diagrama.';$('mermaid').textContent='sequenceDiagram';$('maturity').disabled=true;$('download-png').disabled=true;$('download-pdf').disabled=true;rememberSelectedProject();});
let rootChangeTimer=null,lastLoadedRoot='';
function autoLoadRoot(){const value=$('root').value.trim();if(!value||value===lastLoadedRoot)return;lastLoadedRoot=value;$('load').click();}
$('root').addEventListener('input',()=>{clearTimeout(rootChangeTimer);rootChangeTimer=setTimeout(autoLoadRoot,650);});
$('root').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();clearTimeout(rootChangeTimer);lastLoadedRoot='';autoLoadRoot();}});
$('load').addEventListener('click',()=>{lastLoadedRoot=$('root').value.trim();});
function setProjectSource(source){const upload=source==='zip';$('directory-source').hidden=upload;$('zip-source').hidden=!upload;$('source-directory').classList.toggle('active',!upload);$('source-zip').classList.toggle('active',upload);$('source-directory').setAttribute('aria-selected',String(!upload));$('source-zip').setAttribute('aria-selected',String(upload));}
async function restoreUploadedProject(){
  try{
    const data=await json('/api/projects/upload/current');
    if(!data.available)return;
    let saved={};
    try{saved=JSON.parse(localStorage.getItem('expert-code-flow:selected-project')||'{}');}catch{}
    setProjectSource('zip');
    projects=data.projects||[];
    $('root').value=data.root;
    lastLoadedRoot=data.root;
    $('project').innerHTML=projects.length?projects.map((project,index)=>`<option value="${index}">${escapeXml(project.name)}</option>`).join(''):'<option>Nenhum projeto Spring Boot</option>';
    const projectIndex=projects.findIndex(project=>project.path===saved.project_path);
    if(projectIndex>=0)$('project').value=String(projectIndex);
    if(projects.length){
      await loadEndpoints();
      if(saved.endpoint_id&&[...$('endpoint').options].some(option=>option.value===saved.endpoint_id))$('endpoint').value=saved.endpoint_id;
      $('capacity').disabled=false;
      $('xray').disabled=false;
      rememberSelectedProject();
      const progress=$('upload-progress');
      progress.hidden=false;
      progress.classList.remove('processing');
      $('upload-progress-bar').value=100;
      $('upload-progress-percent').textContent='100%';
      $('upload-progress-label').textContent='Pacote mantido na sessão';
      $('upload-progress-detail').textContent=`${data.filename} · ${projects.length} projeto(s) disponível(is).`;
      status(`${data.filename} restaurado. Escolha um microsserviço ou outro endpoint.`);
    }
  }catch(error){
    console.warn('Não foi possível restaurar o pacote da sessão.',error);
  }
}
async function restoreProjectSource(){
  await restoreUploadedProject();
  if(projects.length)return;
  try{
    const saved=JSON.parse(localStorage.getItem(projectSourceKey)||'{}');
    if(saved.source==='directory'&&saved.root){
      setProjectSource('directory');
      $('root').value=saved.root;
      lastLoadedRoot='';
      $('load').click();
    }
  }catch(error){console.warn('Não foi possível restaurar o último diretório.',error);}
}
$('source-directory').onclick=()=>setProjectSource('directory');
$('source-zip').onclick=()=>setProjectSource('zip');
$('project-zip').addEventListener('change',()=>{$('upload-project').disabled=!$('project-zip').files?.length;$('upload-progress').hidden=true;$('upload-progress').classList.remove('processing');$('upload-progress-bar').value=0;$('upload-progress-percent').textContent='0%';});
function sendUploadChunk(uploadId,index,chunk,completed,total,onProgress){return new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST',`/api/projects/upload/chunk?upload_id=${encodeURIComponent(uploadId)}&index=${index}`);xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.upload.addEventListener('progress',event=>{window.dispatchEvent(new Event('codeflow:activity'));if(event.lengthComputable){const loaded=completed+event.loaded;onProgress(Math.min(99,Math.round(loaded/total*100)),loaded,total);}});xhr.addEventListener('load',()=>{let data={};try{data=JSON.parse(xhr.responseText||'{}');}catch{}if(xhr.status>=200&&xhr.status<300)resolve(data);else reject(new Error(data.detail||'Falha ao enviar um bloco do pacote ZIP'));});xhr.addEventListener('error',()=>reject(new Error('A conexão foi interrompida durante o upload.')));xhr.addEventListener('abort',()=>reject(new Error('Upload cancelado.')));xhr.send(chunk);});}
async function uploadProjectArchive(file,onProgress){const initResponse=await fetch('/api/projects/upload/init',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:file.name,size:file.size})}),init=await initResponse.json();if(!initResponse.ok)throw new Error(init.detail||'Não foi possível iniciar o upload');const chunkSize=init.chunk_size;let completed=0,index=0;while(completed<file.size){const chunk=file.slice(completed,Math.min(completed+chunkSize,file.size));await sendUploadChunk(init.upload_id,index,chunk,completed,file.size,onProgress);completed+=chunk.size;index++;onProgress(Math.min(99,Math.round(completed/file.size*100)),completed,file.size);}onProgress(100,file.size,file.size);const finishResponse=await fetch('/api/projects/upload/finish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({upload_id:init.upload_id})}),result=await finishResponse.json();if(!finishResponse.ok)throw new Error(result.detail||'Falha ao processar o pacote ZIP');return result;}
$('upload-project').onclick=async()=>{const file=$('project-zip').files?.[0];if(!file)return;if(!file.name.toLowerCase().endsWith('.zip')){status('Selecione um pacote com extensão .zip.',true);return;}if(file.size>300*1024*1024){status('O pacote ZIP excede o limite de 300 MB.',true);return;}const progress=$('upload-progress'),bar=$('upload-progress-bar'),percent=$('upload-progress-percent'),label=$('upload-progress-label'),detail=$('upload-progress-detail');progress.hidden=false;progress.classList.remove('processing');bar.value=0;percent.textContent='0%';label.textContent=`Enviando ${file.name}`;detail.textContent=`0 de ${formatBytes(file.size)} enviados`;$('upload-project').disabled=true;resetProjectAnalysis();$('project').innerHTML='<option>Enviando pacote…</option>';$('endpoint').innerHTML='<option>Aguardando projeto…</option>';status(`Enviando ${file.name} e procurando projetos Spring Boot…`);try{const data=await uploadProjectArchive(file,(value,loaded,total)=>{bar.value=value;percent.textContent=`${value}%`;detail.textContent=`${formatBytes(loaded)} de ${formatBytes(total)} enviados`;if(value===100){progress.classList.add('processing');label.textContent='Upload concluído. Analisando pacote…';detail.textContent='Validando arquivos e procurando projetos Spring Boot.';}});bar.value=100;percent.textContent='100%';progress.classList.remove('processing');label.textContent='Pacote carregado com sucesso';detail.textContent=`${data.projects.length} projeto(s) Spring Boot encontrado(s).`;projects=data.projects;$('root').value=data.root;lastLoadedRoot=data.root;$('project').innerHTML=projects.map((project,index)=>`<option value="${index}">${escapeXml(project.name)}</option>`).join('');status(`${projects.length} projeto(s) encontrado(s) em ${file.name}.`);await loadEndpoints();$('capacity').disabled=!projects.length;$('xray').disabled=!projects.length;localStorage.setItem(projectSourceKey,JSON.stringify({source:'zip'}));rememberSelectedProject();}catch(error){progress.classList.remove('processing');label.textContent='Falha no upload';detail.textContent=error.message;percent.textContent='Erro';projects=[];$('project').innerHTML='<option>Falha no pacote ZIP</option>';$('endpoint').innerHTML='<option>Nenhum endpoint</option>';status(error.message,true);}finally{$('upload-project').disabled=false;}};
$('xray').onclick=openXray;
$('xray-maximize').onclick=()=>setXrayMaximized(!$('xray-modal').classList.contains('maximized'));
$('xray-close').onclick=$('xray-close-icon').onclick=()=>$('xray-modal').close();
$('xray-modal').addEventListener('close',()=>setXrayMaximized(false));
$('xray-modal').addEventListener('click',event=>{if(event.target===$('xray-modal'))$('xray-modal').close();});
$('capacity').onclick=()=>{const project=projects[+$('project').value];if(!project)return;const capacityContext={project_name:project.name,project_path:project.path,endpoint:$('endpoint').selectedOptions[0]?.textContent||'',endpoint_id:$('endpoint').value,target_tps:positiveNumber('average-tps'),average_response_time_ms:positiveNumber('target-p95-ms')};sessionStorage.setItem('expert-code-flow:capacity-context',JSON.stringify(capacityContext));localStorage.setItem('expert-code-flow:selected-project',JSON.stringify(capacityContext));location.href='/avaliacao-capacity';};
$('zoom-in').onclick=()=>{diagramZoom=Math.min(2,diagramZoom+.15);applyZoom();};
$('zoom-out').onclick=()=>{diagramZoom=Math.max(.55,diagramZoom-.15);applyZoom();};
$('zoom-reset').onclick=()=>{diagramZoom=1;applyZoom();};
$('copy').onclick=async()=>{await navigator.clipboard.writeText($('mermaid').textContent);$('copy').textContent='Copiado';setTimeout(()=>$('copy').textContent='Copiar',1200);};
function buildExportSvg(){
  const original=$('sequence-diagram').querySelector('svg');
  if(!original||!currentDiagramModel)return null;
  const clone=original.cloneNode(true),sourceNodes=[original,...original.querySelectorAll('*')],cloneNodes=[clone,...clone.querySelectorAll('*')];
  const properties=['fill','stroke','stroke-width','stroke-dasharray','stroke-linecap','stroke-linejoin','opacity','font-family','font-size','font-weight','font-style','text-anchor','dominant-baseline'];
  sourceNodes.forEach((source,index)=>{const target=cloneNodes[index];if(!target)return;const computed=getComputedStyle(source);target.setAttribute('style',properties.map(name=>`${name}:${computed.getPropertyValue(name)}`).join(';'));});
  const viewBox=(clone.getAttribute('viewBox')||'0 0 1600 900').split(/\s+/).map(Number),width=viewBox[2],height=viewBox[3];
  clone.setAttribute('xmlns','http://www.w3.org/2000/svg');clone.setAttribute('width',String(width));clone.setAttribute('height',String(height));clone.style.width='';
  const background=document.createElementNS('http://www.w3.org/2000/svg','rect');background.setAttribute('x','0');background.setAttribute('y','0');background.setAttribute('width',String(width));background.setAttribute('height',String(height));background.setAttribute('fill','#07110f');clone.insertBefore(background,clone.firstChild);
  const markup=new XMLSerializer().serializeToString(clone),safeName=currentDiagramModel.interaction.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
  return {markup,width,height,baseName:`sequence-${safeName||'diagram'}`};
}
function downloadBlob(blob,fileName){const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=fileName;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function exportPng(){
  const exported=buildExportSvg();if(!exported){status('Analise um endpoint antes de gerar a imagem.',true);return;}
  status('Gerando PNG em alta resolução…');const svgBlob=new Blob([exported.markup],{type:'image/svg+xml;charset=utf-8'}),url=URL.createObjectURL(svgBlob),image=new Image();
  image.onload=()=>{const scale=Math.min(2,12000/exported.width,12000/exported.height),canvas=document.createElement('canvas');canvas.width=Math.round(exported.width*scale);canvas.height=Math.round(exported.height*scale);const context=canvas.getContext('2d');context.fillStyle='#07110f';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(image,0,0,canvas.width,canvas.height);URL.revokeObjectURL(url);canvas.toBlob(blob=>{if(!blob){status('Não foi possível gerar o PNG.',true);return;}downloadBlob(blob,`${exported.baseName}.png`);status(`PNG gerado: ${exported.baseName}.png`);},'image/png');};
  image.onerror=()=>{URL.revokeObjectURL(url);status('Não foi possível renderizar o PNG.',true);};image.src=url;
}
function exportPdf(){
  const popup=window.open('','_blank'),exported=buildExportSvg();if(!exported){popup?.close();status('Analise um endpoint antes de gerar o PDF.',true);return;}if(!popup){status('O navegador bloqueou a janela de PDF.',true);return;}
  popup.document.open();popup.document.write(`<!doctype html><html><head><title>${exported.baseName}</title><style>@page{size:landscape;margin:8mm}html,body{margin:0;background:#07110f}body{display:grid;place-items:center;min-height:100vh}svg{display:block;width:100%;height:auto;max-height:96vh}@media print{body{background:#07110f;-webkit-print-color-adjust:exact;print-color-adjust:exact}}</style></head><body>${exported.markup}</body></html>`);popup.document.close();setTimeout(()=>{popup.focus();popup.print();},500);status('PDF preparado. Escolha “Salvar como PDF” no diálogo de impressão.');
}
$('download-png').onclick=exportPng;$('download-pdf').onclick=exportPdf;
document.querySelectorAll('[data-section]').forEach(link=>link.addEventListener('click',()=>{document.querySelectorAll('[data-section]').forEach(item=>item.classList.remove('active'));link.classList.add('active');}));
loadAnalysisEngines();
restoreProjectSource();



