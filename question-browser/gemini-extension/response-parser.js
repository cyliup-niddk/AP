/* Parse JSON objects even when fenced or containing braces inside strings. */
(() => {
  function parse(text, requestId, questionId) {
    for (let start=0; start<text.length; start++) {
      if (text[start] !== '{') continue;
      let depth=0, quoted=false, escaped=false;
      for (let end=start; end<text.length; end++) {
        const ch=text[end];
        if (quoted) {
          if (escaped) escaped=false;
          else if (ch==='\\') escaped=true;
          else if (ch==='"') quoted=false;
          continue;
        }
        if (ch==='"') quoted=true;
        else if (ch==='{') depth++;
        else if (ch==='}' && --depth===0) {
          try {
            const value=JSON.parse(text.slice(start,end+1));
            const numbers = value.unit_numbers === undefined ? [value.unit_number] : value.unit_numbers;
            if (value.request_id===requestId && value.question_id===questionId &&
                Array.isArray(numbers) && numbers.length>0 && numbers.every(n=>Number.isInteger(n) && n>=1 && n<=8) &&
                typeof value.reason==='string') {
              const unique = [...new Set(numbers)].sort((a,b)=>a-b);
              return {...value, unit_numbers:unique, unit_number:unique[0]};
            }
          } catch {}
          break;
        }
      }
    }
    return null;
  }
  globalThis.PhysicsUnitResponse = {parse};
})();
