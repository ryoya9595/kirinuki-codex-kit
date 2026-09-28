// ===== コピー用テキスト =====
const PAGE_URL = "https://ryoya9595.github.io/kirinuki-codex-kit/";

const USE_PROMPT = `$my-kirinuki
切り抜き動画を作りたいです。
切り口：あべむつきがAIを使いこなす場面まとめ
形式：横（YouTube）
素材は ~/kirinuki/素材 に入れました。`;

const TEXTS = {
  pageUrl: PAGE_URL,
  usePrompt: USE_PROMPT,
};

// 各 <pre> に本文を流し込む
Object.entries(TEXTS).forEach(([id, text]) => {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
});

// ===== コピー処理 =====
async function copyText(text, target) {
  let ok = false;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      ok = true;
    }
  } catch { ok = false; }
  if (!ok && target) {
    const range = document.createRange();
    range.selectNodeContents(target);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    sel.removeAllRanges();
  }
  return ok;
}

function showToast(msg) {
  let toast = document.getElementById("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 1800);
}

document.querySelectorAll(".copy-btn").forEach((button) => {
  button.addEventListener("click", async () => {
    const targetId = button.dataset.target;
    const target = document.getElementById(targetId);
    const text = TEXTS[targetId] || (target ? target.textContent : "");
    const ok = await copyText(text, target);
    const original = button.textContent;
    button.textContent = ok ? "コピーしました" : "手動でコピー";
    button.classList.toggle("done", ok);
    showToast(ok ? "📋 コピーしました" : "コピーできませんでした");
    setTimeout(() => {
      button.textContent = original;
      button.classList.remove("done");
    }, 2000);
  });
});

// ===== ナビ現在地ハイライト =====
const navLinks = Array.from(document.querySelectorAll(".topnav a[href^='#']"));
const sections = navLinks
  .map((a) => document.querySelector(a.getAttribute("href")))
  .filter(Boolean);
if ("IntersectionObserver" in window && sections.length) {
  const obs = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        const id = "#" + e.target.id;
        navLinks.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === id));
      }
    });
  }, { rootMargin: "-45% 0px -50% 0px" });
  sections.forEach((s) => obs.observe(s));
}
