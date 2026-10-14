(configuration => {
  // Integration-only passive observations run in the production extension eval world.
  const fail = reason => ({ready:false, reason});
  if (!configuration || !Number.isInteger(configuration.case) || configuration.case < 0 || configuration.case >= 14 ||
      !/^[0-9a-f]{40}$/.test(configuration.sourceCommit || '') ||
      !/^[1-9][0-9]*$/.test(configuration.runId || '') || !/^[1-9][0-9]*$/.test(configuration.runAttempt || '') ||
      !/^[0-9a-f]{32}$/.test(configuration.runNonce || '')) return fail('Invalid observation owner');
  const expectedUrl = 'http://127.0.0.1:8771/caret?case=' + configuration.case;
  if (configuration.documentUrl !== expectedUrl || location.href !== expectedUrl ||
      document.documentElement?.getAttribute('data-caret-case') !== String(configuration.case)) return fail('Document owner differs');
  const composer = document.getElementById('prompt-textarea'), other = document.getElementById('other-draft'), send = document.getElementById('send');
  if (!composer || !other || !send) return fail('Seed document is not complete');
  const owner = {sourceCommit:configuration.sourceCommit, runId:configuration.runId, runAttempt:configuration.runAttempt,
    runNonce:configuration.runNonce, case:configuration.case, documentUrl:expectedUrl, timeOrigin:performance.timeOrigin};
  const key = '__pocketCaretObservation';
  if (Object.prototype.hasOwnProperty.call(window, key)) {
    const previous = window[key];
    if (!previous || previous.document !== document || previous.composer !== composer || previous.other !== other || previous.send !== send ||
        Object.keys(owner).some(field => previous.owner[field] !== owner[field])) return fail('Existing observation owner differs');
    return previous.snapshot();
  }
  const state = {owner, document, composer, other, send, events:[], overflow:false, sendCount:0};
  const record = event => {
    if (state.events.length >= 512) {state.overflow=true; return;}
    state.events.push({index:state.events.length, time:performance.now(), type:event.type, key:event.key || '', data:event.data ?? '',
      inputType:event.inputType || '', trusted:event.isTrusted, ctrl:!!event.ctrlKey, shift:!!event.shiftKey, composing:!!event.isComposing,
      start:composer.selectionStart, end:composer.selectionEnd, draft:composer.value, prevented:event.defaultPrevented});
  };
  for (const type of ['focus','blur','select','keydown','keyup','beforeinput','input','compositionstart','compositionupdate','compositionend'])
    composer.addEventListener(type, event => {if (type === 'beforeinput' && owner.case === 10) event.preventDefault(); record(event);});
  document.addEventListener('selectionchange', event => {if (document.activeElement === composer) record(event);}, true);
  send.addEventListener('click', () => {state.sendCount++;});
  state.snapshot = () => {
    const r=composer.getBoundingClientRect(), style=getComputedStyle(composer), canvas=document.createElement('canvas'), context=canvas.getContext('2d');
    if (!context) return fail('Canvas measurement is unavailable');
    context.font=style.font;
    const points=[];
    for (let index=0; index<=composer.value.length; index++) points.push({
      x:r.left+parseFloat(style.borderLeftWidth)+parseFloat(style.paddingLeft)+context.measureText(composer.value.slice(0,index)).width-composer.scrollLeft,
      y:r.top+parseFloat(style.borderTopWidth)+parseFloat(style.paddingTop)+parseFloat(style.fontSize)*.6});
    const events=state.events;
    return {ready:true, ...owner, observerWorld:'extension-isolated-world', listenerInstallCount:1,
      draft:composer.value, otherDraft:other.value, focused:document.activeElement===composer, start:composer.selectionStart,
      end:composer.selectionEnd, direction:composer.selectionDirection, cookie:document.cookie, sendCount:state.sendCount,
      width:innerWidth, height:innerHeight, devicePixelRatio, scrollX, scrollY, readyState:document.readyState,
      documentFontsLoaded:!document.fonts || document.fonts.status==='loaded',
      viewport:{width:visualViewport?.width??innerWidth,height:visualViewport?.height??innerHeight,
        scale:visualViewport?.scale??1,offsetLeft:visualViewport?.offsetLeft??0,offsetTop:visualViewport?.offsetTop??0,
        pageLeft:visualViewport?.pageLeft??scrollX,pageTop:visualViewport?.pageTop??scrollY},
      bounds:{x:r.x,y:r.y,width:r.width,height:r.height}, points, events, overflow:state.overflow,
      eventCount:events.length, keyCount:events.filter(event=>event.type==='keydown').length,
      characterKeyCount:events.filter(event=>event.type==='keydown'&&event.key.length===1).length,
      qKeyCount:events.filter(event=>event.type==='keydown'&&event.key==='Q').length, inputCount:events.filter(event=>event.type==='input').length,
      beforeCount:events.filter(event=>event.type==='beforeinput').length, compositionCount:events.filter(event=>event.type==='compositionstart').length,
      compositionEndCount:events.filter(event=>event.type==='compositionend').length, allTrusted:events.every(event=>event.trusted)};
  };
  window[key]=state;
  return state.snapshot();
})
