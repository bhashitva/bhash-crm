// Unit-test the browser asset emitted by Bhash without touching a system clipboard.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const script = fs.readFileSync(0, 'utf8');

async function scenario({deny = false, secure = true} = {}) {
  const source = 'फलन नमस्ते() -> पाठ {\n\tलौटाओ "<script>&\\\""; // १२.३\n}\n';
  const code = {textContent: source};
  const status = {textContent: ''};
  const block = {querySelector: selector => selector === 'code' ? code : status};
  const button = {dataset: {copyReady: 'कोड कॉपी करें', copyDone: 'कॉपी हो गया', copyError: 'manual copy'},
    textContent: 'कोड कॉपी करें', disabled: false, closest: () => block};
  let click, written, timer, selected, writes = 0;
  const rootClasses = [];
  const context = {
    document: {documentElement: {classList: {add: name => rootClasses.push(name)}},
      addEventListener: (name, fn) => {assert.equal(name, 'click'); click = fn;},
      createRange: () => ({selectNodeContents: node => {selected = node;}})},
    navigator: {clipboard: {writeText: async text => {
      assert.equal(button.disabled, true); writes++; if (deny) throw new Error('denied'); written = text;
    }}},
    window: {isSecureContext: secure, getSelection: () => ({removeAllRanges() {}, addRange() {}})},
    setTimeout: fn => {timer = fn; return 1;}, clearTimeout() {}
  };
  vm.runInNewContext(script, context, {timeout: 1000});
  assert.deepEqual(rootClasses, ['source-copy-ready']);
  await click({target: {closest: () => null}});
  assert.equal(writes, 0);
  await click({target: {closest: () => button}});
  assert.equal(button.disabled, false);
  if (!deny && secure) {
    assert.equal(written, source, 'Clipboard gets the exact raw text, with Unicode, indentation and final newline');
    assert.equal(button.textContent, button.dataset.copyDone);
    assert.equal(status.textContent, button.dataset.copyDone);
    assert.equal(selected, undefined);
    timer();
    assert.equal(button.textContent, button.dataset.copyReady);
    assert.equal(status.textContent, '');
  } else {
    assert.equal(written, undefined);
    assert.equal(selected, code);
    assert.equal(status.textContent, button.dataset.copyError, 'Failure must not claim a successful copy');
    assert.equal(button.textContent, button.dataset.copyReady);
    assert.equal(writes, secure ? 1 : 0);
  }
}
(async () => {
  await scenario(); await scenario({deny: true}); await scenario({secure: false});
  console.log('PASS: exact Unicode clipboard payload, success/reset, denied/insecure fallback, unrelated clicks.');
})().catch(error => {console.error(error); process.exitCode = 1;});
