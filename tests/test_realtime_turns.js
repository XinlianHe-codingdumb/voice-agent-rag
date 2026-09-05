const test = require("node:test");
const assert = require("node:assert/strict");
const {classifyUtterance} = require("../web/realtime_turns.js");

test("short acknowledgements are backchannels", () => {
  for (const text of ["OK", "yeah", "OK啊", "好啊", "嗯嗯", "你继续", "uh-huh"]) {
    assert.equal(classifyUtterance(text), "backchannel", text);
  }
});

test("explicit corrections are hard interruptions", () => {
  for (const text of ["Wait a second", "No, that is wrong", "不对，我问的是DPO", "停一下"]) {
    assert.equal(classifyUtterance(text), "hard_interrupt", text);
  }
});

test("questions and qualified acknowledgements start a new turn", () => {
  assert.equal(classifyUtterance("What chapter should I read?"), "new_turn");
  assert.equal(classifyUtterance("Okay but what about chapter eight?"), "new_turn");
});
