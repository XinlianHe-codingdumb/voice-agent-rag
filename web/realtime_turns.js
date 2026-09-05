(function exposeRealtimeTurnPolicy(root) {
  const backchannels = new Set([
    "ok", "okay", "yeah", "yep", "yes", "right", "sure", "got it", "i see",
    "uh huh", "mhm", "mm hmm", "all right", "continue", "ok啊", "okay啊",
    "yeah啊", "好", "好的", "好啊", "好呀", "嗯", "嗯嗯", "嗯啊", "对", "对的",
    "对啊", "可以", "明白", "知道了", "继续", "你继续", "行", "行啊",
  ]);
  const hardInterruptPrefixes = [
    "wait", "wait a second", "stop", "hold on", "no", "nope", "actually",
    "but", "sorry", "等等", "等一下", "等会", "停", "停一下", "不对", "不是",
    "但是", "我想问", "我问的是", "换一个",
  ];

  function normalizeUtterance(text) {
    return String(text || "")
      .toLocaleLowerCase()
      .replace(/[.,!?;:'"\-，。！？；：、…]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function classifyUtterance(text) {
    const normalized = normalizeUtterance(text);
    if (!normalized) return "noise";
    if (backchannels.has(normalized)) return "backchannel";
    if (hardInterruptPrefixes.some(prefix =>
      normalized === prefix || normalized.startsWith(`${prefix} `)
    )) return "hard_interrupt";
    return "new_turn";
  }

  const api = {classifyUtterance, normalizeUtterance};
  root.RealtimeTurnPolicy = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
