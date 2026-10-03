// Test-only RFC 8785 number/string serialization oracle. No stateOwl operations.
'use strict';
const readline = require('node:readline');
function canonical(v) {
  if (v === null || typeof v !== 'object') {
    if (typeof v === 'number' && !Number.isFinite(v)) throw Error('nonfinite');
    return JSON.stringify(v);
  }
  if (Array.isArray(v)) return '[' + v.map(canonical).join(',') + ']';
  return '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + canonical(v[k])).join(',') + '}';
}
readline.createInterface({input:process.stdin, crlfDelay:Infinity}).on('line', line => {
  try {
    const q = JSON.parse(line);
    const value = q.op === 'numbers' ? q.values.map(s => {
      const x = Number(s); if (!Number.isFinite(x)) return null;
      return JSON.stringify(x);
    }) : q.op === 'canonical' ? canonical(q.value) : (() => {throw Error('operation');})();
    process.stdout.write(JSON.stringify({value}) + '\n');
  } catch(e) { process.stdout.write(JSON.stringify({error:String(e)}) + '\n'); }
});
