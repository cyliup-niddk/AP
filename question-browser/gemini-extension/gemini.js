(() => {
  if (globalThis.__physicsClassifierInstalled) return;
  globalThis.__physicsClassifierInstalled = true;
  const progress=text=>chrome.runtime.sendMessage({type:"CLASSIFIER_PROGRESS",text}).catch(()=>{});
  let working=false;
  const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  const visible=node=>node && node.getClientRects().length && getComputedStyle(node).visibility!=='hidden';
  const responses=()=>Array.from(document.querySelectorAll('model-response, [data-message-author-role="model"]'));
  const generating=()=>Array.from(document.querySelectorAll('button')).some(b=>visible(b)&&/stop (generating|response)|stop generation/i.test((b.getAttribute('aria-label')||'')+' '+(b.getAttribute('title')||'')+' '+b.textContent));
  const parse=(text,requestId,questionId)=>globalThis.PhysicsUnitResponse.parse(text,requestId,questionId);
  async function classify(message) {
    if(working)throw Error('A query is already running in this Gemini tab.');
    working=true;
    try {
      progress('Connected to Gemini. Looking for its message input…');
      if(generating())throw Error('Gemini is already generating a response. Wait for it to finish.');
      const editor=Array.from(document.querySelectorAll('rich-textarea [contenteditable="true"], .ql-editor[contenteditable="true"], [contenteditable="true"][role="textbox"], textarea')).find(visible);
      if(!editor)throw Error('Gemini input not found. Sign in and open a chat; Gemini may have changed its page layout.');
      if((editor.value||editor.textContent||'').trim())throw Error('Gemini has an unsent draft. Clear it before using the classifier.');
      if(editor.tagName==='TEXTAREA') {
        const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
        setter.call(editor,message.prompt);
      } else {
        editor.focus();
        const selection=window.getSelection();
        const range=document.createRange();range.selectNodeContents(editor);selection.removeAllRanges();selection.addRange(range);
        // Use the browser edit operation so rich-text editor state receives the change.
        const inserted=document.execCommand('insertText',false,message.prompt);
        if(!inserted || !(editor.innerText||editor.textContent||'').includes(message.questionId)) {
          editor.replaceChildren();
          const paragraph=document.createElement('p');paragraph.textContent=message.prompt;editor.append(paragraph);
        }
      }
      editor.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:message.prompt}));
      editor.dispatchEvent(new Event('change',{bubbles:true}));
      progress('Question prompt inserted. Looking for Gemini’s Send button…');
      let send;
      for(let i=0;i<40;i++) {
        send=Array.from(document.querySelectorAll('button')).find(b=>visible(b)&&!b.disabled&&b.getAttribute('aria-disabled')!=='true'&&(b.matches('[data-test-id="send-button"], .send-button, [mattooltip="Send message"]')||/^send(?: message| prompt)?$/i.test(b.getAttribute('aria-label')||'')));
        if(send)break;await sleep(100);
      }
      if(!send)throw Error('Gemini Send button not found. Clear the injected draft before retrying.');
      send.click();
      progress('Prompt submitted to Gemini. Waiting for its unit classification (up to 120 seconds)…');
      let previous='',stableSince=0;
      const deadline=Date.now()+120000;
      while(Date.now()<deadline) {
        await sleep(400);
        // IDs bind the answer to this query, even if Gemini reuses an existing DOM element.
        const texts=responses().map(node=>node.innerText||node.textContent||'');
        const raw=texts.reverse().find(t=>parse(t,message.requestId,message.questionId));
        if(!raw)continue;
        if(raw!==previous){previous=raw;stableSince=Date.now();}
        if(!generating()&&Date.now()-stableSince>=1600)return {ok:true,answer:parse(raw,message.requestId,message.questionId),raw};
      }
      throw Error('Timed out after 120 seconds without a valid matching JSON response. Check Gemini for login, rate limits, or a changed layout.');
    } finally {working=false;}
  }
  chrome.runtime.onMessage.addListener((message,sender,reply)=>{
    if(message.type==='PING'){reply({ok:true});return;}
    if(message.type==='CLASSIFY') {
      classify(message).then(reply).catch(error=>reply({ok:false,error:error.message}));return true;
    }
  });
})();
