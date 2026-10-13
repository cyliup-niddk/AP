const parse=PhysicsUnitResponse.parse;
const valid={request_id:'request-1',question_id:'question-1',unit_number:8,reason:'Pressure in a fluid'};
const encode=value=>JSON.stringify(value);
const tests=[];
function check(name,text,expected) {
  const value=parse(text,'request-1','question-1');
  const passed=expected===null?value===null:value?.unit_number===expected;
  tests.push({name,passed});
}
check('Plain JSON unit 8',encode(valid),8);
check('Markdown fenced JSON','```json\n'+encode(valid)+'\n```',8);
check('Extra prose around JSON','The classification is:\n'+encode(valid)+'\nDone.',8);
check('Braces and escaped quotes in explanation',encode({...valid,reason:'Use {pressure} and "density".'}),8);
check('Nested metadata',encode({...valid,metadata:{topic:'fluids'}}),8);
check('Wrong request ID',encode({...valid,request_id:'earlier'}),null);
check('Wrong question ID',encode({...valid,question_id:'different'}),null);
check('String unit number',encode({...valid,unit_number:'8'}),null);
check('Out of range unit',encode({...valid,unit_number:9}),null);
check('Fractional unit',encode({...valid,unit_number:2.5}),null);
check('Missing reason',encode({...valid,reason:undefined}),null);
check('Unstructured answer is rejected','This question belongs to Unit 8: Fluids.',null);
check('Old response followed by current',encode({...valid,request_id:'earlier'})+'\n'+encode(valid),8);
for(let unit=1;unit<=8;unit++)check('Valid unit '+unit,encode({...valid,unit_number:unit}),unit);
const failed=tests.filter(t=>!t.passed);
document.getElementById('results').textContent=tests.map(t=>(t.passed?'PASS':'FAIL')+' '+t.name).join('\n')+'\n'+(tests.length-failed.length)+'/'+tests.length+' passed';
document.body.dataset.testResult=failed.length?'FAIL':'PASS';

function checkMultiple(name,numbers,expected) {
  const value=parse(encode({...valid,unit_number:undefined,unit_numbers:numbers}),'request-1','question-1');
  const passed=expected===null?value===null:JSON.stringify(value?.unit_numbers)===JSON.stringify(expected);
  tests.push({name,passed});
}
checkMultiple('Multiple units',[2,3,8],[2,3,8]);
checkMultiple('Duplicate units normalized',[8,2,8],[2,8]);
checkMultiple('Single-element array',[8],[8]);
checkMultiple('Empty array',[],null);
checkMultiple('Invalid unit in array',[2,9],null);
checkMultiple('String in array',[2,'8'],null);
checkMultiple('Boolean in array',[true],null);
checkMultiple('Non-array units',8,null);
checkMultiple('Null units',null,null);
const failures=tests.filter(t=>!t.passed);
document.getElementById('results').textContent=tests.map(t=>(t.passed?'PASS':'FAIL')+' '+t.name).join('\n')+'\n'+(tests.length-failures.length)+'/'+tests.length+' passed';
document.body.dataset.testResult=failures.length?'FAIL':'PASS';
